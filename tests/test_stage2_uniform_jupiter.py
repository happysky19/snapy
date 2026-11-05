#!/usr/bin/env python3
"""#280 stage 2 (tests only): the UNIFORM jupiter_gcm and jupiter_gcm_dry decks stay bitwise
identical to chengcli/snapy main 2d9fa419 (no-regression arm; expected GREEN today).

Each deck is read from examples/ and reduced to fit a CPU test, and nothing else is changed:
  * geometry/cells nx2 = nx3 = 8 per panel side (deck: 48); nx1 stays 100, the x1 bounds,
    nghost, physics, reconstruction, Riemann solver and implicit-scheme 9 are the deck's;
  * six panels in one process (Mesh API, blocks_per_process 6) instead of six ranks;
  * NSTEPS = 5 cycles driven here (dt from mesh.max_time_step), no file outputs, no
    kinetics (examples/run_hydro.cpp's kinetics step is a driver step, not part of Mesh);
  * a deterministic initial state: an isothermal column projected by balance_column, fixed
    vapour mass fractions and a fixed sin/cos horizontal wind (no random noise).
The digest is the sha256 of every block's hydro_u (float64, block order) followed by the dt
of every cycle. References are stored per platform in test_stage2_uniform_jupiter.json and
were written by running this script with --write-reference against a build of 2d9fa419.
No reference for this platform (or a CUDA run) -> exit 125 (skipped).

  python test_stage2_uniform_jupiter.py [--write-reference] [--device cpu|cuda]
"""
import argparse
import hashlib
import json
import math
import os
import platform
import struct
import sys
import tempfile
from pathlib import Path

import torch
import yaml

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent / "examples"
REF = HERE / "test_stage2_uniform_jupiter.json"
DECKS = ("jupiter_gcm.yaml", "jupiter_gcm_dry.yaml")
NX_PANEL = 8
NSTEPS = 5
P0, H0 = 1.0e6, 6.0e4


def platform_key(device):
    try:
        from importlib.metadata import version
        kv = version("kintera")
    except Exception:
        kv = "unknown"
    return "%s-%s-%s-torch%s-kintera%s" % (platform.system(), platform.machine(), device,
                                           torch.__version__.split("+")[0], kv)


def reduced(deck):
    with open(EXAMPLES / deck) as f:
        cfg = yaml.safe_load(f)
    cfg["geometry"]["cells"]["nx2"] = NX_PANEL
    cfg["geometry"]["cells"]["nx3"] = NX_PANEL
    cfg["distribute"]["blocks_per_process"] = 6
    cfg.pop("outputs", None)
    return cfg


def digest(deck, device):
    from snapy import Mesh, MeshOptions, kIDN, kIPR, kICY, kIV2, kIV3
    import snapy

    cfg = reduced(deck)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, dir=os.getcwd()) as f:
        yaml.safe_dump(cfg, f)
        tmp = f.name
    try:
        options = MeshOptions.from_yaml(tmp)
        options.blocks_per_process(6)
        options.set_local_horizontal_cells(NX_PANEL, NX_PANEL)
        mesh = Mesh(options)
    finally:
        os.unlink(tmp)
    blocks = list(mesh.blocks)
    g = -float(cfg["forcing"]["const-gravity"]["grav1"])
    ng, nx1 = cfg["geometry"]["cells"]["nghost"], cfg["geometry"]["cells"]["nx1"]
    rho0 = P0 / (g * H0)
    mesh_vars = []
    for block in blocks:
        block.to(torch.device(device))
        coord = block.module("coord")
        r = coord.buffer("x1v")[ng:ng + nx1].double().cpu()
        dr = coord.buffer("dx1f")[ng:ng + nx1].double().cpu()
        p = P0 * torch.exp(-(r - r[0]) / H0)
        col = torch.zeros(kIPR + 1, 1, 1, nx1, dtype=torch.float64)
        col[kIDN, 0, 0] = p * rho0 / P0
        col[kIPR, 0, 0] = p
        wb, _, _ = snapy.balance_column(col, dr.contiguous(), g)
        w = dict(block.named_buffers())["hydro.D"].clone().zero_()
        for c in (kIDN, kIPR):
            w[c][..., ng:ng + nx1] = wb[c, 0, 0].to(w)
            w[c][..., :ng] = w[c][..., ng:ng + 1]
            w[c][..., ng + nx1:] = w[c][..., ng + nx1 - 1:ng + nx1]
        ny = w.shape[0] - kICY
        for n, y in enumerate((1.0e-2, 2.0e-3, 1.0e-4)[:ny]):  # H2O, NH3, H2S mass fractions
            w[kICY + n] = y
        nk, nj = w.shape[1], w.shape[2]
        kk = torch.arange(nk, dtype=torch.float64).view(-1, 1, 1)
        jj = torch.arange(nj, dtype=torch.float64).view(1, -1, 1)
        w[kIV2] = (0.1 * torch.sin(2 * math.pi * jj / nj) * torch.cos(2 * math.pi * kk / nk)).to(w)
        w[kIV3] = (0.1 * torch.cos(2 * math.pi * jj / nj) * torch.sin(2 * math.pi * kk / nk)).to(w)
        mesh_vars.append({"hydro_w": w})
    mesh_vars, _ = mesh.initialize(mesh_vars)
    intg = blocks[0].module("intg")
    dts = []
    for cycle in range(1, NSTEPS + 1):
        mesh.set_cycle(cycle)
        dt = mesh.max_time_step(mesh_vars)
        for stage in range(len(intg.stages)):
            mesh.forward(mesh_vars, dt, stage)
        if mesh.check_redo(mesh_vars) != 0:
            raise RuntimeError("step rejected at cycle %d" % cycle)
        dts.append(float(dt))
    h = hashlib.sha256()
    for mv in mesh_vars:
        h.update(mv["hydro_u"].detach().to("cpu", torch.float64).contiguous().numpy().tobytes())
    for dt in dts:
        h.update(struct.pack("<d", dt))
    return h.hexdigest(), dts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    ap.add_argument("--write-reference", action="store_true",
                    help="write this platform's digests (run against a build of 2d9fa419)")
    args = ap.parse_args(argv)
    if args.device == "cuda" and (os.environ.get("SNAPY_BUILD_CUDA", "1") == "0"
                                  or not torch.cuda.is_available()):
        print("SKIP: cuda requested but not available")
        return 125
    key = platform_key(args.device)
    refs = json.loads(REF.read_text()) if REF.exists() else {}
    if not args.write_reference and key not in refs:
        print("SKIP: no 2d9fa419 reference digests for platform %s" % key)
        return 125

    got = {}
    for deck in DECKS:
        d, dts = digest(deck, args.device)
        got[deck] = d
        print("%-22s %s  dt = %s" % (deck, d, ", ".join("%.6e" % x for x in dts)))
    if args.write_reference:
        refs[key] = got
        REF.write_text(json.dumps(refs, indent=1, sort_keys=True) + "\n")
        print("wrote %s for %s" % (REF.name, key))
        return 0
    bad = [d for d in DECKS if got[d] != refs[key].get(d)]
    for d in bad:
        print("FAIL: %s digest %s != 2d9fa419 reference %s" % (d, got[d], refs[key].get(d)))
    if bad:
        return 1
    print("### uniform jupiter decks bitwise equal to 2d9fa419 (%s). ###" % key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
