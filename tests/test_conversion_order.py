#!/usr/bin/env python3
"""dynamics/conversion-order 4: a fourth-order x1 cell-average <-> point conversion.

(a) a 1-D right-moving isentropic acoustic pulse, c = 1 + 0.03 exp(-((x - 0.3) / 0.07)^2), rho = c^5, from the exact
    u averages, on a uniform x1 and on the stretched x1 = s + 0.8 sin(2 pi s) / (2 pi) (neighbour width
    ratio up to 1.139 at nx1 = 64), nx1 = 64, 128, 256 against nx1 = 1024 on the nested faces, one dt for all:
    the fitted order of the L1 density error is >= 3.8 with key 4; key 2's order is printed;
(b) an isothermal column at rest on that stretched x1 (nx1 = 32) with key 4, balanced by balance_column: the relative change
    of rho and E and max|w|/c after 20 steps are <= 1e-13 and <= 1e-12;
(c) a uniform tracer ratio in (a) and (b) stays within 1e-13 with key 4;
(d) any other key value is refused.

  python test_conversion_order.py [--device cpu|cuda]
"""
import argparse
import math
import os
import tempfile

import numpy as np
import torch
import yaml
from snapy import MeshBlock, MeshBlockOptions, balance_column, kIDN, kIPR

NG, G, A, T, NREF = 3, 1.4, 0.8, 0.12, 1024
NX = (64, 128, 256)


def block(nx, a, key, grav=0.0, device="cpu"):
    geo = {"type": "cartesian", "cells": {"nx1": nx, "nx2": 1, "nx3": 1, "nghost": NG},
           "bounds": {"x1min": 0., "x1max": 1., "x2min": 0., "x2max": 1., "x3min": 0., "x3max": 1.}}
    if a:
        s = np.linspace(0., 1., nx + 1)
        geo["x1f"] = (s + a * np.sin(2 * np.pi * s) / (2 * np.pi)).tolist()
    bc = {f"x{d}-{s}": ("reflecting" if d == 1 else "periodic") for d in (1, 2, 3) for s in ("inner", "outer")}
    cfg = {"geometry": geo, "boundary-condition": {"external": bc},
           "dynamics": {"equation-of-state": {"type": "ideal-gas", "gammad": G, "limiter": False},
                        "reconstruct": {"vertical": {"type": "weno5", "scale": True, "shock": False},
                                        "horizontal": {"type": "weno5", "scale": True, "shock": False}},
                        "riemann-solver": {"type": "lmars"}, "conversion-order": key},
           "integration": {"type": "rk3", "cfl": 0.4, "implicit-scheme": 0, "nlim": -1, "tlim": 1.e9},
           "scalar": {"nvar": 1, "names": ["q"], "reconstruct": {"type": "weno5", "shock": False},
                      "riemann-solver": {"type": "upwind"}}}
    if grav:
        cfg["forcing"] = {"const-gravity": {"grav1": -grav}}
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, dir=os.getcwd()) as f:
        yaml.safe_dump(cfg, f)
    try:
        b = MeshBlock(MeshBlockOptions.from_yaml(f.name))
    finally:
        os.unlink(f.name)
    b.to(torch.device(device), torch.float64)
    return b


def run(b, w, nstep, dt):
    bv, _ = b.initialize({"hydro_w": w, "scalar_r": torch.full_like(w[:1], .01)})
    for _ in range(nstep):
        b.inc_cycle()
        for st in range(len(b.intg.stages)):
            b.forward(bv, dt, st)
    assert b.check_redo(bv) == 0
    u, s = bv["hydro_u"][..., NG:-NG].cpu(), bv["scalar_s"][..., NG:-NG].cpu()
    return u, float((s[0] / u[kIDN] / .01 - 1.).abs().max())


def pulse(nx, a, key, dt, device):
    b = block(nx, a, key, device=device)
    x1f = b.buffer("coord.x1f").cpu().double()
    x, wq = (torch.from_numpy(v) for v in np.polynomial.legendre.leggauss(6))
    xq = (x1f[:-1, None] + x1f[1:, None] + (x1f[1:, None] - x1f[:-1, None]) * x) / 2
    c = 1. + .03 * torch.exp(-((xq - .3) / .07) ** 2)  # right-moving simple wave, p = rho^G / G
    rho, v = c ** (2 / (G - 1)), 2 / (G - 1) * (c - 1.)
    m, e = ((q * wq).sum(-1) / 2 for q in (rho * v, rho ** G / G / (G - 1) + rho * v * v / 2))
    w = b.buffer("hydro.D").clone().zero_()  # w = W(u) of the exact u averages
    w[kIDN] = (rho * wq).sum(-1).to(w) / 2
    w[1], w[kIPR] = (m / w[kIDN]).to(w), ((G - 1) * (e - m * m / w[kIDN] / 2)).to(w)
    u, q = run(b, w, round(T / dt), dt)
    h = (x1f[1:] - x1f[:-1])[NG:-NG]
    return u[kIDN, 0, 0] * h, h, q


def order(a, key, device):
    dt = 0.25 * (1. - a) / NREF
    ref, href, _ = pulse(NREF, a, key, dt, device)
    err, qs = [], []
    for nx in NX:
        m, h, q = pulse(nx, a, key, dt, device)
        r = NREF // nx
        err.append(float((m - ref.view(nx, r).sum(1)).abs().sum()))
        qs.append(q)
    p = -np.polyfit(np.log(NX), np.log(err), 1)[0]
    print(f"x1 {'stretched' if a else 'uniform'} key {key}: L1 {err} order {p:.2f} tracer {max(qs):.1e}")
    return p, max(qs)


def column(device):
    b = block(32, A, 4, grav=1., device=device)
    x1f = b.buffer("coord.x1f").cpu().double()[NG:-NG]
    zc = (x1f[1:] + x1f[:-1]) / 2
    col = torch.stack([torch.exp(-zc)] + [0 * zc] * 3 + [torch.exp(-zc)]).view(5, 1, 1, 32)
    wb, _, _ = balance_column(col, (x1f[1:] - x1f[:-1]).contiguous(), 1., rtol=1.e-14, stretched=True)
    w = b.buffer("hydro.D").clone().zero_()
    wb = torch.cat([wb[..., :1]] * NG + [wb] + [wb[..., -1:]] * NG, -1).to(w)
    w[kIDN], w[kIPR] = wb[kIDN], wb[kIPR]
    u0, _ = run(b, w.clone(), 0, 0.)
    u, q = run(b, w, 20, 0.3 * (1. - A) / 32 / math.sqrt(G))
    rest = float(((u - u0)[[kIDN, kIPR]] / u0[[kIDN, kIPR]]).abs().max())
    vc = float((u[1] / u[kIDN] / torch.sqrt(G * u0[kIPR] * (G - 1) / u0[kIDN])).abs().max())
    print(f"column key 4: rest {rest:.1e} max|w|/c {vc:.1e} tracer {q:.1e}")
    return rest, vc, q


def main(device):
    for a in (0., A):
        order(a, 2, device)
        p, q = order(a, 4, device)
        assert p >= 3.8 and q <= 1.e-13, (a, p, q)
    rest, vc, q = column(device)
    assert rest <= 1.e-13 and vc <= 1.e-12 and q <= 1.e-13, (rest, vc, q)
    for bad in (1, 3, 6):
        try:
            block(32, 0., bad)
        except RuntimeError as e:
            assert "conversion-order" in str(e), e
        else:
            raise AssertionError(f"conversion-order {bad} was accepted")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    d = p.parse_args().device
    if d == "cuda" and not torch.cuda.is_available():
        raise SystemExit(125)
    main(d)
