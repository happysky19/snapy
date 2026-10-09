#!/usr/bin/env python3
"""
Standalone verification of the face-form gravitational-work booking in a 1D
plane-parallel finite-volume column with two solid walls.

No snapy / kintera dependency: numpy only for the numerics, sympy only for the
(optional) exact rational Taylor coefficients.

Conventions (see the companion markdown document):
  z increases upward, Phi(z) = g z, g > 0 constant.
  Column [z_L, z_R], N cells of uniform height h, cell i = 1..N occupies
  [z_{i-1/2}, z_{i+1/2}], centre z_i.  Faces j+1/2, j = 0..N.
  m(z) = rho w  is the mass flux density; m_{j+1/2} is the face mass flux used
  by the discrete continuity equation.  Solid walls: m_{1/2} = m_{N+1/2} = 0.
  Exact cell-averaged gravitational work source
        S_i = -(g/h) \int_{z_{i-1/2}}^{z_{i+1/2}} m(z) dz.
  We set m_{j+1/2} = m(z_{j+1/2}) exactly, so that only the booking error is
  measured (the Riemann-flux error is a separate, additive contribution).

Bookings compared:
  A   plain face form                 W_i = -(g/2)(m_{i+1/2} + m_{i-1/2})
  B0  A + curvature flux H, H zeroed at both wall faces
  B1  A + curvature flux H, 3rd-order one-sided dm at the wall faces
  W4  A + curvature flux H, ghost-face extrapolation at the wall faces
      (the part-2 scheme; exactly conservative with the modified potential)
  with H_{j+1/2} = (g h^2/12) * dm_{j+1/2}, dm ~ dm/dz at the face, and
        W_i = W_i^A + (H_{i+1/2} - H_{i-1/2})/h .
"""

import numpy as np

EPS = np.finfo(float).eps

# --------------------------------------------------------------------------
# 0.  exact rational Taylor coefficients of every stencil used below
# --------------------------------------------------------------------------


