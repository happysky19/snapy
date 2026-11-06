#!/usr/bin/env python3
"""C24 full-sphere checks for the n5 stretched radial grid (#280 stage 2)."""
import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import torch
import yaml

HERE = Path(__file__).resolve().parent
FACES = HERE / "test_stage2_faces_n5.csv"
FACES_SHA256 = "70e36e8503fb9651912faaf159bdfc51c22f985e594e8d85e1d2f02f141f8c7e"
NSTEP = 100
P0, H0, GRAV, GAMMA = 1.0e6, 6.0e4, 22.0, 1.4


def setup(arm, implicit, device):
    from snapy import Mesh, MeshOptions

    raw = FACES.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FACES_SHA256
    faces = [float(row["x1f_m"]) for row in csv.DictReader(raw.decode().splitlines())]
    with (HERE / "test_stage2_cubed_stretched.yaml").open() as f:
        cfg = yaml.safe_load(f)
    cfg["geometry"]["x1f"] = faces
    cfg["geometry"]["cells"].update(nx1=len(faces) - 1, nx2=24, nx3=24)
    cfg["integration"]["implicit-scheme"] = 9 if implicit else 0
    if arm == "tracer":
        cfg.pop("forcing")
        cfg["scalar"] = {"nvar": 1, "names": ["uniform_q"],
                         "reconstruct": {"type": "weno5", "scale": True, "shock": False},
                         "riemann-solver": {"type": "upwind"}}
    if arm == "conduction":
        cfg["forcing"]["diffusion"] = {
            "nu_iso": 0.0, "kappa_iso": 100000.0, "dynamic": False,
            "temperature_inner": 0.0, "temperature_outer": 0.0,
            "implicit_radial": False}
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(cfg, f)
        filename = f.name
    try:
        options = MeshOptions.from_yaml(filename)
        options.blocks_per_process(6)
        options.set_local_horizontal_cells(24, 24)
        mesh = Mesh(options)
    finally:
        os.unlink(filename)
    blocks = list(mesh.blocks)
    for block in blocks:
        block.to(torch.device(device))
    assert len(blocks) == 6
    return cfg, mesh, blocks


def balanced_state(cfg, blocks):
    import snapy
    from snapy import kIDN, kIPR

    ng, nx1 = 3, cfg["geometry"]["cells"]["nx1"]
    rho0 = P0 / (GRAV * H0)
    result = []
    for block in blocks:
        faces = block.module("coord").buffer("x1f").double().cpu()
        dr = (faces[ng + 1:ng + nx1 + 1] - faces[ng:ng + nx1]).contiguous()
        centers = (faces[ng + 1:ng + nx1 + 1] + faces[ng:ng + nx1]) / 2
        p = P0 * torch.exp(-(centers - centers[0]) / H0)
        col = torch.zeros(kIPR + 1, 1, 1, nx1, dtype=torch.float64)
        col[kIDN, 0, 0] = p * rho0 / P0
        col[kIPR, 0, 0] = p
        wb, _, _ = snapy.balance_column(col, dr, GRAV, rtol=1e-13, stretched=True)
        w = dict(block.named_buffers())["hydro.D"].clone().zero_()
        for c in (kIDN, kIPR):
            w[c][..., ng:ng + nx1] = wb[c, 0, 0].to(w)
            w[c][..., :ng] = w[c][..., ng:ng + 1]
            w[c][..., ng + nx1:] = w[c][..., ng + nx1 - 1:ng + nx1]
        result.append({"hydro_w": w})
    return result


def tracer_state(blocks):
    import snapy
    from snapy import kIDN, kIPR, kIV1, kIV2, kIV3

    result = []
    for ib, block in enumerate(blocks):
        coord = block.module("coord")
        beta, alpha = torch.meshgrid(coord.buffer("x3v").cpu(),
                                     coord.buffer("x2v").cpu(), indexing="ij")
        face = int(block.get_layout().loc_of(ib)[2])
        _, lat = snapy.coord.cs_ab_to_lonlat(snapy.coord.get_cs_face_name(face), alpha, beta)
        vel = torch.zeros((3,) + tuple(alpha.shape), dtype=torch.float64)
        vel[2] = 30.0 * torch.cos(lat)
        snapy.coord.cs_sph_to_contra_(vel, alpha, beta, face)
        w = dict(block.named_buffers())["hydro.D"].clone().zero_()
        q = dict(block.named_buffers())["scalar.D"].clone().zero_()
        w[kIDN], w[kIPR], q[0] = 1.0, 1.0e5, 0.01
        for c, v in zip((kIV1, kIV2, kIV3), vel):
            w[c] = v.unsqueeze(-1).to(w)
        result.append({"hydro_w": w, "scalar_r": q})
    return result


def advance(mesh, blocks, state):
    state, _ = mesh.initialize(state)
    stages = len(blocks[0].module("intg").stages)
    for cycle in range(1, NSTEP + 1):
        mesh.set_cycle(cycle)
        dt = mesh.max_time_step(state)
        for stage in range(stages):
            mesh.forward(state, dt, stage)
        assert mesh.check_redo(state) == 0, f"rejected cycle {cycle}"
    return state


def check(arm, implicit, device):
    from snapy import kIDN

    cfg, mesh, blocks = setup(arm, implicit, device)
    ng, nx1 = 3, cfg["geometry"]["cells"]["nx1"]
    if arm == "widths":
        errors, widths = [], []
        for block in blocks:
            coord = block.module("coord")
            faces = coord.buffer("x1f")
            actual = coord.buffer("dx1f")[ng:ng + nx1]
            exact = faces[ng + 1:ng + nx1 + 1] - faces[ng:ng + nx1]
            errors.append((actual - exact).abs().max().item())
            widths.extend(actual.cpu().tolist())
        assert max(widths) / min(widths) > 4.0
        value, tol = max(errors), 1e-8  # metres; four ulps at the shell radius
    else:
        state = advance(mesh, blocks, tracer_state(blocks) if arm == "tracer"
                        else balanced_state(cfg, blocks))
        value = 0.0
        for block, mv in zip(blocks, state):
            sl = block.part((0, 0, 0), False)[1:]
            u = mv["hydro_u"]
            if arm == "tracer":
                ratio = mv["scalar_s"][0][sl] / u[kIDN][sl]
                value = max(value, (ratio - 0.01).abs().max().item())
            else:
                velocity = u[1:4][(slice(None),) + tuple(sl)] / u[kIDN][sl]
                value = max(value, velocity.abs().max().item()
                            / math.sqrt(GAMMA * GRAV * H0))
        tol = 2e-13 if arm == "tracer" else 2e-12
    print(json.dumps(dict(arm=arm, implicit=implicit, device=device, value=value,
                          tolerance=tol, steps=0 if arm == "widths" else NSTEP)), flush=True)
    assert math.isfinite(value) and value <= tol, f"{arm}: {value} > {tol}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arm", choices=("widths", "rest", "tracer", "conduction"), required=True)
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    p.add_argument("--implicit", action="store_true")
    p.add_argument("--child", action="store_true")
    args = p.parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        return 125
    if args.child:
        check(args.arm, args.implicit, args.device)
        return 0
    modes = (False, True) if args.arm == "rest" else (False,)
    for implicit in modes:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--arm", args.arm,
               "--device", args.device, "--child"]
        if implicit:
            cmd.append("--implicit")
        subprocess.run(cmd, check=True, timeout=1800)
    return 0


if __name__ == "__main__":
    sys.exit(main())
