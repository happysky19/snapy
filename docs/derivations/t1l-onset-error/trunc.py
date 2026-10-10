"""Closed-form truncation of each discrete ingredient (sympy)."""
import sympy as sp

h, z = sp.symbols('h z', positive=True)
f = sp.Function('f')
NT = 8


def expand_op(weights, offsets, order=NT):
    """sum_k w_k f(z + off_k h) as a series in h."""
    e = sum(sp.nsimplify(w) * f(z + sp.nsimplify(o) * h) for w, o in zip(weights, offsets))
    return sp.series(e, h, 0, order).removeO().expand()


def rel(expr, target):
    return sp.simplify(sp.expand(expr - target))


print("== 1. binomial smoothing (1,4,6,4,1)/16, W off  [hydro_ref_x1_impl.h:77]")
b = [sp.Rational(c, 16) for c in (1, 4, 6, 4, 1)]
e = expand_op(b, [-2, -1, 0, 1, 2])
print("   S[f] - f =", sp.simplify(e - f(z)))

print("== 2. fourth-order filter (-1,4,10,4,-1)/16, W on  [wb_ref4.cpp:124]")
b = [sp.Rational(c, 16) for c in (-1, 4, 10, 4, -1)]
e = expand_op(b, [-2, -1, 0, 1, 2])
print("   F[f] - f =", sp.simplify(e - f(z)))

print("== 3. cell-average operator  <f>_i")
avg = sp.series(sp.integrate(f(z + h * sp.Symbol('t')), (sp.Symbol('t'), sp.Rational(-1, 2), sp.Rational(1, 2))), h, 0, NT)
print("   <f> - f =", sp.simplify(avg.removeO() - f(z)))

print("== 4. half-sum of neighbours at a face: 0.5(q(z-h/2)+q(z+h/2))")
e = expand_op([sp.Rational(1, 2)] * 2, [sp.Rational(-1, 2), sp.Rational(1, 2)])
print("   err =", sp.simplify(e - f(z)))

print("== 5. w6 cell quadrature from six faces [hydro_ref_x1_impl.h:111]")
w6 = [sp.Rational(11, 1440), sp.Rational(-31, 480), sp.Rational(401, 720),
      sp.Rational(401, 720), sp.Rational(-31, 480), sp.Rational(11, 1440)]
offs = [sp.Rational(-5, 2), sp.Rational(-3, 2), sp.Rational(-1, 2),
        sp.Rational(1, 2), sp.Rational(3, 2), sp.Rational(5, 2)]
e = expand_op(w6, offs)
print("   w6[f_faces] - <f>_cell =", sp.simplify(e - avg.removeO()))

print("== 6. A4 face value (-1,7,7,-1)/12 of a cell-average field [wb_ref4.cpp:199]")
a4 = [sp.Rational(-1, 12), sp.Rational(7, 12), sp.Rational(7, 12), sp.Rational(-1, 12)]
# cells f-2,f-1,f,f+1 have centres at -3h/2, -h/2, +h/2, +3h/2 relative to the face
g = sp.Function('g')


def avg_at(c):
    t = sp.Symbol('t')
    return sp.series(sp.integrate(f(z + c * h + h * t), (t, sp.Rational(-1, 2), sp.Rational(1, 2))), h, 0, NT).removeO()


e = sum(a * avg_at(c) for a, c in zip(a4, [sp.Rational(-3, 2), sp.Rational(-1, 2),
                                           sp.Rational(1, 2), sp.Rational(3, 2)]))
print("   A4[<f>] - f(face) =", sp.simplify(sp.expand(e) - f(z)))

print("== 7. Center5 right state at the face, from cell averages [cp5.cpp:13]")
c5 = [sp.Rational(-1, 20), sp.Rational(9, 20), sp.Rational(47, 60), sp.Rational(-13, 60), sp.Rational(1, 30)]
e = sum(a * avg_at(c) for a, c in zip(c5, [sp.Rational(-3, 2), sp.Rational(-1, 2), sp.Rational(1, 2),
                                           sp.Rational(3, 2), sp.Rational(5, 2)]))
print("   C5[<f>] - f(face) =", sp.simplify(sp.expand(e) - f(z)))

print("== 8. face gravity work, interior cell  [hydro_forward.cpp:742-800]")
# booking = -(M_lo + M_hi)/2 + (1/12)(m_{i+1} - 2 m_i + m_{i-1});  target = -<m>_i
m = f
face_avg = sp.Rational(1, 2) * (avg_at(0) * 0)      # placeholder
Mlo = sp.series(f(z - h / 2), h, 0, NT).removeO()
Mhi = sp.series(f(z + h / 2), h, 0, NT).removeO()
cell = [avg_at(c) for c in (-1, 0, 1)]
book = -(Mlo + Mhi) / 2 + sp.Rational(1, 12) * (cell[2] - 2 * cell[1] + cell[0])
print("   book + <m> =", sp.simplify(sp.expand(book + avg_at(0))))

print("== 9. face gravity work, BOTTOM wall cell (wall curvature flux zeroed)")
book_w = -(Mlo + Mhi) / 2 + sp.Rational(1, 12) * (cell[2] - cell[1])
print("   book + <m> =", sp.simplify(sp.expand(book_w + avg_at(0))))

print("== 10. face gravity work, TOP wall cell")
book_t = -(Mlo + Mhi) / 2 - sp.Rational(1, 12) * (cell[1] - cell[0])
print("   book + <m> =", sp.simplify(sp.expand(book_t + avg_at(0))))

print("== 11. centred second difference used by the diffusion (face normal derivative)")
d = (f(z + h / 2) - f(z - h / 2)) / h
print("   err =", sp.simplify(sp.series(d, h, 0, 6).removeO() - sp.diff(f(z), z)))

print("== 12. centred x-derivative (2 h) used by div(v) and the covariance D1")
d = (f(z + h) - f(z - h)) / (2 * h)
print("   err =", sp.simplify(sp.series(d, h, 0, 6).removeO() - sp.diff(f(z), z)))
