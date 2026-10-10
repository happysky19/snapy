"""From-source numpy reimplementation of the T1L discrete RHS (2-D, nonlinear).

Transcribed from snapy @ 37dce4efdd8b1bdf9f08a91edf8fd3da38384672:

  reference scan / cell pressure / smoothed rho-p ratio   src/hydro/hydro_ref_x1_impl.h:22-168
  SNAP_WB_REF4 cell + face density                        src/hydro/wb_ref4.cpp:120-286
  reference subtraction, even-parity ghosts, restore      src/hydro/hydro_forward.cpp:268-325
  Center5 / WENO5 stencils                                src/recon/cp5.cpp:13-17, src/recon/weno5.cpp:11-23
  row -> interpolator (IDN weno5, IVX..IPR cp5)           src/recon/reconstruct.cpp:75-76,133-143
  LMARS                                                   src/riemann/lmars_impl.h:16-78
  divergence                                              src/coord/coordinate.cpp:509-553
  cell gravity source and work (non-hydrostatic = 1)      src/forcing/const_gravity.cpp:46-52
  face gravity work, cp5/weno5 curvature flux             src/hydro/hydro_forward.cpp:721-800
  flux covariance (Cartesian, no tracers)                 src/hydro/hydro_forward.cpp:113-158
  dynamic viscosity and conduction                        src/forcing/diffusion.cpp:70-108,486-560

State layout: w[v, x, z] with v = (rho, v1, v2, p), z the full array (nc1 = nz + 6), x periodic.
"""
import numpy as np

GAMMA = 1.4
GM1 = GAMMA - 1.0
NG = 3
IDN, IV1, IV2, IPR = 0, 1, 2, 3

C5M = np.array([-1. / 20., 9. / 20., 47. / 60., -13. / 60., 1. / 30.])
C5P = C5M[::-1]
W6 = np.array([11. / 1440., -31. / 480., 401. / 720., 401. / 720., -31. / 480., 11. / 1440.])
W6E = np.array([[95. / 288., 1427. / 1440., -133. / 240., 241. / 720., -173. / 1440., 3. / 160.],
                [-3. / 160., 637. / 1440., 511. / 720., -43. / 240., 77. / 1440., -11. / 1440.]])
BIN5 = np.array([1., 4., 6., 4., 1.]) / 16.
F5 = np.array([-1., 4., 10., 4., -1.]) / 16.
EXT = np.array([[4., -6., 4., -1.], [10., -20., 15., -4.]])
A4 = np.array([-1., 7., 7., -1.]) / 12.              # wb_ref4.cpp:199
# 7-point upwind-biased cell-average -> face reconstruction, one order above C5M;
# used only as an ablation showing the reconstruction is not the limiting term
C7M = np.array([1. / 105., -19. / 210., 107. / 210., 319. / 420., -101. / 420., 5. / 84., -1. / 140.])


def _lagrange_deriv(X, j, x):
    """wb_ref4.cpp:28-41."""
    out = 0.
    n = len(X)
    for l in range(n):
        if l == j:
            continue
        prod = 1. / (X[j] - X[l])
        for m in range(n):
            if m in (j, l):
                continue
            prod *= (x - X[m]) / (X[j] - X[m])
        out += prod
    return out


def _stencil(q, c, shift):
    """sum_j c[j] q[..., f - shift + j] for every face index f, zero where it does not fit."""
    n = q.shape[-1]
    out = np.zeros_like(q)
    for j, cj in enumerate(c):
        lo = shift - j
        if lo >= 0:
            out[..., lo:] += cj * q[..., :n - lo] if lo else cj * q
        else:
            out[..., :n + lo] += cj * q[..., -lo:]
    return out


def recon_c5(q):
    """(right state at face f, left state at face f) from cell values."""
    return _stencil(q, C5M, 2), _stencil(q, C5P, 3)


