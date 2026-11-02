# snapy#280: a stretched (non-uniform) vertical x1 grid — phase-1 design note

**Status: DRAFT, documentation only.** No snapy source was changed and nothing was pushed, branched or posted. Authors: Linfeng Li (skeleton, §2, §3, the dx-fill items) and Tianhao Le (§4 route-A layout and §7, which he still has to finish and check). Inputs: Linfeng's uniform-x1 inventory, Tianhao's `weno5-cp5-nonuniform-x1.md` and `followup-coarse-citations-cuda.md`, Xinyue's `wb280-wellbalance-2d9fa419.md`, and Jiheng's implicit-solver finding as summarised in the thread.

**Pinned code.** Every `path:line` is at `2d9fa419be56513159c695267b68753d5b223b31`. `git ls-remote https://github.com/chengcli/snapy refs/heads/main` returned that sha at 2026-11-02T18:17:43Z, 18:23:28Z and 19:44:58Z, so main has not moved during phase 1.

**Conventions.** A claim marked **[H]** is a hypothesis: not tested in snapy. A **[measured offline]** number comes from a standalone script (numpy/sympy or a standalone CUDA kernel), not from snapy's solver. A **[measured in snapy]** number comes from a snapy source build at 2d9fa419 with no source change. Faces are x_{i∓1/2}, widths h_i = x_{i+1/2} − x_{i−1/2}, and x1 increases upward.

---

## 1. Problem and scope

**Goal (thread, UU9SW7MHU).** Run a column on a geometric x1 grid where each cell is 1.05–1.2× the one above it. The hot, deep part of the atmosphere then gets coarse cells and a run costs less. Three properties must survive: a resting column stays at rest to round-off, WENO5 keeps its order, and the vertical implicit solver stays stable up to vertical Courant ~250.

**What phase 1 found.**
1. **The grid cannot be asked for.** `geometry` accepts only `type/bounds/cells` (`src/coord/coordinate.cpp:70`), and `cells` only `nx1, nx2, nx3, nghost, interp_order` (`:125-126`). `check_keys` throws on any other key (`src/input/check_keys.cpp:26`). Faces are one global uniform `linspace`, ghosts included (`src/coord/coordinate.cpp:308-325`). This is the first blocker (§2, §3).
2. **Reconstruction loses order.** One fixed WENO5/cp5 coefficient table serves every face (`src/recon/weno5.cpp:11-23`, `src/recon/cp5.cpp:13-14`, weights `src/recon/interp_impl.h:115-117`). On a stretched grid that is about 2nd order under a fixed stretching map [measured offline, Tianhao: 1.66–1.93], and 1st order at a fixed per-cell ratio [measured offline, Linfeng]. §4.
3. **Well-balance is already structural on main.** The face scan uses per-cell `dx1f` (`src/hydro/hydro_ref_x1_impl.h:43,53`), and a stretched grid automatically takes the log-mean cell reference (`src/hydro/hydro.cpp:550-556`, `src/hydro/hydro_ref_x1_impl.h:181-186`). Rest fails at nx1 = 128 only through the round-off of that log-mean [measured in snapy, Xinyue]. §5.
4. **The implicit operator already uses per-cell metrics** (`src/implicit/vic_assemble_full_impl.h:89-99`). §6.
5. **An open physics question decides whether this is worth doing:** the Jiang–Shu nonlinear weights collapse at a coarse bottom (dz/H ≳ 0.6) on perfectly smooth data. §7.

**In scope:** Cartesian x1 (vertical) columns. The design must not change the arithmetic of spherical-polar/gnomonic geometries. **Out of scope:** x2/x3 stretching, AMR, and shocks: every profile measured so far is smooth.

---

## 2. Grid key

### 2.1 What the code does today

| step | location | today |
|---|---|---|
| yaml keys | `src/coord/coordinate.cpp:70`, `:125-126`; `src/input/check_keys.cpp:26` | no stretching key; unknown keys throw |
| global faces | `src/coord/coordinate.cpp:308-325` | `dx = (gmax−gmin)/gnx`; `linspace(gmin − ng·dx, gmax + ng·dx, gnx + 2ng + 1)`, sliced per block (`:322-324`) |
| why one global array | `src/coord/coordinate.cpp:292-299` | so a face shared by two blocks has one value whoever owns it. Keep this. |
| Cartesian metrics | `src/coord/cartesian.cpp:23-28` | `dx1f = ones·dx1()`, `dx1v = ones·dx1()`, `x1v` = face midpoints |
| gnomonic metrics | `src/coord/gnomonic_equiangle.cpp:32-38` | same scalar fill |
| spherical metrics | `src/coord/spherical_polar.cpp:59-62` | already derived from `x1f` |
| scalar width | `src/coord/coordinate.hpp:76-80` | `dx1() = (gx1max − gx1min)/gnx1` |
| block offset | `src/coord/coordinate.hpp:93`, `:126-128` | `ix1 = lround((x1min − gx1min)/dx1())` |
| block bounds | `src/coord/coordinate.cpp:270-271`, `:279` | equal-length slices `x1min = gx1min + lx1·L/nb1`, equal counts `nx1 = gnx1/nb1` |
| meshgen hook | `src/coord/coordinate.cpp:327-350`, `src/coord/cartesian.cpp:50-79` | not called from the built library (its only caller is `src/z.junk/initialize.cpp:163`, and `z.junk` is not in `src/CMakeLists.txt:35-53`). It also leaves `dx1v[0]` stale (`src/coord/cartesian.cpp:58-60`). |

