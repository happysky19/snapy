#!/usr/bin/env python3
"""dynamics/conversion-order 4: a fourth-order x1 cell-average <-> point conversion (#339).

order    right-moving acoustic pulse, c = 1 + 0.03 exp(-((x - 0.3) / 0.07)^2), from the exact u averages, on a
         uniform x1 and on x1 = s + 0.8 sin(2 pi s) / (2 pi), nx1 = 64, 128, 256 against 1024 on the nested faces:
         fitted order >= 3.8 (key 2 printed), a uniform tracer ratio within 1e-13.
radial   the conversion alone on gnomonic-equiangle and spherical-polar blocks (r^2 dr cells), r in [1, 2]: the
         converted velocity average of exact r^2 averages, nx1 = 64, 128, 256, fitted order >= 3.8.
refused  conversion-order 1, 3 and 6 are refused.
shock    a 1:1000 shock tube (WENO5 shock: true, LMARS) stays finite with rho > 0 to t = 0.2, fallback trips > 0.
mass     |dM|/M <= 1e-13 after 40 steps: two pulses against a reflecting wall (one block), a 2:1 jump exactly on
         the seam of two x1 blocks in one process.
limiter  limiter on, 20 steps through the redo loop, no redo: a 4-cell dip whose u - L u is below the floor, and
         a moist column whose vapor steps to zero (u - L u has negative vapor there).
theta    a coarse Straka density current (32 x 128, dry, adiabatic, reflecting walls) to t = 900 s: theta' stays
         within its initial range +- 2 K (adiabatic flow carries theta).
gravity  a column at rest with T = 1 - 0.8 z (g = 1, discretely balanced) and a density/pressure pulse at z = 0.5,
         nx1 = 64, 128, 256 against 1024: the pulse's fitted order >= 3.8 (the default face density reference is
         O(dz^2) where p/rho curves; key 4 takes the fourth-order one, docs/derivations/wb-ref4.md).

  python test_conversion_order.py [--device cpu|cuda]
"""
import argparse
import os
import tempfile
import time

import numpy as np
import torch
import yaml
from snapy import Mesh, MeshOptions, balance_column, kICY, kIDN, kIPR

G, NG, TOL = 1.4, 3, 1.e-13
X, WQ = (torch.from_numpy(v) for v in np.polynomial.legendre.leggauss(8))


def mesh(key, nx=64, geo="cartesian", x1f=None, nb1=1, limiter=False, moist=False, shock=False, tracer=False,
         grav=0., straka=False):
    bounds = {"x1min": 0., "x1max": 1., "x2min": 0., "x2max": 1., "x3min": 0., "x3max": 1.}
    bounds.update({"spherical-polar": {"x1min": 1., "x1max": 2., "x2min": 1., "x2max": 2.},
                   "gnomonic-equiangle": {"x1min": 1., "x1max": 2., "x2min": -.05, "x2max": .05,
                                          "x3min": -.05, "x3max": .05}}.get(geo, {}))
    weno = {"type": "weno5", "scale": True, "shock": shock}
    cfg = {"geometry": {"type": geo, "bounds": bounds, "cells": {"nx1": nx, "nx2": 1, "nx3": 1, "nghost": NG}},
           "boundary-condition": {"external": {f"x{d}-{s}": "reflecting" if d == 1 else "periodic"
                                               for d in (1, 2, 3) for s in ("inner", "outer")}},
           "distribute": {"layout": "cubed" if nb1 > 1 else "slab", "nb1": nb1, "nb2": 1, "nb3": 1,
                          "blocks_per_process": nb1},
           "dynamics": {"equation-of-state": {"type": "ideal-gas", "gammad": G, "limiter": limiter,
                                              "density-floor": 1.e-10, "pressure-floor": 1.e-10},
                        "reconstruct": {"vertical": weno, "horizontal": weno},
                        "riemann-solver": {"type": "lmars"}, "conversion-order": key},
           "integration": {"type": "rk3", "cfl": 0.4, "implicit-scheme": 0, "nlim": -1, "tlim": 1.e9}}
    if limiter:
        cfg["dynamics"]["equation-of-state"].update({"density-floor": 1.e-3, "pressure-floor": 1.e-3,
                                                     "temperature-floor": 1.e-12})
    if geo != "cartesian":
        cfg["boundary-condition"]["external"] = {"x1-inner": "reflecting", "x1-outer": "reflecting"}
    if x1f is not None:
        cfg["geometry"]["x1f"] = x1f
    if tracer:
        cfg["scalar"] = {"nvar": 1, "names": ["q"], "reconstruct": {"type": "weno5", "shock": False},
                         "riemann-solver": {"type": "upwind"}}
    if straka:
        cfg["geometry"].update(bounds={"x1min": 0., "x1max": 6.4e3, "x2min": 0., "x2max": 25.6e3, "x3min": 0.,
                                       "x3max": 1.}, cells={"nx1": nx, "nx2": 4 * nx, "nx3": 1, "nghost": NG})
        cfg["dynamics"]["equation-of-state"]["weight"] = 29.e-3
        cfg["boundary-condition"]["external"] = {f"x{d}-{s}": "reflecting" for d in (1, 2, 3)
                                                 for s in ("inner", "outer")}
        cfg["integration"]["cfl"] = .9
    if grav:
        cfg["forcing"] = {"const-gravity": {"grav1": -grav}}
    if moist:
        cfg["reference-state"] = {"Tref": 0., "Pref": 1.e5}
        cfg["species"] = [{"name": "dry", "composition": {"H": 1.6667, "He": 0.16667}, "cv_R": 2.5},
                          {"name": "vapor", "composition": {"H": 2, "O": 1}, "cv_R": 2.5, "u0_R": 0.},
                          {"name": "cloud", "composition": {"H": 2, "O": 1}, "cv_R": 9.0, "u0_R": -3430.}]
        cfg["reactions"] = [{"equation": "vapor <=> cloud", "type": "nucleation",
                             "rate-constant": {"formula": "h2o_ideal"}}]
        bounds["x1max"] = 1.e4
        cfg["dynamics"]["equation-of-state"] = {"type": "ideal-moist", "density-floor": 1.e-10,
                                                "pressure-floor": 1.e-10, "limiter": True}
        cfg["forcing"] = {"const-gravity": {"grav1": -10.}}
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, dir=os.getcwd()) as f:
        yaml.safe_dump(cfg, f)
    try:
        options = MeshOptions.from_yaml(f.name)
        options.blocks_per_process(nb1)
        return Mesh(options)
    finally:
        os.unlink(f.name)


