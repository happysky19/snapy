#!/usr/bin/env python3
"""#280 stage 2 (tests only): a stretched x1 on the cubed sphere (gnomonic-equiangle).

Six panels in one process (Mesh API) on the jupiter_gcm shell, r = 69911000 .. 70211000 m.
The stretched grids are the n5 and n10 contract face lists of the jupiter_gcm column
(jihenghu/snapy data/280-jupiter-gcm-faces 2070a4cc), vendored here as
test_stage2_faces_n{5,10}.csv and checked by sha256 before use. Every arm first runs the
UNIFORM control at the same nx1 (30 for n5, 59 for n10) and prints its floor.

  --arm volume      the six panels' cell volumes sum to 4 pi (ro^3 - ri^3) / 3, with ro, ri
                    the stored end faces and plain fp64 face differences in the metric
  --arm rest        a discretely balanced isothermal column (balance_column, rtol 1e-13)
                    stays at rest: max |v| / c_s after NLIM cycles, explicit and implicit-9
  --arm freestream  constant rho, p, v = 0, gravity off: the state stays constant to
                    round-off in every cell and in the panel-edge ghosts (x2/x3 exchange)

At 515201ad (#280 stage 1) a stretched x1 on gnomonic-equiangle is refused
(src/coord/coordinate.cpp:400-405), so the stretched part of every arm FAILS there; with the
refusal lifted but src/coord/gnomonic_equiangle.cpp:31-38 unchanged (scalar dx1f), the volume
and rest arms fail on the wrong radial metric.

  python test_stage2_cubed_stretched.py --arm volume|rest|freestream [--device cpu|cuda]
"""
import argparse
import csv
import hashlib
import math
import os
import sys
import tempfile
from pathlib import Path

import torch
import yaml

HERE = Path(__file__).resolve().parent
LISTS = {  # name -> (file, sha256 of the vendored copy = data/280-jupiter-gcm-faces 2070a4cc)
    "n5": ("test_stage2_faces_n5.csv",
           "70e36e8503fb9651912faaf159bdfc51c22f985e594e8d85e1d2f02f141f8c7e"),
    "n10": ("test_stage2_faces_n10.csv",
            "5eff3ab4b4c936049d8cca145f4ce7e29d5da6a4993db3a80f058cef09c15811"),
}

# Tolerances, fixed once from the uniform-control floors measured at 515201ad on CPU
# (largest over uniform30/uniform59 and, for rest, explicit and implicit-9; every run prints
# the floors again): TOL = 100 x that floor, rounded up to one significant digit, never
# below 64 eps = 1.4e-14.
#   volume      floor 4.441e-16 (uniform30)                 -> 5e-14
#   freestream  floor 3.331e-16 (panel-edge ghosts, both N) -> 4e-14
#   rest        floor 1.562e-14 (uniform30 implicit-9)      -> 2e-12
#               (re-measured after the column moved to true face widths: largest
#               floor 4.593e-14, uniform59 explicit; the tolerance stays 2e-12, 43x)
TOL_VOLUME = 5e-14
TOL_REST = 2e-12
TOL_FREESTREAM = 4e-14
NLIM = 20
P0, H0 = 1.0e6, 6.0e4          # isothermal column: bottom pressure (Pa), scale height (m)
GRAV = 22.0                    # examples/jupiter_gcm.yaml:128
GAMMA = 1.4                    # dry cv_R = 2.5


def face_list(name):
    fname, want = LISTS[name]
    raw = (HERE / fname).read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != want:
        raise SystemExit("FAIL: %s sha256 %s != %s" % (fname, got, want))
    rows = list(csv.DictReader(raw.decode().splitlines()))
    return [float(r["x1f_m"]) for r in rows]


def build(cfg, device):
    from snapy import Mesh, MeshOptions

    nx = cfg["geometry"]["cells"]["nx2"]
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, dir=os.getcwd()) as f:
        yaml.safe_dump(cfg, f)
        tmp = f.name
    try:
        options = MeshOptions.from_yaml(tmp)
        options.blocks_per_process(6)
        options.set_local_horizontal_cells(nx, nx)
        mesh = Mesh(options)
    finally:
        os.unlink(tmp)
    blocks = list(mesh.blocks)
    for block in blocks:
        block.to(torch.device(device))
    return mesh, blocks


def config(grid, implicit=False, gravity=True):
    with open(HERE / "test_stage2_cubed_stretched.yaml") as f:
        cfg = yaml.safe_load(f)
    if grid.startswith("uniform"):
        cfg["geometry"]["cells"]["nx1"] = int(grid[len("uniform"):])
    else:
        faces = face_list(grid)
        cfg["geometry"]["cells"]["nx1"] = len(faces) - 1
        cfg["geometry"]["x1f"] = faces
    cfg["integration"]["implicit-scheme"] = 9 if implicit else 0
    if not gravity:
        cfg.pop("forcing", None)
    return cfg


