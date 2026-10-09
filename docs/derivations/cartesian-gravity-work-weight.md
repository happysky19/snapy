# Face-form gravitational work in a plane-parallel finite-volume column

Independent derivation, Cartesian (plane-parallel) geometry, two solid walls.
Parts 1–3 were written and verified before any other derivation of this problem
was read.

Companion script: `gravity_work_weight_check.py` (numpy + sympy, no snapy
dependency).

---

## 0. Setting, symbols, conventions

| symbol | meaning |
|---|---|
| $z$ | vertical coordinate, increasing **upward** |
| $g>0$ | constant gravitational acceleration magnitude |
| $\Phi(z)=g\,z$ | geopotential; the body force per unit mass is $-\partial_z\Phi=-g$ |
| $[z_L,z_R]$ | the column, closed by solid walls at both ends |
| $N$ | number of cells, $h=(z_R-z_L)/N$ the uniform cell height |
| $i=1\ldots N$ | cell index; cell $i$ is $[z_{i-1/2},z_{i+1/2}]$, $z_{j+1/2}=z_L+jh$ |
| $z_i=\tfrac12(z_{i-1/2}+z_{i+1/2})$ | cell centre $=$ cell centroid (slab geometry) |
| $j+1/2$, $j=0\ldots N$ | face index; $j=0$ and $j=N$ are the two **wall faces** |
| $\rho_i,\ (\rho w)_i,\ E_i$ | **cell averages** of density, momentum, total energy |
| $E=\rho e+\tfrac12\rho w^2$ | total energy **excluding** potential energy |
| $m(z)=\rho w$ | mass flux density of the exact solution |
| $m_{j+1/2}$ | the numerical face mass flux used by the discrete continuity equation |
| $V_i=h$ | cell volume per unit cross-section |

Per unit cross-sectional area the 1-D equations are

$$\partial_t\rho+\partial_z(\rho w)=0,\qquad
\partial_t(\rho w)+\partial_z(\rho w^2+p)=-\rho\,\partial_z\Phi,$$
$$\partial_t E+\partial_z\big[(E+p)w\big]=-\rho w\,\partial_z\Phi=-g\,m .$$

**Wall conditions.** No mass flux through the bottom face of cell 1 or the top
face of cell $N$:
$$m_{1/2}=m_{N+1/2}=0 ,$$
and the same holds for the *exact* solution, $m(z_L)=m(z_R)=0$. The energy flux
also vanishes there (no mass flux, and $w=0$ so the pressure does no work); the
momentum flux at a wall is the wall pressure.

**Target.** The quantity that the energy update should book in cell $i$ is the
exact cell average of the gravitational work,
$$\boxed{\;S_i\;=\;-\frac{1}{V_i}\int_{z_{i-1/2}}^{z_{i+1/2}}\rho w\,g\;dz
\;=\;-\frac{g}{h}\int_{z_{i-1/2}}^{z_{i+1/2}} m(z)\,dz\;}$$

**Face form.** The scheme instead books a linear combination of the *face* mass
fluxes weighted by a face quantity,
$$W_i=-g\sum_{j} c_{ij}\,m_{j+1/2},\qquad \sum_j c_{ij}=1 \ \ (\text{consistency}).$$

**Isolation of the booking error.** Throughout parts 1 and 2 we set
$m_{j+1/2}=m(z_{j+1/2})$ exactly. The error of the Riemann solver that produces
$m_{j+1/2}$ is a separate, additive contribution and is not the subject here;
what is measured is the error of the *booking*, i.e. of replacing the cell
average of $\rho w g$ by a face-weighted combination.

**Notation for the expansions.** $m^{(k)}$ denotes $\mathrm d^k m/\mathrm dz^k$;
all series are about the point named in each statement.

### 0.1 The two Cartesian variants of the "curvature flux" $H$

In curved geometry the booked work is usually written as a face-flux difference
plus a correction flux $H$ that accounts for the mismatch between a *volume
average* and a *face-centroid* weighting. In Cartesian geometry the name is
ambiguous, so both readings are carried through and labelled.

Start from the exact identity
$$\rho w\,\partial_z\Phi=\partial_z(\Phi\,\rho w)-\Phi\,\partial_z(\rho w)
=\partial_z(\Phi m)+\Phi\,\partial_t\rho ,$$
so that
$$S_i=-\frac1h\Big[\Phi_{i+1/2}m_{i+1/2}-\Phi_{i-1/2}m_{i-1/2}\Big]
-\overline{\big(\Phi\,\partial_t\rho\big)}_i , \tag{0.1}$$
where the overbar is the cell average and $\Phi_{j+1/2}=\Phi(z_{j+1/2})$.

**Variant A — the plain face form.** Replace the cell average of the product
$\Phi\,\partial_t\rho$ by the product of the cell-centre value of $\Phi$ with
the cell average of $\partial_t\rho$ (the latter being exactly the discrete
continuity residual):
$$W_i^{A}=-\frac1h\Big[\Phi_{i+1/2}m_{i+1/2}-\Phi_{i-1/2}m_{i-1/2}\Big]
+\Phi_i\,\frac{m_{i+1/2}-m_{i-1/2}}{h} .$$
With $\Phi=gz$ one has $\Phi_{i\pm1/2}-\Phi_i=\pm gh/2$, hence the familiar
half-and-half face weighting
$$\boxed{\;W_i^{A}=-\frac{g}{2}\big(m_{i+1/2}+m_{i-1/2}\big)\;}\tag{A}$$
i.e. "face gravity times weight $1/2$ on each face". This is what is meant below
by *the plain face form*, *without* $H$.

Two remarks that matter for the Cartesian case.

* The *geometric* correction that is often called the curvature term, namely
  the difference between the **volume-averaged** geopotential
  $\bar\Phi_i=\frac1h\int_{\rm cell}\Phi\,dz$ and the **centroid** value
  $\Phi(z_i)$, is **identically zero** in Cartesian geometry: $\Phi$ is linear
  in $z$ and the slab centroid is the cell centre, so $\bar\Phi_i=\Phi(z_i)$
  exactly, for every $h$. Any Cartesian "curvature flux" defined as
  $\propto(\bar\Phi_i-\Phi(z_i))$ vanishes and changes nothing.
* The correction that does *not* vanish is the one visible in (0.1): the cell
  average of the **product** $\Phi\,\partial_t\rho$ is not the product of the
  averages. With $\overline{fg}=\bar f\bar g+\frac{h^2}{12}f'g'+O(h^4)$ and
  $\partial_t\rho=-\partial_z m$,
  $$\overline{\Phi\,\partial_t\rho}_i-\Phi_i\,\overline{\partial_t\rho}_i
  =\frac{h^2}{12}\,\Phi'(z_i)\,(\partial_t\rho)'(z_i)+O(h^4)
  =-\frac{g h^2}{12}\,m''(z_i)+O(h^4). \tag{0.2}$$
  This *is* the Cartesian "cell-average versus face-centroid weighting"
  correction, and it is non-zero.

