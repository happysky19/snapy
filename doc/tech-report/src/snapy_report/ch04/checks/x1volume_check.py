"""Executable check of the radial x1 volume coordinate (chapter 4, _x1volume).

`rows()` below is a numpy port, line for line, of the per-face x1 coefficient
builder of src/recon/x1_coeffs.cpp:10-31, 33-57, 59-90, 92-106, 108-113, 115-120,
140-153@68f4e066974ede87e4379285c4fba895b970b7f1 (primitive_row, quad_inv_rows,
ptype_row, window_weno5, combine_optimal, window_cp5, build_x1_coeffs in that
order), and `row_faces()` is a port of CoordinateImpl::x1_row_faces,
src/coord/coordinate.cpp:546-562@68f4e066974ede87e4379285c4fba895b970b7f1.  The
shipped uniform weights it is compared against are the `cm` buffers of
src/recon/weno5.cpp:13-25@68f4e066974ede87e4379285c4fba895b970b7f1 and
src/recon/cp5.cpp:15-18@68f4e066974ede87e4379285c4fba895b970b7f1.
Claims C1-C7 of the Derivation layer.

Run: python3 x1volume_check.py   (numpy only; exits with the number of failed claims)
"""
import math
import sys

import numpy as np

FAIL = []

NCOEFF_WENO5, NCOEFF_CP5 = 48, 5

# src/recon/weno5.cpp :13-25, the `cm` buffer: three candidate rows, then the six
# smoothness rows.  `cp` is its column flip (:25).
WENO5_CM = np.array([[-1 / 6, 5 / 6, 1 / 3, 0, 0],
                     [0, 1 / 3, 5 / 6, -1 / 6, 0],
                     [0, 0, 11 / 6, -7 / 6, 1 / 3],
                     [1, -2, 1, 0, 0],
                     [1, -4, 3, 0, 0],
                     [0, 1, -2, 1, 0],
                     [0, -1, 0, 1, 0],
                     [0, 0, 1, -2, 1],
                     [0, 0, 3, -4, 1]])
WENO5_D = np.array([0.3, 0.6, 0.1])
CP5_CM = np.array([-1 / 20, 9 / 20, 47 / 60, -13 / 60, 1 / 30])  # src/recon/cp5.cpp :15-20

GX, GW = np.polynomial.legendre.leggauss(20)


def report(tag, ok, what, detail):
    print(f"[{tag}] {'PASS' if ok else 'FAIL'} {what}: {detail}")
    if not ok:
        FAIL.append(tag)


# ---------------------------------------------------------------- the port --
def primitive_row(z, n):                                  # x1_coeffs.cpp :10-31
    lp = np.zeros(n + 1)
    for j in range(n + 1):
        s = 0.
        for i in range(n + 1):
            if i == j:
                continue
            term = 1. / (z[j] - z[i])
            for l in range(n + 1):
                if l in (j, i):
                    continue
                term *= (0. - z[l]) / (z[j] - z[l])
            s += term
        lp[j] = s
    return np.array([(z[k + 1] - z[k]) * lp[k + 1:n + 1].sum() for k in range(n)])


def quad_inv_rows(z):                                     # x1_coeffs.cpp :33-57
    V = np.array([[1., .5 * (z[k] + z[k + 1]),
                   (z[k] ** 2 + z[k] * z[k + 1] + z[k + 1] ** 2) / 3.]
                  for k in range(3)])
    inv = np.linalg.inv(V)          # cof[j][m] / det of the C++ is inv[m][j]
    return inv[1].copy(), inv[2].copy()


def ptype_row(y):                                         # x1_coeffs.cpp :59-90
    h2 = y[3] - y[2]
    z = (np.asarray(y, float) - y[3]) / h2
    row = np.zeros(NCOEFF_WENO5)
    for r, (k0, bsign) in enumerate(zip((2, 1, 0), (1., 1., -1.))):
        nodes = z[k0:k0 + 4]
        w = primitive_row(nodes, 3)
        r1, r2 = quad_inv_rows(nodes)
        for n in range(3):
            col = k0 + n
            row[r * 5 + col] = w[n]
            row[(3 + 2 * r) * 5 + col] = 2. * r2[n]
            row[(4 + 2 * r) * 5 + col] = bsign * (2. * r2[n] - 2. * r1[n])
    a, b, c, e = -z[0], -z[1], z[4], z[5]
    row[45] = a * b / ((a + e) * (b + e))
    row[46] = a * e * (a + b + c + e) / ((a + e) * (b + e) * (a + c))
    row[47] = c * e / ((a + c) * (a + e))
    return row