tracer = lambda b: "scalar.D" in dict(b.named_buffers())


def start(m, init, device):
    """init(x1f, x1v) -> {w row: values}; returns (state, blocks)"""
    blocks, state = list(m.blocks), []
    for b in blocks:
        b.to(torch.device(device), torch.float64)
        w = b.buffer("hydro.D").clone().zero_()
        for row, val in init(b.buffer("coord.x1f").double().cpu(), b.buffer("coord.x1v").double().cpu()).items():
            w[row] = val.to(w)
        state.append({"hydro_w": w} | ({"scalar_r": torch.full_like(w[:1], .01)} if tracer(b) else {}))
    return m.initialize(state)[0], blocks


def run(m, init, device, nstep=None, dt=None, tend=None, state=None):
    """steps nstep (or to tend) through the driver's redo loop; returns (state, blocks, steps, redos)"""
    blocks = list(m.blocks)
    if state is None:
        state, blocks = start(m, init, device)
    t, steps, redos = 0., 0, 0
    while (steps < nstep) if nstep is not None else (t < tend):
        m.set_cycle(steps + 1)
        h = dt or m.max_time_step(state)
        for st in range(len(blocks[0].module("intg").stages)):
            m.forward(state, h, st)
        err = m.check_redo(state)
        assert err >= 0, f"terminated after {redos} redos at step {steps}"
        redos, steps, t = redos + (err > 0), steps + (err == 0), t + h * (err == 0)
    assert all(torch.isfinite(s["hydro_u"]).all() for s in state), f"non-finite at step {steps}"
    return state, blocks, steps, redos


def interior(state, blocks, name, row):
    return torch.cat([s[name][row][b.part((0, 0, 0), False)[1:]].cpu().flatten() for s, b in zip(state, blocks)])


def averages(xf, rho, v, p, r2=False):
    """the exact (r^2-weighted) averages of rho, rho v, E, as w = W(u)"""
    r = (xf[:-1, None] + xf[1:, None] + (xf[1:, None] - xf[:-1, None]) * X) / 2
    wr = WQ * (r * r if r2 else 1.)
    avg = lambda q: (q(r) * wr).sum(-1) / wr.sum(-1)
    a, m, e = avg(rho), avg(lambda r: rho(r) * v(r)), avg(lambda r: p(r) / (G - 1) + rho(r) * v(r) ** 2 / 2)
    return {kIDN: a, 1: m / a, kIPR: (G - 1) * (e - m * m / a / 2)}, avg(v)


def pulse(x0, amp=.03, sig=.07):
    c = lambda r: 1. + amp * torch.exp(-((r - x0) / sig) ** 2)
    return lambda r: c(r) ** (2 / (G - 1)), lambda r: 2 / (G - 1) * (c(r) - 1.), lambda r: c(r) ** (2 * G / (G - 1)) / G


def fit(err, nx=(64, 128, 256)):
    return -np.polyfit(np.log(nx), np.log(err), 1)[0]