def interior(block):
    return block.part((0, 0, 0), False)[1:]


def volume(cfg, blocks):
    ng, nx1 = cfg["geometry"]["cells"]["nghost"], cfg["geometry"]["cells"]["nx1"]
    total = 0.0
    ri = ro = None
    for block in blocks:
        coord = block.module("coord")
        k, j, _ = interior(block)
        x1f = coord.buffer("x1f").double().cpu()
        ri, ro = x1f[ng].item(), x1f[ng + nx1].item()
        total += coord.cell_volume()[k, j, slice(ng, ng + nx1)].double().sum().item()
    # (ro - ri) is exact (Sterbenz); the factored form avoids the cancellation of ro^3 - ri^3
    exact = 4.0 * math.pi / 3.0 * (ro - ri) * (ro * ro + ro * ri + ri * ri)
    return abs(total / exact - 1.0)


def run(mesh, blocks, mesh_vars):
    mesh_vars, _ = mesh.initialize(mesh_vars)
    intg = blocks[0].module("intg")
    for cycle in range(1, NLIM + 1):
        mesh.set_cycle(cycle)
        dt = mesh.max_time_step(mesh_vars)
        for stage in range(len(intg.stages)):
            mesh.forward(mesh_vars, dt, stage)
        if mesh.check_redo(mesh_vars) != 0:
            raise RuntimeError("step rejected at cycle %d" % cycle)
    return mesh_vars


def rest(cfg, mesh, blocks, stretched):
    from snapy import kIDN, kIPR
    import snapy

    ng, nx1 = cfg["geometry"]["cells"]["nghost"], cfg["geometry"]["cells"]["nx1"]
    rho0 = P0 / (GRAV * H0)
    mesh_vars = []
    for block in blocks:
        coord = block.module("coord")
        # the column is balanced on the TRUE geometry: widths are plain fp64 differences of
        # the block's faces, not the coordinate's dx1f buffer. A metric that fills dx1f with
        # anything else (gnomonic_equiangle.cpp:31-38 at 515201ad: the scalar global width)
        # then leaves an imbalance the run shows; a correct one makes the two identical.
        x1f = coord.buffer("x1f").double().cpu()
        dr = (x1f[ng + 1:ng + nx1 + 1] - x1f[ng:ng + nx1]).contiguous()
        r = 0.5 * (x1f[ng + 1:ng + nx1 + 1] + x1f[ng:ng + nx1])
        p = P0 * torch.exp(-(r - r[0]) / H0)
        col = torch.zeros(kIPR + 1, 1, 1, nx1, dtype=torch.float64)
        col[kIDN, 0, 0] = p * rho0 / P0
        col[kIPR, 0, 0] = p
        wb, _, _ = snapy.balance_column(col, dr, GRAV, rtol=1e-13, stretched=stretched)
        w = dict(block.named_buffers())["hydro.D"].clone().zero_()
        for c in (kIDN, kIPR):
            w[c][..., ng:ng + nx1] = wb[c, 0, 0].to(w)
            w[c][..., :ng] = w[c][..., ng:ng + 1]
            w[c][..., ng + nx1:] = w[c][..., ng + nx1 - 1:ng + nx1]
        mesh_vars.append({"hydro_w": w})
    mesh_vars = run(mesh, blocks, mesh_vars)
    cs = math.sqrt(GAMMA * P0 / rho0)
    vmax = 0.0
    for ib, block in enumerate(blocks):
        sl = interior(block)
        u = mesh_vars[ib]["hydro_u"]
        v = u[1:4][(slice(None),) + tuple(sl)] / u[kIDN][sl]
        vmax = max(vmax, v.abs().max().item())
    return vmax / cs


def freestream(cfg, mesh, blocks):
    from snapy import kIDN, kIPR

    rho0, p0 = 1.0, 1.0e5
    mesh_vars = []
    for block in blocks:
        w = dict(block.named_buffers())["hydro.D"].clone().zero_()
        w[kIDN] = rho0
        w[kIPR] = p0
        mesh_vars.append({"hydro_w": w})
    mesh_vars = run(mesh, blocks, mesh_vars)
    cs = math.sqrt(GAMMA * p0 / rho0)
    ng, nx1 = cfg["geometry"]["cells"]["nghost"], cfg["geometry"]["cells"]["nx1"]
    dev_in, dev_ghost = 0.0, 0.0
    for ib, block in enumerate(blocks):
        u = mesh_vars[ib]["hydro_u"]
        w = mesh_vars[ib]["hydro_w"]
        sl = interior(block)
        v = u[1:4][(slice(None),) + tuple(sl)] / u[kIDN][sl]
        dev_in = max(dev_in, v.abs().max().item() / cs,
                     (u[kIDN][sl] / rho0 - 1).abs().max().item())
        # panel-edge ghosts: the x2/x3 ghost zones (filled by the cubed-sphere exchange and
        # interp_ghost), over the interior x1 range
        i = slice(ng, ng + nx1)
        nk, nj = w.shape[1], w.shape[2]
        for kk, jj in ((slice(0, ng), slice(None)), (slice(nk - ng, nk), slice(None)),
                       (slice(None), slice(0, ng)), (slice(None), slice(nj - ng, nj))):
            g = w[:, kk, jj, i]
            dev_ghost = max(dev_ghost, (g[kIDN] / rho0 - 1).abs().max().item(),
                            (g[kIPR] / p0 - 1).abs().max().item(),
                            g[1:4].abs().max().item() / cs)
    return dev_in, dev_ghost