def taylor_coefficients():
    """Return the exact leading truncation coefficients, in rational form.

    Every stencil is applied to m(z) expanded about a reference point; the
    result is compared with the exact cell average of m over the target cell.
    Units: the returned number c multiplies h^k m^{(k)} in  (W - S)/(-g).
    """
    import sympy as sp

    h, s = sp.symbols('h s', positive=True)
    K = 9                                   # Taylor order
    a = sp.symbols('a0:%d' % K)             # a_k = m^{(k)}(ref)

    def m_at(ds):
        """m(ref + ds*h) as a truncated Taylor series."""
        return sum(a[k] * (ds * h) ** k / sp.factorial(k) for k in range(K))

    def cell_average(lo, hi):
        """(1/h) int_{ref+lo*h}^{ref+hi*h} m dz, exact for the series."""
        t = sp.symbols('t')
        return sp.integrate(m_at(t), (t, lo, hi)) / (hi - lo)

    out = {}

    # ---- interior cell, reference = cell centre -------------------------
    # plain face form A: faces at -1/2, +1/2
    errA = sp.expand(sp.Rational(1, 2) * (m_at(sp.Rational(1, 2))
                                          + m_at(sp.Rational(-1, 2)))
                     - cell_average(sp.Rational(-1, 2), sp.Rational(1, 2)))
    out['A_interior'] = sp.simplify(errA)

    # face form + H with the *exact* face derivative:
    #   W/(-g) = half-sum  -  (h^2/12) * (m'(+1/2) - m'(-1/2))/h
    dm_exact = (sp.diff(m_at(s), s).subs(s, sp.Rational(1, 2))
                - sp.diff(m_at(s), s).subs(s, sp.Rational(-1, 2))) / h ** 2
    errBex = sp.expand(sp.Rational(1, 2) * (m_at(sp.Rational(1, 2))
                                            + m_at(sp.Rational(-1, 2)))
                       - h ** 2 / 12 * dm_exact
                       - cell_average(sp.Rational(-1, 2), sp.Rational(1, 2)))
    out['B_interior_exactH'] = sp.simplify(errBex)

    # face form + H with the centred 2-point face derivative
    #   -> symmetric 4-point face stencil (-1/24, 13/24, 13/24, -1/24)
    w = [sp.Rational(-1, 24), sp.Rational(13, 24),
         sp.Rational(13, 24), sp.Rational(-1, 24)]
    nodes = [sp.Rational(-3, 2), sp.Rational(-1, 2),
             sp.Rational(1, 2), sp.Rational(3, 2)]
    errB = sp.expand(sum(wi * m_at(ni) for wi, ni in zip(w, nodes))
                     - cell_average(sp.Rational(-1, 2), sp.Rational(1, 2)))
    out['B_interior_discreteH'] = sp.simplify(errB)

    # ---- bottom wall cell, reference = the wall face z_{1/2} ------------
    # faces available: s = 0, 1, 2, 3 (m(0) = 0 physically, but we do not use
    # that in the expansion, so the statements hold for general smooth m)
    f = [m_at(sp.Integer(k)) for k in range(5)]
    cavg1 = cell_average(sp.Integer(0), sp.Integer(1))

    # A at the wall cell: faces 0 and 1 with weight 1/2
    out['A_wall'] = sp.simplify(sp.expand(
        sp.Rational(1, 2) * (f[0] + f[1]) - cavg1))

    # B0: H_{1/2} = 0, H_{3/2} = (g h^2/12) * (m(2)-m(0))/(2h)
    #   W/(-g) = (1/2)(f0+f1) - (h^2/12)*[ (f2-f0)/(2h) - 0 ]/h
    out['B0_wall'] = sp.simplify(sp.expand(
        sp.Rational(1, 2) * (f[0] + f[1])
        - sp.Rational(1, 12) * ((f[2] - f[0]) / 2) - cavg1))

    # B1: one-sided 3rd-order dm at the wall face
    dm_wall_b1 = (sp.Rational(-11, 6) * f[0] + 3 * f[1]
                  - sp.Rational(3, 2) * f[2] + sp.Rational(1, 3) * f[3]) / h
    out['B1_wall'] = sp.simplify(sp.expand(
        sp.Rational(1, 2) * (f[0] + f[1])
        - h ** 2 / 12 * ((f[2] - f[0]) / (2 * h) - dm_wall_b1) / h - cavg1))

    # W4: ghost-face extrapolation m(-1) = 4f0 - 6f1 + 4f2 - f3
    ghost = 4 * f[0] - 6 * f[1] + 4 * f[2] - f[3]
    dm_wall_w4 = (f[1] - ghost) / (2 * h)
    out['W4_wall'] = sp.simplify(sp.expand(
        sp.Rational(1, 2) * (f[0] + f[1])
        - h ** 2 / 12 * ((f[2] - f[0]) / (2 * h) - dm_wall_w4) / h - cavg1))

    # ... and the equivalent one-sided quadrature row (3/8, 19/24, -5/24, 1/24)
    wrow = [sp.Rational(3, 8), sp.Rational(19, 24),
            sp.Rational(-5, 24), sp.Rational(1, 24)]
    out['W4_wall_row'] = sp.simplify(sp.expand(
        sum(wi * f[k] for k, wi in enumerate(wrow)) - cavg1))

    return out, a, h


# --------------------------------------------------------------------------
# 1.  the bookings, as pure functions of the face mass fluxes
# --------------------------------------------------------------------------

def book_A(mf, g, h):
    """Plain face form, W_i = -(g/2)(m_{i+1/2} + m_{i-1/2})."""
    return -0.5 * g * (mf[1:] + mf[:-1])


def _H_interior(mf, g, h):
    """Curvature flux at every face; wall faces filled in by the caller."""
    nf = mf.size
    H = np.zeros(nf)
    # centred 2-point face derivative, available for faces j = 1..N-1
    H[1:-1] = (g * h * h / 12.0) * (mf[2:] - mf[:-2]) / (2.0 * h)
    return H


def book_B0(mf, g, h):
    """Curvature flux with H = 0 at both wall faces (naive closure)."""
    H = _H_interior(mf, g, h)
    return book_A(mf, g, h) + (H[1:] - H[:-1]) / h


def book_B1(mf, g, h):
    """Curvature flux with a 3rd-order one-sided dm at the wall faces."""
    H = _H_interior(mf, g, h)
    c = g * h * h / 12.0
    H[0] = c * (-11.0 / 6 * mf[0] + 3 * mf[1]
                - 1.5 * mf[2] + 1.0 / 3 * mf[3]) / h
    H[-1] = c * (11.0 / 6 * mf[-1] - 3 * mf[-2]
                 + 1.5 * mf[-3] - 1.0 / 3 * mf[-4]) / h
    return book_A(mf, g, h) + (H[1:] - H[:-1]) / h


