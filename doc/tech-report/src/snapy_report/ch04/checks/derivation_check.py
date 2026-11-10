"""Symbolic check of every algebraic step of the chapter 4 Derivation layers.

Each claim re-derives one step of a Derivation layer with sympy and compares it with the formula the code runs at
snapy@6fbb39750f62b83df096058a4746e77d0a634bc5 (the code pin):

  C1   the finite-volume balance and its telescoping sum (src/coord/coordinate.cpp:509-552,
       src/hydro/hydro_forward.cpp:870-872);
  C2   donor cell: the face value is first order (src/recon/interpolation.hpp:88-107);
  C3   PLM: the harmonic-mean slope keeps the face value between the neighbours and is second order
       where the field is smooth (src/recon/plm.cpp:10-32);
  C4   cp3 and cp5: the weights solved from cell-average exactness equal the coefficient buffers, with their
       leading errors (src/recon/cp3.cpp:9-13, src/recon/cp5.cpp:9-15);
  C5   WENO3 and WENO5: candidates, linear weights and Jiang-Shu indicators solved from their definitions equal
       the rows of the coefficient buffers (src/recon/weno3.cpp:9-17, src/recon/weno5.cpp:10-24) as the kernels
       use them (src/recon/interp_impl.h:33-122);
  C6   the production rows equal the ports of recon_check.py, so its measured orders hold for them;
  C7   the scale key: with scale on, the kernel output is homogeneous of degree one in the data; with it off the
       fixed floor 1e-6 makes the weights depend on the units (src/recon/interp_impl.h:46-68, 89-120);
  C8   LMARS from linear acoustics, and its sound speed and enthalpy (src/riemann/lmars_impl.h:17-78);
  C9   HLLC: contact speed and pressure from the Rankine-Hugoniot conditions, the code's flux form against the
       star-state flux, the shock factor and the clipped supersonic limit (src/riemann/hllc_impl.h:16-130);
  C10  Roe: the Roe property, the wave strengths, the species and energy rows (src/riemann/roe_impl.h:23-211);
  C11  shallow-water Roe: the Roe property and the wave strengths (src/riemann/shallow_roe_impl.h:14-72,
       src/eos/shallow_water_impl.h:17-20);
  C12  plume-roe: consistency of the Lax-Friedrichs flux on primitive jumps (src/riemann/plume_roe.cpp:14-39);
  C13  the density-weighted face-flux gap of every row, Cartesian (src/hydro/hydro_forward.cpp:136-184);
  C14  the face-measure gap on a spherical-polar face: covariance plus centroid shift
       (src/hydro/hydro_forward.cpp:54-206);
  C15  the x1 stored-velocity gap, the centred and the one-sided slopes (src/hydro/hydro_forward.cpp:35-52, 397-427);
  C16  the compositional-to-thermal buoyancy ratio of the tracer and energy rows;
  C17  WENO3 at a critical point: why the measured order falls to two (src/recon/interp_impl.h:33-70);
  C18  the round-off bound of the divergence: the rounding count, eps_m and the bound the text quotes
       (src/coord/coordinate.cpp:509-552);
  C19  conversion-order 4: the cell-average/point-value relation, the weights of the curvature operator Q
       (src/hydro/hydro_forward.cpp, conv4_x1_weights) and the order of W(u - Q u) + Q W(u) against W(u)
       (src/hydro/hydro_forward.cpp, HydroImpl::forward), with the grid dependence measured in numpy.

Run: python3 derivation_check.py   (sympy only; prints one line per claim, exits with the number of failures)
"""
import sys

import sympy as sp

FAIL = []


def report(tag, ok, what, detail):
    print(f"[{tag}] {'PASS' if ok else 'FAIL'} {what}: {detail}")
    if not ok:
        FAIL.append(tag)


def zero(e):
    return sp.simplify(sp.together(sp.expand(e))) == 0


# ---------- cell averages of a Taylor polynomial on a uniform grid ----------
x, h = sp.symbols("x h", positive=True)
K = 8
a = sp.symbols("a0:%d" % K)                       # a_k = d^k u / dx^k at the centre of cell 0 over k!
U = sum(a[k] * x**k for k in range(K))


def cavg(f, j):
    """cell average of f over cell j (centre j h, width h)"""
    return sp.expand(sp.integrate(f, (x, j * h - h / 2, j * h + h / 2)) / h)


def solve_weights(cells, face):
    c = sp.symbols("c0:%d" % len(cells))
    eqs = []
    for d in range(len(cells)):
        eqs.append(sum(ci * cavg(x**d, j) for ci, j in zip(c, cells)) - face**d)
    sol = sp.solve(eqs, c, dict=True)[0]
    return [sol[ci] for ci in c]


def lead(expr, n=8):
    s = sp.expand(sp.series(expr, h, 0, n).removeO())
    for p in range(n):
        t = s.coeff(h, p)
        if t != 0:
            return p, sp.factor(t)
    return None, 0


def check_C1():
    xm, xp, t = sp.symbols("x_m x_p t")
    F = sp.Function("F")
    ok1 = sp.integrate(sp.diff(F(x), x), (x, xm, xp)) == F(xp) - F(xm)
    G = sp.symbols("G0:7")                         # G_k = A F at face k - 1/2
    tele = sp.expand(sum(G[i + 1] - G[i] for i in range(6)))
    ok2 = tele == G[6] - G[0]
    report("C1", ok1 and ok2, "the cell integral of a flux divergence is the face difference, and the sum over "
           "cells telescopes", "int_{x-}^{x+} dF/dx dx = F(x+) - F(x-); sum over 6 cells of (G_{i+1/2} - G_{i-1/2}) "
           "= %s (exact, sympy)" % tele)


def check_C2():
    p, c = lead(cavg(U, 0) - U.subs(x, h / 2))
    report("C2", p == 1 and c == -a[1] / 2, "donor cell: the cell average used as the right-face value",
           "u_avg - u(x_{i+1/2}) = %s h^%d + O(h^2): first order" % (c, p))


