"""Mode-restricted linearisation of the compiled snapy semi-discrete operator.

The scheme is linear and x-translation invariant about the x-uniform base, so a single
x-Fourier mode decouples.  For a real perturbation dw(x,z) = Re[ what(z) e^{i k x} ] the
response is Re[ (M what)(z) e^{i k x} ]; M is built column by column with central
differences in the cosine basis.
"""
import numpy as np
import torch

import t1lsnap as T

NG = T.NG
GAMMA = T.GAMMA
NV = 4                       # rho, v1, v2, p   (v3 stays zero)
ROWS = [0, 1, 2, 4]          # kIDN, IV1, IV2, kIPR in the 5-row state


def grid(blk):
    coord = blk.module("coord")
    x2v = coord.buffer("x2v").numpy()[NG:-NG]
    x1v = coord.buffer("x1v").numpy()[NG:-NG]
    return x1v, x2v


def jac_diag(rho0):
    """d(cons)/d(prim) at zero velocity, per cell: diag(1, rho, rho, 1/(gamma-1))."""
    return np.stack([np.ones_like(rho0), rho0, rho0, np.ones_like(rho0) / (GAMMA - 1.)])


def apply_real(blk, wbase, dw_real, dt=1.0):
    """RHS(conserved) of the base plus a real primitive perturbation field (nz, nx->broadcast)."""
    w = wbase.clone()
    w[ROWS, 0, NG:-NG, NG:-NG] += torch.as_tensor(dw_real)
    L, _ = T.rhs(blk, w, dt)
    return L[ROWS, 0, NG:-NG, NG:-NG].numpy()


def mode_operator(blk, wbase, kx, eps=1e-6, cols=None, verbose=False, dt=1.0):
    """Complex (4 nz, 4 nz) operator M in primitive variables for wavenumber kx."""
    x1v, x2v = grid(blk)
    nz, nx = x1v.size, x2v.size
    ck = np.cos(kx * x2v)[:, None]            # (nx, 1)
    emk = np.exp(-1j * kx * x2v)[:, None]
    rho0 = T.interior(wbase)[0, 0, 0].numpy()
    jd = jac_diag(rho0)                        # (4, nz)
    L0 = apply_real(blk, wbase, np.zeros((NV, nx, nz)), dt)
    M = np.zeros((NV * nz, NV * nz), complex)
    idx = cols if cols is not None else range(NV * nz)
    for col in idx:
        v, i = divmod(col, nz)
        pert = np.zeros((NV, nx, nz))
        pert[v, :, i] = eps * ck[:, 0]
        Lp = apply_real(blk, wbase, pert, dt)
        Lm = apply_real(blk, wbase, -pert, dt)
        resp = (Lp - Lm) / (2. * eps)          # (4, nx, nz) conserved tendency
        hat = (2.0 / nx) * np.einsum("vxz,xo->vz", resp, emk)   # (4, nz) complex
        hat = hat / jd                          # back to primitive tendency
        M[:, col] = hat.reshape(-1)
        if verbose and col % 50 == 0:
            print("   col", col, flush=True)
    return M, L0


def leading(M, k_ret=6):
    val, vec = np.linalg.eig(M)
    ok = np.isfinite(val) & (np.abs(val) < 1e8)
    order = np.argsort(-val[ok].real)
    j = np.flatnonzero(ok)[order]
    return val[j[:k_ret]], vec[:, j[0]]