def book_W4(mf, g, h):
    """Part-2 booking: curvature flux with ghost-face extrapolation at walls."""
    H = _H_interior(mf, g, h)
    c = g * h * h / 12.0
    ghost_lo = 4 * mf[0] - 6 * mf[1] + 4 * mf[2] - mf[3]
    ghost_hi = 4 * mf[-1] - 6 * mf[-2] + 4 * mf[-3] - mf[-4]
    H[0] = c * (mf[1] - ghost_lo) / (2.0 * h)
    H[-1] = c * (ghost_hi - mf[-2]) / (2.0 * h)
    return book_A(mf, g, h) + (H[1:] - H[:-1]) / h


def book_W4_rows(mf, g, h):
    """Same booking written directly as face weights (cross-check)."""
    n = mf.size - 1
    W = np.empty(n)
    W[1:-1] = -g * (13.0 / 24 * (mf[2:-1] + mf[1:-2])
                    - 1.0 / 24 * (mf[3:] + mf[:-3]))
    W[0] = -g * (3.0 / 8 * mf[0] + 19.0 / 24 * mf[1]
                 - 5.0 / 24 * mf[2] + 1.0 / 24 * mf[3])
    W[-1] = -g * (3.0 / 8 * mf[-1] + 19.0 / 24 * mf[-2]
                  - 5.0 / 24 * mf[-3] + 1.0 / 24 * mf[-4])
    return W


def phi_tilde(zc, g, h):
    """Modified discrete geopotential making book_W4 exactly conservative."""
    pt = g * zc.copy()
    pt[0] += -g * h / 6.0
    pt[1] += g * h / 8.0
    pt[2] += -g * h / 24.0
    pt[-1] += g * h / 6.0
    pt[-2] += -g * h / 8.0
    pt[-3] += g * h / 24.0
    return pt


# --------------------------------------------------------------------------
# 2.  manufactured mass-flux profile and exact cell averages
# --------------------------------------------------------------------------

ZL, ZR = 0.0, 1.0
GRAV = 2.5


def m_profile(z):
    """Smooth manufactured mass flux, vanishing at both walls.

    m(z) = z (1-z) exp(0.7 z) (1 + 0.4 sin(3 z + 0.5))
    Chosen so that m(z_L) = m(z_R) = 0 but m'' and m'''' do NOT vanish at the
    walls (a profile odd about the walls would hide the wall-cell error).
    """
    return z * (1.0 - z) * np.exp(0.7 * z) * (1.0 + 0.4 * np.sin(3.0 * z + 0.5))


def m_derivatives():
    """Analytic derivatives of m_profile via sympy, as fast callables."""
    import sympy as sp
    z = sp.symbols('z')
    expr = z * (1 - z) * sp.exp(sp.Rational(7, 10) * z) * \
        (1 + sp.Rational(2, 5) * sp.sin(3 * z + sp.Rational(1, 2)))
    return {k: sp.lambdify(z, sp.diff(expr, z, k), 'numpy')
            for k in (1, 2, 3, 4)}


_GL_N = 24
_GLX, _GLW = np.polynomial.legendre.leggauss(_GL_N)


def exact_cell_average(zf):
    """(1/h) int_cell m dz with 24-point Gauss-Legendre (machine accurate)."""
    lo, hi = zf[:-1], zf[1:]
    mid = 0.5 * (lo + hi)
    half = 0.5 * (hi - lo)
    acc = np.zeros(mid.size)
    for x, w in zip(_GLX, _GLW):
        acc += w * m_profile(mid + half * x)
    return 0.5 * acc            # (half * acc) / h, with h = 2*half


# --------------------------------------------------------------------------
# 3.  convergence study
# --------------------------------------------------------------------------

BOOKINGS = [('A  (plain face form)', book_A),
            ('B0 (H, wall H = 0)', book_B0),
            ('B1 (H, one-sided dm)', book_B1),
            ('W4 (part 2)', book_W4)]