def check_C3():
    dm, dp = sp.symbols("D_m D_p", positive=True)
    D = 2 * dm * dp / (dm + dp)
    b1 = sp.factor(2 * dp - D)
    b2 = sp.factor(2 * dm - D)
    ok_b = sp.simplify(b1 - 2 * dp**2 / (dm + dp)) == 0 and sp.simplify(b2 - 2 * dm**2 / (dm + dp)) == 0
    # smooth limit on cell averages, slope a1 != 0
    w = [cavg(U, j) for j in (-1, 0, 1)]
    Dm, Dp = w[1] - w[0], w[2] - w[1]
    Dsl = 2 * Dm * Dp / (Dm + Dp)
    p, c = lead(w[1] + Dsl / 2 - U.subs(x, h / 2), 5)
    pd, cd = lead(Dsl - h * a[1], 5)
    report("C3", ok_b and p == 2, "PLM: 2 D_+ - D = 2 D_+^2/(D_- + D_+) >= 0 and 2 D_- - D = 2 D_-^2/(D_- + D_+) >= 0, "
           "so the faces stay between the neighbours; smooth limit",
           "D - h u' = %s h^%d; face error = %s h^%d (second order)" % (cd, pd, c, p))


CP3_CODE = [sp.Rational(1, 3), sp.Rational(5, 6), -sp.Rational(1, 6)]               # cp3.cpp cm
CP5_CODE = [-sp.Rational(1, 20), sp.Rational(9, 20), sp.Rational(47, 60), -sp.Rational(13, 60),
            sp.Rational(1, 30)]                                                       # cp5.cpp cm


def check_C4():
    w3 = solve_weights([-1, 0, 1], -h / 2)
    w5 = solve_weights([-2, -1, 0, 1, 2], -h / 2)
    w3r = solve_weights([-1, 0, 1], h / 2)
    e3 = lead(sum(c * cavg(U, j) for c, j in zip(w3, [-1, 0, 1])) - U.subs(x, -h / 2))
    e5 = lead(sum(c * cavg(U, j) for c, j in zip(w5, [-2, -1, 0, 1, 2])) - U.subs(x, -h / 2))
    ok = w3 == CP3_CODE and w5 == CP5_CODE and w3r == CP3_CODE[::-1]
    report("C4", ok and e3[0] == 3 and e5[0] == 5, "cp3 and cp5 weights solved from cell-average exactness equal "
           "the coefficient buffers; cp = cm flipped is the right face",
           "cp3 %s, error %s h^%d; cp5 %s, error %s h^%d" % (w3, e3[1], e3[0], w5, e5[1], e5[0]))


W5_CODE = [[-sp.Rational(1, 6), sp.Rational(5, 6), sp.Rational(1, 3), 0, 0],
           [0, sp.Rational(1, 3), sp.Rational(5, 6), -sp.Rational(1, 6), 0],
           [0, 0, sp.Rational(11, 6), -sp.Rational(7, 6), sp.Rational(1, 3)],
           [1, -2, 1, 0, 0], [1, -4, 3, 0, 0], [0, 1, -2, 1, 0], [0, -1, 0, 1, 0],
           [0, 0, 1, -2, 1], [0, 0, 3, -4, 1]]                                         # weno5.cpp cm
W3_CODE = [[sp.Rational(1, 2), sp.Rational(1, 2), 0], [0, sp.Rational(3, 2), -sp.Rational(1, 2)],
           [1, -1, 0], [0, 1, -1]]                                                     # weno3.cpp cm


def candidate(cells, deg):
    """the polynomial of degree deg whose cell averages on cells are the symbols phi_j"""
    b = sp.symbols("b0:%d" % (deg + 1))
    P = sum(b[k] * x**k for k in range(deg + 1))
    return P, b


def check_C5():
    phi = sp.symbols("phi0:5")                    # cells -2..2
    ok = True
    betas = []
    for k, cells in enumerate([(-2, -1, 0), (-1, 0, 1), (0, 1, 2)]):
        P, b = candidate(cells, 2)
        sol = sp.solve([cavg(P, j) - phi[j + 2] for j in cells], b, dict=True)[0]
        P = P.subs(sol)
        face = sp.expand(P.subs(x, -h / 2))
        ok &= sp.expand(face - sum(c * f for c, f in zip(W5_CODE[k], phi))) == 0
        beta = sp.expand(sum(h**(2 * l - 1) * sp.integrate(sp.diff(P, x, l)**2, (x, -h / 2, h / 2))
                             for l in (1, 2)))
        code = sp.Rational(13, 12) * sum(c * f for c, f in zip(W5_CODE[3 + 2 * k], phi))**2 + \
            sp.Rational(1, 4) * sum(c * f for c, f in zip(W5_CODE[4 + 2 * k], phi))**2
        ok &= sp.expand(beta - code) == 0
        betas.append(beta)
    d = sp.symbols("d0:3")
    lin = sum(d[k] * sum(c * f for c, f in zip(W5_CODE[k], phi)) for k in range(3)) - \
        sum(c * f for c, f in zip(CP5_CODE, phi))
    dsol = sp.solve(sp.Poly(sp.expand(lin), *phi).coeffs(), d, dict=True)
    ok &= len(dsol) == 1 and [dsol[0][dk] for dk in d] == [sp.Rational(3, 10), sp.Rational(3, 5), sp.Rational(1, 10)]
    # weno3: linear candidates on (-1,0) and (0,1), indicator h int (P')^2 over cell 0
    p3 = sp.symbols("p0:3")
    ok3 = True
    for k, cells in enumerate([(-1, 0), (0, 1)]):
        P, b = candidate(cells, 1)
        sol = sp.solve([cavg(P, j) - p3[j + 1] for j in cells], b, dict=True)[0]
        P = P.subs(sol)
        ok3 &= sp.expand(P.subs(x, -h / 2) - sum(c * f for c, f in zip(W3_CODE[k], p3))) == 0
        beta = sp.expand(h * sp.integrate(sp.diff(P, x)**2, (x, -h / 2, h / 2)))
        ok3 &= sp.expand(beta - sum(c * f for c, f in zip(W3_CODE[2 + k], p3))**2) == 0
    lin3 = sp.Rational(2, 3) * sum(c * f for c, f in zip(W3_CODE[0], p3)) + \
        sp.Rational(1, 3) * sum(c * f for c, f in zip(W3_CODE[1], p3)) - sum(c * f for c, f in zip(CP3_CODE, p3))
    ok3 &= sp.expand(lin3) == 0
    report("C5", ok and ok3, "WENO candidates, linear weights and Jiang-Shu indicators re-derived equal the rows of "
           "the weno3/weno5 coefficient buffers",
           "weno5: 3 candidates and 3 indicators (sum over l=1,2 of h^(2l-1) int (P^(l))^2) match rows 0-8; unique "
           "linear weights (3/10, 3/5, 1/10) rebuild cp5; weno3: 2 candidates, 2 indicators, (2/3, 1/3) rebuild cp3 "
           "(exact, sympy)")


