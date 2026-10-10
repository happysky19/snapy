"""T1L: build the snapy MeshBlock of run_t1l.py at 37dce4e and expose its semi-discrete RHS.

Read-only use of the already-built CPU extension (pyb-cpu of wt-head @ 37dce4e).
Switches are env vars read once per process: set SNAP_WB_REF4 / SNAP_FLUX_COVARIANCE
before importing snapy.
"""
import json
import math
import os
import sys

import numpy as np
import torch
import snapy
from snapy import MeshBlock, MeshBlockOptions, kIDN, kIPR

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "drivers"))
import run_t1l as R  # noqa: E402

NG = 3
GAMMA = 1.4
IV1, IV2, IV3 = 1, 2, 3

INFO = json.load(open(os.path.join(HERE, "out", "evp_e1e-3.json")))
BETA = INFO["beta"]
SIGMA = INFO["sigma"]
KX = INFO["kx"]


def build(nz, gw="face", workdir=None):
    m = dict(eps=1e-3, beta=BETA, Ra=INFO["Ra"], sigma=SIGMA, mu=INFO["mu"], K=INFO["K"])
    out = workdir or os.path.join(HERE, "probe", f"n{nz}")
    os.makedirs(out, exist_ok=True)
    card = os.path.join(out, "card.yaml")
    with open(card, "w") as fo:
        fo.write(R.card_text(m, nz, gw, 1.0, 0.4))
    opts = MeshBlockOptions.from_yaml(card)
    opts.output_dir(out)
    opts.set_bfunc(0, 0, -1, R.make_wall(False, 1.0), "reflecting_inner")
    opts.set_bfunc(0, 0, 1, R.make_wall(True, 1.0 - BETA), "reflecting_outer")
    blk = MeshBlock(opts)
    blk.to(torch.device("cpu"))
    return blk


def base_state(blk, nz, rtol=1e-14):
    """Exactly run_t1l.py's IC + balance_column; returns the full-array primitive w."""
    coord = blk.module("coord")
    eos = blk.module("hydro.eos")
    x1v, x2v, x3v = coord.buffer("x1v"), coord.buffer("x2v"), coord.buffer("x3v")
    X3, X2, X1 = torch.meshgrid(x3v, x2v, x1v, indexing="ij")
    T0 = 1.0 - BETA * X1
    p0 = torch.pow(T0, 1.0 / BETA)
    w = torch.zeros((eos.nvar(),) + tuple(X1.shape), dtype=X1.dtype)
    w[kIDN] = p0 / T0
    w[kIPR] = p0
    I2, I1 = slice(NG, -NG), slice(NG, -NG)
    dx1f = coord.buffer("dx1f")[I1].contiguous()
    wb, res, sweeps = snapy.balance_column(
        w[:, :, I2, I1].contiguous(), dx1f, 1.0, True, rtol, 400)
    w[:, :, I2, I1] = wb
    return w, float(res), int(sweeps)


def rhs(blk, w, dt=1e-6):
    """Semi-discrete RHS du/dt of the conserved state built from primitive w.

    rk3 stage 0 is u <- u0 + dt*L(u0) (wght0=0, wght1=wght2=1), so L = (u1-u0)/dt.
    """
    bv, t = blk.initialize({"hydro_w": w.clone()})
    u0 = bv["hydro_u"].clone()
    blk.forward(bv, dt, 0)
    u1 = bv["hydro_u"]
    return ((u1 - u0) / dt).clone(), u0


def interior(a):
    return a[..., NG:-NG, NG:-NG]