def arm_order(device, a):
    nref, dt = 1024, 0.25 * (1. - a) / 1024
    def mass(nx, key):
        s = np.linspace(0., 1., nx + 1)
        m = mesh(key, nx, x1f=(s + a * np.sin(2 * np.pi * s) / (2 * np.pi)).tolist() if a else None, tracer=True)
        state, blocks, _, _ = run(m, lambda xf, xv: averages(xf, *pulse(.3))[0], device, round(.12 / dt), dt)
        xf = blocks[0].buffer("coord.x1f").double().cpu()[NG:-NG]
        q = float((interior(state, blocks, "scalar_s", 0) / interior(state, blocks, "hydro_u", kIDN) / .01 - 1).abs().max())
        return interior(state, blocks, "hydro_u", kIDN) * (xf[1:] - xf[:-1]), q
    out = {}
    for key in (2, 4):
        ref, _ = mass(nref, key)
        runs = [mass(nx, key) for nx in (64, 128, 256)]
        err = [float((r - ref.view(len(r), -1).sum(1)).abs().sum()) for r, _ in runs]
        out[key] = (fit(err), max(q for _, q in runs))
        print(f"order {'stretched' if a else 'uniform'} key {key}: L1 {err} order {out[key][0]:.2f} tracer {out[key][1]:.1e}")
    return out[4][0] >= 3.8 and out[4][1] <= TOL


def arm_radial(device):
    ok = True
    for geo in ("spherical-polar", "gnomonic-equiangle"):
        for key in (2, 4):
            err = []
            for nx in (64, 128, 256):
                exact = {}
                def init(xf, xv):
                    w, exact["v"] = averages(xf, lambda r: 1. + .5 * torch.sin(4 * r) * torch.exp(-r / 2),
                                             lambda r: .1 * torch.cos(3 * r), lambda r: 1. + .2 * torch.sin(2 * r), r2=True)
                    return w
                m = mesh(key, nx, geo=geo)
                state, _ = start(m, init, device)
                m.set_cycle(1)
                m.forward(state, 1.e-12, 0)
                s = slice(2 * NG, -2 * NG)
                err.append(float((state[0]["hydro_w"][1, 0, 0].cpu()[s] - exact["v"][s]).abs().max()))
            print(f"radial {geo} key {key}: max err {err} order {fit(err):.2f}")
            ok &= key == 2 or fit(err) >= 3.8
    return ok


def arm_refused(device):
    for bad in (1, 3, 6):
        try:
            mesh(bad, 16)
        except RuntimeError as e:
            assert "conversion-order" in str(e), e
        else:
            return False
    return True


def arm_shock(device):
    m = mesh(4, 256, shock=True)
    state, blocks, steps, _ = run(m, lambda xf, xv: {kIDN: torch.where(xv < .5, 1., 1.e-3).double(),
                                                     kIPR: torch.where(xv < .5, 1., 1.e-3).double()}, device, tend=.2)
    trips = int(blocks[0].buffer("hydro.conversion_trips"))
    rho = float(interior(state, blocks, "hydro_u", kIDN).min())
    print(f"shock key 4: {steps} steps, min rho {rho:.3e}, trips {trips}")
    return rho > 0 and trips > 0


def arm_mass(device):
    ok = True
    for name, nb1, rho, p in (("wall", 1, None, None), ("seam jump", 2, (1., .5), (1., .5))):
        init = (lambda xf, xv: averages(xf, *pulse(.08))[0]) if rho is None else \
            (lambda xf, xv: {kIDN: torch.where(xv < .5, 1., .5).double(), kIPR: torch.where(xv < .5, 1., .5).double()})
        m = mesh(4, nb1=nb1)
        state, blocks = start(m, init, device)
        dx = torch.cat([b.buffer("coord.dx1f").double().cpu()[NG:-NG] for b in blocks])
        m0 = float((interior(state, blocks, "hydro_u", kIDN) * dx).sum())
        run(m, None, device, 40, state=state)
        drift = abs(float((interior(state, blocks, "hydro_u", kIDN) * dx).sum()) - m0) / m0
        print(f"mass {name} key 4: |dM|/M {drift:.2e}")
        ok &= drift <= TOL
        del m, state, blocks  # a mesh still alive stalls the next one's in-process x1 seam
    return ok


def arm_limiter(device):
    ok = True
    dip = lambda xf, xv: {kIDN: torch.where((xv > .45) & (xv < .45 + 4 / 64), .0405, 1.).double(),
                          kIPR: 1. + 0. * xv}
    def moist(xf, z):
        p = 1.e5 * torch.exp(-z * 10. / (3900. * 320.))
        return {kIDN: p / (3900. * 320.), kIPR: p, kICY: torch.where(z < 5.e3, 2.e-3, 0.).double()}
    for name, m, init in (("dip", mesh(4, limiter=True), dip), ("moist vapor step", mesh(4, moist=True), moist)):
        try:
            _, blocks, _, redos = run(m, init, device, 20)
            print(f"limiter {name} key 4: redos {redos}, trips {int(blocks[0].buffer('hydro.conversion_trips'))}")
        except AssertionError as e:
            redos = str(e)
            print(f"limiter {name} key 4: {redos}")
        ok &= redos == 0
    return ok