def check_C6():
    sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
    import importlib.util
    spec = importlib.util.spec_from_file_location("recon_port", __import__("os").path.join(
        __import__("os").path.dirname(__import__("os").path.abspath(__file__)), "recon_check.py"))
    src = open(spec.origin).read().split("# --- C1:")[0]       # the ports only, not the claims
    ns = {}
    exec(compile(src, spec.origin, "exec"), ns)
    phi = sp.symbols("phi0:5")
    (q0, q1, q2), (b0, b1, b2), _ = ns["weno5_parts"](*phi)
    rows = [q0, q1, q2]
    ok = all(sp.expand(sp.nsimplify(sp.expand(r)) - sum(c * f for c, f in zip(W5_CODE[k], phi))) == 0
             for k, r in enumerate(rows))
    for k, bk in enumerate((b0, b1, b2)):
        code = sp.Rational(13, 12) * sum(c * f for c, f in zip(W5_CODE[3 + 2 * k], phi))**2 + \
            sp.Rational(1, 4) * sum(c * f for c, f in zip(W5_CODE[4 + 2 * k], phi))**2
        ok &= sp.expand(sp.nsimplify(sp.expand(bk)) - code) == 0
    cp5 = sp.nsimplify(sp.expand(ns["interp_cp5"](*phi)))
    ok &= sp.expand(cp5 - sum(c * f for c, f in zip(CP5_CODE, phi))) == 0
    p3 = sp.symbols("p0:3")
    (r0, r1), (c0, c1), _ = ns["weno3_parts"](*p3)
    ok &= all(sp.expand(sp.nsimplify(sp.expand(r)) - sum(c * f for c, f in zip(W3_CODE[k], p3))) == 0
              for k, r in enumerate((r0, r1)))
    ok &= all(sp.expand(sp.nsimplify(sp.expand(b)) - sum(c * f for c, f in zip(W3_CODE[2 + k], p3))**2) == 0
              for k, b in enumerate((c0, c1)))
    report("C6", ok, "the rows the production kernels read equal the ports measured in recon_check.py",
           "weno5 candidates and indicators, weno3 candidates and indicators, cp5: identical polynomials, so the "
           "orders of recon_check [C4] are the orders of the scale-off kernels")


def weno5_kernel(phi, scale, eps=sp.Rational(1, 10**6)):
    """interp_weno5_impl (interp_impl.h:73-122), the left-face rows"""
    vs = sum(sp.Abs(f) for f in phi) / 5 if scale else 1
    ph = [f / vs for f in phi]
    p = [sum(c * f for c, f in zip(W5_CODE[k], ph)) for k in range(3)]
    be = [sp.Rational(13, 12) * sum(c * f for c, f in zip(W5_CODE[3 + 2 * k], ph))**2 +
          sp.Rational(1, 4) * sum(c * f for c, f in zip(W5_CODE[4 + 2 * k], ph))**2 for k in range(3)]
    al = [dk / (bk + eps)**2 for dk, bk in zip((sp.Rational(3, 10), sp.Rational(6, 10), sp.Rational(1, 10)), be)]
    return vs * sum(ak * pk for ak, pk in zip(al, p)) / sum(al), [ak / sum(al) for ak in al]


def check_C7():
    lam = sp.Symbol("lambda", positive=True)
    phi = sp.symbols("phi0:5", real=True)
    vs = sum(sp.Abs(f) for f in phi) / 5
    vs_l = sum(sp.Abs(lam * f) for f in phi) / 5
    ok_h = sp.simplify(vs_l - lam * vs) == 0           # so phi/vscale is invariant and out scales with lambda
    data = [sp.Rational(1), sp.Rational(1), sp.Rational(1), sp.Rational(2), sp.Rational(3)]   # a jump right of cell 0
    rows = []
    for mag in (1, sp.Rational(1, 10**3), sp.Rational(1, 10**6)):
        d = [mag * v for v in data]
        out_off, w_off = weno5_kernel(d, False)
        out_on, w_on = weno5_kernel(d, True)
        rows.append((mag, float(w_off[2]), float(w_on[2]), float(out_on / mag)))
    ok = ok_h and abs(rows[0][2] - rows[2][2]) < 1e-15 and rows[2][1] > 0.09 and rows[0][1] < 1e-6
    report("C7", ok, "scale: on, the output is homogeneous of degree one (vscale(lambda phi) = lambda vscale(phi), "
           "exact); off, the 1e-6 floor decides the weights by the data's units",
           "weight of the candidate across the jump at magnitude 1, 1e-3, 1e-6: scale off %s; scale on %s" %
           (", ".join("%.3g" % r[1] for r in rows), ", ".join("%.3g" % r[2] for r in rows)))


def check_C8():
    rho, c, pL, pR, uL, uR = sp.symbols("rho c p_L p_R v_L v_R", positive=True)
    A = sp.Matrix([[0, rho * c**2], [1 / rho, 0]])               # d_t (p, v) + A d_x (p, v) = 0
    ev = sorted(A.eigenvals().keys(), key=str)
    lv = [sp.Matrix([[1, rho * c]]), sp.Matrix([[1, -rho * c]])]
    ok_e = all(sp.simplify(l * A - s * l) == sp.zeros(1, 2) for l, s in zip(lv, (c, -c)))
    pf, vf = sp.symbols("p_f v_f")
    sol = sp.solve([pf + rho * c * vf - (pL + rho * c * uL), pf - rho * c * vf - (pR - rho * c * uR)], [pf, vf])
    code_p = (pL + pR) / 2 + rho * c * (uL - uR) / 2                              # lmars_impl.h:38-39
    code_u = (uL + uR) / 2 + (pL - pR) / (2 * rho * c)                             # lmars_impl.h:42-43
    ok_s = zero(sol[pf] - code_p) and zero(sol[vf] - code_u)
    g, rL, rR = sp.symbols("gamma rho_L rho_R", positive=True)
    rav, gav = (rL + rR) / 2, g
    cbar = sp.sqrt(gav * (pL + pR) / 2 / rav)
    ok_c = zero(cbar**2 - gav * ((pL + pR) / 2) / rav)
    e, v2, v3 = sp.symbols("e v2 v3")
    H = e + (uL**2 + v2**2 + v3**2) / 2 + pL / rL                                   # lmars_impl.h:28-31
    E = rL * e + rL * (uL**2 + v2**2 + v3**2) / 2
    ok_h = zero(rL * H - (E + pL))
    ok_cons = zero(code_p.subs(pR, pL).subs(uR, uL) - pL) and zero(code_u.subs(pR, pL).subs(uR, uL) - uL)
    report("C8", ok_e and ok_s and ok_c and ok_h and ok_cons, "LMARS: the two Riemann invariants p +- rho c v of "
           "linear acoustics give the face pressure and velocity of the code; rho H = E + p; equal states give p, v",
           "eigenvalues %s with left eigenvectors (1, +-rho c); p_f = %s, v_f = %s (exact, sympy)" %
           (ev, sp.simplify(sol[pf]), sp.simplify(sol[vf])))


