#!/usr/bin/env python3
"""dynamics/conversion-order 4 conserves mass at reflecting x1 walls and at in-process x1 seams, and its
temporary point state does not trip the EOS limiter.

(a), (b) Two right-moving acoustic pulses, c = 1 + 0.03 exp(-((x - x0) / 0.07)^2), x0 = 0.08 (against the inner
    wall) and 0.45 (across the seam at 0.5), ideal gas, WENO5, LMARS, nx1 = 64 on [0, 1] between reflecting walls,
    as (a) one block and (b) two x1 blocks in one process: after 40 steps |M - M0| / M0 <= 1e-13, keys 2 and 4.
(c) The EOS limiter on (density floor 1e-3) and a 4-cell density dip of 0.0405 in rho = p = 1: u - L u is
    positive but below the floor at the dip's edges. 20 steps with the driver's redo loop must take no redo.

  python test_conversion_order_mass.py [--device cpu|cuda]
"""
import argparse
import os
import tempfile

import torch
import yaml
from snapy import Mesh, MeshOptions, kIDN, kIPR

G, NX, TOL = 1.4, 64, 1.e-13


def mesh(key, nb1, limiter=False):
    bc = {f"x{d}-{s}": ("reflecting" if d == 1 else "periodic") for d in (1, 2, 3) for s in ("inner", "outer")}
    weno = {"type": "weno5", "scale": True, "shock": False}
    eos = {"type": "ideal-gas", "gammad": G, "limiter": limiter, "density-floor": 1.e-3, "pressure-floor": 1.e-3,
           "temperature-floor": 1.e-12}
    cfg = {"geometry": {"type": "cartesian", "cells": {"nx1": NX, "nx2": 1, "nx3": 1, "nghost": 3},
                        "bounds": {"x1min": 0., "x1max": 1., "x2min": 0., "x2max": 1., "x3min": 0., "x3max": 1.}},
           "boundary-condition": {"external": bc},
           "distribute": {"layout": "cubed" if nb1 > 1 else "slab", "nb1": nb1, "nb2": 1, "nb3": 1,
                          "blocks_per_process": nb1},
           "dynamics": {"equation-of-state": eos, "reconstruct": {"vertical": weno, "horizontal": weno},
                        "riemann-solver": {"type": "lmars"}, "conversion-order": key},
           "integration": {"type": "rk3", "cfl": 0.4, "implicit-scheme": 0, "nlim": -1, "tlim": 1.e9}}
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, dir=os.getcwd()) as f:
        yaml.safe_dump(cfg, f)
    try:
        options = MeshOptions.from_yaml(f.name)
        options.blocks_per_process(nb1)
        m = Mesh(options)
    finally:
        os.unlink(f.name)
    assert len(list(m.blocks)) == nb1
    return m


def run(m, init, nstep, device):
    """init(x1v) -> (rho, v1, p); returns (relative mass drift, redos, trips)"""
    blocks = list(m.blocks)
    state = []
    for b in blocks:
        b.to(torch.device(device), torch.float64)
        w = b.buffer("hydro.D").clone().zero_()
        rho, v, p = init(b.buffer("coord.x1v").double().cpu())
        w[kIDN], w[1], w[kIPR] = rho.to(w), v.to(w), p.to(w)
        state.append({"hydro_w": w})
    state, _ = m.initialize(state)
    parts = [b.part((0, 0, 0), False)[1:] for b in blocks]
    dx = [b.buffer("coord.dx1f").double().cpu()[sl[-1]] for b, sl in zip(blocks, parts)]
    mass = lambda: sum(float((s["hydro_u"][kIDN][sl].cpu() * h).sum()) for s, sl, h in zip(state, parts, dx))
    m0, redos, cycle = mass(), 0, 0
    while cycle < nstep:
        m.set_cycle(cycle + 1)
        dt = m.max_time_step(state)
        for st in range(len(blocks[0].module("intg").stages)):
            m.forward(state, dt, st)
        err = m.check_redo(state)
        assert err >= 0, f"terminated after {redos} redos at cycle {cycle}"
        redos, cycle = redos + (err > 0), cycle + (err == 0)
    assert all(torch.isfinite(s["hydro_u"]).all() for s in state)
    trips = sum(int(dict(b.named_buffers()).get("hydro.conversion_trips", torch.zeros(1)).sum()) for b in blocks)
    return abs(mass() - m0) / m0, redos, trips


def pulses(x):
    c = 1. + .03 * (torch.exp(-((x - .08) / .07) ** 2) + torch.exp(-((x - .45) / .07) ** 2))
    return c ** (2 / (G - 1)), 2 / (G - 1) * (c - 1.), c ** (2 * G / (G - 1)) / G


def dip(x):
    rho = torch.where((x > .45) & (x < .45 + 4. / NX), .0405, 1.).to(x.dtype)
    return rho, 0. * x, 1. + 0. * x


def main(device):
    bad = []
    for key in (2, 4):
        for nb1 in (1, 2):
            drift, redos, trips = run(mesh(key, nb1), pulses, 40, device)
            print(f"mass key {key} blocks {nb1}: |dM|/M {drift:.2e} redos {redos} trips {trips}")
            bad += [f"mass key {key} blocks {nb1}"] if drift > TOL else []
        try:
            drift, redos, trips = run(mesh(key, 1, limiter=True), dip, 20, device)
        except AssertionError as e:
            drift, redos, trips = float("nan"), str(e), 0
        print(f"dip key {key}: redos {redos} trips {trips} |dM|/M {drift:.2e}")
        bad += [f"dip key {key}"] if redos else []
    assert not bad, bad


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    d = p.parse_args().device
    if d == "cuda" and not torch.cuda.is_available():
        raise SystemExit(125)
    main(d)