def arm_theta(device):
    rd, g = 8.314462618 / 29.e-3, 9.8
    cp = G * rd / (G - 1)
    m = mesh(4, 32, grav=g, straka=True)
    b = list(m.blocks)[0]
    b.to(torch.device(device), torch.float64)
    z, x = b.buffer("coord.x1v").double()[None, :], b.buffer("coord.x2v").double()[:, None]
    big = torch.sqrt((x / 4.e3) ** 2 + ((z - 3.e3) / 2.e3) ** 2)
    temp = 300. - g * z / cp
    p = 1.e5 * (temp / 300.) ** (cp / rd)
    temp = temp + torch.where(big <= 1, -7.5 * (torch.cos(big * np.pi) + 1), 0.)
    w = b.buffer("hydro.D").clone().zero_()
    w[kIPR], w[kIDN] = p.to(w), (p / (rd * temp)).to(w)
    state, _ = m.initialize([{"hydro_w": w}])
    th = lambda: (lambda w: w[kIPR] / (rd * w[kIDN]) * (1.e5 / w[kIPR]) ** (rd / cp) - 300.)(
        state[0]["hydro_w"][b.part((0, 0, 0), False)])
    lo, hi = float(th().min()), float(th().max())
    run(m, None, device, tend=900., state=state)
    a, z = float(th().min()), float(th().max())
    print(f"theta key 4: theta' initial [{lo:.2f}, {hi:.2f}] at t = 900 s [{a:.2f}, {z:.2f}]")
    return lo - 2. <= a and z <= hi + 2.


def arm_gravity(device):
    temp = lambda r: 1. - .8 * r
    p0, d = lambda r: temp(r) ** 1.25, lambda r: 1.e-3 * torch.exp(-((r - .5) / .1) ** 2)
    rho0 = lambda r: p0(r) / temp(r)
    def run_nx(nx, dt):
        bg = []
        def init(xf, xv):  # the pulse's exact averages on the balanced column
            w0, w1 = averages(xf, rho0, lambda r: 0 * r, p0)[0], \
                averages(xf, lambda r: rho0(r) * (1 + d(r)), lambda r: 0 * r, lambda r: p0(r) * (1 + d(r)) ** G)[0]
            s = slice(NG, -NG)
            col = torch.stack([w0[kIDN][s]] + [0 * w0[kIDN][s]] * 3 + [w0[kIPR][s]]).view(5, 1, 1, -1)
            wb = balance_column(col, (xf[1:] - xf[:-1])[s].contiguous(), 1., rtol=1.e-13)[0]
            wb = torch.cat([wb[..., :1]] * NG + [wb] + [wb[..., -1:]] * NG, -1)[:, 0, 0]
            bg.append(wb[kIDN][s])
            return {kIDN: wb[kIDN] + w1[kIDN] - w0[kIDN], kIPR: wb[kIPR] + w1[kIPR] - w0[kIPR]}
        state, blocks, _, _ = run(mesh(4, nx, grav=1.), init, device, round(.1 / dt), dt)
        return (interior(state, blocks, "hydro_u", kIDN) - bg[0]) / nx
    dt = .25 / 1024 / G ** .5
    ref = run_nx(1024, dt)
    err = [float((run_nx(nx, dt) - ref.view(nx, -1).sum(1)).abs().sum()) for nx in (64, 128, 256)]
    print(f"gravity key 4: L1 {err} order {fit(err):.2f}")
    return fit(err) >= 3.8


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--arms", default="order,radial,refused,shock,mass,limiter,theta,gravity")
    a = ap.parse_args()
    if a.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit(125)
    arms = {"order": lambda d: arm_order(d, 0.) and arm_order(d, .8), "radial": arm_radial, "refused": arm_refused,
            "shock": arm_shock, "mass": arm_mass, "limiter": arm_limiter,
            "theta": arm_theta, "gravity": arm_gravity}
    bad = []
    for name in a.arms.split(","):
        t0 = time.time()
        try:
            ok = arms[name](a.device)
        except Exception as e:  # an unknown key or a non-finite state fails the arm, not the run
            print(f"{name}: {type(e).__name__}: {str(e).splitlines()[0][:160]}")
            ok = False
        print(f"arm {name}: {'PASS' if ok else 'FAIL'} in {time.time() - t0:.1f} s")
        bad += [] if ok else [name]
    assert not bad, bad