def check_C9():
    rL, rR, uL, uR, pL, pR, SL, SR, g = sp.symbols("rho_L rho_R v_L v_R p_L p_R S_L S_R gamma")
    vL, wL, EL = sp.symbols("vt_L wt_L E_L")
    # Rankine-Hugoniot of mass and normal momentum across the left and right waves, u* = S*, p* shared
    Ss, ps, rsL, rsR = sp.symbols("S_s p_s rhos_L rhos_R")
    eqs = [rsL * (SL - Ss) - rL * (SL - uL), rsR * (SR - Ss) - rR * (SR - uR),
           (rsL * Ss**2 + ps - SL * rsL * Ss) - (rL * uL**2 + pL - SL * rL * uL),
           (rsR * Ss**2 + ps - SR * rsR * Ss) - (rR * uR**2 + pR - SR * rR * uR)]
    sol = sp.solve(eqs, [Ss, ps, rsL, rsR], dict=True)[0]
    tl = pL + (uL - SL) * rL * uL                                                    # hllc_impl.h:58-70
    tr = pR + (uR - SR) * rR * uR
    ml = rL * (uL - SL)
    mr = -(rR * (uR - SR))
    am = (tl - tr) / (ml + mr)
    cp = (ml * tr + mr * tl) / (ml + mr)
    ok1 = zero(am - sol[Ss]) and zero(cp - sol[ps])
    # the code's flux for am >= 0 equals the star-state flux F_L + S_L (U*_L - U_L)
    S = Ss
    p_s = pL + rL * (SL - uL) * (S - uL)
    UL = sp.Matrix([rL, rL * uL, rL * vL, rL * wL, EL])
    FL = sp.Matrix([rL * uL, rL * uL**2 + pL, rL * uL * vL, rL * uL * wL, (EL + pL) * uL])
    fac = rL * (SL - uL) / (SL - S)
    Us = fac * sp.Matrix([1, S, vL, wL, EL / rL + (S - uL) * (S + pL / (rL * (SL - uL)))])
    star = FL + SL * (Us - UL)
    fl = sp.Matrix([rL * (uL - SL), rL * uL * (uL - SL) + pL, rL * vL * (uL - SL), rL * wL * (uL - SL),
                    EL * (uL - SL) + pL * uL])                                      # hllc_impl.h:76-100, bm = S_L
    sl, sm = S / (S - SL), -SL / (S - SL)                                           # hllc_impl.h:105-108
    code = sl * fl + sm * p_s * sp.Matrix([0, 1, 0, 0, S])                           # hllc_impl.h:119-123
    ok2 = all(zero(v) for v in (code - star))
    # shock factor: relative shock speed from RH for an ideal gas with pressure ratio P = p*/p
    P, r0, p0 = sp.symbols("P rho0 p0", positive=True)
    ratio = ((g + 1) * P + (g - 1)) / ((g - 1) * P + (g + 1))                        # Hugoniot density ratio
    w2 = (P * p0 - p0) / (r0 * (1 - 1 / ratio))
    ok3 = zero(w2 - g * p0 / r0 * (1 + (g + 1) / (2 * g) * (P - 1)))
    # clipped supersonic limit: all waves right (S_L > 0 clipped to -tiny): flux -> F_L
    tiny = sp.Symbol("tiny", positive=True)
    lim = (S / (S + tiny)) * fl.subs(SL, -tiny) + (tiny / (S + tiny)) * (pL + rL * (-tiny - uL) * (S - uL)) * \
        sp.Matrix([0, 1, 0, 0, S])
    ok4 = all(zero(sp.limit(v, tiny, 0) - f) for v, f in zip(lim, FL))
    report("C9", ok1 and ok2 and ok3 and ok4, "HLLC: the code's am and cp are the contact speed and pressure of the "
           "Rankine-Hugoniot conditions; its weighted flux is F_L + S_L (U*_L - U_L); the PVRS shock factor is the "
           "ideal-gas shock speed; the clip gives F_L when every wave moves right",
           "S* = %s (exact, sympy)" % sp.factor(sol[Ss]))