**Variant B — face form plus the geometric correction flux $H$.** Write (0.2) as
a difference of face quantities and add it to (A):
$$\boxed{\;W_i^{B}=W_i^{A}+\frac1h\big(H_{i+1/2}-H_{i-1/2}\big),\qquad
H_{j+1/2}=\frac{g h^{2}}{12}\,\delta m_{j+1/2},\quad
\delta m_{j+1/2}\simeq \partial_z m\big|_{z_{j+1/2}} .}\tag{B}$$
In the interior, the centred two-point face derivative is used,
$$\delta m_{j+1/2}=\frac{m_{j+3/2}-m_{j-1/2}}{2h}\qquad (1\le j\le N-1),$$
which is available at every face except the two wall faces. Substituting it into
(B) gives the equivalent symmetric four-point face stencil
$$W_i^{B}=-g\Big[\tfrac{13}{24}\big(m_{i+1/2}+m_{i-1/2}\big)
-\tfrac{1}{24}\big(m_{i+3/2}+m_{i-3/2}\big)\Big],\qquad
\tfrac{13}{24}+\tfrac{13}{24}-\tfrac1{24}-\tfrac1{24}=1. \tag{B'}$$

What to do with $H$ at the two **wall faces** is exactly the question of
part 1(b,c) and part 2. Three closures are studied:

* **B0** — $H_{1/2}=H_{N+1/2}=0$ ("no flux through a wall"), the naive closure;
* **B1** — $\delta m$ at a wall face from the third-order one-sided difference
  $\delta m_{1/2}=\frac1h\big(-\tfrac{11}{6}m_{1/2}+3m_{3/2}-\tfrac32 m_{5/2}+\tfrac13 m_{7/2}\big)$;
* **W4** — the ghost-face closure of part 2.

---

## PART 1. Truncation error of the booked face-form work

All expansions below were produced by hand and then verified in exact rational
arithmetic with sympy (`taylor_coefficients()` in the script); the printed
coefficients agree with every number quoted here.

### 1.0 The two elementary expansions

About the cell centre $z_i$, with $\mu_k=m(z_i+kh)$,
$$\tfrac12\big(\mu_{1/2}+\mu_{-1/2}\big)=m+\frac{h^2}{8}m''+\frac{h^4}{384}m''''+O(h^6),$$
$$\frac1h\int_{z_i-h/2}^{z_i+h/2}\!\!m\,dz=m+\frac{h^2}{24}m''+\frac{h^4}{1920}m''''+O(h^6).$$

### 1(a) Interior cell

**Without $H$ (variant A).** Subtracting the two series,
$$\boxed{\;W_i^{A}-S_i=-\frac{g h^{2}}{12}\,m''(z_i)
\;-\;\frac{g h^{4}}{480}\,m''''(z_i)+O(h^{6})\;}$$
because $\tfrac18-\tfrac1{24}=\tfrac1{12}$ and $\tfrac1{384}-\tfrac1{1920}=\tfrac1{480}$.
**Second order.** (The same coefficient follows from (0.2), as it must.)

**With $H$ (variant B).** Two sub-cases, depending on how $\delta m$ is formed.

*Exact face derivative*, $H_{j+1/2}=\frac{gh^2}{12}m'(z_{j+1/2})$:
$$W_i^{B}-S_i=+\frac{g h^{4}}{720}\,m''''(z_i)+O(h^{6}).$$

*Centred discrete face derivative*, i.e. the stencil (B′):
$$\boxed{\;W_i^{B}-S_i=+\frac{11\,g h^{4}}{720}\,m''''(z_i)+O(h^{6})\;}$$
**Fourth order.** The factor 11 is the price of the $O(h^2)$ error
$\frac{h^2}{6}m'''$ of the centred two-point face derivative; because that error
is a smooth function of the face position it survives the flux difference only
at $O(h^4)$, so the order is not degraded.

### 1(b) Bottom wall cell $i=1$

Here $m_{1/2}=0$, and this is also the exact value $m(z_L)=0$, so the
expansions above are still legitimate term by term.

**Without $H$.** The formula (A) is unchanged, $W_1^{A}=-\frac g2 m_{3/2}$, and
expanding about the wall face $z_{1/2}=z_L$,
$$\boxed{\;W_1^{A}-S_1=-\frac{g h^{2}}{12}\,m''(z_L)+O(h^{3})\;}$$
**Second order — the same order and the same coefficient as the interior.** The
wall does not degrade the plain face form, because the only thing the wall does
is set one face flux to zero, which is also the true value there.

**With $H$ and the naive closure B0** ($H_{1/2}=0$). The correct value of the
wall curvature flux is $\frac{gh^2}{12}m'(z_L)$, and $m'(z_L)\neq0$ in general
even though $m(z_L)=0$ (indeed $m'=-\partial_t\rho\neq0$ at a wall). Replacing
it by zero leaves the residue $+\frac1h H^{\rm true}_{1/2}$:
$$\boxed{\;W_1^{B0}-S_1=+\frac{g h}{12}\,m'(z_L)+O(h^{2})\;}$$
**First order.**

**With $H$ and closure B1** (third-order one-sided $\delta m_{1/2}$):
$$W_1^{B1}-S_1=+\frac{g h^{3}}{72}\,m'''(z_L)+O(h^{4}).$$
Third, not fourth order: the one-sided formula has an error of a *different
functional form* from the $\frac{h^2}{6}m'''$ error carried by the centred
formula at the neighbouring face $z_{3/2}$, so the two no longer cancel in the
flux difference.

**With $H$ and closure W4** (part 2): $-\dfrac{19\,g h^{4}}{720}m''''(z_L)+O(h^5)$,
fourth order.

### 1(c) Top wall cell $i=N$

By the mirror of 1(b) (the stencil reflects, $\int$ reflects, and the sign of the
odd-derivative term flips):

* without $H$: $\;W_N^{A}-S_N=-\dfrac{g h^{2}}{12}m''(z_R)+O(h^{3})$, second order;
* with $H$, closure B0: $\;W_N^{B0}-S_N=-\dfrac{g h}{12}m'(z_R)+O(h^{2})$, first order;
* with $H$, closure B1: $\;-\dfrac{g h^{3}}{72}m'''(z_R)+O(h^4)$;
* with $H$, closure W4: $\;-\dfrac{19\,g h^{4}}{720}m''''(z_R)+O(h^5)$, fourth order.

### 1(d) Is the booking first order at the walls? — explicit answer

> **Without the curvature flux (the plain face form A): NO.** The booking is
> second order at the bottom and top wall cells, with exactly the same leading
> coefficient $-\frac{gh^2}{12}m''$ as in the interior. The wall is not a
> special point for variant A.
>
> **With the curvature flux and the naive wall closure $H_{\rm wall}=0$ (B0):
> YES.** It is first order in the two wall cells, with leading error
> $+\frac{gh}{12}m'(z_L)$ at the bottom and $-\frac{gh}{12}m'(z_R)$ at the top,
> while remaining fourth order in every other cell. Adding the curvature flux
> and then zeroing it at the walls therefore *lowers* the wall-cell order from
> two to one.

Two caveats worth recording, because they are easy ways to really get a
first-order wall and are sometimes confused with the above.

1. If a code drops the wall face from the average instead of using
   $m_{\rm wall}=0$ — i.e. books $W_1=-g\,m_{3/2}$ (weight 1 instead of $1/2$)
   — the error is $-\frac{gh}{2}m'(z_1)+O(h^2)$, first order, and the booking
   is also no longer consistent ($\sum_j c_{1j}\ne 1$ in the sense required by
   §2.1). This is a bug, not a property of the face form.
2. If the discrete wall mass flux is not exactly zero (e.g. extrapolated), the
   statement in 1(b) fails, because the expansion there uses $m_{1/2}=m(z_L)=0$.

---

## PART 2. A booking that is exactly conservative **and** $O(h^4)$ everywhere

### 2.1 The exact discrete conservation condition

Let the discrete potential energy be the linear functional
$$P[\rho]=h\sum_{i=1}^{N}\rho_i\,\tilde\Phi_i ,$$
with discrete geopotential values $\tilde\Phi_i$ still to be chosen. Discrete
continuity with the *same* face fluxes that the booking uses,
$\dot\rho_i=-\frac1h(m_{i+1/2}-m_{i-1/2})$, and $m_{1/2}=m_{N+1/2}=0$, give by
summation by parts
$$\dot P=-\sum_{i=1}^{N}\tilde\Phi_i\big(m_{i+1/2}-m_{i-1/2}\big)
=\sum_{j=1}^{N-1}m_{j+1/2}\,\Delta\tilde\Phi_j,\qquad
\Delta\tilde\Phi_j:=\tilde\Phi_{j+1}-\tilde\Phi_j . \tag{2.1}$$
The advective and pressure fluxes in the energy equation telescope to zero in a
closed column, so
$$\frac{d}{dt}\Big[h\sum_i E_i+P\Big]=h\sum_i W_i+\dot P .$$

> **Condition (C).** Writing $W_i=-g\sum_j c_{ij}m_{j+1/2}$ and $T_j:=\sum_i c_{ij}$,
> the booking conserves $\sum_i hE_i+P$ **exactly**, for arbitrary face mass
> fluxes, if and only if
> $$\Delta\tilde\Phi_j=g h\,T_j\qquad\text{for every interior face } j=1,\dots,N-1. \tag{C}$$

The weights on the two wall faces are unconstrained, because $m=0$ there. Note
that because $P$ is *linear* in $\rho$, (C) makes the balance exact for **any**
time integrator and any step size, not merely in the semi-discrete limit:
$P^{n+1}-P^n=h\sum_i\tilde\Phi_i(\rho_i^{n+1}-\rho_i^n)$ requires no expansion.

Two immediate consequences.

* With the plain potential $\tilde\Phi_i=\Phi_i=g z_i$, (C) reads $T_j=1$ for
  every interior face: **every face must receive total weight exactly one when
  the rows are summed.** Variant A satisfies this ($\tfrac12+\tfrac12$), and so
  does the symmetric interior stencil (B′) ($\tfrac{13}{24}+\tfrac{13}{24}-\tfrac1{24}-\tfrac1{24}$).
* Closure B0 is exactly conservative with $\tilde\Phi_i=\Phi_i$ as well, since
  $H$ telescopes and vanishes at both walls. It is the *accuracy* at the wall,
  not the conservation, that B0 sacrifices — and §2.2 shows that this sacrifice
  is unavoidable as long as $\tilde\Phi_i=\Phi_i$.

### 2.2 Why the interior formula fails at the wall, and an obstruction theorem

The interior stencil (B′) applied to cell 1 needs the face $z_{-1/2}$, which
does not exist; applied to cell 2 it needs $z_{1/2}$, which does exist (and
carries the value 0). **So only rows $1$ and $N$ need modification**, not rows 2
and $N-1$.

The natural fix — choose for row 1 the unique four-point quadrature on the
available faces $z_{1/2},z_{3/2},z_{5/2},z_{7/2}$ that is exact for cubics — is
fourth order, but its column sums are $T_1=\tfrac{31}{24}$, $T_2=\tfrac56$,
$T_3=\tfrac{25}{24}$, not $1$. So it is **not** conservative against
$\tilde\Phi_i=\Phi_i$. This is not an accident:

> **Proposition (wall obstruction).** Let the booking use the symmetric
> four-point interior stencil (B′) in all cells $i>K$ (for some fixed $K\ge1$),
> let rows $1,\dots,K$ be arbitrary face-weighted rows, and let the booking be
> exactly conservative with the plain potential $\tilde\Phi_i=g z_i$. Then
> $$\sum_{i=1}^{K}\big(W_i-S_i\big)=+\frac{g h}{12}\,m'(z_L)+O(h^{2}),$$
> so at least one of the first $K$ cells carries an $O(h)$ error, for **every**
> $K$ and every choice of the wall rows.

*Proof.* Conservation forces $T_j=1$ for all interior faces $j$. The rows
$i>K$ are known, so the partial column sums $C_j:=\sum_{i\le K}c_{ij}$ over the
modified block are determined:
$$C_j=1\ (1\le j\le K-2),\quad C_{K-1}=\tfrac{25}{24},\quad C_K=\tfrac12,\quad
C_{K+1}=-\tfrac1{24},\quad C_j=0\ (j\ge K+2),$$
with $C_0$ (the wall face) free. The block booking error is
$$\sum_{i\le K}(W_i-S_i)=-g\Big[\sum_{j\ge0}C_j\,m(z_{j+1/2})
-\frac1h\int_{z_L}^{z_L+Kh}\! m\,dz\Big].$$
Put $s=(z-z_L)/h$ and expand $m$ about the wall. The $m(z_L)$ term drops
($m(z_L)=0$, which is also why $C_0$ is irrelevant). The coefficient of
$h\,m'(z_L)$ is
$$\sum_{j\ge1}C_j\,j-\int_0^K\! s\,ds
=\frac{(K-2)(K-1)}{2}+\frac{25(K-1)}{24}+\frac K2-\frac{K+1}{24}-\frac{K^2}{2}
=-\frac1{12}$$
independently of $K$. Hence the block error is $+\frac{gh}{12}m'(z_L)+O(h^2)$. $\square$

The case $K=1$ of the proposition *is* closure B0: its row 1 has
$C_1=\tfrac12,\ C_2=-\tfrac1{24}$, and its wall error $+\frac{gh}{12}m'(z_L)$ of
part 1(b) is exactly the obstruction constant. **The first-order wall error of
the naive curvature-flux closure is therefore not a careless choice of stencil;
it is forced by exact conservation against the plain discrete potential
$h\sum_i\rho_i g z_i$.** Widening the modified block does not help; the only way
out is to change $P$.

### 2.3 The construction

**(W) The work term.** Use (B) at every face, and close the two wall faces by a
**ghost face**: extrapolate $m$ to the non-existent face $z_{-1/2}=z_L-h$ with
the cubic through the four available faces,
$$m_{-1/2}^{\rm ext}:=4m_{1/2}-6m_{3/2}+4m_{5/2}-m_{7/2},$$
and then form the *same* centred derivative as everywhere else,
$$\delta m_{1/2}=\frac{m_{3/2}-m_{-1/2}^{\rm ext}}{2h},\qquad
\delta m_{N+1/2}=\frac{m_{N+3/2}^{\rm ext}-m_{N-1/2}}{2h},\quad
m_{N+3/2}^{\rm ext}:=4m_{N+1/2}-6m_{N-1/2}+4m_{N-3/2}-m_{N-5/2}.$$
Because every face then uses the *same* formula up to an $O(h^4)$ extrapolation
error, the $O(h^2)$ parts of the face-derivative errors still cancel in the flux
difference, which is precisely what closure B1 failed to achieve.

Written out as face weights (using $m_{1/2}=m_{N+1/2}=0$), the scheme is

$$\boxed{
\begin{aligned}
W_i&=-g\Big[\tfrac{13}{24}\big(m_{i+1/2}+m_{i-1/2}\big)
      -\tfrac1{24}\big(m_{i+3/2}+m_{i-3/2}\big)\Big], & 2\le i\le N-1,\\[2pt]
W_1&=-g\Big[\tfrac38 m_{1/2}+\tfrac{19}{24}m_{3/2}-\tfrac5{24}m_{5/2}+\tfrac1{24}m_{7/2}\Big],\\[2pt]
W_N&=-g\Big[\tfrac38 m_{N+1/2}+\tfrac{19}{24}m_{N-1/2}-\tfrac5{24}m_{N-3/2}+\tfrac1{24}m_{N-5/2}\Big].
\end{aligned}}\tag{W}$$

The wall rows came out *identical* to the unique four-point quadrature of
§2.2 that is exact for cubics — the ghost-face closure and the one-sided
quadrature are the same object. Row sums are $1$ in every row
($\tfrac38+\tfrac{19}{24}-\tfrac5{24}+\tfrac1{24}=1$).

**(P) The discrete potential energy.** The column sums of (W) are
$$T_1=T_{N-1}=\tfrac{31}{24},\qquad T_2=T_{N-2}=\tfrac56,\qquad
T_3=T_{N-3}=\tfrac{25}{24},\qquad T_j=1 \text{ otherwise.}$$
Integrating (C), $\Delta\tilde\Phi_j=gh\,T_j$, outward from the interior (where
$\tilde\Phi_i=gz_i$) gives $\tilde\Phi_i=g z_i+\varepsilon_i$ with
$$\boxed{\;\varepsilon_1=-\frac{gh}{6},\quad
\varepsilon_2=+\frac{gh}{8},\quad
\varepsilon_3=-\frac{gh}{24},\quad
\varepsilon_{N}=+\frac{gh}{6},\quad
\varepsilon_{N-1}=-\frac{gh}{8},\quad
\varepsilon_{N-2}=+\frac{gh}{24},\;}$$
and $\varepsilon_i=0$ for $4\le i\le N-3$. Equivalently $\tilde\Phi_i=g\tilde z_i$
with shifted lever arms $\tilde z_1=z_1-\tfrac h6$, $\tilde z_2=z_2+\tfrac h8$,
$\tilde z_3=z_3-\tfrac h{24}$ (mirrored at the top). So
$$\boxed{\;P[\rho]=h\sum_{i=1}^{N}\rho_i\,\tilde\Phi_i\;}$$
$P$ is unique up to an additive multiple of the (conserved) total mass. The
construction requires $N\ge 7$ so that the two wall blocks do not overlap.

### 2.4 Proof of (i): exact conservation

By construction $\Delta\tilde\Phi_j=gh\,T_j$ for every interior face, which is
condition (C); hence with the forward-Euler (or any) update
$$\rho_i^{n+1}=\rho_i^{n}-\frac{\Delta t}{h}\big(m_{i+1/2}-m_{i-1/2}\big),\qquad
E_i^{n+1}=E_i^{n}-\frac{\Delta t}{h}\big(F_{i+1/2}-F_{i-1/2}\big)+\Delta t\,W_i,$$
with $F_{1/2}=F_{N+1/2}=0$,
$$h\sum_i\big(E_i^{n+1}-E_i^{n}\big)=\Delta t\,h\sum_i W_i
=-\Delta t\sum_{j=1}^{N-1}m_{j+1/2}\,gh\,T_j,$$
$$P^{n+1}-P^{n}=h\sum_i\tilde\Phi_i\big(\rho_i^{n+1}-\rho_i^n\big)
=\Delta t\sum_{j=1}^{N-1}m_{j+1/2}\,\Delta\tilde\Phi_j
=+\Delta t\sum_{j=1}^{N-1}m_{j+1/2}\,gh\,T_j .$$
The two cancel identically, term by term in $j$, for arbitrary $m_{j+1/2}$,
arbitrary $\Delta t$ and arbitrary state: the residual is zero in exact
arithmetic and at round-off level in floating point. $\square$

Note what is *not* needed: no property of the Riemann solver, no hydrostatic
balance, no smoothness. The only requirements are that the booking use the same
face mass fluxes as the continuity update and that the wall mass fluxes vanish.
(The momentum source $-\rho_i g$ does not enter this budget: in the total-energy
formulation the gravitational source of $E$ is $-\rho w g$ in full, and the
kinetic-energy exchange is internal to $E$.)

### 2.5 Proof of (ii): $O(h^4)$ everywhere

*Interior cells $2\le i\le N-1$.* Here (W) is the stencil (B′) and part 1(a)
gives $W_i-S_i=+\frac{11gh^4}{720}m''''(z_i)+O(h^6)$. Cell 2 and cell $N-1$ are
included: their stencils reach only faces that exist, and in particular they do
**not** use the wall curvature flux, so no closure enters them.

*Wall cells.* Row 1 of (W) is the four-point rule on $s=0,1,2,3$ (with
$s=(z-z_L)/h$) that is exact for cubics, so its error is governed by the fourth
moment:
$$\sum_{k=0}^{3}c_{1k}\frac{k^4}{24}-\int_0^1\frac{s^4}{24}ds
=\frac1{24}\Big(\frac{19-80+81}{24}-\frac15\Big)=\frac{19}{720},$$
hence
$$W_1-S_1=-\frac{19\,g h^{4}}{720}\,m''''(z_L)+O(h^{5}),$$
and the mirror image for cell $N$. **Fourth order in every cell.** $\square$

Seen through (B), the same statement reads: the ghost-face extrapolation errs by
$m^{(4)}h^4+O(h^5)$, which enters $H_{1/2}$ at $O(h^5)$ and therefore $W_1$ at
$O(h^4)$ — whereas the naive closure B0 errs in $H_{1/2}$ at $O(h^2)$ and so in
$W_1$ at $O(h)$, and the one-sided closure B1 errs at $O(h^3)$ in $W_1$ because
its error has the wrong functional form to cancel against the neighbouring face.

### 2.6 The modified potential is *more* accurate, not less

The $O(h)$ shifts $\varepsilon_i$ look alarming, but they improve $P$. For cell
averages $\rho_i$ of a smooth $\rho$,
$$\int_{z_L}^{z_R}\!\rho\,\Phi\,dz-h\sum_i\rho_i\Phi_i
=\sum_i h\cdot\frac{h^2}{12}\rho'(z_i)\Phi'(z_i)+O(h^4)
=\frac{g h^{2}}{12}\big[\rho(z_R)-\rho(z_L)\big]+O(h^{4}),$$
so the plain $P_0=h\sum_i\rho_i g z_i$ is only second-order accurate, with the
error living entirely at the two boundaries. Meanwhile, expanding
$\rho_1,\rho_2,\rho_3$ about $z_L$,
$$h\sum_i\rho_i\varepsilon_i\Big|_{\rm bottom}
=g h^{2}\Big[-\tfrac16\rho_1+\tfrac18\rho_2-\tfrac1{24}\rho_3\Big]
=-\frac{g h^{2}}{12}\rho(z_L)+O(h^{4}),$$
because the weights satisfy $-\tfrac16+\tfrac18-\tfrac1{24}=-\tfrac1{12}$ *and*
$-\tfrac1{12}+\tfrac3{16}-\tfrac5{48}=0$ (the first moment vanishes). With the
mirrored top block, $P=P_0+\frac{gh^2}{12}[\rho(z_R)-\rho(z_L)]+O(h^4)$: the
correction is exactly the missing boundary term. **The modified $P$ is
fourth-order accurate where the plain one is second order.** The $-1/12$ of the
obstruction proposition and the $-1/12$ here are the same number, which is why
the construction closes.

---

## PART 3. Numerical verification

Script: `gravity_work_weight_check.py`, numpy only for the numerics (sympy is
used to confirm the rational Taylor coefficients). Run:

```
python gravity_work_weight_check.py
```

### 3(a) Convergence

Manufactured profile on $[0,1]$, $g=2.5$:
$$m(z)=z(1-z)\,e^{0.7z}\big(1+0.4\sin(3z+0.5)\big).$$
It vanishes at both walls, as the physical mass flux must, but is **not** odd
about them, so $m''$ and $m''''$ do not vanish at the walls — a profile odd
about the walls (e.g. $\sin\pi z$ times an even factor) would make the wall-cell
leading terms vanish and would hide the very error being measured. Face fluxes
are set to $m(z_{j+1/2})$ with the wall values set to exactly zero; the reference
$S_i$ uses 24-point Gauss–Legendre per cell (machine accurate).

"interior" = cells $3\dots N-2$; "wall" = $\max$ over cells $1$ and $N$.

| booking | nz | max int | ord | rms int | ord | max wall | ord |
|---|---|---|---|---|---|---|---|
| A (plain face form) | 16 | 4.2163e-03 | – | 3.2035e-03 | – | 1.2911e-03 | – |
| | 32 | 1.0590e-03 | 1.99 | 7.5181e-04 | 2.09 | 2.9733e-04 | 2.12 |
| | 64 | 2.6496e-04 | 2.00 | 1.8249e-04 | 2.04 | 7.1594e-05 | 2.05 |
| | 128 | 6.6242e-05 | 2.00 | 4.4986e-05 | 2.02 | 1.7586e-05 | 2.03 |
| | 256 | 1.6561e-05 | 2.00 | 1.1170e-05 | 2.01 | 4.3595e-06 | 2.01 |
| B0 (H, wall H=0) | 16 | 4.0578e-05 | – | 2.6860e-05 | – | 2.2452e-02 | – |
| | 32 | 2.5740e-06 | 3.98 | 1.6342e-06 | 4.04 | 1.1262e-02 | 1.00 |
| | 64 | 1.6143e-07 | 4.00 | 1.0383e-07 | 3.98 | 5.6345e-03 | 1.00 |
| | 128 | 1.1647e-08 | 3.79 | 6.5961e-09 | 3.98 | 2.8176e-03 | 1.00 |
| | 256 | 7.8434e-10 | 3.89 | 4.1643e-10 | 3.99 | 1.4088e-03 | 1.00 |
| B1 (H, one-sided dm) | 16 | 4.0578e-05 | – | 2.6860e-05 | – | 8.5110e-05 | – |
| | 32 | 2.5740e-06 | 3.98 | 1.6342e-06 | 4.04 | 1.0518e-05 | 3.02 |
| | 64 | 1.6143e-07 | 4.00 | 1.0383e-07 | 3.98 | 1.3340e-06 | 2.98 |
| | 128 | 1.1647e-08 | 3.79 | 6.5961e-09 | 3.98 | 1.6866e-07 | 2.98 |
| | 256 | 7.8434e-10 | 3.89 | 4.1643e-10 | 3.99 | 2.1221e-08 | 2.99 |
| **W4 (part 2)** | 16 | 4.0578e-05 | – | 2.6860e-05 | – | 4.4151e-05 | – |
| | 32 | 2.5740e-06 | 3.98 | 1.6342e-06 | 4.04 | 4.3144e-06 | 3.36 |
| | 64 | 1.6143e-07 | 4.00 | 1.0383e-07 | 3.98 | 3.2034e-07 | 3.75 |
| | 128 | 1.1647e-08 | 3.79 | 6.5961e-09 | 3.98 | 2.1627e-08 | 3.89 |
| | 256 | 7.8434e-10 | 3.89 | 4.1643e-10 | 3.99 | 1.4021e-09 | 3.95 |

Measured versus predicted orders:

| | interior, predicted | interior, measured (rms) | wall, predicted | wall, measured |
|---|---|---|---|---|
| A | 2 | 2.01 | 2 | 2.01 |
| B0 | 4 | 3.99 | **1** | **1.00** |
| B1 | 4 | 3.99 | 3 | 2.99 |
| W4 | 4 | 3.99 | 4 | 3.95 → 4 |

The max-norm interior column drifts to 3.79–3.89 only because the argmax cell
migrates toward the top wall where $|m''''|$ grows; the rms column is clean
(3.98–3.99) and the pointwise coefficient test below is exact.

Leading coefficients, measured/predicted at $nz=256$ (ratio should be 1):

| quantity | predicted leading term | got | pred | ratio |
|---|---|---|---|---|
| A, interior cell | $-\frac{gh^2}{12}m''$ | 1.60597e-05 | 1.60598e-05 | 1.0000 |
| W4, interior cell | $+\frac{11gh^4}{720}m''''$ | 6.03267e-10 | 6.03284e-10 | 1.0000 |
| A, wall cell | $-\frac{gh^2}{12}m''(z_L)$ | -4.35783e-06 | -4.35789e-06 | 1.0000 |
| B0, wall cell | $+\frac{gh}{12}m'(z_L)$ | 9.69843e-04 | 9.69865e-04 | 1.0000 |
| B1, wall cell | $+\frac{gh^3}{72}m'''(z_L)$ | -2.12214e-08 | -2.13726e-08 | 0.9929 |
| W4, wall cell | $-\frac{19gh^4}{720}m''''(z_L)$ | 7.34156e-10 | 7.46061e-10 | 0.9840 |

The last two ratios approach 1 as $h\to0$ (their measured orders are still
rising to 3 and 4).

Independently, sympy reproduces every coefficient of part 1 in exact rational
arithmetic (printed by the script, as the leading term of $(W-S)/(-g)$):
$\frac1{12}h^2m^{(2)}$ (A interior and A wall), $-\frac1{720}h^4m^{(4)}$
(B with exact $H$), $-\frac{11}{720}h^4m^{(4)}$ (B with discrete $H$),
$-\frac1{12}h\,m^{(1)}$ (B0 wall), $-\frac1{72}h^3m^{(3)}$ (B1 wall),
$\frac{19}{720}h^4m^{(4)}$ (W4 wall, both spellings).

### 3(b) Exact conservation, one closed-column step

Closed column, ideal gas $\gamma=1.4$, stratified and *randomly perturbed*
(deliberately not hydrostatic), Rusanov fluxes on the interior faces, reflecting
walls (zero mass and energy flux, wall pressure in the momentum flux), one
forward-Euler step with $\Delta t=2\times10^{-4}$. Machine epsilon
$\varepsilon=2.220\times10^{-16}$; scale $=|h\sum_iE_i|+|P|\approx0.906$.

| $n_z$ | $\sum hE+P$ before | $\sum hE+P$ after | change | in units of $\varepsilon\cdot$scale |
|---|---|---|---|---|
| 32 | +9.06123660842183876e-01 | +9.06123660842183876e-01 | 0.000000e+00 | 0.00 |
| 64 | +9.06143716962931611e-01 | +9.06143716962931722e-01 | +1.110223e-16 | 0.55 |
| 128 | +9.06911566634287181e-01 | +9.06911566634286959e-01 | -2.220446e-16 | 1.10 |

The change is zero or one unit in the last place — round-off, as claimed.

Control: with the **plain** potential $P_0=h\sum_i\rho_i g z_i$ and the same
booking (W), the budget fails, and it fails by exactly the predicted amount
$\Delta t\,(H_{N+1/2}-H_{1/2})$:

| $n_z$ | measured change with $P_0$ | predicted $\Delta t (H_{\rm top}-H_{\rm bot})$ | ratio to $\varepsilon\cdot$scale |
|---|---|---|---|
| 32 | -1.439701e-07 | -1.439701e-07 | 7.2e+08 |
| 64 | -3.670097e-08 | -3.670097e-08 | 1.8e+08 |
| 128 | -9.058080e-09 | -9.058080e-09 | 4.5e+07 |

(The residual scales as $h^2$, as $H\propto h^2$ requires.) This is the
quantitative statement of §2.2: fourth-order accuracy at the wall and exact
conservation are incompatible *unless* $P$ is modified.

### 3(c) Accuracy of the discrete potential energy (extra check of §2.6)

$\big|P-\int\rho\Phi\,dz\big|$ for $\rho(z)=e^{-z/0.35}(1+0.05\sin 9z)$:

| $n_z$ | plain $P_0$ | order | modified $P$ | order |
|---|---|---|---|---|
| 16 | 7.6583e-04 | – | 7.6752e-07 | – |
| 32 | 1.9151e-04 | 2.00 | 7.9272e-08 | 3.28 |
| 64 | 4.7880e-05 | 2.00 | 7.5912e-09 | 3.38 |
| 128 | 1.1970e-05 | 2.00 | 5.8751e-10 | 3.69 |
| 256 | 2.9926e-06 | 2.00 | 4.0754e-11 | 3.85 |

Confirms §2.6: the wall-shifted potential is three orders of magnitude more
accurate at $n_z=16$ and converges at fourth order rather than second.

---

## Summary of part 1–3 results

| | interior | bottom wall cell | top wall cell |
|---|---|---|---|
| plain face form A | $-\frac{gh^2}{12}m''(z_i)$, **2nd** | $-\frac{gh^2}{12}m''(z_L)$, **2nd** | $-\frac{gh^2}{12}m''(z_R)$, **2nd** |
| A + $H$, $H_{\rm wall}=0$ (B0) | $+\frac{11gh^4}{720}m''''$, **4th** | $+\frac{gh}{12}m'(z_L)$, **1st** | $-\frac{gh}{12}m'(z_R)$, **1st** |
| A + $H$, one-sided (B1) | $+\frac{11gh^4}{720}m''''$, **4th** | $+\frac{gh^3}{72}m'''(z_L)$, 3rd | $-\frac{gh^3}{72}m'''(z_R)$, 3rd |
| A + $H$, ghost face (W4) | $+\frac{11gh^4}{720}m''''$, **4th** | $-\frac{19gh^4}{720}m''''(z_L)$, **4th** | $-\frac{19gh^4}{720}m''''(z_R)$, **4th** |

* The Cartesian "curvature flux" in the sense of *volume-average minus
  centroid geopotential* is identically zero; the non-trivial correction is the
  average-of-a-product term (0.2).
* Is the booking first order at the walls? **Without $H$: no** (second order).
  **With $H$ and $H_{\rm wall}=0$: yes** (first order), and that first-order
  error is forced by exact conservation against $P_0=h\sum\rho_i g z_i$.
* W4 + the shifted potential $\tilde\Phi$ is exactly conservative to round-off
  and fourth order in every cell including both wall cells, and its $P$ is
  itself fourth-order accurate.

---

## PART 4. Comparison with `UCzhangxi/snapy`, branch `next/curved-gravity-work-weight`

Parts 1–3 above were complete, with all numbers, before this document was
fetched or read.

**Source read.** `docs/derivations/curved-gravity-work-weight.md` at commit
**`c06546d83610078de242d0979b2af5600c0ad91d`** (branch
`next/curved-gravity-work-weight`, author Xi Zhang, dated Fri 9 Oct 2026
10:46:58 −0700, subject "Derivation: exact radial weights for the face gravity
work break discrete E+PE conservation"), 136 lines. Its companion replica
`docs/derivations/curved_gravity_work_weight.py` exists at that commit and was
read but not run. The "Base: 8cea3ae" named in its line 6 is not reachable from
my shallow clone, so I did not verify it.

Below, their symbols are mapped to mine by
$$g_1=-g,\qquad \phi=-g_1r \leftrightarrow \Phi=gz,\qquad F \leftrightarrow m,
\qquad G=AF \leftrightarrow m \ (A\equiv1),\qquad A_f\equiv1,\ V_i\equiv h .$$

### 4.1 Scope — the largest difference

Their document is about the **spherical-polar radial** grid. It has no section
headed "Cartesian"; the Cartesian content is three asides: the "Cartesian" label
on the $\frac{h^2}{12}F''$ term in their (2) (lines 36–39), the Cartesian limit
of their exact weights (lines 53–54), and the closing sentence of their §4
"Wider stencils" remark (lines 99–100). Their question is whether the exact
$r^2$-measure **two-point** weights break E+PE conservation; mine is the
Cartesian truncation order, including at the walls, and whether exact
conservation and fourth-order accuracy can hold together. Consequently most of
my parts 1(b), 1(c), 2 and 3 have no counterpart there, and most of their §§3–6
has no counterpart here.

### 4.2 Where we agree

I verified each of the following independently (their equation numbers in
parentheses); the sympy checks are in the transcript of this job.

1. **Face-form definition.** Their (1),
   $W_i=\frac1{V_i}[\phi_{c,i}(A_+F_+-A_-F_-)-(A_+\phi_+F_+-A_-\phi_-F_-)]$, is
   my $W^A$ written in curved form. Agreed.
2. **Cartesian limit of the face form.** Their lines 53–54: $r_c=\bar r$ gives
   $a=b=1/2$ and their (1) also gives $1/2$. Same as my (A),
   $W^A_i=-\frac g2(m_{i+1/2}+m_{i-1/2})$. Agreed.
3. **Cartesian interior truncation error.** Their (2) gives
   $\frac{W-g_1\langle F\rangle_V}{g_1}=\frac{h^2}{12}F''+(\text{curvature})$;
   in Cartesian the curvature pair vanishes and this is
   $W-S=-\frac{gh^2}{12}m''$, **identical to my part 1(a)**: same coefficient,
   same sign, and the same identification as the trapezoid-rule error. Agreed.
   I re-derived their full (2) with sympy and got exactly
   $\frac{F''}{12}+\frac{F'}{6\bar r}-\frac{F}{6\bar r^2}$ at $O(h^2)$ — their
   curvature coefficients are right too.
4. **The conservation condition.** Their §4 Lemma (shared-face weight sum
   $S_f=A_f(r_{c,i+1}-r_{c,i})$, "the interior $F_f$ are independent, so … iff")
   is the two-point case of my condition (C) with $\tilde\Phi=\Phi$, i.e. column
   sums $T_j=1$. Agreed, including the observation that the other energy fluxes
   telescope to the walls and drop out, and that the statement must hold for
   *every* flux field.
5. **The plain face form conserves exactly on any grid** (their line 71–72, my
   §2.1). Agreed.
6. **Their (3), (4), (5) are algebraically correct.** I re-derived the exact
   two-point weights $a=(r_c-r_-)/h,\ b=(r_+-r_c)/h$, the defect closed form
   $\frac{h^3(3R^4-R^2h^2+h^4/6)}{9R^4-3R^2h^2+h^4}$ and its relative form
   $\frac{h^2}{3R^2}+\frac{h^4}{18R^4}$ with sympy; all three match to the last
   printed term. Their observation that the two offsets are "swapped" between
   (1) and (3), and that (1) is exact for $G=\text{const}$ while (3) is not
   (their lines 42–43, 92–93), are both correct.
7. **The Cartesian obstruction term itself.** Their line 99 identifies it as
   $(h^2/12)[G']_{\rm walls}$ — a pure **wall** quantity. I derive exactly the
   same object by Euler–Maclaurin: for a booking that is the exact cell average,
   $\sum_i hW_i+\dot P_0=\frac{gh^2}{12}\big[m'(z_R)-m'(z_L)\big]$, and this is
   also the source of the $-\tfrac1{12}$ in my obstruction proposition §2.2 and
   of the $+\frac{gh}{12}m'(z_L)$ wall error of closure B0. **Complete numerical
   and symbolic agreement on this term.**
8. Implicitly, on part 1(b): their own convergence ladder (lines 117–118) takes
   a max over *all* cells, wall cells included, and the face form still shows
   slope 1.97. That is consistent with my explicit answer that the plain face
   form is second order at the walls, not first.

### 4.3 Differences in results

| | this document | `c06546d8` |
|---|---|---|
| geometry | Cartesian only | spherical-polar; Cartesian only as a limit |
| stencil width considered | 2-point and 4-point | 2-point only (§3, §4 Lemma); wider stencils only in the non-proof remark, §4 lines 95–100 |
| discrete potential energy | a **free** functional $P=h\sum\rho_i\tilde\Phi_i$; $\tilde\Phi$ is solved for | **fixed** at $\mathrm{PE}=\sum\rho_i\phi(r_{c,i})V_i$ throughout (line 23) |
| wall-cell truncation error | derived for all four closures, parts 1(b),(c) | not derived anywhere |
| "is it first order at the walls?" | answered: no without $H$, yes with $H$ and $H_{\rm wall}=0$ | not asked |
| a curvature flux $H$ in Cartesian | two readings distinguished: the volume-average-minus-centroid one is identically zero; the average-of-a-product one is $-\frac{gh^2}{12}m''$ and is written as a flux | "curvature" means only the $1/\bar r$ terms, which vanish in Cartesian; no additive flux $H$ |
| conservative **and** 4th order | constructed and verified (W4 + $\tilde\Phi$) | asserted impossible in Cartesian ("gives up the trapezoid error to conserve") |
| $O(h^4)$ Cartesian interior coefficient | $+\frac{11gh^4}{720}m''''$ (discrete $H$), $+\frac{gh^4}{720}m''''$ (exact $H$) | not given |

### 4.4 Claims I believe are wrong, or load-bearing and under-qualified

**(a) Line 99–100 — the Cartesian claim. I believe this is wrong.** It reads:

> "The Cartesian part, $(h^2/12)[G']_{\rm walls}$, is the same conflict the face
> form already resolves in Cartesian (it gives up the trapezoid error to
> conserve)."

Calling it a *conflict* that must be *resolved by giving up* the trapezoid error
is incorrect: in Cartesian the conflict is removable at no cost in accuracy.
Reason: the defect is, by their own identification, a **pure wall term**. A wall
term is exactly what a boundary-localised modification of the discrete potential
can absorb. My §2.3 does this with the three cells next to each wall,
$\varepsilon_1=-\frac{gh}6,\ \varepsilon_2=+\frac{gh}8,\ \varepsilon_3=-\frac{gh}{24}$
(mirrored at the top), after which the four-point booking (W) is exactly
conservative *and* fourth order in every cell including the wall cells. Verified
in §3: conservation residual $0$, $+1.1\times10^{-16}$, $-2.2\times10^{-16}$
(0.0–1.1 units of $\varepsilon\cdot$scale) at $n_z=32,64,128$, and wall-cell
order $3.95\to4$. The trapezoid error is not given up; it is removed.
Furthermore the modified $P$ is *more* accurate than the fixed one — fourth
order against second (§3c) — so nothing is sacrificed on that side either.

Mitigating: their line 95 labels that whole paragraph "a remark not a proof",
and the Cartesian sentence is one clause of an aside in a spherical document. I
would not call it a defect of the spherical analysis; I would call it a wrong
claim that should be struck or corrected, because it is the sentence a reader
will carry away about the Cartesian path, which is the path snapy's plane-parallel
runs take.

**(b) Lines 9–11 and 81–83 — the headline "no weight choice" claim is correct
but under-qualified.** "No weight choice that keeps the face form's conservation
removes both terms; one or the other, not both." My independent Cartesian
analogue (the obstruction proposition, §2.2, with the same $-\frac1{12}$
constant, confirmed symbolically for every block width $K$) supports the
*spirit* of this. But as written it omits two hypotheses that do all the work:
(i) **two-point** weights, and (ii) **PE held fixed** at
$\sum\rho_i\phi(r_{c,i})V_i$. Both are stated earlier in the document but
neither appears in the Result box or in the §6 options table, where a reader
will take "no weight choice" at face value. Under (i)+(ii) the claim is right;
drop either and it is not established.

**(c) Line 23–24 — the premise.** "$\mathrm{PE}=\sum_i\rho_i\phi(r_{c,i})V_i$
(the exact $\int\rho\phi\,dV$ for piecewise-constant $\rho$)." True, but it is a
*choice*, and it is the single assumption on which the impossibility rests. The
parenthetical justification is weaker than it looks: a finite-volume state is a
cell **average** of a smooth field, not a piecewise-constant field, and read that
way this PE is only $O(h^2)$ accurate — so an $O(h^2)$ modification of it is
within its own error bar and costs nothing. This should be flagged as the
load-bearing assumption rather than passed over as a definition.

**(d) Equation (4) — the remainder order is overstated.** It is printed as
$$\frac{W_{\rm exact}-g_1\langle F\rangle_V}{g_1}=\frac{h^2}{12}F''
-\frac{h^4}{360\bar r^2}F''+O(h^5),$$
annotated "exact to the printed order". With sympy I get the $h^4$ coefficient
$$-\frac{F''}{360\bar r^{2}}+\frac{F'''}{360\bar r}+\frac{F''''}{480},$$
so two terms of the *same* $O(h^4)$ order are missing and the remainder is not
$O(h^5)$ for general smooth $F$. The cause is visible at their line 35: the
expansion is truncated at $F=F_0+F_1s+F_2s^2/2$, for which $F'''=F''''=0$. The
equation is therefore correct **for quadratic $F$ only**; the stated remainder
should be $O(h^6)$ within that truncation, or the two $h^4$ terms should be
restored. Low severity — it does not affect any conclusion — but "exact to the
printed order" is not accurate as written. Their (2), by contrast, carries
$O(h^4)$ and is fine; I confirmed its $h^4$ coefficient is
$-\frac{F'}{24\bar r^3}-\frac{17F''}{720\bar r^2}+\frac{7F'''}{720\bar r}+\frac{F''''}{480}$,
whose Cartesian part $\frac{F''''}{480}$ matches my part 1(a) term
$-\frac{gh^4}{480}m''''$ exactly.

**(e) §5, line 110 and 113 — "round-off" is generous at large $R$.** The face
form's residual is quoted as $-6.5\times10^{-13}$ relative at $R=1000H$ and
called round-off. That is ~3000 $\varepsilon$; it is plausibly cancellation in
sums of $r^2$-weighted terms spanning a large dynamic range rather than a defect,
but it is three orders above round-off and sits only a factor ~200 below the
exact weights' $1.2\times10^{-10}$ in the same row. For contrast, the Cartesian
test in my §3(b) lands at 0–1.1 units of $\varepsilon\cdot$scale. I would
either say "at the cancellation floor of this sum" or add a Kahan/compensated
sum to show the floor is cancellation and not a residual.

### 4.5 What my result does **not** contradict

Their central spherical claim — that the exact $r^2$ weights (3) break E+PE
conservation with a per-face defect $h^3/3$, relative $h^2/(3R^2)$, the same
order as the curvature terms they remove — is, as far as I checked, correct, and
I reproduced (5) exactly. My Cartesian construction does not refute it: in
Cartesian the obstruction is a **wall** term, whereas their line 97–98 shows the
spherical curvature obstruction is a **column integral**,
$+g_1\frac{h^2}{6}\int F\,dr$, which is extensive and therefore not absorbable by
a boundary-localised fix.

**Hypothesis, untested.** Extensive is not the same as unabsorbable. Their "no
local telescoping correction cancels it" rules out fixing the *weights*; it does
not address fixing the *potential*, which is what makes the Cartesian case work.
Repeating my §2.1 derivation in their notation, a modified discrete potential
$\tilde\phi_i=\phi(r_{c,i})+\eta_i$ changes the conservation requirement by
$-A_f(\eta_{i+1}-\eta_i)/g_1$ per face, so absorbing a per-face defect
$g_1\frac{h^3}{6}F_f$ needs
$$\eta_{i+1}-\eta_i=-\frac{g_1h^3}{6\,r_f^{2}}
\quad\Longrightarrow\quad \eta_i\simeq \frac{g_1h^{2}}{6\,r_{c,i}} ,$$
i.e. a smooth, decaying, **$O(h^2)$** shift of the discrete potential — the same
relative order $h^2/r^2$ as the terms being removed, and well inside the
accuracy of PE itself. If that works, their option B would move from "defect
$g_1(h^2/3)\int F\,dr$" to "round-off", and the §6 table would gain a row.

I have **not** verified this: I did not derive the exact $\eta$ for the actual
weights (3) (the $h^3/3$ defect of (5) is a different coefficient from the
$h^3/6$ of the wider-stencil remark), I did not check that it stays consistent at
the two walls, and I ran no spherical numerics. The check that would settle it is
cheap and is the direct analogue of my §3(b): solve
$g_1S_f=-A_f(\tilde\phi_{i+1}-\tilde\phi_i)$ for $\tilde\phi$ by telescoping from
one wall with the weights (3) in place, then rerun their §2 closed-column step
with that $\tilde\phi$ in PE and confirm the residual drops to the cancellation
floor; and separately confirm $\big|\sum_i\rho_i\tilde\phi_iV_i-\int\rho\phi\,dV\big|$
is no worse than with $\phi(r_c)$.

### 4.6 Difference list, condensed

1. Scope: spherical there, Cartesian here; no Cartesian section exists in their
   document, only three asides. (§4.1)
2. Conventions: $g_1<0$, $\phi=-g_1r$, per-steradian $A=r^2$, $V=\frac13\Delta r^3$,
   $F$ a flux density, $G=AF$ — versus $g>0$, $\Phi=gz$, $A=1$, $V=h$, $m=\rho w$.
   The two map one-to-one; no disagreement. (§4)
3. Interior Cartesian truncation order and coefficient: **agree exactly**,
   $-\frac{gh^2}{12}m''$, second order, and the $h^4$ term $-\frac{gh^4}{480}m''''$.
4. Wall-cell truncation: **they give none**; I give four closures with orders
   2, 1, 3, 4 and explicit coefficients.
5. The explicit yes/no on first order at the walls: absent there; answered here
   (no without $H$, yes with $H$ and $H_{\rm wall}=0$).
6. The Cartesian "curvature flux": they have none (their curvature is purely the
   $1/\bar r$ terms, which vanish); I distinguish the identically-zero reading
   from the non-zero average-of-a-product reading.
7. Discrete PE: fixed there, free here. This single difference produces the
   opposite conclusion about whether conservation and accuracy can coexist.
8. Stencil width: two-point there, two- and four-point here.
9. Their conservation Lemma = my condition (C) restricted to two-point weights
   and $\tilde\Phi=\Phi$: agree.
10. Their Cartesian wall defect $(h^2/12)[G']_{\rm walls}$ = my
    $\frac{gh^2}{12}[m']_{\rm walls}$ and my $-\frac1{12}$ obstruction constant:
    agree exactly.
11. Their claim that the Cartesian conflict is resolved by giving up the
    trapezoid error: **I believe this is wrong**; §2–§3 here construct and verify
    a booking that keeps both. (§4.4a)
12. Their headline "no weight choice …": correct under two unstated hypotheses
    (two-point, PE fixed); should be qualified. (§4.4b)
13. Their (4) remainder $O(h^5)$: overstated for general smooth $F$; two $h^4$
    terms missing because $F$ is truncated at $s^2$. (§4.4d)
14. Their (3) and (5): I re-derived both symbolically — **correct**, including
    the "swapped offsets" remark and the $G=\text{const}$ exactness of (1).
15. Their $R=1000H$ "round-off" at $6.5\times10^{-13}$: likely a cancellation
    floor, not round-off; worth relabelling. (§4.4e)
16. Not contradicted: their spherical conclusion that (3) breaks conservation at
    the same order it fixes. I add an untested hypothesis that a modified
    discrete potential $\eta_i\simeq g_1h^2/(6r_{c,i})$ may escape it there too,
    with the concrete check that would settle it. (§4.5)

I did not edit their document.
