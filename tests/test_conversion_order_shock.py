#!/usr/bin/env python3
"""dynamics/conversion-order 4 next to a 1:1000 jump: the per-cell second-order fallback keeps it finite.

A 1-D shock tube in x1, rho = p = 1 | 1e-3 at x = 0.5, nx1 = 256, WENO5 (shock: true), LMARS, RK3 at cfl 0.4, run to
t = 0.2. Without the fallback the point density u - L u is negative in the first low cell at step 1 and the run is
non-finite at step 2 with key 4 (key 2 finishes). With it, key 4 must stay finite with positive density at every
step, and hydro.conversion_trips must count the cells that fell back.

  python test_conversion_order_shock.py [--device cpu|cuda]
"""
import argparse
import os
import tempfile

import torch
import yaml
from snapy import MeshBlock, MeshBlockOptions, kIDN, kIPR


def run(key, device):
    bc = {f"x{d}-{s}": ("reflecting" if d == 1 else "periodic") for d in (1, 2, 3) for s in ("inner", "outer")}
    weno = {"type": "weno5", "scale": True, "shock": True}
    cfg = {"geometry": {"type": "cartesian", "cells": {"nx1": 256, "nx2": 1, "nx3": 1, "nghost": 3},
                        "bounds": {"x1min": 0., "x1max": 1., "x2min": 0., "x2max": 1., "x3min": 0., "x3max": 1.}},
           "boundary-condition": {"external": bc},
           "dynamics": {"equation-of-state": {"type": "ideal-gas", "gammad": 1.4, "limiter": False},
                        "reconstruct": {"vertical": weno, "horizontal": weno},
                        "riemann-solver": {"type": "lmars"}, "conversion-order": key},
           "integration": {"type": "rk3", "cfl": 0.4, "implicit-scheme": 0, "nlim": -1, "tlim": 1.e9}}
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, dir=os.getcwd()) as f:
        yaml.safe_dump(cfg, f)
    try:
        b = MeshBlock(MeshBlockOptions.from_yaml(f.name))
    finally:
        os.unlink(f.name)
    b.to(torch.device(device), torch.float64)
    x1f = b.buffer("coord.x1f")
    w = b.buffer("hydro.D").clone().zero_()
    w[kIDN] = torch.where((x1f[1:] + x1f[:-1]) / 2 < .5, 1., 1.e-3).to(w)
    w[kIPR] = w[kIDN]
    bv, _ = b.initialize({"hydro_w": w})
    t, step = 0., 0
    while t < .2:
        dt = b.max_time_step(bv)
        b.inc_cycle()
        for st in range(len(b.intg.stages)):
            b.forward(bv, dt, st)
        t, step = t + dt, step + 1
        u = bv["hydro_u"]
        assert torch.isfinite(u).all() and (u[kIDN] > 0).all(), f"key {key}: non-finite or rho <= 0 at step {step}"
    trips = int(b.buffer("hydro.conversion_trips")) if key == 4 else 0
    print(f"key {key}: t {t:.4f} after {step} steps, min rho {float(u[kIDN].min()):.3e}, trips {trips}")
    return trips


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    d = p.parse_args().device
    if d == "cuda" and not torch.cuda.is_available():
        raise SystemExit(125)
    run(2, d)
    assert run(4, d) > 0, "the 1:1000 jump never tripped the fallback"