def check_C10():
    A_, B_, g = sp.symbols("a b gamma", positive=True)               # a = sqrt(rho_L), b = sqrt(rho_R)
    uL, uR, vL, vR, pL, pR = sp.symbols("v_L v_R vt_L vt_R p_L p_R")
    rL, rR = A_**2, B_**2
    EL = pL / (g - 1) + rL * (uL**2 + vL**2) / 2
    ER = pR / (g - 1) + rR * (uR**2 + vR**2) / 2
    HL, HR = (EL + pL) / rL, (ER + pR) / rR
    u = (A_ * uL + B_ * uR) / (A_ + B_)
    v = (A_ * vL + B_ * vR) / (A_ + B_)
    H = (A_ * HL + B_ * HR) / (A_ + B_)
    rho = A_ * B_
    q, m, n, E = sp.symbols("q m n E")
    Fc = sp.Matrix([m, m**2 / q + (g - 1) * (E - (m**2 + n**2) / (2 * q)),
                    m * n / q, (E + (g - 1) * (E - (m**2 + n**2) / (2 * q))) * m / q])
    J = Fc.jacobian([q, m, n, E])
    uu, vv, HH = sp.symbols("uu vv HH")
    Jp = J.subs({m: q * uu, n: q * vv}).subs(E, q * (HH + (g - 1) * (uu**2 + vv**2) / 2) / g)
    Jp = sp.simplify(Jp)
    ok_q = all(sp.diff(e, q) == 0 for e in Jp)
    dU = sp.Matrix([rR - rL, rR * uR - rL * uL, rR * vR - rL * vL, ER - EL])
    FLv = sp.Matrix([rL * uL, rL * uL**2 + pL, rL * uL * vL, (EL + pL) * uL])
    FRv = sp.Matrix([rR * uR, rR * uR**2 + pR, rR * uR * vR, (ER + pR) * uR])
    roe = Jp.subs({uu: u, vv: v, HH: H}) * dU - (FRv - FLv)
    ok1 = ok_q and all(zero(e) for e in roe)
    # wave strengths and right eigenvectors as the code writes them (roe_impl.h:137-174), dry gas, ny = 0
    c2 = (g - 1) * (H - (u**2 + v**2) / 2)                                          # roe_impl.h:114-117
    c = sp.sqrt(c2)
    du, dv, dp = uR - uL, vR - vL, pR - pL
    am = -rho / (2 * c) * du + dp / (2 * c2)
    ap = rho / (2 * c) * du + dp / (2 * c2)
    av = rho * dv
    a0 = (rR - rL) - dp / c2
    rows = [am + a0 + ap,
            am * (u - c) + u * a0 + ap * (u + c),
            am * v + (v * a0 + av) + ap * v,
            am * (H - u * c) + (rho * (HR - HL - u * du) + a0 * H - dp) + ap * (H + u * c)]
    ok2 = all(zero(r - d) for r, d in zip(rows, dU))
    # species: Roe-averaged fractions sum to one; entropy strengths add up to the dry alpha_0
    dL, dR, yL, yR = sp.symbols("d_L d_R y_L y_R")
    q0 = (rL * dL / A_ + rR * dR / B_) / (A_ + B_)
    q1 = (rL * yL / A_ + rR * yR / B_) / (A_ + B_)
    ok3 = zero((q0 + q1).subs({dL: 1 - yL, dR: 1 - yR}) - 1)
    a_d = rR * dR - rL * dL - dp / c2 * q0
    a_n = rR * yR - rL * yL - dp / c2 * q1
    ok4 = zero((a_d + a_n - a0).subs({dL: 1 - yL, dR: 1 - yR}))
    ok5 = zero((am * q1 + a_n + ap * q1) - (rR * yR - rL * yL))
    # ideal-moist sound speed of the code: c^2 = (gamma - 1)(H - |v|^2/2 - sum y u*), gamma - 1 = (gd - 1) f_eps/f_sig
    Rd, cvd, T, ystar, feps, fsig, kin = sp.symbols("R_d c_vd T yustar f_eps f_sig kin", positive=True)
    Rm, cvm = Rd * feps, cvd * fsig                           # R_mix = R_d f_eps, c_v = c_vd f_sig
    gm = (cvm + Rm) / cvm
    Hm = cvm * T + ystar + Rm * T + kin                       # e + p/rho + |v|^2/2, e = c_v T + sum y u*
    ok6 = zero((gm - 1) * (Hm - kin - ystar) - gm * Rm * T) and \
        zero((gm - 1) - ((cvd + Rd) / cvd - 1) * feps / fsig)
    report("C10", ok1 and ok2 and ok3 and ok4 and ok5 and ok6, "Roe: the Jacobian at the square-root averages maps the "
           "jump of U to the jump of F; the code's strengths times its eigenvector rows rebuild the jump of every row, "
           "the energy row's entropy form included; the species strengths add up to the total one",
           "Roe property 4 rows, eigen-decomposition 4 rows, sum of Roe fractions = 1, species rows (exact, sympy, "
           "dry gamma-law gas with one tangential velocity); ideal-moist c^2 = (gamma-1)(H - |v|^2/2 - sum y u*) = "
           "gamma R_mix T with gamma - 1 = (gamma_d - 1) f_eps/f_sig")


def check_C11():
    A_, B_ = sp.symbols("a b", positive=True)                   # a = sqrt(Phi_L), b = sqrt(Phi_R)
    uL, uR, vL, vR = sp.symbols("v_L v_R vt_L vt_R")
    PL, PR = A_**2, B_**2
    u = (A_ * uL + B_ * uR) / (A_ + B_)
    v = (A_ * vL + B_ * vR) / (A_ + B_)
    c2 = (PL + PR) / 2                                           # shallow_water_impl.h:18-20
    c = sp.sqrt(c2)
    J = sp.Matrix([[0, 1, 0], [c2 - u**2, 2 * u, 0], [-u * v, v, u]])
    dU = sp.Matrix([PR - PL, PR * uR - PL * uL, PR * vR - PL * vL])
    F = lambda P, uu, vv: sp.Matrix([P * uu, P * uu**2 + P**2 / 2, P * uu * vv])
    ok1 = all(zero(e) for e in J * dU - (F(PR, uR, vR) - F(PL, uL, vL)))
    hb = A_ * B_
    a1 = (c * (PR - PL) - hb * (uR - uL)) / (2 * c)                                 # shallow_roe_impl.h:41-43
    a2 = hb * (vR - vL)
    a3 = (c * (PR - PL) + hb * (uR - uL)) / (2 * c)
    rec = a1 * sp.Matrix([1, u - c, v]) + a2 * sp.Matrix([0, 0, 1]) + a3 * sp.Matrix([1, u + c, v])
    ok2 = all(zero(e) for e in rec - dU)
    report("C11", ok1 and ok2, "shallow-water Roe: square-root averaged velocities with c^2 = (Phi_L + Phi_R)/2 give "
           "the Roe property, and the code's three strengths rebuild the jump",
           "Roe property 3 rows, decomposition 3 rows (exact, sympy)")


def check_C12():
    R, W, B, V, al = sp.symbols("R W B V alpha")
    c1 = 1 - sp.exp(-1)

    def f(R, W, B, V):                                           # plume_roe.cpp:14-24
        return sp.Matrix([c1 * R * R * W, R * R * W * V / 2 - R**3 * V / 2 - R * R * V * V / 8,
                          R * R * B * W / 2, R**3 * V * W / 4 + R**4 * W / 2])
    psi = sp.Matrix([R, W, B, V])
    lf = (f(R, W, B, V) + f(R, W, B, V)) / 2 - al / 2 * (psi - psi)
    ok = all(zero(e) for e in lf - f(R, W, B, V))
    report("C12", ok, "plume-roe: the Lax-Friedrichs flux on primitive jumps is consistent",
           "F(psi, psi) = f(psi) for any alpha (exact, sympy); the damping term is alpha/2 times the primitive jump")


def smooth(name, n=6):
    c = sp.symbols(name + "0:%d" % n)
    return sum(c[k] * x**k for k in range(n)), c