def window_weno5(y):                                      # x1_coeffs.cpp :92-106
    cp = ptype_row(y)
    tmp = ptype_row(-np.asarray(y, float)[::-1])
    cm = np.empty(NCOEFF_WENO5)
    for r in range(9):
        cm[r * 5:r * 5 + 5] = tmp[r * 5:r * 5 + 5][::-1]
    cm[45:48] = tmp[45:48]
    return cm, cp


def combine_optimal(row):                                 # x1_coeffs.cpp :108-113
    return row[45] * row[0:5] + row[46] * row[5:10] + row[47] * row[10:15]


def window_cp5(y):                                        # x1_coeffs.cpp :115-120
    rm, rp = window_weno5(y)
    return combine_optimal(rm), combine_optimal(rp)


def rows(faces, kind="cp5"):                              # x1_coeffs.cpp :140-153
    f = np.asarray(faces, float)
    window = window_weno5 if kind == "weno5" else window_cp5
    out = [window(f[m:m + 6]) for m in range(len(f) - 5)]
    return np.array([o[0] for o in out]), np.array([o[1] for o in out])


def row_faces(x1f, nghost=3, wall_lo=True, wall_hi=True):  # coordinate.cpp :546-562
    v = np.asarray(x1f, float) ** 3 / 3.
    v = v.copy()
    n = v.size
    if wall_lo:
        v[:nghost] = 2. * v[nghost] - v[nghost + 1:2 * nghost + 1][::-1]
    if wall_hi:
        v[n - nghost:] = 2. * v[n - 1 - nghost] - v[n - 1 - 2 * nghost:n - 1 - nghost][::-1]
    return v


# ------------------------------------------------------------- the grids ----
def geometric(n, q, h0=1.):
    f = [0.]
    for k in range(n):
        f.append(f[-1] + h0 * q ** k)
    return np.array(f)


def cell_average(fun, a, b):
    return (GW * fun(0.5 * (a + b) + 0.5 * (b - a) * GX)).sum() / 2.


def averages(fun, faces, measure=None):
    """Cell averages of `fun` over `faces`, against d(measure) if given."""
    out = []
    for i in range(len(faces) - 1):
        a, b = faces[i], faces[i + 1]
        if measure is None:
            out.append(cell_average(fun, a, b))
        else:
            num = cell_average(lambda t: fun(t) * measure(t), a, b)
            out.append(num / cell_average(measure, a, b))
    return np.array(out)


# ------------------------------------------------------------- the claims ---
def check_C1_uniform_rows():
    """On equal widths the per-face rows are the shipped uniform weights."""
    worst_w = worst_p = worst_d = 0.
    for h in (1., 1.e-3, 7.5e3):
        f = np.arange(12) * h
        cm, cp = rows(f, "weno5")
        pm, pp = rows(f, "cp5")
        for m in range(cm.shape[0]):
            worst_w = max(worst_w,
                          np.abs(cm[m, :45].reshape(9, 5) - WENO5_CM).max(),
                          np.abs(cp[m, :45].reshape(9, 5) - WENO5_CM[:, ::-1]).max())
            worst_d = max(worst_d, np.abs(cm[m, 45:] - WENO5_D).max(),
                          np.abs(cp[m, 45:] - WENO5_D).max())
            worst_p = max(worst_p, np.abs(pm[m] - CP5_CM).max(),
                          np.abs(pp[m] - CP5_CM[::-1]).max())
    ok = worst_w < 1.e-14 and worst_p < 1.e-14 and worst_d < 1.e-15
    report("C1", ok, "equal widths give back the shipped uniform weights",
           f"max |row - shipped| weno5 {worst_w:.1e}, cp5 {worst_p:.1e}, "
           f"optimal weights (0.3, 0.6, 0.1) to {worst_d:.1e}; "
           "thresholds 1e-14, 1e-14, 1e-15 (a 48-entry row of order-1 numbers "
           "built from six divisions, so a few units in the last place)")
    return ok