def convergence(nzs=(16, 32, 64, 128, 256)):
    rows = {name: [] for name, _ in BOOKINGS}
    for nz in nzs:
        h = (ZR - ZL) / nz
        zf = ZL + h * np.arange(nz + 1)
        zc = 0.5 * (zf[:-1] + zf[1:])
        mf = m_profile(zf)
        mf[0] = 0.0                 # solid walls, exactly
        mf[-1] = 0.0
        S = -GRAV * exact_cell_average(zf)
        for name, fn in BOOKINGS:
            W = fn(mf, GRAV, h)
            err = W - S
            interior = np.abs(err[2:-2]).max()      # away from both walls
            rms = np.sqrt(np.mean(err[2:-2] ** 2))
            wall = max(abs(err[0]), abs(err[-1]))
            rows[name].append((nz, h, interior, wall, rms))
        # consistency of the two spellings of W4
        assert np.allclose(book_W4(mf, GRAV, h), book_W4_rows(mf, GRAV, h),
                           rtol=0, atol=1e-13 * GRAV), 'W4 spellings disagree'
    return rows


def orders(seq):
    return [np.log2(seq[k] / seq[k + 1]) for k in range(len(seq) - 1)]


# --------------------------------------------------------------------------
# 4.  one closed-column time step: exact conservation of sum(E) + P
# --------------------------------------------------------------------------

GAMMA = 1.4


def closed_column_step(nz=64, dt=2.0e-4, seed=7):
    """One forward-Euler step of a closed column with the part-2 booking.

    Returns (before, after, residual) for the modified potential P and for the
    naive potential P0 = h sum rho_i g z_i.
    """
    rng = np.random.default_rng(seed)
    h = (ZR - ZL) / nz
    zf = ZL + h * np.arange(nz + 1)
    zc = 0.5 * (zf[:-1] + zf[1:])

    # a stratified, perturbed state (not hydrostatic: the test must not rely
    # on any special balance)
    rho = 1.0 * np.exp(-zc / 0.35) * (1.0 + 0.05 * np.sin(9.0 * zc))
    w = 0.25 * np.sin(np.pi * zc) * (1.0 + 0.3 * rng.standard_normal(nz))
    pres = 0.8 * np.exp(-zc / 0.35) * (1.0 + 0.02 * np.cos(5.0 * zc))
    mom = rho * w
    E = pres / (GAMMA - 1.0) + 0.5 * rho * w * w

    # Rusanov fluxes on interior faces; walls are reflecting
    mf = np.zeros(nz + 1)
    fmom = np.zeros(nz + 1)
    fE = np.zeros(nz + 1)
    cs = np.sqrt(GAMMA * pres / rho)
    aL, aR = np.abs(w[:-1]) + cs[:-1], np.abs(w[1:]) + cs[1:]
    alpha = np.maximum(aL, aR)
    mf[1:-1] = 0.5 * (mom[:-1] + mom[1:]) - 0.5 * alpha * (rho[1:] - rho[:-1])
    fmom[1:-1] = (0.5 * (mom[:-1] * w[:-1] + pres[:-1]
                         + mom[1:] * w[1:] + pres[1:])
                  - 0.5 * alpha * (mom[1:] - mom[:-1]))
    fE[1:-1] = (0.5 * ((E[:-1] + pres[:-1]) * w[:-1]
                       + (E[1:] + pres[1:]) * w[1:])
                - 0.5 * alpha * (E[1:] - E[:-1]))
    fmom[0] = pres[0]            # wall pressure only
    fmom[-1] = pres[-1]
    # mf and fE vanish at both walls by construction

    W = book_W4(mf, GRAV, h)
    pt = phi_tilde(zc, GRAV, h)

    Etot0 = h * np.sum(E)
    P0mod = h * np.sum(rho * pt)
    P0nai = h * np.sum(rho * GRAV * zc)

    rho_n = rho - dt / h * (mf[1:] - mf[:-1])
    E_n = E - dt / h * (fE[1:] - fE[:-1]) + dt * W
    # (momentum is updated too, but it does not enter the sum E + P budget)
    mom_n = mom - dt / h * (fmom[1:] - fmom[:-1]) - dt * rho * GRAV

    Etot1 = h * np.sum(E_n)
    P1mod = h * np.sum(rho_n * pt)
    P1nai = h * np.sum(rho_n * GRAV * zc)

    # the naive potential P0 must fail by exactly dt * (H_{N+1/2} - H_{1/2})
    Hw = _H_interior(mf, GRAV, h)
    c = GRAV * h * h / 12.0
    Hw[0] = c * (mf[1] - (4 * mf[0] - 6 * mf[1] + 4 * mf[2] - mf[3])) / (2 * h)
    Hw[-1] = c * ((4 * mf[-1] - 6 * mf[-2] + 4 * mf[-3] - mf[-4])
                  - mf[-2]) / (2 * h)

    return dict(h=h, dt=dt,
                before_mod=Etot0 + P0mod, after_mod=Etot1 + P1mod,
                before_nai=Etot0 + P0nai, after_nai=Etot1 + P1nai,
                Etot0=Etot0, P0mod=P0mod, P0nai=P0nai,
                nai_predicted=dt * (Hw[-1] - Hw[0]),
                mom_n=mom_n)