def check_C13():
    rho, r = smooth("r")
    v, vc = smooth("v")
    q, qc = smooth("q")
    av = lambda f: cavg(f, 0)
    gap = av(rho * v * q) - av(rho * v) * av(rho * q) / av(rho)
    p, cf = lead(gap, 5)
    ok = p == 2 and sp.simplify(cf - r[0] * vc[1] * qc[1] / 12) == 0
    p4, _ = lead(sp.expand(sp.series(gap, h, 0, 5).removeO()) - h**2 * r[0] * vc[1] * qc[1] / 12, 6)
    gap_m = av(rho * v) - av(rho * v)
    ok &= gap_m == 0 and p4 == 4
    report("C13", ok, "density-weighted rows: <rho v q> - <rho v><rho q>/<rho> = (h^2/12) rho v_1 q_1 + O(h^4), with "
           "no density-slope term; the total mass flux <rho v> has no gap",
           "leading term %s h^2, next order h^%d (exact series, sympy)" % (cf, p4))


def check_C14():
    r0 = sp.Symbol("r0", positive=True)
    rho, rc = smooth("r", 4)
    v, vc = smooth("v", 4)
    q, qc = smooth("q", 4)
    N = 5                                                         # series order in h: terms through h^4 kept

    def avg(f, wgt):                                              # x = r - r0, cell [-h/2, h/2]
        num = sp.integrate(sp.expand(f * wgt), (x, -h / 2, h / 2))
        den = sp.integrate(wgt, (x, -h / 2, h / 2))
        return sp.series(num / den, h, 0, N).removeO()

    def mul(*fs):
        out = 1
        for f in fs:
            out = sp.series(sp.expand(out * f), h, 0, N).removeO()
        return out
    wA, wV = r0 + x, (r0 + x)**2
    xc = avg(x, wV)                                               # cell centroid offset from the midpoint
    xA = avg(x, wA)
    s2A = avg((x - xA)**2, wA)
    inv_rho = sp.series(1 / avg(rho, wV), h, 0, N).removeO()
    gap = avg(rho * v * q, wA) - mul(avg(rho * v, wV), avg(rho * q, wV), inv_rho)
    at = lambda f: sp.series(f.subs(x, xc), h, 0, N).removeO()
    d1 = lambda f: at(sp.diff(f, x))
    model = mul(s2A, at(rho), d1(v), d1(q)) - mul(xc - xA, d1(rho * v * q))
    res = sp.expand(sp.series(sp.expand(gap - model), h, 0, 4).removeO())
    ok = res == 0
    sh = sp.series(xc - xA, h, 0, 4).removeO()
    report("C14", ok, "spherical-polar x2/x3 face: the face-measure flux minus the flux of cell values is "
           "face_moment2 rho v_1 q_1 - (x_{1,i} - x^A_{1,i}) d_1(rho v q) + O(h^4)",
           "remainder through h^3: %s; shift x_{1,i} - x^A_{1,i} = %s + O(h^4) (exact series, sympy)" %
           (res, sp.simplify(sh)))


def check_C15():
    rho, rc = smooth("r")
    w, wc = smooth("w")
    av = lambda f, j=0: cavg(f, j)
    gap = av(rho * w) / av(rho) - av(w)
    p, cf = lead(gap, 6)
    ok1 = p == 2 and sp.simplify(cf - rc[1] * wc[1] / (12 * rc[0])) == 0
    cen = (av(rho, 1) - av(rho, -1)) / (2 * h)
    pc, ccf = lead(cen - rc[1], 5)
    resid = sp.series(gap - h**2 / 12 * ((av(rho, 1) - av(rho, -1)) / (2 * h)) *
                      ((av(w, 1) - av(w, -1)) / (2 * h)) / av(rho), h, 0, 6).removeO()
    pr = min(sp.Poly(sp.expand(resid), h).monoms())[0] if resid != 0 else None
    oks = []
    for s in (1, -1):
        hh = s * h                                               # x1v[i+s] - x1v[i]
        one = s * (-3 * av(rho, 0) + 4 * av(rho, s) - av(rho, 2 * s)) / (2 * s * hh)
        po, co = lead(one - rc[1], 5)
        oks.append((po, co))
    ok = ok1 and pc == 2 and pr == 4 and all(po == 2 for po, _ in oks)
    report("C15", ok, "x1 stored velocity: <rho w>/<rho> - <w> = (h^2/12) rho_1 w_1/rho + O(h^4); centred slopes of "
           "cell averages are second order, so the corrected gap is O(h^4); the one-sided wall slope is second order "
           "for s = +1 and s = -1",
           "leading %s h^2; centred slope error %s h^2; corrected remainder h^%s; one-sided errors %s, %s" %
           (cf, ccf, pr, oks[0][1], oks[1][1]))


def check_C16():
    mud, muv, y = sp.symbols("mu_d mu_v y", positive=True)
    p, T, R = sp.symbols("p T R", positive=True)
    mumix = 1 / ((1 - y) / mud + y / muv)
    rho = p * mumix / (R * T)
    alpha = sp.simplify(-sp.diff(sp.log(rho), y))
    ok1 = zero(alpha - mumix * (1 / muv - 1 / mud))
    # energy row minus the enthalpy the mass rows move = the thermal part
    s2, rr, cp_, T1, y1, u1, hv, hd = sp.symbols("sigma2 rho c_p T_1 y_1 u_1 hv hd")
    hhat1 = cp_ * T1 + (hv - hd) * y1                              # d_1 of the mixture enthalpy
    GE = s2 * rr * hhat1 * u1
    Gv = s2 * rr * u1 * y1
    Gd = -Gv
    ok2 = zero(GE - (hv * Gv + hd * Gd) - s2 * rr * cp_ * T1 * u1)
    # errors share sigma^2 d_2 d_1 u; the ratio cancels sigma^2 and the mode
    k2, uu = sp.symbols("k2 uu", positive=True)
    Terr, yerr = s2 * T1 * k2 * uu, s2 * y1 * k2 * uu
    Bv = sp.simplify(alpha * yerr / (Terr / T))
    ok3 = zero(Bv - alpha * T * y1 / T1) and sp.diff(Bv, s2) == 0 and sp.diff(Bv, k2) == 0
    # the mode: incompressible 2-D, d_2 v_2 = -d_1 v_1, v_1 ~ sin(2 pi x1/lambda)
    lw, x1 = sp.symbols("lambda_w x1", positive=True)
    v1 = sp.sin(2 * sp.pi * x1 / lw)
    ok4 = zero(sp.diff(-sp.diff(v1, x1), x1) - (2 * sp.pi / lw)**2 * v1)
    # saturated small-y limit: y = (mu_v/mu_d) p_sat(T)/p, d ln p_sat/dT = L/(R_v T^2), d_1 ln p = g_1/(R_d T)
    L, Rv, Rd, g1, Gam = sp.symbols("L R_v R_d g_1 Gamma")
    dlny_dz = L / (Rv * T**2) * (-Gam) - g1 / (Rd * T)
    Bsat = alpha * T * (y * dlny_dz) / (-Gam)
    ok5 = zero(Bsat - alpha * y * (L / (Rv * T) + g1 / (Rd * Gam)))
    # a vapour falling off with p over one scale height on the dry adiabat: bracket c_p/R_d
    cpd = sp.Symbol("c_pd", positive=True)
    Bp = (alpha * T * y * (g1 / (Rd * T)) / (-Gam)).subs(Gam, -g1 / cpd)
    ok6 = zero(Bp - alpha * y * cpd / Rd)
    report("C16", all((ok1, ok2, ok3, ok4, ok5, ok6)), "buoyancy ratio: alpha_v = mu_mix (1/mu_v - 1/mu_d); energy row "
           "minus the enthalpy of the mass rows = sigma^2 rho c_p T_1 u_1; B = alpha_v T y_1/T_1, free of sigma^2 and "
           "of the mode; d_1 d_2 v_2 = (2 pi/lambda_w)^2 v_1; saturated and one-scale-height limits",
           "alpha_v = %s; saturated B = alpha_v y [L/(R_v T) - |g_1|/(R_d Gamma)]; scale-height B = alpha_v y c_pd/R_d "
           "(exact, sympy)" % sp.factor(alpha))