### 2.2 Proposal

Add **one** of two mutually exclusive inputs. Absent both, the code path is unchanged byte for byte.

```yaml
geometry:
  type: cartesian
  bounds: {x1min: 0., x1max: 2.0e4}
  cells:  {nx1: 128, nghost: 3, x1rat: 0.952380952}   # option A: geometric ratio
  # x1f: [0., 954.2, ...]                            # option B: explicit interior faces (nx1+1 values)
```

**Option A, `cells/x1rat` = q ≡ h_{k+1}/h_k** (the cell above divided by the cell below). With L = x1max − x1min and n = global nx1:

$$
h_0 = L\,\frac{q-1}{q^{n}-1},\qquad x_k = x_{\min} + L\,\frac{q^{k}-1}{q^{n}-1}\quad(k = 0,\dots,n),\qquad q = 1 \Rightarrow x_k = x_{\min} + kL/n .
$$

Pin x_n = x1max exactly, as Xinyue's driver did (her report B0, step 4). **Decision for Xi/Cheng (D1):** the thread's "x1rat 1.05, each cell 1.05× the one above it" means q = 1/1.05 in this convention. The alternative is to define the key as (cell below)/(cell above). I recommend the convention above (the ratio along +x1) and documenting it. Whichever is chosen, the tests must state it, because Xinyue's runs grew cells *downward* by 1.05.

**Option B, `geometry/x1f`** (a list of nx1+1 strictly increasing values). `bounds/x1min` and `x1max` must equal the first and last entries, or be omitted and taken from them. Use it for piecewise profiles (for example a stretched troposphere under a uniform stratosphere). Route A is indifferent to a jump in the ratio (§4.4). Option B is the cheaper way to get arbitrary grids into tests.

**`check_keys`:** add `x1f` to the allowed list at `src/coord/coordinate.cpp:70` and `x1rat` at `:125-126`. Reject both together, reject `x1rat ≤ 0`, and reject a non-increasing list.

**Faces.** Generalise `block_faces_` (`src/coord/coordinate.cpp:308-325`) to slice from one **global face vector** of length gnx + 2·ng + 1. It is built once from the key plus the ghost rule of §3, in float64, with the same slicing (`:324`). If neither key is present, build exactly today's `linspace` (`:322-323`). That keeps criterion 3 (bitwise uniform) by construction.

**dx fill.** On the stretched path, Cartesian and gnomonic must set `dx1f = diff(x1f)`, `x1v` = face midpoints, and `dx1v[i] = x1v[i] − x1v[i−1]`. For `dx1v[0]`, extend the global face vector by one more face per end so the value is defined. On the uniform path keep today's `ones·dx1()` fill (`src/coord/cartesian.cpp:25,28`): `diff(linspace)` differs from it by ULPs and would break bitwise identity [H, ULP-level; not measured]. These tensors feed:
- per-cell users that become correct automatically: the CFL (`src/hydro/hydro.cpp:392-396` via `center_width1`, `src/coord/coordinate.cpp:402-404`), the scan, and the implicit area/volume;
- `dx1v` users that need the new fill: diffusion normal gradients (`src/forcing/diffusion.cpp:86-97`) and `curl` (`src/coord/coordinate.cpp:603-615`);
- scalar-`dx1()` users that stay wrong and need their own fix (§9): `src/forcing/diffusion_cubed_sphere.cpp:191`.

**Multi-block (nb1 > 1).** Replace the length-based offset and bounds on the stretched path:

$$
\texttt{ix1} = l_{x1}\cdot n_{x1},\qquad \texttt{x1min} = X_{\rm glob}[\texttt{ix1}],\qquad \texttt{x1max} = X_{\rm glob}[\texttt{ix1}+n_{x1}] ,
$$

with l_{x1} from the layout (`src/coord/coordinate.cpp:262`). Equal **cell counts** per block stay (`:279`), and the equal **lengths** (`:270-271`) go. Keep today's formulas on the uniform path: `x1min` is read by output slicing (`src/output/output_type.cpp:420-423`), and its value must not change by round-off. Cubed-sphere keeps `lx1 = 0` (`src/coord/coordinate.cpp:137,264`). The implicit scheme refuses nb1 > 1 anyway (`src/hydro/hydro.cpp:428-431`). The well-balanced reference is already continuous across x1 seams (anchor relay `src/hydro/hydro.cpp:524-548,591-593`; ghost-row exchange `:595-654`).

**Uniform classification.** Today each block probes `dx1f` once, ghosts included (`src/hydro/hydro.cpp:550-556`, cached in `src/hydro/hydro.hpp:274`). With option B, a block lying entirely in a uniform part of the column would choose the uniform operator while its neighbours choose the non-uniform one, and no single initial condition would be a fixed point for both (`src/hydro/balance_column.hpp:73-79`). **Proposal:** on the stretched path, derive the classification from the grid key (any stretching key means non-uniform in every block) instead of the per-block probe. `balance_column` must then make the same choice (`src/hydro/balance_column.cpp:66-68`).

---

## 3. Ghost and boundary widths

**Today:** ghost faces are the uniform extension at the **mean** width (`src/coord/coordinate.cpp:322-323`). On q = 1/1.1 with nx1 = 128 the ratio h_max/h_min is about 440 (Tianhao §4), so the ghost width is wrong by orders of magnitude next to both walls.

