"""Mode operator of the numpy model (same convention as t1lop.mode_operator)."""
import numpy as np
import t1lmodel as Mod

GM1 = Mod.GM1


def mode_operator(mdl, rho_i, p_i, kx, x2v, eps=1e-6):
    nz, nx = mdl.nz, mdl.nx
    w0 = np.zeros((4, nx, nz + 6))
    w0[Mod.IDN, :, 3:-3] = rho_i[None, :]
    w0[Mod.IPR, :, 3:-3] = p_i[None, :]
    ck = np.cos(kx * x2v)
    emk = np.exp(-1j * kx * x2v)
    jd = np.stack([np.ones(nz), rho_i, rho_i, np.ones(nz) / GM1])
    M = np.zeros((4 * nz, 4 * nz), complex)
    for col in range(4 * nz):
        v, i = divmod(col, nz)
        d = np.zeros((4, nx, nz + 6))
        d[v, :, 3 + i] = eps * ck
        rp = mdl.rhs(w0 + d)
        rm = mdl.rhs(w0 - d)
        resp = (rp - rm) / (2. * eps)
        hat = (2.0 / nx) * np.einsum("vxz,x->vz", resp, emk)
        M[:, col] = (hat / jd).reshape(-1)
    return M
