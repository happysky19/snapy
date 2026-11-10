"""Executable check of the relative species/tracer factor (chapter 8, _theta.qmd, "Where the dry air is over-drained").

What is checked: the relaxation of the donor factor toward the dry-air factor and the share of the over-drain the
poorer neighbour repays, as HydroImpl::forward (src/hydro/hydro_forward.cpp, step 4.C) and ScalarImpl::forward
(src/scalar/scalar.cpp) apply them, and flux_positivity_share (src/hydro/flux_positivity.cpp), at
snapy@919936da07d80a310b98ab11da184972a3203274. Claims C1-C4.

  C1  with Theta = (1-eta) r rho V / D_n < 1 and Theta_d = (1-eta) rho V / D_d in (0, 1), Theta/Theta_d <= 1:
      the relaxed drain Theta' D_n equals (1-eta) r rho V + Xi r (D_d - (1-eta) rho V)            (sympy, exact)
  C2  at a uniform ratio (D_n = r D_d) and Xi = 1 the relaxed factor is 1; with Xi = 0 it is the plain factor
                                                                                                  (sympy, exact)
  C3  the explicit update is bounded below by eta u V + dt in - Xi r (D_d - (1-eta) rho V)       (sympy, exact)
  C4  a numpy port of flux_positivity_share, line for line, equals the minimum over the two neighbours along each
      resolved direction computed without wrap-around on every cell at least one cell from each array end, so the
      roll wrap reaches the first and last index only                                   (numpy, bitwise, seed 7)

The port of C4 mirrors flux_positivity.cpp lines `auto low = torch::minimum(q.roll(1, 3), q.roll(-1, 3));` to
`return torch::where(q > 0., (low / q).clamp(0., 1.), torch::zeros_like(q));`. The check imports no snapy.

Run: python3 relative_check.py   (numpy and sympy only; prints one labelled line per claim and exits with the number
of failed claims)
"""
import sys

import numpy as np
import sympy as sp


def report(tag, ok, label, numbers=""):
    print("[%s] %s %s: %s" % (tag, "PASS" if ok else "FAIL", label, numbers))
    return bool(ok)


eta, r, rho, V, Dn, Dd, Xi, dtin = sp.symbols("eta r rho V D_n D_d Xi dtin", positive=True)
theta = (1 - eta) * r * rho * V / Dn          # plain factor of species n, limited case
theta_d = (1 - eta) * rho * V / Dd            # dry-air factor, 0 < theta_d < 1
relaxed = theta + Xi * (theta / theta_d - theta)   # the code's blend where theta/theta_d <= 1 (clamp_max(1) inactive)


def check_C1_relaxed_drain():
    lhs = sp.simplify(relaxed * Dn)
    rhs = (1 - eta) * r * rho * V + Xi * r * (Dd - (1 - eta) * rho * V)
    ok = sp.simplify(lhs - rhs) == 0
    return report("C1", ok, "relaxed drain = content + Xi r (dry over-drain)", "difference simplifies to 0")


def check_C2_limits():
    uni = sp.simplify(relaxed.subs(Dn, r * Dd).subs(Xi, 1))
    plain = sp.simplify(relaxed.subs(Xi, 0) - theta)
    ok = uni == 1 and plain == 0
    return report("C2", ok, "uniform ratio with Xi = 1 gives 1; Xi = 0 gives the plain factor",
                  "relaxed = %s, relaxed - plain = %s" % (uni, plain))


def check_C3_bound():
    u = r * rho
    update = u * V - relaxed * Dn + dtin              # V (u + dt du): content - limited drain + inflow
    bound = eta * u * V + dtin - Xi * r * (Dd - (1 - eta) * rho * V)
    ok = sp.simplify(update - bound) == 0
    return report("C3", ok, "V(u + dt du) = eta u V + dt in - Xi r (D_d - (1-eta) rho V)", "equality, so >= holds")


def share_port(q):
    """flux_positivity_share, axes (chan, x3, x2, x1) = (0, 1, 2, 3)."""
    low = np.minimum(np.roll(q, 1, 3), np.roll(q, -1, 3))
    for dim in (2, 1):
        if q.shape[dim] > 1:
            low = np.minimum(low, np.minimum(np.roll(q, 1, dim), np.roll(q, -1, dim)))
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(q > 0., np.clip(low / q, 0., 1.), np.zeros_like(q))


def share_direct(q, k, j, i):
    """min over the two neighbours along every resolved direction, no wrap; cell (k, j, i) away from the ends."""
    nbr = [q[:, k, j, i - 1], q[:, k, j, i + 1]]
    if q.shape[2] > 1:
        nbr += [q[:, k, j - 1, i], q[:, k, j + 1, i]]
    if q.shape[1] > 1:
        nbr += [q[:, k - 1, j, i], q[:, k + 1, j, i]]
    low = np.min(np.stack(nbr), axis=0)
    c = q[:, k, j, i]
    return np.where(c > 0., np.clip(low / np.where(c > 0., c, 1.), 0., 1.), 0.)


def check_C4_share_port():
    rng = np.random.default_rng(7)
    shapes = [(2, 1, 1, 9), (2, 1, 7, 9), (3, 6, 7, 9)]
    cells, bad, edge_diff = 0, 0, 0
    for shp in shapes:
        q = rng.uniform(-0.2, 1.0, shp)
        got = share_port(q)
        n3, n2, n1 = shp[1], shp[2], shp[3]
        ks = range(1, n3 - 1) if n3 > 1 else [0]
        js = range(1, n2 - 1) if n2 > 1 else [0]
        for k in ks:
            for j in js:
                for i in range(1, n1 - 1):
                    cells += 1
                    if not np.array_equal(got[:, k, j, i], share_direct(q, k, j, i)):
                        bad += 1
        # the wrap does reach the end cells: count where the end cells differ from a no-wrap (edge-only) minimum
        qe = np.concatenate([q[..., :1] * 0 + np.inf, q, q[..., -1:] * 0 + np.inf], axis=3)
        lo = np.minimum(qe[..., :-2], qe[..., 2:])[..., [0, -1]]
        edge_diff += int(np.sum(lo != np.minimum(np.roll(q, 1, 3), np.roll(q, -1, 3))[..., [0, -1]]))
    ok = bad == 0 and cells > 0
    return report("C4", ok, "share port equals the no-wrap neighbour minimum away from the array ends",
                  "%d cells (all channels) compared over 3 shapes, %d mismatches; %d end-cell x1 entries where the "
                  "wrap changes the minimum" % (cells, bad, edge_diff))


def main():
    results = [check_C1_relaxed_drain(), check_C2_limits(), check_C3_bound(), check_C4_share_port()]
    return sum(1 for ok in results if not ok)


if __name__ == "__main__":
    sys.exit(main())