def check_C2_row_sums():
    """Every candidate row and the optimal weights sum to 1 on any grid."""
    grids = {"uniform": np.arange(17.),
             "geometric q=1.05": geometric(16, 1.05),
             "geometric q=1.2": geometric(16, 1.2),
             "jump 1:4": np.concatenate([np.arange(9.), 8. + 4. * np.arange(1, 8)])}
    worst = 0.
    for name, f in grids.items():
        cm, cp = rows(f, "weno5")
        pm, pp = rows(f, "cp5")
        for m in range(cm.shape[0]):
            for t in (cm[m], cp[m]):
                for r in range(3):
                    worst = max(worst, abs(t[5 * r:5 * r + 5].sum() - 1.))
                worst = max(worst, abs(t[45:].sum() - 1.), -min(t[45:].min(), 0.))
            worst = max(worst, abs(pm[m].sum() - 1.), abs(pp[m].sum() - 1.))
    ok = worst < 1.e-14
    report("C2", ok, "candidate rows and optimal weights sum to one, weights positive",
           f"max |row sum - 1| over uniform, q = 1.05, q = 1.2 and a 1:4 jump = "
           f"{worst:.1e}; threshold 1e-14 (a sum of five rounded entries)")
    return ok


def check_C3_optimal_weights():
    """The optimal weights rebuild the five-cell row from the three candidates."""
    worst = 0.
    for q in (1.0, 1.05, 0.9408, 1.2, 0.8, 1.6):
        f = geometric(16, q)
        cm, cp = rows(f, "weno5")
        pm, pp = rows(f, "cp5")
        for m in range(cm.shape[0]):
            direct_p = primitive_row((np.asarray(f[m:m + 6]) - f[m + 3])
                                     / (f[m + 3] - f[m + 2]), 5)
            worst = max(worst, np.abs(pp[m] - direct_p).max(),
                        np.abs(combine_optimal(cp[m]) - direct_p).max(),
                        np.abs(pm[m] - combine_optimal(cm[m])).max())
    ok = worst < 1.e-13
    report("C3", ok, "the three candidates with the optimal weights are the five-cell row",
           f"max |d-combination - the six-node primitive row| over q = 0.8 to 1.6 "
           f"= {worst:.1e}; threshold 1e-13 (two nested solves of a 3x3 Vandermonde "
           "at width ratios up to 1.6^5)")
    return ok


def check_C4_exactness():
    """The cp5 row is exact for cell averages of polynomials up to degree 4."""
    f = geometric(18, 1.1, 0.37)
    pm, pp = rows(f, "cp5")
    got, worst5 = [], 0.
    for deg in range(6):
        c = np.zeros(deg + 1)
        c[deg], c[0] = 1., (1. if deg == 0 else -0.3)
        poly = np.polynomial.polynomial.Polynomial(c)
        u = averages(poly, f)
        scale = max(np.abs(u).max(), 1.)
        err = max(max(abs(pp[m] @ u[m:m + 5] - poly(f[m + 3])),
                      abs(pm[m] @ u[m:m + 5] - poly(f[m + 2])))
                  for m in range(pp.shape[0])) / scale
        got.append(err)
        if deg == 5:
            worst5 = err
    ok = max(got[:5]) < 1.e-13 < worst5
    report("C4", ok, "the cp5 row reproduces polynomial cell averages to degree 4",
           "max relative face error on 18 cells of ratio 1.1: "
           + ", ".join(f"degree {d} {e:.1e}" for d, e in enumerate(got))
           + "; exact below 1e-13 up to degree 4 and not at degree 5")
    return ok


def check_C5_volume_widths():
    """A uniform radial grid is a non-uniform grid in the volume coordinate."""
    r = np.linspace(1., 2., 13)
    h = r[1] - r[0]
    rb = 0.5 * (r[:-1] + r[1:])
    dv = np.diff(r ** 3 / 3.)
    closed = np.abs(dv - (rb * rb * h + h ** 3 / 12.)).max()
    ratio = dv[1:] / dv[:-1]
    ok = closed < 1.e-15
    report("C5", ok, "the volume width of a uniform radial cell is rb^2 h + h^3/12",
           f"max |dv - (rb^2 h + h^3/12)| = {closed:.1e} on r in [1, 2], n = 12 "
           f"(threshold 1e-15, three roundings on numbers of order 1); neighbouring "
           f"volume widths differ by {ratio.min():.3f} to {ratio.max():.3f} and the "
           f"widest is {dv.max() / dv.min():.2f} times the narrowest, while every "
           "radial width is the same")
    return ok