class T1L:
    """Discrete RHS for the T1L deck.  `opt` toggles per-term ablations."""

    def __init__(self, nz, nx, dz, dx, kx, mu, kappa, T_in, T_out, beta,
                 g=1.0, wb4=True, cov=True, gw="face", curv=True, recon="c5"):
        self.nz, self.nx, self.dz, self.dx = nz, nx, dz, dx
        self.kx, self.mu, self.kappa, self.g = kx, mu, kappa, g
        self.T_in, self.T_out, self.beta = T_in, T_out, beta
        self.wb4, self.cov, self.gw, self.curv, self.recon = wb4, cov, gw, curv, recon
        self.nc1 = nz + 2 * NG
        self.il, self.iu = NG, NG + nz - 1
        self.z_f = (np.arange(self.nc1 + 1) - NG) * dz          # face coordinate x1f
        self.z_c = (np.arange(self.nc1) - NG + 0.5) * dz        # cell centre x1v
        self.abl = {}                                            # ablation overrides

    # ------------------------------------------------------------------ ghosts
    def fill_ghosts(self, w):
        il, iu = self.il, self.iu
        for lo, hi, Tw in ((0, il, self.T_in), (iu + 1, self.nc1, self.T_out)):
            src = slice(il, il + NG) if lo == 0 else slice(iu + 1 - NG, iu + 1)
            g = w[:, :, src][:, :, ::-1]
            w[:, :, lo:hi] = g
            w[IV1, :, lo:hi] *= -1.
            rho = w[IDN, :, lo:hi]
            w[IPR, :, lo:hi] = rho * (2. * Tw - w[IPR, :, lo:hi] / rho)
        return w

    # --------------------------------------------------------------- reference
    def reference(self, w):
        nc1, il, iu, dz, g = self.nc1, self.il, self.iu, self.dz, self.g
        rho, p = w[IDN], w[IPR]
        a_exp = g * 0.5 * dz * rho[:, iu] / p[:, iu]
        anchor = p[:, iu] * np.exp(-a_exp)
        lo = np.zeros_like(rho)
        hi = np.zeros_like(rho)
        face = anchor
        for i in range(iu, -1, -1):
            hi[:, i] = face
            lo[:, i] = face + g * rho[:, i] * dz
            face = lo[:, i]
        face = anchor
        for i in range(iu + 1, nc1):
            lo[:, i] = face
            hi[:, i] = face - g * rho[:, i] * dz
            face = hi[:, i]
        pface = np.concatenate([lo, hi[:, nc1 - 1:nc1]], axis=1)
        pref = 0.5 * (lo + hi)
        for i in range(nc1):
            wall_in = (il <= i < il + 2)
            wall_out = (iu - 2 < i <= iu)
            if wall_in:
                row, start, rev = W6E[i - il], il, False
            elif wall_out:
                st = iu + 1 - 5
                row, start, rev = W6E[4 - (i - st)], st, True
            elif 2 <= i < nc1 - 2:
                row, start, rev = W6, i - 2, False
            else:
                continue
            ww = row[::-1] if rev else row
            val = sum(ww[m] * pface[:, start + m] for m in range(6))
            lower, upper = np.minimum(lo[:, i], hi[:, i]), np.maximum(lo[:, i], hi[:, i])
            pref[:, i] = np.where((val >= lower) & (val <= upper), val, pref[:, i])
        rat = rho / p
        # kernel path (hydro_ref_x1_impl.h:159-167): wall-clamped binomial smoothing
        sm = np.zeros_like(rat)
        for i in range(nc1):
            acc = 0.
            for m in range(-2, 3):
                j = min(max(i + m, il), iu)
                acc = acc + BIN5[m + 2] * rat[:, j]
            sm[:, i] = acc
        dref = pref * sm
        rf = np.zeros_like(sm)
        rf[:, 0] = sm[:, 0]
        rf[:, 1:] = 0.5 * (sm[:, :-1] + sm[:, 1:])
        dsf = lo * rf
        if self.wb4:
            # wb_ref4_cells (wb_ref4.cpp:261-273): dref = pref * F(rho/p), guarded by the
            # range of rho/p over cells i-1, i, i+1 (clamped inside the owned cells)
            d_old = dref[:, il:iu + 1].copy()
            frat = np.zeros((rho.shape[0], self.nz))
            for n in range(self.nz):
                i = il + n
                acc = 0.
                for m in range(-2, 3):
                    j, wm = i + m, F5[m + 2]
                    if j < il:
                        acc = acc + wm * sum(EXT[il - j - 1][q] * rat[:, il + q] for q in range(4))
                    elif j > iu:
                        acc = acc + wm * sum(EXT[j - iu - 1][q] * rat[:, iu - q] for q in range(4))
                    else:
                        acc = acc + wm * rat[:, j]
                frat[:, n] = acc
            nb = np.stack([rat[:, [min(max(il + n - 1, il), iu) for n in range(self.nz)]],
                           rat[:, il:iu + 1],
                           rat[:, [min(max(il + n + 1, il), iu) for n in range(self.nz)]]], 0)
            mn, mx = nb.min(0), nb.max(0)
            okc = (frat >= mn - 1e-10 * np.abs(mn)) & (frat <= mx + 1e-10 * np.abs(mx))
            self.cell_guard = okc
            dref[:, il:iu + 1] = np.where(okc, pref[:, il:iu + 1] * frat, d_old)
            # wb_ref4_faces (wb_ref4.cpp:276-286) with the exact Lagrange weights
            face = np.zeros((rho.shape[0], self.nz + 1))
            for n, f in enumerate(range(il, iu + 2)):
                st, wt = self.face_stencil(f)
                face[:, n] = sum(wt[k] * dref[:, st + k] for k in range(4))
            dl, dr = dref[:, il - 1:iu + 1], dref[:, il:iu + 2]
            mn, mx = np.minimum(dl, dr), np.maximum(dl, dr)
            okf = (face >= mn - 1e-10 * np.abs(mn)) & (face <= mx + 1e-10 * np.abs(mx))
            self.face_guard = okf
            dsf[:, il:iu + 2] = np.where(okf, face, dsf[:, il:iu + 2])
        return lo, hi, pref, dref, dsf

    def face_stencil(self, f):
        """wb_ref4.cpp:200-219: P'(x_f) of the quartic through the primitive of dref."""
        il, iu, nc1 = self.il, self.iu, self.nc1
        xf = self.z_f
        s = f - 2
        s = max(s, il)                    # clamp_in
        s = min(s, iu - 3)                # clamp_out
        s = min(max(s, 0), nc1 - 4)
        h = xf[f + 1] - xf[f] if f < nc1 else xf[f] - xf[f - 1]
        X = [(xf[s + j] - xf[f]) / h for j in range(5)]
        wt = np.zeros(4)
        for k in range(4):
            dzk = (xf[s + k + 1] - xf[s + k]) / h
            for j in range(k + 1, 5):
                wt[k] += dzk * _lagrange_deriv(X, j, 0.)
        return s, wt

    # ------------------------------------------------------------------- fluxes
    def _recon_z(self, q, weno):
        # the nonlinear WENO5 weights are irrelevant here: the compiled solver with
        # dynamics/reconstruct type cp5 gives the same eigenvalue to 1e-4 relative
        if self.abl.get("recon7"):
            return _stencil(q, C7M, 3), _stencil(q, C7M[::-1], 4)
        return recon_c5(q)

    def flux_x1(self, w, lo, pref, dref, dsf):
        il, iu = self.il, self.iu
        dp = w[IPR] - pref
        dr = w[IDN] - dref
        for q in (dp, dr):                                  # even-parity ghosts
            q[:, :il] = q[:, il:il + NG][:, ::-1]
            q[:, iu + 1:] = q[:, iu + 1 - NG:iu + 1][:, ::-1]
        prR, prL = self._recon_z(dr, True)
        ppR, ppL = self._recon_z(dp, False)
        v1R, v1L = self._recon_z(w[IV1], False)
        v2R, v2L = self._recon_z(w[IV2], False)
        off = self.abl.get("dsf_off")
        if off is not None:          # shift the base face density (dRf has no linear effect)
            dsf = dsf.copy()
            dsf[:, il:iu + 2] += off[None, :]
        pL, pR = ppL + lo, ppR + lo
        dL, dR = prL + dsf, prR + dsf
        return self.lmars(dL, v1L, v2L, pL, dR, v1R, v2R, pR, normal=1,
                          zf=self.abl.get("Zf"), hf=self.abl.get("hf"), face=True)

    def lmars(self, dL, vnL, vtL, pL, dR, vnR, vtR, pR, normal, zf=None, hf=None, face=False):
        hL = pL / (GM1 * dL) + 0.5 * (vnL ** 2 + vtL ** 2) + pL / dL
        hR = pR / (GM1 * dR) + 0.5 * (vnR ** 2 + vtR ** 2) + pR / dR
        if hf is not None:
            il, iu = self.il, self.iu
            hL = hL.copy()
            hR = hR.copy()
            hL[:, il:iu + 2] = hf[None, :]
            hR[:, il:iu + 2] = hf[None, :]
        rb = 0.5 * (dL + dR)
        cb = np.sqrt(0.5 * GAMMA * (pL + pR) / rb)
        if zf is not None:
            il, iu = self.il, self.iu
            rb = rb.copy()
            cb = cb.copy()
            cb[:, il:iu + 2] = zf[None, :] / rb[:, il:iu + 2]
        pbar = 0.5 * (pL + pR) + 0.5 * rb * cb * (vnL - vnR)
        ubar = 0.5 * (vnL + vnR) + 0.5 / (rb * cb) * (pL - pR)
        up = ubar > 0.
        d = np.where(up, dL, dR)
        vn = np.where(up, vnL, vnR)
        vt = np.where(up, vtL, vtR)
        h = np.where(up, hL, hR)
        return dict(rho=ubar * d, mn=ubar * d * vn + pbar, mt=ubar * d * vt,
                    E=ubar * d * h, p=pbar, u=ubar)

    def flux_x2(self, w):
        R = {}
        L = {}
        for v in range(4):
            q = w[v]
            rr = sum(C5M[j] * np.roll(q, 2 - j, axis=0) for j in range(5))
            ll = sum(C5P[j] * np.roll(q, 3 - j, axis=0) for j in range(5))
            R[v], L[v] = rr, ll
        f = self.lmars(L[IDN], L[IV2], L[IV1], L[IPR],
                       R[IDN], R[IV2], R[IV1], R[IPR], normal=2)
        out = dict(rho=f["rho"], m2=f["mn"], m1=f["mt"], E=f["E"])
        if self.cov:
            wbar = {v: 0.5 * (L[v] + R[v]) for v in range(4)}
            enth = GAMMA * wbar[IPR] / GM1
            h = enth / wbar[IDN]
            un = wbar[IV2]
            s2 = self.dz ** 2 / 12.
            d1 = lambda q: (q[:, 2:] - q[:, :-2]) / (2. * self.dz)
            dE = np.zeros_like(f["E"])
            dh = d1(h)
            if self.abl.get("cov_dh") is not None:        # exact dh0/dz on the interior rows
                dh = dh.copy()
                il, iu = self.il, self.iu
                dh[:, il - 1:iu] = self.abl["cov_dh"][None, :]
            dE[:, 1:-1] = s2 * wbar[IDN][:, 1:-1] * dh * d1(un)
            out["E"] = out["E"] + dE
            out["cov"] = dE
        return out

    # ---------------------------------------------------------------- diffusion
    def diffusion(self, w):
        """Dynamic nu/kappa; centred stress, wall faces take the extrapolated coefficient
        (irrelevant for dynamic), conduction -kappa dT/dn.  diffusion.cpp:486-560."""
        dz, dx, il, iu = self.dz, self.dx, self.il, self.iu
        nx = self.nx
        du = np.zeros_like(w)
        T = w[IPR] / w[IDN]
        # divergence of velocity at cells (both directions)
        dv = np.zeros_like(T)
        dv[:, 1:-1] = (w[IV1][:, 2:] - w[IV1][:, :-2]) / (2. * dz)
        dv += (np.roll(w[IV2], -1, axis=0) - np.roll(w[IV2], 1, axis=0)) / (2. * dx)
        # ---- x1 faces il .. iu+1
        sl = slice(il, iu + 2)
        fm1 = np.zeros((nx, self.nc1))
        fm2 = np.zeros((nx, self.nc1))
        fE = np.zeros((nx, self.nc1))
        dvf = 0.5 * (dv[:, sl] + dv[:, il - 1:iu + 1])
        s11 = 2. * (w[IV1][:, sl] - w[IV1][:, il - 1:iu + 1]) / dz - (2. / 3.) * dvf
        # shear: d(v1)/dx at the face, average of the two cells' centred x derivatives
        dxv1 = (np.roll(w[IV1], -1, axis=0) - np.roll(w[IV1], 1, axis=0)) / (2. * dx)
        s21 = (w[IV2][:, sl] - w[IV2][:, il - 1:iu + 1]) / dz + 0.5 * (dxv1[:, sl] + dxv1[:, il - 1:iu + 1])
        fm1[:, sl] = -self.mu * s11
        fm2[:, sl] = -self.mu * s21
        fE[:, sl] = (0.5 * (w[IV1][:, sl] + w[IV1][:, il - 1:iu + 1]) * fm1[:, sl]
                     + 0.5 * (w[IV2][:, sl] + w[IV2][:, il - 1:iu + 1]) * fm2[:, sl])
        fE[:, sl] -= self.kappa * (T[:, sl] - T[:, il - 1:iu + 1]) / dz
        # ---- x2 faces (periodic)
        back = lambda q: np.roll(q, 1, axis=0)
        dvf2 = 0.5 * (dv + back(dv))
        s22 = 2. * (w[IV2] - back(w[IV2])) / dx - (2. / 3.) * dvf2
        dzv2 = np.zeros_like(T)
        dzv2[:, 1:-1] = (w[IV2][:, 2:] - w[IV2][:, :-2]) / (2. * dz)
        s12 = (w[IV1] - back(w[IV1])) / dx + 0.5 * (dzv2 + back(dzv2))
        gm2 = -self.mu * s22
        gm1 = -self.mu * s12
        gE = (0.5 * (w[IV2] + back(w[IV2])) * gm2 + 0.5 * (w[IV1] + back(w[IV1])) * gm1
              - self.kappa * (T - back(T)) / dx)
        return (fm1, fm2, fE), (gm1, gm2, gE)

    # --------------------------------------------------------------------- RHS
    def rhs(self, w_in):
        il, iu, dz, dx, g = self.il, self.iu, self.dz, self.dx, self.g
        w = self.fill_ghosts(w_in.copy())
        lo, hi, pref, dref, dsf = self.reference(w)
        f1 = self.flux_x1(w, lo, pref, dref, dsf)
        f2 = self.flux_x2(w)
        sl, slp = slice(il, iu + 1), slice(il + 1, iu + 2)
        fwd = lambda q: np.roll(q, -1, axis=0)
        d = {}
        d["rho"] = (f1["rho"][:, slp] - f1["rho"][:, sl]) / dz + (fwd(f2["rho"]) - f2["rho"])[:, sl] / dx
        d["m1"] = (f1["mn"][:, slp] - f1["mn"][:, sl]) / dz + (fwd(f2["m1"]) - f2["m1"])[:, sl] / dx
        d["m2"] = (f1["mt"][:, slp] - f1["mt"][:, sl]) / dz + (fwd(f2["m2"]) - f2["m2"])[:, sl] / dx
        d["E"] = (f1["E"][:, slp] - f1["E"][:, sl]) / dz + (fwd(f2["E"]) - f2["E"])[:, sl] / dx
        out = np.zeros((4, self.nx, self.nz))
        out[IDN] = -d["rho"]
        out[IV1] = -d["m1"]
        out[IV2] = -d["m2"]
        out[IPR] = -d["E"]
        # gravity: cell source, non-hydrostatic = 1
        rho_c, v1_c = w[IDN][:, sl], w[IV1][:, sl]
        out[IV1] += -g * rho_c
        cell_work = -g * rho_c * v1_c
        if self.gw == "cell":
            out[IPR] += cell_work
        else:
            M = f1["rho"]
            fw = -0.5 * (M[:, sl] + M[:, slp])          # = phi_c divM - div(phi M), uniform grid
            if self.abl.get("gw_exactavg"):
                # exact cell average of -g rho v for a mode: use Simpson on the three
                # face/cell values of the mass flux (4th order cell average)
                M = f1["rho"]
                rhov = w[IDN] * w[IV1]
                fw = -(M[:, sl] + 4. * rhov[:, sl] + M[:, slp]) / 6.
            elif self.curv:
                rhov = w[IDN] * w[IV1]
                cf = (dz / 12.) * (rhov[:, 1:] - rhov[:, :-1])     # face f uses cells f-1, f
                cfl = np.zeros((self.nx, self.nc1 + 1))
                cfl[:, 1:self.nc1] = cf
                cfl[:, il] = 0.
                cfl[:, iu + 1] = 0.
                cur = (cfl[:, il + 1:iu + 2] - cfl[:, il:iu + 1]) / dz
                if self.abl.get("gw_wall1side"):
                    cur[:, 0] = (rhov[:, il + 2] - 2 * rhov[:, il + 1] + rhov[:, il]) / 12.
                    cur[:, -1] = (rhov[:, iu - 2] - 2 * rhov[:, iu - 1] + rhov[:, iu]) / 12.
                fw = fw + cur
            out[IPR] += fw
        # diffusion
        (fm1, fm2, fE), (gm1, gm2, gE) = self.diffusion(w)
        out[IV1] -= (fm1[:, slp] - fm1[:, sl]) / dz + (fwd(gm1) - gm1)[:, sl] / dx
        out[IV2] -= (fm2[:, slp] - fm2[:, sl]) / dz + (fwd(gm2) - gm2)[:, sl] / dx
        out[IPR] -= (fE[:, slp] - fE[:, sl]) / dz + (fwd(gE) - gE)[:, sl] / dx
        return out