def check_C17():
    """WENO3 at a critical point offset zeta_ex h from the centre of cell 0, indicators far above the floor"""
    th = sp.Symbol("zeta_ex")
    A2, A3 = sp.symbols("A2 A3")
    u = a[0] + A2 * (x - th * h)**2 + A3 * (x - th * h)**3
    p = [cavg(u, j) for j in (-1, 0, 1)]
    b0, b1 = sp.expand((p[0] - p[1])**2), sp.expand((p[1] - p[2])**2)
    ratio = sp.factor(sp.limit(b1 / b0, h, 0))
    P0 = (p[0] + p[1]) / 2
    P1 = sp.Rational(3, 2) * p[1] - p[2] / 2
    al0, al1 = sp.Rational(2, 3) / b0**2, sp.Rational(1, 3) / b1**2
    face = (al0 * P0 + al1 * P1) / (al0 + al1)
    err = sp.series(sp.simplify(face - u.subs(x, -h / 2)), h, 0, 3).removeO()
    c2 = sp.factor(sp.simplify(err.coeff(h, 2)))
    ok = sp.simplify(ratio - (2 * th - 1)**2 / (2 * th + 1)**2) == 0 and err.coeff(h, 0) == 0 and \
        sp.simplify(err.coeff(h, 1)) == 0 and sp.simplify(c2.subs(th, 0)) == 0 and \
        sp.simplify(c2.subs(th, sp.Rational(1, 4))) != 0
    report("C17", ok, "WENO3 at a critical point zeta_ex h from the cell centre, beta far above the floor: the "
           "indicator ratio stays O(1) away from one and the face error is second order unless zeta_ex = 0",
           "beta_1/beta_0 -> %s; face error = %s h^2 + O(h^3) (exact series, sympy)" % (ratio, c2))


# The values the Derivation layer of _divergence.qmd states (step 3 and step 4 of its round-off argument).
TEXT_K = 7                     # roundings along one path
TEXT_EPS_M = 2.0**-52          # machine epsilon as the text defines it
TEXT_BOUND = 2.73e-14          # bound quoted for operator_check.py [C2]


def check_C18():
    """the divergence round-off bound: count the roundings, take eps_m from the hardware, compare with the text"""
    import numpy as np
    path = {"area A (r^2 times the solid angle)": 2, "product A F": 1, "difference a - b": 1,
            "volume V ((r+^3 - r-^3)/3)": 2, "quotient / V": 1}
    k = sum(path.values())
    eps_m = float(np.finfo(np.float64).eps)          # 2^-52; one rounding is at most eps_m / 2
    rf = np.linspace(2.0, 3.0, 7)                    # the r in [2, 3], h = 1/6 grid of operator_check.py [C2]
    rm, rp = rf[:-1], rf[1:]
    a, b, V = rp**2 * rp, rm**2 * rm, (rp**3 - rm**3) / 3.0
    bound = k * (eps_m / 2) * (np.abs(a) + np.abs(b)) / V
    resid = np.abs((a - b) / V - 3.0)
    ok = (k == TEXT_K and eps_m == TEXT_EPS_M and abs(bound.max() - TEXT_BOUND) <= 0.01 * TEXT_BOUND
          and bool((resid <= bound).all()))
    report("C18", ok, "divergence round-off: k roundings along a path, each at most eps_m/2, bound k (eps_m/2)(|a|+|b|)/V",
           "counted k = %d (text %d); eps_m = 2^%d (text 2^%d); max bound %.3g (text %.3g); max residual %.2g"
           % (k, TEXT_K, int(np.log2(eps_m)), int(np.log2(TEXT_EPS_M)), bound.max(), TEXT_BOUND, resid.max()))


# The weights the code builds in conv4_x1_weights, in the report's notation: with the three widths
# h_{i-1}, h_i, h_{i+1} read off x1f, c_i = h_i^2 / (4 (h_{i-1} + h_i + h_{i+1})), k^+ = c_i/(h_i + h_{i+1})
# and k^- = c_i/(h_{i-1} + h_i) (src/hydro/hydro_forward.cpp conv4_x1_weights).
def conv4_weights(f0, f1, f2, f3):
    """(k+, k-) of eq-ch04-conv4-weights from the four faces bounding cells i-1, i, i+1"""
    c = (f2 - f1) ** 2 / 4 / (f3 - f0)
    return c / (f3 - f1), c / (f2 - f0)