def child(arm, grid, implicit, device):
    """one configuration in this (fresh) process; prints one JSON line"""
    import json
    stretched = not grid.startswith("uniform")
    res = {}
    try:
        cfg = config(grid, implicit=implicit, gravity=(arm != "freestream"))
        mesh, blocks = build(cfg, device)
        if arm == "volume":
            res["value"] = volume(cfg, blocks)
        elif arm == "rest":
            res["value"] = rest(cfg, mesh, blocks, stretched)
        else:
            res["value"], res["ghosts"] = freestream(cfg, mesh, blocks)
    except Exception as e:  # a refusal or a crash is a failure of that arm, not a skip
        res["error"] = "%s: %s" % (type(e).__name__, str(e).splitlines()[0])
    print("G6S2JSON " + json.dumps(res), flush=True)
    return 0


def measure(arm, grid, device):
    """returns [(label, value or None, message)]. Every configuration runs in its own child
    process: a second cubed-sphere Mesh built in a process whose first Mesh is still alive
    can block in its first collective (observed at 515201ad on CPU)."""
    import json
    import subprocess
    out = []
    for implicit in ([False, True] if arm == "rest" else [False]):
        label = "%s %s%s" % (arm, grid, " implicit-9" if implicit else (" explicit" if arm == "rest" else ""))
        cmd = [sys.executable, str(Path(__file__).resolve()), "--child", arm, grid,
               "1" if implicit else "0", "--device", device]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        lines = [l for l in p.stdout.splitlines() if l.startswith("G6S2JSON ")]
        if p.returncode != 0 or not lines:
            out.append((label, None, "child exit %d: %s" % (p.returncode, (p.stderr or p.stdout)[-300:])))
            continue
        res = json.loads(lines[-1][len("G6S2JSON "):])
        if "error" in res:
            out.append((label, None, res["error"]))
        elif arm == "freestream":
            out.append((label + " cells", res["value"], ""))
            out.append((label + " panel-edge ghosts", res["ghosts"], ""))
        else:
            out.append((label, res["value"], ""))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("volume", "rest", "freestream"))
    ap.add_argument("--child", nargs=3, metavar=("ARM", "GRID", "IMPLICIT"), help=argparse.SUPPRESS)
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    ap.add_argument("--measure-only", action="store_true",
                    help="print floors and values, never fail (used once to fix the tolerances)")
    args = ap.parse_args(argv)
    if args.device == "cuda" and (os.environ.get("SNAPY_BUILD_CUDA", "1") == "0"
                                  or not torch.cuda.is_available()):
        print("SKIP: cuda requested but not available")
        return 125
    if args.child:
        return child(args.child[0], args.child[1], args.child[2] == "1", args.device)
    if not args.arm:
        ap.error("--arm is required")
    tol = {"volume": TOL_VOLUME, "rest": TOL_REST, "freestream": TOL_FREESTREAM}[args.arm]

    failures = []
    for uni, lst in (("uniform30", "n5"), ("uniform59", "n10")):
        for grid, role in ((uni, "uniform control"), (lst, "stretched")):
            for label, val, msg in measure(args.arm, grid, args.device):
                if val is None:
                    print("%-17s %-40s FAILED TO RUN: %s" % (role, label, msg))
                    failures.append("%s: %s" % (label, msg))
                    continue
                ok = tol is not None and val <= tol
                print("%-17s %-40s %.3e  (tol %s)  %s" % (role, label, val,
                      "%.0e" % tol if tol is not None else "unset",
                      "ok" if ok else ("FAIL" if tol is not None else "-")))
                if tol is not None and not ok:
                    failures.append("%s = %.3e > %.0e" % (label, val, tol))
    if args.measure_only:
        return 0
    if tol is None:
        print("FAIL: tolerance not set")
        return 1
    for msg in failures:
        print("FAIL:", msg)
    if failures:
        return 1
    print("### stage-2 cubed-sphere stretched-x1 %s arm passed. ###" % args.arm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
