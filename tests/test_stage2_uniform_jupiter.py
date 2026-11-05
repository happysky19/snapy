#!/usr/bin/env python3
"""#280 stage 2 (tests only): the UNIFORM jupiter_gcm and jupiter_gcm_dry decks stay bitwise
identical to a BASE build made on the same machine (no-regression arm; GREEN today).

Same approach as the G3 control (tests/g3_decks.cpp, tests/g3_compare.py): one driver is run
by two builds with the same arguments, every tensor is dumped as raw little-endian float64
with a manifest, and the two dumps are compared tensor by tensor with torch.equal
(g3_compare.main). There are no stored digests: digests are not portable across machines.

  base  the snapy install of the base commit (chengcli/snapy main 2d9fa419 for #280),
        built on THIS machine, given by SNAPY_STAGE2_BASE_PYTHONPATH (CMake cache variable of
        the same name, passed to the test's environment) or --base-pythonpath;
  head  the snapy this test is run with (SNAPY_TEST_PYTHONPATH / PYTHONPATH).
Each side runs in its own child process with only its own install on PYTHONPATH.

No base install given -> exit 125 (SKIPPED, with a message saying how to supply one); a base
that resolves to the head's own snapy -> FAIL (it would compare a build with itself).

Each deck is read from examples/ and reduced to fit a CPU test, and nothing else is changed:
  * geometry/cells nx2 = nx3 = 8 per panel side (deck: 48); nx1 stays 100, the x1 bounds,
    nghost, physics, reconstruction, Riemann solver and implicit-scheme 9 are the deck's;
  * six panels in one process (Mesh API, blocks_per_process 6) instead of six ranks;
  * NSTEPS = 5 cycles driven here (dt from mesh.max_time_step), no file outputs, no kinetics
    (examples/run_hydro.cpp's kinetics step is a driver step, not part of Mesh);
  * a deterministic initial state: an isothermal column projected by balance_column, fixed
    vapour mass fractions and a fixed sin/cos horizontal wind (no random numbers).
Dumped per deck and block: hydro_u after every cycle, and every variable after the last.

  python test_stage2_uniform_jupiter.py [--base-pythonpath PATH] [--device cpu|cuda]
"""
import argparse
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent / "examples"
DECKS = ("jupiter_gcm.yaml", "jupiter_gcm_dry.yaml")
NX_PANEL = 8
NSTEPS = 5
P0, H0 = 1.0e6, 6.0e4
BASE_ENV = "SNAPY_STAGE2_BASE_PYTHONPATH"


def reduced(deck):
    import yaml

    with open(EXAMPLES / deck) as f:
        cfg = yaml.safe_load(f)
    cfg["geometry"]["cells"]["nx2"] = NX_PANEL
    cfg["geometry"]["cells"]["nx3"] = NX_PANEL
    cfg["distribute"]["blocks_per_process"] = 6
    cfg.pop("outputs", None)
    return cfg


def dump_tensor(outdir, tag, man, blk, key, t):
    """one tensor in g3_decks' format: raw <f8 file + 'blk key numel file hash' line"""
    import zlib

    a = t.detach().to("cpu").double().contiguous().numpy()
    fn = "%s.%d.%s.bin" % (tag, blk, key)
    a.astype("<f8").tofile(Path(outdir) / fn)
    man.write("%d %s %d %s %d\n" % (blk, key, a.size, fn, zlib.crc32(a.tobytes())))


def run_deck(deck, outdir, device):
    """drive one reduced deck with the snapy on sys.path and dump it (child process)"""
    import torch
    import yaml
    import snapy
    from snapy import Mesh, MeshOptions, kIDN, kIPR, kICY, kIV2, kIV3

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
    tag = Path(deck).stem
    with open(Path(outdir) / (tag + ".manifest"), "w") as man:
        for cycle in range(1, NSTEPS + 1):
            mesh.set_cycle(cycle)
            dt = mesh.max_time_step(mesh_vars)
            for stage in range(len(intg.stages)):
                mesh.forward(mesh_vars, dt, stage)
            if mesh.check_redo(mesh_vars) != 0:
                raise RuntimeError("%s: step rejected at cycle %d" % (deck, cycle))
            for ib, mv in enumerate(mesh_vars):
                dump_tensor(outdir, tag, man, ib, "c%d.hydro_u" % cycle, mv["hydro_u"])
            dump_tensor(outdir, tag, man, 0, "c%d.dt" % cycle, torch.tensor([float(dt)]))
        for ib, mv in enumerate(mesh_vars):
            for key in sorted(mv):
                if torch.is_tensor(mv[key]):
                    dump_tensor(outdir, tag, man, ib, "final." + key, mv[key])
    return snapy.__file__


def child_main(outdir, device):
    import snapy
    print("SNAPY_FILE", snapy.__file__, getattr(snapy, "__version__", "?"), flush=True)
    for deck in DECKS:
        run_deck(deck, outdir, device)
    return 0


def run_side(pythonpath, outdir, device):
    env = dict(os.environ)
    env["PYTHONPATH"] = pythonpath
    cmd = [sys.executable, str(Path(__file__).resolve()), "--child", outdir, "--device", device]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=1800)
    info = [l for l in p.stdout.splitlines() if l.startswith("SNAPY_FILE ")]
    if p.returncode != 0 or not info:
        print(p.stdout[-2000:])
        print(p.stderr[-2000:])
        raise SystemExit("FAIL: child run with PYTHONPATH=%s exited %d" % (pythonpath, p.returncode))
    return info[-1].split()[1:]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    ap.add_argument("--base-pythonpath", default=os.environ.get(BASE_ENV, ""))
    ap.add_argument("--child", metavar="OUTDIR", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.child:
        return child_main(args.child, args.device)

    import torch
    if args.device == "cuda" and (os.environ.get("SNAPY_BUILD_CUDA", "1") == "0"
                                  or not torch.cuda.is_available()):
        print("SKIP: cuda requested but not available")
        return 125
    if not args.base_pythonpath:
        print("SKIP: no base build. Build and install the base commit (chengcli/snapy main "
              "2d9fa419 for #280) on this machine and pass its install path as "
              "-D%s=<path> at configure time, or set %s / --base-pythonpath." % (BASE_ENV, BASE_ENV))
        return 125
    head_path = os.environ.get("PYTHONPATH", "")
    sys.path.insert(0, str(HERE))
    import g3_compare

    with tempfile.TemporaryDirectory() as tmp:
        bdir, hdir = os.path.join(tmp, "base"), os.path.join(tmp, "head")
        os.makedirs(bdir)
        os.makedirs(hdir)
        bfile = run_side(args.base_pythonpath, bdir, args.device)
        hfile = run_side(head_path, hdir, args.device)
        print("base snapy: %s (%s)" % (bfile[0], bfile[1] if len(bfile) > 1 else "?"))
        print("head snapy: %s (%s)" % (hfile[0], hfile[1] if len(hfile) > 1 else "?"))
        if os.path.realpath(bfile[0]) == os.path.realpath(hfile[0]):
            print("FAIL: base and head resolve to the same snapy install; nothing is compared")
            return 1
        rc = g3_compare.main(bdir, hdir)
    if rc != 0:
        print("FAIL: uniform jupiter decks differ from the base build")
        return 1
    print("### uniform jupiter decks bitwise equal to the base build. ###")
    return 0


if __name__ == "__main__":
    sys.exit(main())