def potential_accuracy(nzs=(16, 32, 64, 128, 256)):
    """Is the modified P a better approximation of int rho Phi dz than P0?"""
    def rho_fn(z):
        return np.exp(-z / 0.35) * (1.0 + 0.05 * np.sin(9.0 * z))

    out = []
    for nz in nzs:
        h = (ZR - ZL) / nz
        zf = ZL + h * np.arange(nz + 1)
        zc = 0.5 * (zf[:-1] + zf[1:])
        mid, half = zc, 0.5 * h
        rho_bar = np.zeros(nz)
        exact = 0.0
        for x, w in zip(_GLX, _GLW):
            zz = mid + half * x
            rho_bar += w * rho_fn(zz)
            exact += np.sum(w * rho_fn(zz) * GRAV * zz)
        rho_bar *= 0.5
        exact *= half
        P0 = h * np.sum(rho_bar * GRAV * zc)
        Pm = h * np.sum(rho_bar * phi_tilde(zc, GRAV, h))
        out.append((nz, abs(P0 - exact), abs(Pm - exact)))
    return out


# --------------------------------------------------------------------------
# 5.  report
# --------------------------------------------------------------------------

def main():
    print('=' * 78)
    print('EXACT TAYLOR COEFFICIENTS  (leading term of (W - S)/(-g))')
    print('=' * 78)
    try:
        import sympy as sp
        coeffs, a, h = taylor_coefficients()
        for key in ('A_interior', 'B_interior_exactH', 'B_interior_discreteH',
                    'A_wall', 'B0_wall', 'B1_wall', 'W4_wall',
                    'W4_wall_row'):
            e = sp.expand(coeffs[key])
            lead = None
            for k in range(0, 7):
                for j in range(0, 9):
                    c = e.coeff(a[j]).coeff(h, k)
                    if c != 0 and lead is None:
                        lead = (j, k, c)
                if lead is not None:
                    break
            j, k, c = lead
            print('  %-22s leading term  %s * h^%d * m^(%d)'
                  % (key, sp.nsimplify(c), k, j))
        print()
    except Exception as exc:                            # pragma: no cover
        print('  sympy step skipped: %r\n' % (exc,))

    print('=' * 78)
    print('PART 3a  CONVERGENCE  (manufactured m, g = %.3f, domain [%g,%g])'
          % (GRAV, ZL, ZR))
    print('=' * 78)
    nzs = (16, 32, 64, 128, 256)
    rows = convergence(nzs)
    der = m_derivatives()

    for name, _ in BOOKINGS:
        data = rows[name]
        print('\n  %s' % name)
        print('    %5s %12s %6s %12s %6s %12s %6s'
              % ('nz', 'max int', 'order', 'rms int', 'order',
                 'max wall', 'order'))
        oi = orders([d[2] for d in data])
        orms = orders([d[4] for d in data])
        ow = orders([d[3] for d in data])
        for k, d in enumerate(data):
            si = '%6.2f' % oi[k - 1] if k > 0 else '%6s' % '-'
            sr = '%6.2f' % orms[k - 1] if k > 0 else '%6s' % '-'
            sw = '%6.2f' % ow[k - 1] if k > 0 else '%6s' % '-'
            print('    %5d %12.4e %s %12.4e %s %12.4e %s'
                  % (d[0], d[2], si, d[4], sr, d[3], sw))

    # measured vs predicted leading coefficients at the finest grid
    print('\n  Measured / predicted leading error, nz = %d:' % nzs[-1])
    nz = nzs[-1]
    h = (ZR - ZL) / nz
    zf = ZL + h * np.arange(nz + 1)
    zc = 0.5 * (zf[:-1] + zf[1:])
    mf = m_profile(zf)
    mf[0] = mf[-1] = 0.0
    S = -GRAV * exact_cell_average(zf)
    ic = nz // 2                                     # a representative cell

    predA = -GRAV * h ** 2 / 12 * der[2](zc[ic])
    gotA = (book_A(mf, GRAV, h) - S)[ic]
    print('    A  interior : got %12.5e  pred %12.5e  ratio %.4f'
          % (gotA, predA, gotA / predA))

    predB = 11 * GRAV * h ** 4 / 720 * der[4](zc[ic])
    gotB = (book_W4(mf, GRAV, h) - S)[ic]
    print('    W4 interior : got %12.5e  pred %12.5e  ratio %.4f'
          % (gotB, predB, gotB / predB))

    predA1 = -GRAV * h ** 2 / 12 * der[2](zc[0])
    gotA1 = (book_A(mf, GRAV, h) - S)[0]
    print('    A  wall cell: got %12.5e  pred %12.5e  ratio %.4f'
          % (gotA1, predA1, gotA1 / predA1))

    predB01 = GRAV * h / 12 * der[1](zf[0])
    gotB01 = (book_B0(mf, GRAV, h) - S)[0]
    print('    B0 wall cell: got %12.5e  pred %12.5e  ratio %.4f'
          % (gotB01, predB01, gotB01 / predB01))

    predB11 = GRAV * h ** 3 / 72 * der[3](zf[0])
    gotB11 = (book_B1(mf, GRAV, h) - S)[0]
    print('    B1 wall cell: got %12.5e  pred %12.5e  ratio %.4f'
          % (gotB11, predB11, gotB11 / predB11))

    predW41 = -19 * GRAV * h ** 4 / 720 * der[4](zf[0])
    gotW41 = (book_W4(mf, GRAV, h) - S)[0]
    print('    W4 wall cell: got %12.5e  pred %12.5e  ratio %.4f'
          % (gotW41, predW41, gotW41 / predW41))

    print()
    print('=' * 78)
    print('PART 3b  EXACT CONSERVATION, one closed-column step')
    print('=' * 78)
    for nz in (32, 64, 128):
        r = closed_column_step(nz=nz)
        d_mod = r['after_mod'] - r['before_mod']
        d_nai = r['after_nai'] - r['before_nai']
        scale = abs(r['Etot0']) + abs(r['P0mod'])
        print('\n  nz = %d, dt = %.3e, h = %.5f' % (nz, r['dt'], r['h']))
        print('    modified P : before %+.17e' % r['before_mod'])
        print('                 after  %+.17e' % r['after_mod'])
        print('                 change %+.6e   = %.2f * eps * scale'
              % (d_mod, abs(d_mod) / (EPS * scale)))
        print('    naive    P : change %+.6e   = %.2e * eps * scale'
              % (d_nai, abs(d_nai) / (EPS * scale)))
        print('                 predicted dt*(H_top - H_bot) = %+.6e'
              % r['nai_predicted'])
        print('    scale = |sum h E| + |P| = %.6e, eps = %.3e' % (scale, EPS))

    print()
    print('=' * 78)
    print('EXTRA  accuracy of the discrete potential energy functional')
    print('=' * 78)
    print('    %6s %14s %8s %14s %8s'
          % ('nz', '|P0 - exact|', 'order', '|Pmod - exact|', 'order'))
    pa = potential_accuracy()
    o0 = orders([p[1] for p in pa])
    om = orders([p[2] for p in pa])
    for k, p in enumerate(pa):
        s0 = '%8.2f' % o0[k - 1] if k > 0 else '%8s' % '-'
        sm = '%8.2f' % om[k - 1] if k > 0 else '%8s' % '-'
        print('    %6d %14.4e %s %14.4e %s' % (p[0], p[1], s0, p[2], sm))


if __name__ == '__main__':
    main()