def check_C19():
    """conversion-order 4: the average-point relation, the weights of Q, and the order of the scheme"""
    import numpy as np
    y = sp.Symbol("y")

    # (a) an average is a midpoint value plus h^2/24 times the second derivative
    pa, ca = lead(cavg(U, 0) - (U.subs(x, 0) + sp.diff(U, x, 2).subs(x, 0) * h**2 / 24), 6)

    # (b) the code's weights give h_i^2 d1^2 q / 24 exactly for a quadratic on any four faces
    f0, f1, f2, f3 = sp.symbols("f0 f1 f2 f3", real=True)
    A, B, C = sp.symbols("A B C")
    quad = A * y**2 + B * y + C
    av = lambda lo, hi: sp.integrate(quad, (y, lo, hi)) / (hi - lo)
    kp, km = conv4_weights(f0, f1, f2, f3)
    exact = sp.simplify(kp * (av(f2, f3) - av(f1, f2)) - km * (av(f1, f2) - av(f0, f1))
                        - (f2 - f1)**2 / 24 * sp.diff(quad, y, 2))

    # (c) equal widths: both weights are 1/24
    eq = {f0: -3 * h / 2, f1: -h / 2, f2: h / 2, f3: 3 * h / 2}
    uni = (sp.simplify(kp.subs(eq)), sp.simplify(km.subs(eq)))

    # (d) Q of the cell averages of a smooth field is h^2 d1^2 q / 24 to fourth order, on a uniform grid and
    #     on faces drawn from a smooth map x1(s) at a uniform step s
    Qbar = (cavg(U, 1) - 2 * cavg(U, 0) + cavg(U, -1)) / 24
    pd, cd = lead(Qbar - sp.diff(U, x, 2).subs(x, 0) * h**2 / 24, 7)
    be, ga, sv = sp.symbols("beta gamma s_v")
    xmap = sv + be * sv**2 / 2 + ga * sv**3 / 6            # a smooth grid map, dx1/ds = 1 at s = 0
    F = [sp.expand(xmap.subs(sv, k * h / 2)) for k in (-3, -1, 1, 3)]
    qc = sp.symbols("q0:6")
    qs = sum(qc[k] * y**k for k in range(6))
    avs = lambda lo, hi: sp.cancel(sp.integrate(qs, (y, lo, hi)) / (hi - lo))
    kps, kms = [sp.cancel(w) for w in conv4_weights(*F)]
    Qs = sp.cancel(kps * (avs(F[2], F[3]) - avs(F[1], F[2])) - kms * (avs(F[1], F[2]) - avs(F[0], F[1])))
    tgt = (F[2] - F[1])**2 / 24 * sp.diff(qs, y, 2).subs(y, (F[1] + F[2]) / 2)
    ps, cs = lead(sp.cancel(Qs - tgt), 6)

    # (e) the scheme: W(ubar - Q ubar) + Q W(ubar) is the cell average of W(u) to fourth order, and the
    #     plain conversion W(ubar) is second order, with the gap of eq-ch04-conv4-gap. W is carried by its
    #     own Taylor coefficients b_m about the cell's average, so the composition stays polynomial.
    M = 5
    b = sp.symbols("b0:%d" % (M + 1))
    W = lambda z: sum(b[m] * (z - a[0])**m for m in range(M + 1))
    ubar, Qu = cavg(U, 0), (cavg(U, 1) - 2 * cavg(U, 0) + cavg(U, -1)) / 24
    w0 = [W(cavg(U, j)) for j in (-1, 0, 1)]
    Qw0 = (w0[2] - 2 * w0[1] + w0[0]) / 24
    wbar = cavg(sp.expand(W(U)), 0)
    p4, c4 = lead(sp.expand(wbar - (W(ubar - Qu) + Qw0)), 5)
    p2, c2 = lead(sp.expand(wbar - W(ubar)), 5)
    # d^2W/du^2 (d1 u)^2 h^2/24 with b2 = W''/2 and a1 = d1 u
    gap = sp.simplify(c2 - 2 * b[2] * a[1]**2 / 24)

    # (f) the grid dependence, measured: the point value ubar - Q ubar against the exact one, max norm
    qn = lambda z: np.sin(3.0 * z) + 0.4 * np.cos(1.7 * z + 0.3)
    Qn = lambda z: -np.cos(3.0 * z) / 3.0 + 0.4 * np.sin(1.7 * z + 0.3) / 1.7
    def point_err(faces):
        wd = np.diff(faces)
        ca_ = (Qn(faces[1:]) - Qn(faces[:-1])) / wd
        kpn, kmn = conv4_weights(faces[:-3], faces[1:-2], faces[2:-1], faces[3:])
        Qa = kpn * (ca_[2:] - ca_[1:-1]) - kmn * (ca_[1:-1] - ca_[:-2])
        mid = (faces[1:-2] + faces[2:-1]) / 2.0
        return np.abs(ca_[1:-1] - Qa - qn(mid)).max()
    ns = np.array([32, 64, 128, 256, 512], float)
    grids = {
        "uniform": lambda n: np.linspace(0.0, 1.0, n + 1),
        "stretched": lambda n: (lambda z: z + 0.8 * np.sin(2 * np.pi * z) / (2 * np.pi))(
            np.linspace(0.0, 1.0, n + 1)),
        "1:2 width jump": lambda n: (lambda f: f / f[-1])(np.concatenate(
            [[0.0], np.cumsum(np.where(np.arange(n) < n // 2, 1.0, 2.0))])),
    }
    fits = {}
    for name, make in grids.items():
        e = np.array([point_err(make(int(n))) for n in ns])
        fits[name] = -np.polyfit(np.log(ns), np.log(e), 1)[0]

    ok = (pa == 4 and ca == a[4] / 80 and exact == 0 and uni == (sp.Rational(1, 24),) * 2
          and pd == 4 and ps == 4 and p4 == 4 and p2 == 2 and gap == 0
          and fits["uniform"] > 3.9 and fits["stretched"] > 3.9 and 2.5 < fits["1:2 width jump"] < 3.5)
    report("C19", ok, "conversion-order 4: an average is the midpoint value plus h^2 d1^2 q/24; the code's "
           "weights are h_i^2 d1^2 q/24 exactly for a quadratic on any faces and 1/24 on equal widths; Q of "
           "cell averages is fourth order on a uniform grid and on a smooth grid map; W(ubar - Q ubar) + "
           "Q W(ubar) is the cell average of W(u) to O(h^4) while W(ubar) is O(h^2) with the gap "
           "(h^2/24) d_u^2 W (d1 u)^2",
           "average remainder %s h^4; quadratic residual %s; equal widths %s, %s; Q error h^%d (uniform) and "
           "h^%d (smooth map); scheme remainder h^%d, plain conversion h^%d, gap matches; measured point-value "
           "order %s" % (ca, exact, uni[0], uni[1], pd, ps, p4, p2,
                         ", ".join("%s %.2f" % (k, v) for k, v in fits.items())))


def main():
    for fn in (check_C1, check_C2, check_C3, check_C4, check_C5, check_C6, check_C7, check_C8, check_C9, check_C10,
               check_C11, check_C12, check_C13, check_C14, check_C15, check_C16, check_C17, check_C18,
               check_C19):
        fn()
    print(f"{19 - len(FAIL)}/19 claims pass")
    return len(FAIL)


if __name__ == "__main__":
    sys.exit(main())