The ghost-width rule applies only at the two ends of the global face vector. Ghosts at internal seams are the neighbour's real faces, through the global slice (`src/coord/coordinate.cpp:292-299`).

| option | lower ghosts (m = 1..ng) | pro | con |
|---|---|---|---|
| (a) uniform at mean width (today) | h_{−m} = L/n | no change | wrong geometry for the first owned faces under route A; large width jump at the wall |
| (b) continue the stretching | h_{−m} = h_0 q^{−m} | smooth; the map stays C^∞; Xinyue's runs used it (B0 step 4) | a reflecting wall mirrors **by index** (`src/bc/bc_func.cpp:14,27-28`; WB perturbations `src/hydro/hydro_forward.cpp:408-420`; covariance velocity `:444-451`), so the reflected state sits at the wrong positions |
| (c) mirror the widths | h_{−m} = h_{m−1}; upper: h_{n−1+m} = h_{n−m} | makes the index mirror a geometric mirror (**Tianhao's point: a reflecting-wall mirror is physical only when ghost widths mirror interior widths**) | the ratio jumps from q to 1/q at the wall; route A handles that (positive, well-conditioned weights for a jump s ∈ [1/16, 16], Tianhao §4) |
| (d) periodic wrap | h_{−m} = h_{n−m} | consistent with periodic data | only meaningful without x1 gravity |

**Recommendation (D2):** choose the rule per side from that side's boundary type when the global face vector is built: reflecting → (c), periodic → (d), outflow/extrapolation → (b). The rule lives in one function, so every block and `balance_column` see the same ghosts.

**Effect on rest:** none at clamped walls. With `wb-wall-clamp: true` (the default, `src/hydro/hydro_options.cpp:57`), the wall cells' reference uses one-sided rows over owned faces only (`src/hydro/hydro_ref_x1_impl.h:132-135,164-172`). The ghost p′ and ρ′ are overwritten by the even index mirror (`src/hydro/hydro_forward.cpp:408-420`), and a constant p′ mirrors to itself (Xinyue A3). With the clamp off, ghost `dx1f` enters `pref` (`src/hydro/hydro_ref_x1_impl.h:154-156`), and `balance_column` refuses that case (`src/hydro/balance_column.cpp:28-33`).

**Effect on order:** [H] with (b), the reconstruction at the first ng faces above a reflecting wall reads mirrored data at non-mirrored positions, which costs order at the wall but not balance. Not measured. The test is in §8 (criterion 2b).

**Route B would make this worse** (§4.5): it needs J in the ghosts, and (a) or (c) make J discontinuous at the wall.

---

## 4. Reconstruction: route A (Tianhao; section owner Tianhao)

### 4.1 What is fixed today

WENO5 candidate rows c1–c3 and smoothness rows c4–c9 are in `src/recon/weno5.cpp:11-23`. The linear weights `.3/.6/.1`, ε = 1e−6 (absolute) and p = 2 are at `src/recon/interp_impl.h:115-117`, with 13/12 and 1/4 at `:108-113`. The CUDA kernel uses the same constants (`src/recon/interp_impl.cuh:95-101`). cp5 is `(−3, 27, 47, −13, 2)/60` (`src/recon/cp5.cpp:13-14`), which equals Σ d_r p_r. The reconstruction modules carry no geometry: the interface is `InterpImpl::forward(w, dim, wl, wr)` (`src/recon/interpolation.hpp:60-63`), and the only options are `type` and `scale` (`:30-31`).

### 4.2 Per-face coefficients, computed once at setup

**Candidate and cp5 rows** come from the primitive function (Tianhao §2.2; Shu 1998, eq. 2.20). For the n cells bounded by faces z_0 < … < z_n and a target point x_f:

$$
\bar u(x_f) \approx \sum_{k=0}^{n-1} w_k\,\bar u_k,\qquad
w_k = (z_{k+1}-z_k)\sum_{j=k+1}^{n} L_j'(x_f;\,z_0,\dots,z_n),\qquad \sum_k w_k \equiv 1 .
$$

Evaluate this in the normalised coordinate (x − x_f)/h_i. In absolute coordinates the weights lose their digits [measured offline, Tianhao §2.2]. snapy already builds exactly this form for its face density (`src/hydro/wb_ref4.cpp:195-219`).

**Linear weights in closed form, positive on any grid** (Tianhao §2.3, checked symbolically). For the face y_3 of the six faces y_0 < … < y_5 bounding the stencil:

$$
a = y_3-y_0,\; b = y_3-y_1,\; c = y_4-y_3,\; e = y_5-y_3;\qquad
d_0=\frac{ab}{(a+e)(b+e)},\quad d_1=\frac{ae(a+b+c+e)}{(a+e)(b+e)(a+c)},\quad d_2=\frac{ce}{(a+c)(a+e)} .
$$

Every factor is a positive length, so d_r > 0 for every admissible grid. The uniform case (a, b, c, e) = (3, 2, 1, 2) gives (3/10, 3/5, 1/10), today's immediates. So no negative-weight splitting is needed. **Scope of the positivity statement:** it holds for reconstruction at a **face**, with the target interior to the stencil. The CWENO paper's remark that WENO5 optimal weights can leave [0, 1] concerns the **cell centre** (Cravero, Puppo, Semplice & Visconti 2018; follow-up §2.4). **Novelty is not claimed:** Wang, Feng & Spiteri (2008) is the likely prior art for face-dependent WENO5 weights and has not been read (follow-up §2.6).

**Smoothness indicators.** These follow Jiang & Shu (1996, eqs. 3.2–3.4) scaled on the target cell (Tianhao §2.4):

$$
\beta_r = \sum_{m=1}^{2} h_i^{2m-1}\int_{I_i}\big(p_r^{(m)}\big)^2dx = \bar u^{\mathsf T}M_r\bar u = (A_r\!\cdot\!\bar u)^2 + (B_r\!\cdot\!\bar u)^2 .
$$

M_r depends only on the width ratios, so β stays dimensionless and the absolute ε = 1e−6 keeps its uniform-grid meaning. The kernel's two-squares layout and its 13/12 and 1/4 multipliers stay. [Layout choice, H] store A_r/√(13/12) and B_r/√(1/4) in rows c4–c9.

**Storage.** Per face and side: 45 coefficients plus 3 linear weights = 48 doubles. The values depend on i only, so one 1-D array of 2·48·nc1 doubles serves every (k, j) column, about 103 KB per block at nc1 = 134 (Tianhao §3.6). Build it on the CPU in double from the block's own `x1f`. The block holds nx1 + 2·ng + 1 faces (`src/coord/coordinate.cpp:324`), which is enough for every owned face with ng = 3 (`src/recon/reconstruct.cpp:86-88`), so no communication is needed. Cache it on the module with a staleness check, as `wb_ref4` does (`src/hydro/wb_ref4.cpp:97-231`; cache `src/hydro/hydro.cpp:581-588`). cp5 (`pinterp2`) gets the 5-entry row Σ d_r p_r per face and side through `call_poly5` (`src/recon/recon_dispatch.cpp:14-38`). Only DIM1 is affected; `recon23` stays untouched.

### 4.3 Layout on CPU, MPS and CUDA

- **Plumbing:** add an optional per-face coefficient tensor to the x1 interpolators. Hydro sets it from the coordinate object, since `InterpImpl` has no geometry today (`src/recon/interpolation.hpp:52,60-63`).
- **CPU:** `call_weno5_cpu` passes one pointer `c` for every face (`src/recon/recon_dispatch.cpp:101-125`). The lambda must know the x1 index of each output element and read `c + 48·i`. The `iter.for_each` loop does not track that index today (`:114-123`).
- **MPS:** `wu.matmul(c1)` (`src/recon/recon_dispatch.cpp:127-168`) becomes `(wu * C1).sum(-1)` with `C1` of shape (nface, 5).
- **CUDA:** today the 45 coefficients are staged into shared memory once per block (`src/recon/interp_impl.cuh:190-195`) against `kSharedLimit = 48 * 1024` (`src/recon/recon_dispatch.cu:26`). Per-face rows cannot be staged: 45 × tile × 8 B is 90 KB at tile 256 (follow-up §3.3). **Read the rows from global memory.** Adjacent threads read adjacent faces (coalesced), and the array stays L2-resident. **Do not copy them into a private `T c[45]`:** in the follow-up's standalone kernel that pushed registers to 127/137 and the launch failed ("too many resources requested") at blockDim 512 and 1024 (follow-up §3.4, caveat 3). The shared-memory budget (`src/recon/recon_dispatch.cu:26-39`) drops the coefficient term on the per-face path.

### 4.4 Cost

- **Flops:** unchanged. The same nine 5-point dot products and the same β and α arithmetic, about 115–120 flops per face per variable before and after (Tianhao §3.6, counted from `src/recon/interp_impl.h:104-120`).
- **CUDA [measured offline + projection]:** snapy's own WENO5 kernel runs 1.27 Gcell/s at nvar = 5 [measured in snapy, RTX 5090]. A standalone kernel pair that differs only in where the coefficients come from (shared vs global, outputs bitwise equal) is slower on the global path by 0.0 % (nx1 128), +20.5 % (256), +9.8 % (512) and +23.4 % (1024) on the block path, and +13.5 % (2048) / +13.6 % (4096) on the tiled path. **Projected onto snapy's kernel: 11–17 %. This is a projection, not measured in snapy.**
- **Caveats:**
  1. This is the reconstruction kernel alone, not a timestep.
  2. The RTX 5090 has 100 MB of L2. A smaller-L2 GPU, including this machine's GTX 1080 Ti, is unmeasured and expected to do worse [H].
  3. The standalone kernels needed matched `__launch_bounds__`, so the ratios are indicative.
- **CPU:** not measured.

### 4.5 Uniform grids stay bitwise identical

Evaluated on a uniform grid, the general formula differs from the stored literals by about 1 ULP: a worst relative difference of 1.147e−15 in face values [measured offline, Tianhao §3.5]. Therefore, **when the grid is classified uniform** (§2.2), hand the kernels today's `cm`/`cp` buffers (`src/recon/weno5.cpp:11-23`, `src/recon/cp5.cpp:13-16`) and today's kernels. The new path then never runs on a uniform grid.

### 4.6 Why route B (map to a uniform ξ) was rejected

Route B reconstructs q = (u∘X)·J on the uniform ξ grid, using q̄_i = (h_i/Δξ)ū_i, and sets û_f = WENO5(q̄)_f / J_f.

1. **Metric error.** At a well-resolved bottom (dz/H = 0.05), route B's error relative to route A's linear reconstruction is 38×, 245×, 788×, 4828× and 32 936× at R = 1.01, 1.03, 1.05, 1.10 and 1.20 [measured offline, follow-up Check B]. Its error grows as (ln R)^2.32 while route A's is flat (fitted exponent −0.05). The exponent 2.32 is a fit over R ∈ [1.01, 1.20], not a derivation.
2. **Free-stream preservation is lost.** Naive route B leaves |u_f − 1| = 2.8e−8 for u ≡ 1 at r = 1.1, N = 128, against 4.4e−16 for route A [measured offline, Tianhao §3.3]. The fix (divide by WENO5(J̄) with the same nonlinear weights) adds about 10 % flops.
3. **Smoothness requirement.** Route B needs a map with as many derivatives as the scheme's order across every block junction and wall. Shu 1998 states that high-order finite-difference ENO/WENO "can only be applied to a uniform grid or a smoothly varying grid", while finite-volume WENO "can be applied to arbitrary nonuniform grids" (follow-up §2.2). That rules out option B face lists and the ghost rules (a) and (c).
4. **Limiter semantics.** β would be computed on J̄·p′ instead of p′ (Tianhao §3.4).

Shu (1998) recommends route A for non-uniform finite-volume grids in so many words: "pre-compute the constants {c_rj} as in (2.20) … and store them before solving the PDE" (follow-up §2.2).

### 4.7 Not covered by route A

The hydrostatic reference (§5), PLM, WENO3 and cp3. PLM's harmonic-mean slope (`src/recon/plm.cpp:20-29`) is exact for linear data on an exactly geometric grid (slopes (1+1/q)h/2 and (1+q)h/2 have harmonic mean h; order 2.04–2.05 at q = 1.05–1.2) [measured offline, Linfeng]. It is not exact on an option-B face list or at a ratio jump.

---

## 5. Well-balance: reference fix (Xinyue)

**Rest conditions** (Xinyue A2). At u = 0 the Cartesian momentum update of cell i vanishes if and only if

$$
\text{(C1)}\;p^*_{i-\frac12}-p^*_{i+\frac12} = g\bar\rho_i\Delta z_i,\qquad
\text{(C2)}\;p^L_f = p^R_f\;\forall f,
$$

because the LMARS face velocity at rest is ū = (p_L − p_R)/(2ρc) (`src/riemann/lmars_impl.h:42-43`). The faces carry p^{L,R}_f = R^{L,R}_f[p′] + p_sf,f (`src/hydro/hydro_forward.cpp:465-468`). The scan gives p_sf,i−½ − p_sf,i+½ = g·ρ̄_i·Δz_i for any widths (`src/hydro/hydro_ref_x1_impl.h:42-49`), and the source is ρ̄_i·g with no dz (`src/forcing/const_gravity.cpp:49`). So both conditions hold if

$$
\text{(C3)}\quad p'_i = \bar p_i - Q_i[p_{\rm sf}] = C\quad\text{and every reconstruction row sums to 1}.
$$

Route A's rows satisfy that identically (§4.2). Main is therefore **structurally balanced on a stretched grid**. Q is `w6` on uniform grids (`src/hydro/hydro_ref_x1_impl.h:141-142`) and the log-mean on non-uniform grids (`:181-186`).

**Measured on main** [in snapy, CPU, Xinyue B2]. Explicit runs, initial condition projected by `balance_column`, t = 300 s:

| grid | nx1 | isothermal max\|v\| (m/s) | adiabat max\|v\| (m/s) |
|---|---|---|---|
| uniform | 128 | 4.5e−11 | 1.3e−11 |
| x1rat 1.05 | 32 | 7.3e−10 (8.1e−13 at rtol 1e−13) | 1.5e−9 (1.4e−12) |
| x1rat 1.05 | 64 | 1.9e−9 (2.8e−10) | 1.8e−9 (1.2e−11) |
| x1rat 1.05 | 128 | **3.1e−7** | **5.1e−9** |

At nx1 = 128, `balance_column` cannot reach its default rtol of 1e−10: it stalls at 1.5–2.1e−9 (isothermal) and 3.5–4.2e−10 (adiabat). The implicit runs (scheme 9, Courant up to 32) agree with the explicit ones within a factor of 6.

**Cause** [measured offline, Xinyue B3.2]. The log-mean `pref = g ρ dz / log(lo/hi)` (`src/hydro/hydro_ref_x1_impl.h:182-185`) has a round-off floor of about ε(p/Δp)² in units of g·ρ·dz, where Δp/p = g·dz/(RT). Against a long-double scan: 1.6e−9 (isothermal) and 1.4e−10 (adiabat) at nx1 = 128, which matches the stalls within a factor of 3.

**Candidate fix [H, untested in snapy].** In exact arithmetic lo = hi + dp with dp = g·ρ_i·Δz_i, the same increment the scan used (`:43`). Hence

$$
\ln\frac{lo}{hi} = \operatorname{log1p}\!\Big(\frac{dp}{hi}\Big),\qquad
Q_i = \frac{dp}{\operatorname{log1p}(dp/hi)} ,
$$

which is the same mean with a floor of about ε·p/Δp. Offline it gives 8.1e−13 and 3.2e−13 (Xinyue B3.2). Notes for the fix branch:
- It must change **both** copies of the log-mean: the header used by CPU and CUDA (`src/hydro/hydro_ref_x1_impl.h:181-186`; CUDA calls it from `src/hydro/hydro_dispatch.cu:26-29`) and the separate MPS tensor path (`src/hydro/hydro_dispatch.cpp:154-156`).
- `balance_column` calls the same dispatch (`src/hydro/balance_column.cpp:86-90`), so the initial condition and the solver share Q.
- The uniform `w6` branch is untouched, so uniform grids stay bitwise.
- The `|ratio − 1| < 1e−6` arithmetic-mean fallback (`:184-185`) can likely go with log1p [H].
- `SNAP_WB_REF4`'s 4-face cubic Q (`src/hydro/wb_ref4.cpp:165-193`) is the alternative. Its round-off on thin cells is unmeasured.

**Initial conditions.** An unprojected analytic column on x1rat 1.05 sits about 0.1 m/s out of balance at any nx1: 9.0e−2 to 1.2e−1 isothermal, 6.7e−3 to 2.1e−2 adiabat (Xinyue B2). Under fixed-shape refinement it converges at order 2.0. Stretched decks must project with `balance_column`.

**Accuracy only (not rest).** The density reference smooths ρ/p with an index binomial (`src/hydro/hydro_ref_x1_impl.h:107`; `src/hydro/wb_ref4.cpp:124-127`) and takes a midpoint face mean (`src/hydro/hydro_ref_x1_impl.h:195-198`).

**Literature.** Käppeli & Mishra (2014) balance a genuine hydrostatic equilibrium at second order. This was verified indirectly through Grosheintz-Laval & Käppeli (2019), which is high order and built on any standard reconstruction (follow-up §2.5). *Placeholder:* K&M's hydrostatic-reconstruction equations with page/equation numbers, pending Xinyue's reading of the attached PDF.

---

## 6. Implicit solver (Jiheng)

**Recommendation: leave the kernels alone.** They already use per-cell metrics:
- Rows scale by `AREA(i)`, `AREA(i+1)` and `0.5/VOL(i)` (`src/implicit/vic_assemble_full_impl.h:89-99`). In Cartesian, VOL/AREA = Δz_i is the cell width, per cell.
- The gravity Jacobian `Φ(IVX,IDN) = Φ(IPR,IVX) = g` is pointwise (`:38-40`).
- Face work uses `work_lo/hi = ½·A·(x1v − x1f)/V` from the coordinates (`src/implicit/implicit_hydro.cpp:263-266`).
- The Cartesian fast path's ½ and ¼ (`src/implicit/vic_assemble_full_impl.h:101-108`) are midpoint ratios, exact because x1v is the face midpoint (`src/coord/cartesian.cpp:26-27`).
- The geometry cache is keyed on the `x1f` version (`src/implicit/implicit_hydro.cpp:247-279`).

**One open consistency point** (Xinyue A2, correcting my inventory, which called it "OK"). Each face Jacobian is the equal-weight mean ½(∂F/∂q_i + ∂F/∂q_{i±1}) (`src/implicit/vic_assemble_full_impl.h:94-99`). The linearised pressure difference is therefore (p_{i+1} − p_{i−1})/(2Δz_i), while the centres are (Δz_{i−1} + 2Δz_i + Δz_{i+1})/2 apart. This does not affect rest: the right-hand side is zero and the solve is linear in it (`src/implicit/implicit_hydro.cpp:397-400`). Whether it matters for stability at Courant 250 is Jiheng's call; Jiheng recommends no kernel change.

**New test rung.** The tall-column test (`tests/test_implicit_gravity_tall_column.py:31-33`) is uniform: NZ = 45, DZ = 29 946.8 m, g = 23.1, T0 = 786 K, γ = 1.403461, R = 3515, Courant ∈ {6.6, 65.6, 100, 197, 250}. With c_s² = γRT and H_p = RT/g,

$$
\frac{g\,\Delta z}{c_s^2} = \frac{\Delta z/H_p}{\gamma},
$$

which is 0.178 for that test (Δz/H_p = 0.250), computed from those constants. On a stretched column the coarse bottom sets g·Δz_max/c_s². Add a rung (Jiheng) where it reaches the target grid's bottom value: Δz/H_p = 0.6–1.0 gives 0.43–0.71 at that γ. *Placeholder:* Jiheng's exact rung values, and whether the Courant ladder is defined on Δz_min (where the vertical Courant number peaks on a stretched grid) [open, D5].

---

## 7. Open question: nonlinear weights at the coarse bottom (section owner Tianhao)

**Measured offline** (follow-up §1; R = 1.05/1.10, H = 1, profiles P1–P4):
- The linear route-A reconstruction keeps an error-vs-dz/H exponent of **A_lin 4.35–4.78** in the 0.6–1.0 band on P2/P4. Jiang–Shu WENO on the same data falls to **A_weno 1.43–2.25**. These are exponents of error against dz/H, not convergence rates.
- On an isolated stencil with u = exp(−z/H), the deepest candidate's weight relative to optimal is **w2/d2 = 0.096 at dz/H 0.8 and 0.018 at 1.0** (0.003 at 1.2). β measures absolute curvature, which on an exponential column tracks depth, not roughness. For example b2/b0 = 12 at dz/H = 1.0 on a perfectly smooth profile.
- At dz/H = 0.8 the bottom error is 2.97e−3 against 1.43e−7 in the interior. Under a fixed stretching map the bottom recovers fifth order once dz/H ≲ 0.1.
- snapy's `scale` option does not help: weights move by at most 2.3e−5. **WENO-Z** (Borges τ5) helps only up to about **dz/H 0.5** and tracks plain WENO from 0.8. Reconstructing **log p is worse**, by up to 46×, because the log of a cell average is not the cell average of the log.
- Candidate directions (all untested): a relative or mesh-scaled β, an ε tied to the local cell size (Cravero & Semplice 2016 analyse ε = h_j² or h_j, at third order), or WENO-Z.

**Pending answer, placeholder** (asked of Tianhao and Xinyue in ts 1793648649): *which variables WENO5 sees on the x1 sweep at 2d9fa419, and does the collapse persist on those?*
> Code pre-fill for them to confirm or correct (Linfeng's reading, not their answer):
> - With gravity on, the x1 sweep subtracts the reference before reconstructing: `wx1[IPR] −= pref`, `wx1[IDN] −= dref` (`src/hydro/hydro_forward.cpp:400-401`, reconstruction at `:456`).
> - With `type: weno5`, `pinterp1` is WENO5 and `pinterp2` is **cp5** (`src/recon/interpolation.cpp:29-33`; `src/recon/reconstruct.cpp:75-76`).
> - With `shock: false`, which is the default whenever a `vertical` section exists (`src/recon/reconstruct.cpp:33`), WENO5 sees **ρ′ = ρ − dref** (`:139-140`) and the **tracers as full fields** (`:157-158`). **p′ and v go through linear cp5** (`:146-148`).
> - Only with `shock: true` does WENO5 also see p′ and v (`:99-100`).
> - Consequence [H]: the P4 (perturbation) case applies to p′ only under `shock: true`. Under the default it applies to ρ′, whose size depends on the index-smoothed dref (`src/hydro/hydro_ref_x1_impl.h:107`).
>
> *Rerun result on the deviations: pending (Tianhao, Xinyue).*

**Why it goes first:** if the coarse bottom is effectively third order and biased upward even with route A, the cost saving at dz/H ≈ 1 may not be worth it. If WENO5 only sees ρ′ and tracers, the impact may be smaller [H].

---

## 8. Acceptance criteria

1. **Round-off rest.** Resting isothermal and adiabatic columns on x1rat 1.05 and 1.1 (convention per D1) at nx1 = 32, 64, 128, explicit and implicit-9, initial condition projected by `balance_column` **at its default rtol 1e−10**, which must converge. Pass when max|v|/c_s after 300 s is within 10× of the uniform control at the same nx1 [threshold proposed]. Main today passes at 32 and fails at 128 (3.1e−7 m/s isothermal).
2. **WENO5 order (reworded).** Fix the stretching **map** and refine under it: X(ξ) = (q₀^{N₀ξ} − 1)/(q₀^{N₀} − 1) with N₀ = 64, refined by subdividing ξ. Equivalently, per-cell ratio q₀^{N₀/N}. A fixed per-cell ratio on a fixed domain is not a convergent family, because h_max tends to (r − 1)L/r (Tianhao §3.2; Xinyue B4).
   - 2a: a smooth profile converges at ≥ 4.5 over the last two levels [threshold proposed; offline route A reaches 4.94 and 4.84 at N = 2048].
   - 2b: the same test in a running column with reflecting walls, to expose the ghost rule (§3).
3. **Bitwise uniform.** A deck without `x1rat`/`x1f` gives bitwise the same output as 2d9fa419 on CPU and CUDA, and the existing ctest suite passes unchanged.
4. **Tall-column implicit test passes on a stretched grid,** through Courant 250 and including the new g·Δz_max/c_s² rung (§6).
5. **Cost per step vs uniform.** Measure it at the same nx1 on CPU and CUDA, replacing the 11–17 % kernel-only projection with an in-snapy number. Report the GPU and its L2 size, and include one smaller-L2 GPU.

---

## 9. Open items and owners

| # | item | owner | state |
|---|---|---|---|
| D1 | `x1rat` direction convention; whether to add option B (`x1f` list) in the first PR | Linfeng proposes; Xi/Cheng decide | open |
| D2 | ghost-width rule per boundary type (§3) | Linfeng + Tianhao | proposed |
| D3 | uniform classification from the grid key instead of the per-block probe | Linfeng + Xinyue | proposed |
| D4 | route-A layout (CPU index, MPS, CUDA global rows), cp5 per-face rows | Tianhao | drafted here; needs his edit |
| D5 | rung values; Courant defined on Δz_min or Δz_max | Jiheng | pending |
| Q1 | §7: which variables WENO5 sees; rerun on deviations | Tianhao + Xinyue | pending (ts 1793648649) |
| Q2 | log1p Q in snapy (all three backends), and `SNAP_WB_REF4` round-off on thin cells | Xinyue (fix branch, after design sign-off) | hypothesis |
| Q3 | Käppeli & Mishra equations with page/equation numbers | Xinyue | pending |
| Q4 | route-A cost on a smaller-L2 GPU (e.g. this machine's GTX 1080 Ti) and per step | Tianhao / Linfeng | unmeasured |
| Q5 | Wang, Feng & Spiteri (2008) content; novelty not claimed | Tianhao | unread |
| F1 | other uniform-spacing fixes from the inventory: diffusion `centered_derivative` (`src/forcing/diffusion.cpp:70-84`) and `face_average` (`:99-108`), cubed-sphere diffusion scalar h (`src/forcing/diffusion_cubed_sphere.cpp:191`), `bot_heat`/`top_cool` budgets (`src/forcing/bot_heat.cpp:52-54`, `src/forcing/top_cool.cpp:52-54`), the dx²/12 curvature correction (`src/hydro/hydro_forward.cpp:1023-1047`) | unassigned | listed |
| R1 | critic review of this note | UJ42UV0TW | after the note lands |
| H1 | hosting: one file on a doc-only branch of happysky19/snapy (proposed) | Tianhao to agree | no push until agreed |

---

## Appendix A. Conflicts between the input reports and the code at 2d9fa419

1. **WENO report §3.4/§5** names the uniform `w6` quadrature (`src/hydro/hydro_ref_x1_impl.h:140-142,158-163`) and the `:107` binomial as the remaining well-balance obstruction. At 2d9fa419 a stretched grid never takes the `w6` branch: `src/hydro/hydro.cpp:550-556` classifies it non-uniform, and the log-mean (`:181-186`) is used. The `:107` binomial affects ρ′ accuracy only. Xinyue's runs locate the real obstruction in the log-mean's round-off (§5).
2. **WENO report §1.3:** "PLM … on a stretched grid its slope is already the wrong one." On an exactly geometric grid the harmonic-mean slope (`src/recon/plm.cpp:20-29`) is exact for linear data and keeps second order. It is wrong only at ratio changes and on general face lists (§4.7).
3. **Follow-up §1.2 (P4):** "the perturbation alone, which is what the well-balanced x1 path actually hands WENO5." With `type: weno5` and the default `shock: false`, p′ and v go through **cp5**, and WENO5 sees ρ′ and the tracers (§7 pre-fill, `src/recon/reconstruct.cpp:33,139-158`; `src/recon/interpolation.cpp:29-33`). P4 applies to p′ only with `shock: true`.
4. **Well-balance report B1:** "With no section at all the options default to `shock = true` (`reconstruct.hpp:51`)." The struct default is true. However, `from_yaml` returns before setting `interp()` when `dynamics`, `reconstruct` or the section is missing (`src/recon/reconstruct.cpp:19-20,29`). `interp` then stays null (`src/recon/reconstruct.hpp:57`), and `InterpImpl::create` rejects a null option (`src/recon/interpolation.cpp:8`). [H, not run] Such a deck may fail at construction instead of running with shock = true. Xinyue should confirm how her `shock: true` runs were configured.
5. **Linfeng's inventory, row 3a,** marked the implicit face terms "OK". Xinyue's observation that the face Jacobian is an equal-weight mean (`src/implicit/vic_assemble_full_impl.h:94-99`) is correct. §6 carries it as an open consistency point.
6. **Not in either report:** the MPS backend has its own copy of the log-mean (`src/hydro/hydro_dispatch.cpp:154-156`). The log1p fix must change it as well as the header.
7. **Not code, but the record:** follow-up §2.5 says Käppeli & Mishra could not be read. The PDF has since been attached in the thread, and its equations are pending (Q3).
8. **Consistent, but different families:** the frozen-coefficient order is 1.66–1.93 under a fixed map (Tianhao) and 1.00 at a fixed per-cell ratio (Linfeng's inventory). Both are right for their family; criterion 2 fixes the family.

## Appendix B. References (corrected citations from the follow-up report only)

- G.-S. Jiang, C.-W. Shu, *Efficient Implementation of Weighted ENO Schemes*, J. Comput. Phys. 126(1) (1996) 202–228, doi:10.1006/jcph.1996.0130. Eqs. 3.2–3.4 match `src/recon/weno5.cpp` and `src/recon/interp_impl.h:108-113`; written on a uniform mesh.
- C.-W. Shu, *Essentially Non-Oscillatory and Weighted Essentially Non-Oscillatory Schemes for Hyperbolic Conservation Laws*, in *Advanced Numerical Approximation of Nonlinear Hyperbolic Equations*, Lecture Notes in Mathematics, Springer (1998) 325–432, doi:10.1007/BFb0096355; also NASA/CR-97-206253, ICASE Report 97-65. Eq. 2.20 gives the non-uniform c_rj, "pre-compute … and store them". The series volume number is not verified.
- I. Cravero, M. Semplice, *On the Accuracy of WENO and CWENO Reconstructions of Third Order on Nonuniform Meshes*, J. Sci. Comput. 67(3) (2016) 1219–1246, doi:10.1007/s10915-015-0123-3 (arXiv:1503.00736). Third order; mesh-dependent ε. Not a source for the order-loss claim.
- I. Cravero, G. Puppo, M. Semplice, G. Visconti, *CWENO: Uniformly accurate reconstructions for balance laws*, Math. Comp. 87(312) (2018) 1689–1719, doi:10.1090/mcom/3273. CWENO linear weights are geometry-independent, an alternative to route A that should be acknowledged.
- R. Käppeli, S. Mishra, *Well-balanced schemes for the Euler equations with gravitation*, J. Comput. Phys. 259 (2014) 199–219, doi:10.1016/j.jcp.2013.11.028. Second order; content verified indirectly.
- J. Grosheintz-Laval, R. Käppeli, *High-order well-balanced finite volume schemes for the Euler equations with gravitation*, J. Comput. Phys. 378 (2019) 324–343, arXiv:1807.04074.
- R. Wang, H. Feng, R. J. Spiteri, *Observations on the fifth-order WENO method with non-uniform meshes*, Appl. Math. Comput. 196(1) (2008) 433–447, doi:10.1016/j.amc.2007.06.024. Not read; likely prior art for the face-dependent WENO5 weights.
