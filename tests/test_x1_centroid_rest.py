#!/usr/bin/env python3
"""SNAP_X1_CENTROID_EXACT: a column of exact cell averages stays at rest, split by what each part can hold.

The oracle of docs/derivations/x1-centroid-spherical.md, section 5: a hydrostatic column with g = 1,
x = r - r0 in [0, 2], reflecting walls, initialised with the cell averages a finite-volume cell holds (r^2-weighted
on a spherical-polar shell sector, plain on a Cartesian box; six-point Gauss-Legendre per cell). One RK3 step at
dt = 0.3 dx1 / sqrt(1.4); the radial force imbalance is f = max |rho v1| / (dt g <rho>), over the interior cells
and over the three cells next to each wall, explicit (implicit-scheme 0) and vertically implicit (1), full pressure
force (non-hydrostatic 1) and hydrostatic-split (0).

The x1 reference rows factor out exp(-x / H_ref) and interpolate the rest with a quintic, so the column is the
pure exponential p = exp(-x / H), rho = p / H, with dynamics/x1-ref-scale-height = H:
  (a) Cartesian: the rows hold this column exactly and no r^2 conversion is involved, so f must be round-off,
      f < TOL_ON = 1e-10, in the interior and at the walls (measured here at nz = 32: at most 6.6e-15, the
      largest of the eight arms being the interior, explicit, full pressure force).
  (b) spherical-polar at r0 / H = 5: the r^2 <-> plain-mean conversions of the switch are exact for polynomials
      only, so f is their truncation, not round-off. Asserted as a convergence order: between nz = 32 and 64, f
      must fall at an observed order of at least ORDER - ORDER_TOL. ORDER = 5 is measured on main (fe2edaa3, p
      rows): walls 5.08 and interior 5.24 between 32 and 64, 4.99 and 5.12 between 64 and 128; the factored rows
      give 4.92 / 5.10 and 4.96 / 4.99. A regression shows as a lost order. The switch-off control stays: at
      nz = 32 the uniform-measure formulas must leave f > TOL_OFF, so an ignored switch fails.
  (c) spherical-polar at r0 / H = R0_FAR = 1000, nz = 32: the same absolute floor as (a). This is the arm that
      pins the claim of docs/derivations/x1-centroid-spherical.md section 5 -- that the floor the switch leaves,
      larger at the walls because of the one-sided wall closure, does not depend on r0 -- and it is the coverage
      PR #6 carries as R0S = (5.0, 1000.0). It has no order arm and no switch-off control, because there is
      nothing left for them to measure: at this radius the conversions themselves are near the floor, so the
      switch-off values (6.5e-10 interior with the full pressure force, 1.2e-12 hydrostatic-split) sit below
      TOL_OFF. Switch on, measured here: 5.2e-13 to 1.1e-12 interior, 2.3e-12 to 2.8e-11 at the walls.
The switch is read once per process, so each arm runs in its own process.

  python test_x1_centroid_rest.py [--device cpu|cuda]
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
import torch

NZS = (32, 64)
R0 = 5.0  # spherical r0 / H, where curvature is strong
R0_FAR = 1000.0  # spherical r0 / H, where it is not (the floor is r0-independent)
SCHEMES = (0, 1)
NHS = (1.0, 0.0)
LZ = 2.0
H = 1.0  # p = exp(-x / H); the deck's x1-ref-scale-height
TOL_ON = 1.0e-10
TOL_OFF = 1.0e-8
ORDER, ORDER_TOL = 5.0, 0.5
NG, IV1 = 3, 1
GLX, GLW = np.polynomial.legendre.leggauss(6)


def config(geom, r0, nz, scheme, nh):
    half = 0.05
    bounds = ({"x1min": r0, "x1max": r0 + LZ, "x2min": 0.5 * math.pi - half, "x2max": 0.5 * math.pi + half,
               "x3min": 0.0, "x3max": 2.0 * half} if geom == "spherical-polar" else
              {"x1min": r0, "x1max": r0 + LZ, "x2min": 0.0, "x2max": 1.0, "x3min": 0.0, "x3max": 1.0})
    return {"geometry": {"type": geom, "bounds": bounds,
                         "cells": {"nx1": nz, "nx2": 4, "nx3": 4, "nghost": NG}},
            "dynamics": {"equation-of-state": {"type": "ideal-gas", "gammad": 1.4, "weight": 8.31446,
                                               "density-floor": 1.e-12, "pressure-floor": 1.e-12,
                                               "temperature-floor": 1.e-12, "limiter": True},
                         "reconstruct": {"vertical": {"type": "weno5", "scale": True, "shock": False},
                                         "horizontal": {"type": "weno5", "scale": True, "shock": False}},
                         "riemann-solver": {"type": "lmars"},
                         "x1-ref-scale-height": H},
            "boundary-condition": {"external": {"x1-inner": "reflecting", "x1-outer": "reflecting",
                                                "x2-inner": "reflecting", "x2-outer": "reflecting",
                                                "x3-inner": "periodic", "x3-outer": "periodic"}},
            "integration": {"type": "rk3", "cfl": 0.4, "implicit-scheme": scheme, "nlim": -1,
                            "tlim": 1.e9},
            "forcing": {"const-gravity": {"grav1": -1.0, "non-hydrostatic": nh}}}


def column(r, r0):
    """rho and p of the hydrostatic column (g = 1)"""
    p = np.exp(-(r - r0) / H)
    return p / H, p


def means(rf, geom, r0):
    """the cell averages of rho and p on cells [rf_i, rf_i+1], r^2-weighted on the sphere"""
    c, h = 0.5 * (rf[1:] + rf[:-1]), 0.5 * (rf[1:] - rf[:-1])
    r = c[:, None] + h[:, None] * GLX[None, :]
    w = GLW[None, :] * (r * r if geom == "spherical-polar" else np.ones_like(r))
    return tuple((q * w).sum(1) / w.sum(1) for q in column(r, r0))


def imbalance(geom, r0, nz, scheme, nh, device):
    import yaml
    from snapy import MeshBlock, MeshBlockOptions, kIDN, kIPR
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, dir=os.getcwd()) as f:
        yaml.safe_dump(config(geom, r0, nz, scheme, nh), f)
        tmp = f.name
    try:
        block = MeshBlock(MeshBlockOptions.from_yaml(tmp))
    finally:
        os.unlink(tmp)
    block.to(torch.device(device), torch.float64)
    rf = block.buffer("coord.x1f").cpu().numpy()
    w = block.buffer("hydro.D").clone().zero_()
    # interior means; ghosts get the same formula (the reflecting walls refill them)
    rho, p = (torch.from_numpy(q).to(w) for q in means(rf, geom, r0))
    w[kIDN] = rho
    w[kIPR] = p
    bv, _ = block.initialize({"hydro_w": w})
    dt = 0.3 * (LZ / nz) / math.sqrt(1.4)
    block.inc_cycle()
    for st in range(len(block.intg.stages)):
        block.forward(bv, dt, st)
    assert block.check_redo(bv) == 0
    u = bv["hydro_u"].cpu()[:, NG:-NG, NG:-NG, NG:-NG]
    f = (u[IV1] / (dt * u[kIDN])).abs().amax(dim=(0, 1))
    return {"interior": float(f[NG:-NG].max()), "wall": float(torch.cat((f[:NG], f[-NG:])).max())}


def key(geom, r0, nz, scheme, nh):
    return f"{geom}/{r0:g}/{nz}/{scheme}/{nh:g}"


def child(device):
    out = {key("cartesian", R0, nz, s, nh): imbalance("cartesian", R0, nz, s, nh, device)
           for nz in NZS[:1] for s in SCHEMES for nh in NHS}
    out.update({key("spherical-polar", R0, nz, s, nh): imbalance("spherical-polar", R0, nz, s, nh, device)
                for nz in NZS for s in SCHEMES for nh in NHS})
    # the far-radius arm: one grid, judged against the same absolute floor as
    # Cartesian, which is the claim of x1-centroid-spherical.md section 5
    out.update({key("spherical-polar", R0_FAR, nz, s, nh):
                imbalance("spherical-polar", R0_FAR, nz, s, nh, device)
                for nz in NZS[:1] for s in SCHEMES for nh in NHS})
    return out


def run(switch, device, tmpdir):
    env = dict(os.environ)
    env.pop("SNAP_X1_CENTROID_EXACT", None)
    if switch is not None:
        env["SNAP_X1_CENTROID_EXACT"] = switch
    out = os.path.join(tmpdir, f"rest_{switch}.json")
    subprocess.run([sys.executable, __file__, "--child", "--out", out, "--device", device],
                   env=env, check=True)
    return json.load(open(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.device == "cuda" and not torch.cuda.is_available():
        print("CUDA is not available")
        return 125
    if a.child:
        json.dump(child(a.device), open(a.out, "w"))
        return 0
    failures = []
    with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmp:
        res = {s: run(s, a.device, tmp) for s in (None, "1")}
    on, off = res["1"], res[None]
    for k, v in on.items():
        geom, r0, nz, scheme, nh = k.split("/")
        print(f"{geom:15s} r0/H {r0:>6s} nz {nz:>3s} implicit-scheme {scheme} non-hydrostatic {nh}: "
              "max |rho v1|/(dt g rho), interior / wall: "
              f"off {off[k]['interior']:.3e} / {off[k]['wall']:.3e}  on {v['interior']:.3e} / {v['wall']:.3e}",
              flush=True)
        # (a) and (c) round-off: Cartesian, and the sphere where curvature no longer matters
        if geom == "cartesian" or float(r0) == R0_FAR:
            for part in ("interior", "wall"):
                if not v[part] < TOL_ON:
                    failures.append(f"{k} {part}, switch on: {v[part]:.3e} >= {TOL_ON}")
    for scheme in SCHEMES:  # (b) the order of the conversions, and the off control
        for nh in NHS:
            k0, k1 = (key("spherical-polar", R0, nz, scheme, nh) for nz in NZS)
            for part in ("interior", "wall"):
                order = math.log(on[k0][part] / on[k1][part]) / math.log(NZS[1] / NZS[0])
                print(f"spherical-polar r0/H {R0:g} implicit-scheme {scheme} non-hydrostatic {nh:g} {part}: "
                      f"switch-on {on[k0][part]:.3e} -> {on[k1][part]:.3e}, order {order:.2f}", flush=True)
                if not order >= ORDER - ORDER_TOL:
                    failures.append(f"{k0} {part}: observed order {order:.2f} < {ORDER - ORDER_TOL}")
            if not off[k0]["interior"] > TOL_OFF:
                failures.append(f"{k0}, switch off: {off[k0]['interior']:.3e} <= {TOL_OFF}, "
                                "the oracle does not tell the forms apart")
    for f in failures:
        print("FAIL:", f)
    if failures:
        return 1
    print("### x1 centroid rest test passed. ###")
    return 0


if __name__ == "__main__":
    sys.exit(main())