def check_C6_radial_order():
    """On r^2 dr averages the volume rows are fifth order, the uniform ones second."""
    fun = lambda t: 1. + 0.5 * np.sin(4. * t) * np.exp(-0.5 * t)
    ns, e_v, e_u = (32, 64, 128, 256), [], []
    for n in ns:
        f = np.linspace(1., 2., n + 1)
        u = averages(fun, f, measure=lambda t: t * t)
        _, cp = rows(f ** 3 / 3., "cp5")
        e_v.append(max(abs(cp[m] @ u[m:m + 5] - fun(f[m + 3])) for m in range(cp.shape[0])))
        e_u.append(max(abs(CP5_CM[::-1] @ u[m:m + 5] - fun(f[m + 3])) for m in range(cp.shape[0])))
    o_v = [math.log2(e_v[i] / e_v[i + 1]) for i in range(3)]
    o_u = [math.log2(e_u[i] / e_u[i + 1]) for i in range(3)]
    ok = min(o_v) > 4.9 and max(o_u) < 2.1
    report("C6", ok, "the volume coordinate restores fifth order on a uniform radial grid",
           "max face error on exact r^2 dr averages, r in [1, 2], n = 32, 64, 128, 256: "
           f"volume rows {', '.join(f'{e:.2e}' for e in e_v)} (orders "
           f"{', '.join(f'{o:.2f}' for o in o_v)}); the shipped uniform weights "
           f"{', '.join(f'{e:.2e}' for e in e_u)} (orders {', '.join(f'{o:.2f}' for o in o_u)})")
    return ok


def check_C7_wall_mirror():
    """Mirrored ghost volumes make the two one-sided wall-face states agree."""
    nghost, n = 3, 12
    r_int = np.linspace(1., 2., n + 1)
    r = np.concatenate([r_int[0] - (r_int[1:nghost + 1] - r_int[0])[::-1], r_int,
                        r_int[-1] + (r_int[-1] - r_int[-nghost - 1:-1])[::-1]])
    v = row_faces(r, nghost)
    cm, cp = rows(v, "cp5")
    # the wall face is face `nghost`: left state = cp row 0, right state = cm row 1
    row_gap = np.abs(cp[0] - cm[1][::-1]).max()
    even = lambda t: 1. + 0.3 * np.cos(2. * (t - v[nghost])) + 0.1 * (t - v[nghost]) ** 2
    odd = lambda t: np.sin(1.5 * (t - v[nghost]))
    ue = averages(even, v)
    uo = averages(odd, v)
    qL, qR = cp[0] @ ue[0:5], cm[1] @ ue[1:6]
    vL, vR = cp[0] @ uo[0:5], cm[1] @ uo[1:6]
    ok = row_gap == 0. and abs(qL - qR) < 1.e-15 and abs(vL + vR) < 1.e-15
    report("C7", ok, "mirrored ghost volumes close the wall face",
           f"the two wall-face rows are each other reversed to {row_gap:.1e} (exact: "
           f"the mirror maps one six-face window onto the other); a field even in v "
           f"about the wall gives |qL - qR| = {abs(qL - qR):.1e} and an odd one "
           f"|vL + vR| = {abs(vL + vR):.1e}, both at the 1e-15 round-off threshold "
           "of a five-term dot product of order-1 numbers")
    return ok


def main():
    checks = [check_C1_uniform_rows, check_C2_row_sums, check_C3_optimal_weights,
              check_C4_exactness, check_C5_volume_widths, check_C6_radial_order,
              check_C7_wall_mirror]
    passed = sum(bool(c()) for c in checks)
    print(f"{passed}/{len(checks)} claims pass")
    return len(checks) - passed


if __name__ == "__main__":
    sys.exit(main())
