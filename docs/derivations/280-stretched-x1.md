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
5. **The grid contract bounds how coarse the bottom may get.** Cheng has set the contract: dz(z) ≤ H(z)/n with a **fixed n ≥ 5 over the whole column**, so the stretch ratio *follows from* T(z) through H(z) = RT(z)/g and is not a free `x1rat` the deck may choose. That puts the realistic band at **dz/H 0.05–0.25**, with **local stretch ratios near 1**. The earlier dz/H 0.6–1.0 measurements (route-A linear exponent 4.0–4.8; A_weno 1.97 and 1.43, identical for route A, route B and the frozen coefficients) are **out of contract everywhere** and are retained **only as a clearly labelled OUT-OF-CONTRACT APPENDIX** (§7.3); they are **not acceptance evidence**. The in-contract measurement at dz/H 0.05–0.25 is **done**: there is **no Jiang–Shu β mis-fire in band** — the interior nonlinear weights sit exactly on the optimal linear weights (ω_r/d_r = 1.0000 to four decimals) in every case measured [measured offline]. §7.

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

**Grid contract (Cheng).** This section is written for the contract Cheng set: **dz(z) ≤ H(z)/n with a fixed n ≥ 5 over the whole column**. The stretch ratio is then a *consequence* of T(z), not a free `x1rat`: the realistic band is **dz/H 0.05–0.25** and the **local stretch ratios are near 1**. Route A itself is indifferent to the restriction — its linear weights are positive and well conditioned for ratio jumps s ∈ [1/16, 16] (§4.2), far outside anything the contract can produce — but the restriction changes **what counts as evidence**. Any number measured at dz/H 0.6–1.0 is out of contract and lives only in the labelled OUT-OF-CONTRACT APPENDIX (§7.3); it is not acceptance evidence for route A or against it. The in-contract comparison of route A against today's frozen coefficients is **§4.8**, and what the contract implies for the grid key is **§4.9**.

> **OPEN QUESTION (D1) — `x1rat` direction convention. Not settled; do not read §2.2 as a decision.** Cheng is taking this to Xi together with this note. The two candidates are Linfeng's convention in §2.2 — q ≡ h_{k+1}/h_k, the cell above divided by the cell below, so the thread's "each cell 1.05× the one above it" means q = 1/1.05 — and its inverse, (cell below)/(cell above). §2.2 records a *preference* for the first; that preference is **not** a decision and this note does not make one. Linfeng's accompanying point stands under either choice and is exactly why the question has to be answered explicitly rather than inferred: **Xinyue's runs grew cells downward by 1.05**, so whichever convention is adopted, the tests must state it. Route A reads face positions directly and is correct under either convention; what the convention decides is the meaning of the deck key, and therefore which grid a test actually builds.

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

M_r depends only on the width ratios, so β stays dimensionless and the absolute ε = 1e−6 keeps its uniform-grid meaning. The kernel's two-squares layout and its 13/12 and 1/4 multipliers stay. **Route A therefore keeps the shipped absolute ε, and this note recommends no ε change — but that position, like every ε statement here, is scoped by row and by location, not global:** a mesh-scaled ε is the better rule on an interior tracer face and the worse one at the wall on ρ − `dref` (§7.5, §7.7). Route A is independent of which ε is chosen; it only guarantees that the choice means on a stretched grid what it means on a uniform one. [Layout choice, H] store A_r/√(13/12) and B_r/√(1/4) in rows c4–c9.

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

1. **Metric error.** At a well-resolved bottom (dz/H = 0.05), route B's error relative to route A's linear reconstruction is 38×, 245×, 788×, 4828× and 32 936× at R = 1.01, 1.03, 1.05, 1.10 and 1.20 [measured offline, follow-up Check B]. Its error grows as (ln R)^2.32 while route A's is flat (fitted exponent −0.05). The exponent 2.32 is a fit over R ∈ [1.01, 1.20], not a derivation. **This comparison is inside the grid contract** (dz/H = 0.05 is the well-resolved end of the 0.05–0.25 band), so the rejection of route B does not rest on any out-of-contract number.
2. **Free-stream preservation is lost.** Naive route B leaves |u_f − 1| = 2.8e−8 for u ≡ 1 at r = 1.1, N = 128, against 4.4e−16 for route A [measured offline, Tianhao §3.3]. The fix (divide by WENO5(J̄) with the same nonlinear weights) adds about 10 % flops.
3. **Smoothness requirement.** Route B needs a map with as many derivatives as the scheme's order across every block junction and wall. Shu 1998 states that high-order finite-difference ENO/WENO "can only be applied to a uniform grid or a smoothly varying grid", while finite-volume WENO "can be applied to arbitrary nonuniform grids" (follow-up §2.2). That rules out option B face lists and the ghost rules (a) and (c).
4. **Limiter semantics.** β would be computed on J̄·p′ instead of p′ (Tianhao §3.4).

Shu (1998) recommends route A for non-uniform finite-volume grids in so many words: "pre-compute the constants {c_rj} as in (2.20) … and store them before solving the PDE" (follow-up §2.2).

### 4.7 Not covered by route A

The hydrostatic reference (§5), PLM, WENO3 and cp3. PLM's harmonic-mean slope (`src/recon/plm.cpp:20-29`) is exact for linear data on an exactly geometric grid (slopes (1+1/q)h/2 and (1+q)h/2 have harmonic mean h; order 2.04–2.05 at q = 1.05–1.2) [measured offline, Linfeng]. It is not exact on an option-B face list or at a ratio jump.

### 4.8 Measured in the contract band: route A against today's frozen coefficients

All of §4.8 is **[measured offline]** on the replica validated against the compiled library in §7.1. The grid is the dry-adiabat contract grid of §4.9 at **local ratio 1.063** — cells growing *downward* by 1.063, i.e. 1/0.94080 in the +x1 convention §4.9 tabulates, which is exactly the ambiguity D1 has to settle — with the stretching *map* held fixed and refined under it (criterion 2 of §8). Errors are max absolute over the column.

**Tracer through WENO5** (a raw row: no reference is subtracted from tracers, `src/hydro/hydro_forward.cpp:400-401`):

| N | n = H/Δz | route A | rate | frozen | rate | A better by |
|---|---|---|---|---|---|---|
| 18 | 5 | 1.670e−03 | – | 2.904e−03 | – | 1.7× |
| 36 | 10 | 9.958e−05 | **4.07** | 3.074e−04 | 3.24 | 3.1× |
| 72 | 20 | 3.740e−06 | **4.73** | 5.374e−05 | 2.52 | 14× |
| 144 | 40 | 1.208e−07 | **4.95** | 1.266e−05 | **2.09** | **105×** |

**Velocity through cp5** (also raw, rows `IVX..IPR` minus the reference-subtracted pressure, §7.2):

| N | n = H/Δz | route A | rate | frozen cp5 | rate | A better by |
|---|---|---|---|---|---|---|
| 18 | 5 | 3.995e−02 | – | 6.925e−02 | – | 1.7× |
| 36 | 10 | 1.412e−03 | **4.82** | 1.070e−02 | 2.69 | 7.6× |
| 72 | 20 | 4.850e−05 | **4.86** | 2.517e−03 | 2.09 | 52× |
| 144 | 40 | 1.903e−06 | **4.67** | 6.269e−04 | **2.01** | **329×** |

**So even at a local ratio of 1.063 — well inside the contract — today's frozen coefficients are second order on the raw variables and route A is fifth.** This is the in-contract case for route A, and it does not rest on any out-of-contract number.

**Scope of the cp5 columns: they are `shock: false` numbers and do NOT describe the `jupiter_gcm` deck.** `shock` is **explicitly true** in that deck — `examples/jupiter_gcm.yaml:88`, `vertical: {type: weno5, scale: true, shock: true}`, and the same at `examples/jupiter_gcm_dry.yaml:43`. It is not a default. In that branch `src/recon/reconstruct.cpp:99-100` sends the **whole tensor** through `pinterp1` = WENO5, so under that deck the velocities and p − p_ref do not reach cp5 at all (§7.2). The **velocity** table above (route A 4.82/4.86/4.67 against frozen 2.69/2.09/2.01, **329×** at n = 40) and the p − p_ref result below (rate 2.00, route A equal to frozen) are therefore `shock: false` measurements, and **must not be quoted for `jupiter_gcm`**. The **ρ − ρ_ref and tracer columns remain valid for it** — including the **105×** at n = 40 — because those rows go through WENO5 either way. **WENO5 nonlinear weights on p − p_ref and on raw velocity under `shock: true` were NOT run.** That would be **new columns**, not a rescoping of these, and no number in §4.8 is relabelled to stand in for them.

**Where route A changes nothing: ρ − ρ_ref and p − p_ref.** On those two rows route A and the frozen coefficients agree **to three digits** at every level, because both are **reference-limited** rather than reconstruction-limited: p converges at rate **2.00** and ρ at **0.53–1.53**, with the same numbers either way. The cap on p is the log-mean cell reference (`src/hydro/hydro_ref_x1_impl.h:181-186`); the cap on ρ is the index-space binomial smoother in `dref` (`:107`), which §7.1 measures as first order on its own. Route A is invisible on these rows, and an acceptance test for route A must therefore use the **raw** rows above, not ρ′ or p′.

**Isothermal columns.** Under the contract an isothermal column is **exactly uniform** (ratio 1.000000, §4.9), so route A and the frozen coefficients are identical to the digit on every row and both are fifth order. That is §4.5 holding in practice, not a separate result.

**Route B was not run.** The brief made it optional and it was not free — it needs its own metric construction on each refinement level — so no route B number was produced in the contract band. Route B is rejected in §4.6 on the grounds given there (including one in-contract measurement, §4.6 item 1); **nothing in §4.8 adds to or subtracts from that rejection.**

### 4.9 Grid-key consequence of the contract: when one `x1rat` is enough

Solving the contract `Δz(z) = H(z)/n` as `z_{i+1} = z_i + H(z_i)/n` on a 0–100 km Jupiter-like column (R_s = 3600 J/kg/K, g = 24 m/s², dry adiabat Γ = g/c_p = 2e−3 K/m) gives **[measured offline]**:

| atmosphere | n | N | Δz/H | local ratio (min / max / median) |
|---|---|---|---|---|
| isothermal | 5 / 8 / 10 | 11 / 18 / 22 | 0.2020 / 0.1235 / 0.1010 | 1.00000 / 1.00000 / 1.00000 |
| dry adiabat | 5 | 18 | 0.2034 | 0.94080 / 0.94080 / 0.94080 |
| dry adiabat | 8 | 29 | 0.1263 | 0.96283 / 0.96283 / 0.96283 |
| dry adiabat | 10 | 37 | 0.0990 | 0.97075 / 0.97075 / 0.97075 |

Two structural facts follow **[derivation]**:

* **Isothermal ⇒ the contract grid is exactly uniform.** H is constant, so Δz = H/n is constant and no stretching is needed at all.
* **A constant lapse rate ⇒ the contract grid is exactly geometric,** with

$$
\texttt{ratio} \;=\; 1 - \frac{\Gamma R_s/g}{n},
$$

since H ∝ T, T is linear in z, and Δz_{i+1}/Δz_i = T(z_{i+1})/T(z_i) = 1 − Γ·Δz_i/T_i. Checked against the table: Γ R_s/g = 2e−3 · 3600/24 = 0.30, so 1 − 0.30/5 = 0.9400 against the measured 0.94080 and 1 − 0.30/10 = 0.9700 against 0.97075 (the excess is the finite-cell versus continuum difference).

**Consequence for the grid key (§2.2), stated here and not there:** a single `x1rat` satisfies Δz ≤ H(z)/n over the whole column **if and only if the lapse rate is constant**. A column whose lapse rate changes with height — a troposphere under a stratosphere, which is the realistic case — is **not** expressible as one geometric ratio and needs an **explicit face list** (option B). That makes option B a requirement of the contract for realistic T(z), not a convenience. The `x1rat` direction convention itself remains the OPEN QUESTION (D1) recorded at the head of §4; nothing here decides it.

**PENDING:** which of the two cases the `jupiter_gcm` deck is cannot be settled here. Jiheng has not posted the face lists, and no column was invented in their place. §4.8 and §7.5 are ready to rerun on his actual lists at n = 5 and 10.

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

## 7. Nonlinear weights at the bottom of the column (section owner Tianhao)

### 7.1 The grid contract decides what is in scope — and the in-contract answer

**Contract (Cheng).** The vertical grid must satisfy

$$
\Delta z(z)\;\le\;\frac{H(z)}{n},\qquad n\ \text{fixed},\; n \ge 5,\ \text{over the whole column},
$$

with H(z) = RT(z)/g the local scale height. The ratio is therefore **not a free parameter**: a column is specified by n, and the widths **follow from T(z)**. Under this contract the realistic band is

$$
\Delta z/H \in [0.05,\,0.25],\qquad\text{local stretch ratios near } 1 .
$$

**What that does to this section.** The question as the draft posed it — do the Jiang–Shu weights collapse at a coarse bottom, dz/H ≳ 0.6, on smooth data — is **out of contract**: no column satisfying dz ≤ H/n with n ≥ 5 reaches that band anywhere, bottom included. The dz/H 0.6–1.0 measurements are therefore kept **only as the clearly labelled OUT-OF-CONTRACT APPENDIX in §7.3**, and they are **not acceptance evidence**: they support no criterion in §8 and must not be quoted as an acceptance failure of route A.

**The in-contract question that replaces it,** and the only one §7 answers: does the Jiang–Shu β mis-fire appear **at all** inside dz/H 0.05–0.25, measured at dz = H/n for n = 5, 8, 10, on the variables WENO5 actually receives (§7.2)?

**Harness validation** [measured in snapy]. Everything below is measured on an offline replica of what snapy hands WENO5, so the replica was first checked against the **compiled** library built from 2d9fa419 (`Weno5InterpImpl` and `Center5InterpImpl` called on a deterministic input of 3 variables × 24 cells, 60 faces per side). Max |replica − compiled| is **4.441e−16** for WENO5 and **2.220e−16** for cp5, with the cp5 right state **bitwise identical on 60 of 60 faces**. Route A evaluated on a **uniform** grid reproduces the same compiled kernel to **8.882e−16**, which is §4.5 measured against the shipped library rather than against a transcription. The `balance_column` residual comparison was **not** run here: that is a main-code baseline and is Xinyue's.

**The answer: no.** [measured offline] **There is no Jiang–Shu β mis-fire in dz/H 0.05–0.25.** The interior ratio ω_r/d_r — where 1.0000 means the nonlinear weights sit exactly on the optimal linear weights — is **1.0000 to four decimals in every case**: rest isothermal, rest dry adiabat, a smooth wave, a localised perturbation, and a deliberately **mismatched** reference, at N = 18, 36 and 72.

| case | N | bottom face ω_0/ω_1/ω_2 ÷ d | **interior median ω_0/ω_1/ω_2 ÷ d** |
|---|---|---|---|
| rest isothermal | 18/36/72 | 1.0000 / 1.0000 / 1.0000 | **1.0000 / 1.0000 / 1.0000** |
| rest dry adiabat | 18 | 2.9081 / 0.0320 / 0.0001 | **1.0000 / 1.0000 / 1.0000** |
| rest dry adiabat | 36 | 2.8082 / 0.1785 / 0.0012 | **1.0000 / 1.0000 / 1.0000** |
| rest dry adiabat | 72 | 2.0889 / 0.5931 / 0.0105 | **1.0000 / 1.0000 / 1.0000** |
| adiabat + smooth wave 1e−3 | 18 | 2.5971 / 0.2131 / 0.0001 | 1.0055 / 0.9978 / 0.9902 |
| adiabat + localised 1e−3 | 18 | 2.9074 / 0.0325 / 0.0001 | 1.0000 / 1.0001 / 0.9981 |
| inversion (reference mismatched) | 18 | 0.2992 / 1.5500 / 0.0036 | 1.1873 / 1.0000 / 0.4245 |

This **closes** the open question rather than producing a fix. The out-of-contract collapse of §7.3 (ω_2/d_2 → 0.018 at dz/H ≈ 1) has no counterpart in band.

**RETRACTION — the bottom-two-face attribution made in this note is withdrawn.** An earlier revision of §7.1 attributed the bottom-two-face weight excursion to the 5-point index-space **binomial smoother** applied to ρ/p when `dref` is built (`src/hydro/hydro_ref_x1_impl.h:107`), and credited Xinyue Chen's wall-row hypothesis as *measured*. **That attribution is retracted.** It was an artefact of a harness with **no ghost region**. The "bottom face" column of the table above is a no-ghost-region number and is kept only as the record of that harness; the **interior** column is unaffected. With a ghost region in place the smoother is not the lever either way (see variant A below), so this note neither confirms nor refutes her hypothesis — it has nothing to say about it.

**The ghost-region control** [measured offline]. The harness was rebuilt with `nghost = 3` and `il`/`iu`; `wb_wall_clamp = true`, verified to be the shipped default (`src/hydro/hydro.hpp:54`, `src/hydro/hydro_options.cpp:57`); `phys_in`/`phys_out = true`, so `jlo = il` and `jhi = iu`; `ext_lo`/`ext_hi = true` (`src/hydro/hydro_ref_x1_impl.h:189-192`); the wall `rop` continuation (`:68-72`); the scan over the **full** array (`:30-59`); ghost widths continuing the contract map; and the ghost state taken from the reflecting index mirror (`src/bc/bc_func.cpp:14`). Two orders of operation were run, and they disagree.

**Variant B — the order the code actually uses — shows NO collapse.** Variant B subtracts the reference (`src/hydro/hydro_forward.cpp:400-401`), then overwrites the **deviation** ghosts with the even mirror (`:409-413`), then reconstructs (`:456`). This is the faithful one.

* **Rest isothermal is exactly 1.000 at all four bottom faces at N = 18, 36 and 72** — with the shipped smoother and with exact ρ/p alike.
* **Dry adiabat**, worst case **1.003 / 0.998 / 1.004** at i = `il`, N = 18 (1.005 / 0.996 / 1.007 with exact ρ/p); worst single value **0.944** (ω_2/d_2 at `il`+1, N = 18). Everything is 1.000 by N = 36–72.
* **Nothing differs from 1.000 by more than 0.006 at N ≥ 36.**

**Variant A — state mirror only, omitting `:409-413` — collapses.** With the deviation mirror left out, the first two faces collapse on **both** grids, including the **uniform isothermal control**:

| case | face | ω_0/ω_1/ω_2 ÷ d |
|---|---|---|
| rest isothermal (uniform grid), every N | i = `il` | 3.333 / 0.000 / 0.000 |
| rest isothermal (uniform grid), every N | i = `il`+1 | 1.111 / 1.111 / 0.000 |
| rest dry adiabat | i = `il` | 3.009–3.247 / 0.000 / 0.000 |

The smoothed and the exact ρ/p runs are **identical to every printed digit** at those faces. **That is why the smoother is not the lever either way:** the collapse appears on a uniform isothermal column, where ρ/p is constant, the smoother is exact and there is no stretching at all. Whether the deviation mirror at `:409-413` is applied is the whole of the difference.

**The smoother also costs an order globally.** `max |ρ − dref|/ρ` on the dry-adiabat contract grid [measured offline]:

| N | n | smoothed (shipped) | exact ρ/p | inflation |
|---|---|---|---|---|
| 18 | 5 | 2.287e−02 | 1.558e−03 | **15×** |
| 36 | 10 | 1.144e−02 | 4.097e−04 | 28× |
| 72 | 20 | 5.720e−03 | 1.051e−04 | 54× |
| 144 | 40 | **2.860e−03** | **2.660e−05** | **107×** |

The shipped smoother converges at exactly **first** order (2.287e−02 → 2.860e−03 over an 8× refinement); with the exact ρ/p the rate is **1.96**. So it inflates the density deviation 15× at n = 5 and 107× at n = 40, and **caps the ρ path near 0.6 order whatever reconstruction route is used** — which is why route A and the frozen coefficients are indistinguishable on ρ − ρ_ref (§4.8).

**The interior result is untouched, and it never depended on the edge** [measured offline]. ω_r/d_r = **1.0000** in the interior, so **there is no Jiang–Shu β mis-fire in dz/H 0.05–0.25**, and the three controls already written for that answer — the smooth wave, the localised perturbation and the deliberately mismatched reference rows of the table above — stand exactly as they were. Neither variant, nor the presence of the ghost region, nor the smoother setting moved the interior off 1.0000. Nothing in this retraction reaches the in-contract answer of §7.1; it reaches only the bottom-face attribution.

**Caveat [H, not measured]: an OUTFLOW bottom boundary.** `src/hydro/hydro_forward.cpp:409-413` is gated on `phys_x1inner && !is_outflow(pmb->options->bfuncs()[0])`, so with an **outflow** bottom it does not fire at all, and **variant A is then the closer model of the code**. The collapse could therefore be **real for outflow bottoms**. That was not measured and stays a hypothesis; every number above is for a reflecting bottom.

**Open, and not measured: the ghost cell WIDTHS.** The harness continues the contract map into the ghost cells, whereas snapy builds ghost faces as a **uniform** extension at the mean width (`src/coord/coordinate.cpp:322-323`, `torch::linspace(gmin − nghost·dx, gmax + nghost·dx, …)`). The uniform-ghost-width alternative was **not** tested, so every ghost-region number above is at contract-map ghost widths.

### 7.2 Which variables WENO5 receives on the x1 sweep — answered at 2d9fa419

The draft's placeholder asked which variables WENO5 sees. **Xinyue has answered at 2d9fa419**, and her file:line are kept as she gave them. This replaces the pre-fill. It is a **code read**, not a hypothesis.

**With `type: weno5` and `shock: false`:**
- **ρ − ρ_ref** goes through **WENO5** (`src/recon/reconstruct.cpp:139`);
- **the tracers** go through **WENO5** (`:157`);
- **v1, v2, v3 and p − p_ref** go through the **linear cp5**, as **one block**, rows `IVX..IPR` (`:146-148`);
- the WENO5/cp5 pairing itself comes from `InterpImpl::create` (`src/recon/interpolation.cpp:29-33`).

**With `shock: true`, every row including pressure goes through WENO5** (`:99-100`).

**Xinyue's two corrections to the pre-fill.**
1. **The cp5/WENO5 split exists only for `type: weno5`.** `weno3` pairs with `cp3` instead (`src/recon/interpolation.cpp:21-25`), so the split is a property of the chosen type, not of the x1 sweep as such.
2. **A deck with no `vertical` `reconstruct` section does _not_ fail.** It **silently defaults to `shock = true` with `type: dc`** — first-order donor cell (`src/recon/reconstruct.cpp:19,20,29`; `src/recon/reconstruct.hpp:51`; `src/recon/interpolation.hpp:30`). This **replaces the draft's hypothesis that such a deck may fail at construction** (Appendix A item 4), and the **[H] label is dropped**: this is now a code-read result, not a hypothesis. The real behaviour is the more dangerous of the two, because the deck runs and quietly loses four orders of reconstruction instead of throwing.

**Where the references are subtracted.** The well-balanced x1 path subtracts references **only from pressure and density** — `wx1[IPR] −= pref`, `wx1[IDN] −= dref` (`src/hydro/hydro_forward.cpp:400-401`) — and then calls the **same** reconstruction **with the floors off** (`:456`).

**Consequence for the measured cases.** p′ reaches WENO5 only under `shock: true`, so the P4 (perturbation-only) case of §7.3 applies to p′ in that configuration alone. Under the default `shock: false` the case that matters is ρ′, whose amplitude depends on the index-smoothed `dref` (`src/hydro/hydro_ref_x1_impl.h:107`). That amplitude **is** now measured — §7.1, `max |ρ − dref|/ρ` — and the pre-fill's [H] on it is discharged. The in-contract measurement of §7.1 was run on this split, not on primitives.

### 7.3 OUT-OF-CONTRACT APPENDIX: dz/H 0.6–1.0 — not acceptance evidence

> **OUT OF CONTRACT.** Every number below was measured at dz/H 0.6–1.0, a band the grid contract of §7.1 excludes everywhere in the column. It is kept for the record only. It is **not acceptance evidence**, it supports no criterion in §8, and it must not be quoted as an acceptance failure.

**Headline** [measured offline]: in the 0.6–1.0 band the **linear** reconstruction survives and the **nonlinear weights** do not. Route A's linear reconstruction holds an effective error-vs-dz/H exponent of **4.0–4.8** through dz/H = 1.0, while Jiang–Shu WENO falls to **A_weno 1.97** (exponential + structure) and **1.43** (perturbation only). The collapse is **identical for route A, route B and the frozen coefficients**, which is what identifies it as a property of the **weights** rather than of the coefficient route.

Supporting detail [measured offline] (follow-up §1; R = 1.05/1.10, H = 1, profiles P1–P4):
- Per profile, **A_lin 4.35–4.78** on P2/P4 against **A_weno 1.43–2.25**. These are exponents of error against dz/H, not convergence rates.
- On an isolated stencil with u = exp(−z/H), the deepest candidate's weight relative to optimal is **w2/d2 = 0.096 at dz/H 0.8 and 0.018 at 1.0** (0.003 at 1.2). β measures absolute curvature, which on an exponential column tracks depth, not roughness. For example b2/b0 = 12 at dz/H = 1.0 on a perfectly smooth profile.
- At dz/H = 0.8 the bottom error is 2.97e−3 against 1.43e−7 in the interior. Under a fixed stretching map the bottom recovers fifth order once dz/H ≲ 0.1 — that is, **inside** the contract band.
- snapy's `scale` option does not help: weights move by at most 2.3e−5. **WENO-Z** (Borges τ5) helps only up to about **dz/H 0.5** and tracks plain WENO from 0.8. Reconstructing **log p is worse**, by up to 46×, because the log of a cell average is not the cell average of the log.
- Candidate directions, all untested, and all relevant **only if the in-contract measurement finds a problem**: a relative or mesh-scaled β, an ε tied to the local cell size, or WENO-Z. The Cravero & Semplice (2016) ε question — ε = h_j² or h_j, analysed there at third order — is being carried **separately and unconditionally**, and does not depend on this appendix.

**Status of the design question.** The draft's argument that the bottom might be effectively third order and biased even with route A, so that the saving would not be worth it, was built on this out-of-contract band and does not carry over. Inside the contract the expectation is that it does not arise, but the point of the running measurement is to say so with an explicit yes/no rather than to assume it. Until it reports, **§7 makes no acceptance claim in either direction**.

### 7.4 Correction of an earlier premise: "exact rest = round-off only"

**That premise is false for the shipped code** [measured offline]. §1 item 3 and §5 describe rest on a stretched grid as failing "only through the round-off of the log-mean". For an **isothermal** resting column the dominant term is instead snapy's own **top anchor**, `top_anchor = pres_top · exp(−g·0.5·dx1f[iu]/rdt_top)` (`src/hydro/hydro_ref_x1_impl.h:37`):

| anchor | N (n) | `max \|p − pref\|/p` |
|---|---|---|
| snapy's anchor (shipped) | 18 (n ≈ 8) | **5.975e−04** |
| snapy's anchor (shipped) | 128 (n ≈ 58) | 1.245e−05 |
| exact top-face pressure | 18 | **1.421e−15** |
| exact top-face pressure | 128 | 1.038e−14 |

With an exact anchor the rest deviation **is** round-off. With the shipped anchor it is **6e−4 — three orders above round-off and second-order convergent.** The log-mean digit loss is the smaller effect and is visible only on the exact-anchor rows, growing 1.4e−15 → 1.0e−14 between n ≈ 8 and n ≈ 58, which is the loss Xinyue described.

On a **dry adiabat the anchor makes no difference at all**: 1.033e−03 with either anchor, rate 2.00 either way. There the cap is the **log-mean cell reference** (`src/hydro/hydro_ref_x1_impl.h:181-186`) being only second-order accurate as a cell average when the column is not isothermal. For an isothermal column the log-mean is exact **[derivation]**: with `lo/hi = e^{Δz/H}`, `pref = (lo − hi)/ln(lo/hi) = (lo − hi)·H/Δz = p̄` identically — which is why the exact-anchor rows above sit at round-off.

This bears on **§5, which is Xinyue's section**: it is recorded here rather than edited into §5, and the log1p candidate fix (Q2) is unaffected by it either way.

### 7.5 The Cravero & Semplice ε, measured in the contract band

**What the paper prescribes.** `eps_j = h_j` or `eps_j = h_j²`, h_j the local cell size, used for the reconstruction in cell Ω_j (Theorem 3 with eq. (10); §5 Conclusions). The mechanism is the one §7.3 lists as a candidate direction: near a smooth extremum both indicators tend to zero and an ε that does not depend on h lets a slight imbalance between them change the order of convergence.

**It is derived for THIRD order only.** The paper's two candidate stencils are 2 cells wide. On the fifth-order case the paper points at **Henrick, Aslam & Powers, J. Comput. Phys. 207 (2005) 542–567**, eq. (29b), for the corresponding condition, and says that there it "was not found useful" to design an optimal form of the nonlinear weights. **So carrying the h-scaling to WENO5 is [H], and the fifth-order proof was not reproduced here.** Jiang & Shu's own expansions give the same β scalings at fifth order as the paper's third-order indicator, which is why the two candidate exponents carry over at all; the stricter WENO5 accuracy condition (ω − d = O(h²) rather than O(h)) is exactly what the Henrick reference is about.

**It is also dimensionally inconsistent as written:** β carries u² and h is a length. That is invisible in the paper's tests (u = x³ + cos x on h ~ 1e−3 makes both O(1)) but not in snapy, where β is in Pa² or (kg/m³)² and h is in metres. The transfer that preserves their **argument** is **[derivation]**

$$
\varepsilon_j \;=\; \sigma_j^2\,\big(h_j/L\big)^q,\qquad q = 1\ \text{or}\ 2,
$$

with σ_j the stencil's own amplitude scale — the quantity snapy's `scale` option already forms (`src/recon/interp_impl.h:90-98`) — and L a fixed reference length.

**Measured** [measured offline], against snapy's absolute ε = 1e−6 (`src/recon/interp_impl.h:115-117`, same immediates in `src/recon/interp_impl.cuh:95-101`):

* **It helps only raw WENO5 variables with smooth extrema.** On the tracer at n = 5 it tightens `max_r |ω_r/d_r − 1|` from **3.2190 to 0.1294**, and the error falls with it (4.949e−04 → 2.897e−04 at n = 5; 3.579e−08 → 1.546e−08 at n = 40, rate 5.01 against 4.95).
* **On a function with a genuine critical point in the stencil the rate recovers an order earlier:** **3.28 against 2.47 at n = 10** (4.40 against 3.55 at n = 20).
* **It cannot affect p or the velocities at all.** Those rows go through cp5, which is linear and has no ε (§7.2).
* **The interior is ε-independent, and that is a check on §7.1.** Interior face i = 6 reads 1.000 under **all four** ε rules. That it is 1.000 across several orders of magnitude in ε is the proof that the interior 1.0000 of §7.1 is genuine — the βs really are equal — and not an artefact of ε dominating.

**RETRACTION — the bottom-face ω_2/d_2 = 0.000 of this section is withdrawn.** An earlier revision of the bullet above went on to say that **the bottom face reads ω_2/d_2 = 0.000 under all four ε rules**, and that ε therefore "does not fix the edge artefact of §7.1". **That 0.000 is withdrawn.** It is the same **no-ghost-harness artefact** as the bottom-face attribution already retracted in §7.1 — its sibling, produced by the same harness — and the no-ghost analogue is what identifies it: with the deviation mirror omitted, the replica reproduces the old **0.000 exactly**, under abs 1e−6, rel 1e−6 and CS q = 2, at **both** bottom faces. There is no edge artefact left for ε to fix or fail to fix, so the claim that ε "does not fix" one is withdrawn with the number.

**With a ghost region there is no 0.000 anywhere** [measured offline]. Same ghost-region harness and the same variant B as §7.1 — reference subtracted (`src/hydro/hydro_forward.cpp:400-401`), deviation ghosts overwritten by the even mirror (`:409-413`), then reconstruct — on the **synthetic** contract grids of §4.9. The row is **ρ − `dref`**, which reaches WENO5 under `shock: true` and `shock: false` alike (`src/recon/reconstruct.cpp:99-100` against `:139-140`), so this one row is not touched by the `shock` scoping of §4.8. Bottom-face ω_2/d_2:

| grid | face | abs 1e−6 (shipped) | rel 1e−6 | CS q = 1 | CS q = 2 |
|---|---|---|---|---|---|
| rest isothermal, N = 18/36/72 | i = `il`, i = `il`+1 | **1.000** | **1.000** | **1.000** | **1.000** |
| rest dry adiabat, N = 18 | i = `il`+1 | **0.969** | 0.089 | 0.547 | 0.148 |
| rest dry adiabat, N = 36 | i = `il`+1 | **0.999** | 0.094 | 0.717 | 0.158 |
| rest dry adiabat, N = 72 | i = `il`+1 | **1.000** | 0.096 | 0.840 | 0.164 |

The isothermal row is 1.000 at **both** faces under **all four** rules at every N. The adiabat was read at i = `il`+1; **no i = `il` adiabat number is quoted here**, because none was measured under the four rules. What the adiabat column shows is not a residue of the old artefact but a **new** and opposite result, which §7.7 states on its own rather than leaving inside this list.

**Two things to record rather than recommend.** First, **no shock or discontinuity case was tested**: every profile here is smooth, so nothing in §7.5 is a recommendation about ε for shock capturing, and the paper's own trade-off (h better on smooth data, h² better on discontinuities) stands untested by me. Second, **snapy's absolute ε = 1e−6 is not scale-free**: how nonlinear WENO5 actually is depends on the units and magnitude of the row being reconstructed — negligible for pressure in Pa, dominant for a small density deviation. A relative ε would at least make that uniform across rows. Neither point is an acceptance criterion, and §7.1's answer does not depend on either. **That second point is now scoped rather than general:** making ε uniform across rows is an improvement *in the interior*, and §7.7 measures it as a **regression at the wall** on the adiabat. **No ε recommendation in this note is global** — every one of them is scoped **by row and by location**, and the scoping is stated in §7.7.

**PENDING:** the `jupiter_gcm` face-list rerun of §7.1 and §7.5 **under `shock: true`** (the deck's own setting, §4.8) awaits Jiheng's lists (§4.9). It was attempted and **not** done: the face lists were not available on this host, and no column was regenerated and no face position invented in their place. No numbers are guessed for it.

### 7.6 Where this diverges from the in-thread bottom-face study

Recorded as a factual comparison, **not** a verdict. Neither set of numbers is asserted here to be wrong.

**Difference 1 — the deviation mirror, and it is the single switch.** Variant A of §7.1 reproduces the other study's reported collapse on **every** grid, including the **uniform isothermal control**. Variant B, on the same harness and the same columns, does not show it at all. So **whether the even mirror on the deviation at `src/hydro/hydro_forward.cpp:409-413` is applied is the one thing that flips the answer**, and the question that separates the two results is which of the two orders the other study used. Variant B is the order the shipped code uses — that is a statement about which variant models `hydro_forward.cpp`, not a claim about the other study's correctness. The outflow caveat of §7.1 cuts the other way: where `:409-413` does not fire, variant A is the closer model.

**Difference 2 — the temperature profile.** Every column measured here has a **constant** lapse rate, which is precisely why the contract grid of §4.9 carries **one constant ratio per n** rather than varying local ratios. A **varying T(z)** — the troposphere-under-stratosphere case §4.9 points at, where the contract needs an explicit face list — was **not run** here, and a grid with varying local ratios is a materially different input to the β indicators. §7 measures that case in neither direction.

### 7.7 At the wall the ordering of the four ε rules reverses

**The result** [measured offline, on the synthetic contract grids of §4.9]. Once the ghost region is in place, the mesh-scaled ε rules are **worse than snapy's shipped absolute ε = 1e−6 at the wall** on the dry adiabat, on the ρ − `dref` row, and the gap **does not close under refinement**. From the §7.5 table, bottom-face ω_2/d_2 at i = `il`+1 across a 4× refinement (N = 18 → 72):

* **absolute 1e−6 (shipped): 0.969 → 0.999 → 1.000.** The best of the four, and converged by N = 36–72. This is the §7.1 variant-B result seen through the ε axis.
* **relative 1e−6: 0.089 → 0.094 → 0.096.** An order of magnitude off the optimal weight, and **essentially flat in N** — refinement does not repair it.
* **CS q = 2: 0.148 → 0.158 → 0.164.** The same picture: persistent, barely moving.
* **CS q = 1: 0.547 → 0.717 → 0.840.** Recovering, but **only slowly**; still 0.84 at N = 72, where the absolute ε is already 1.000.

**This is opposite in sign to the interior result of §7.5,** where the mesh-scaled CS q = 1 rule was the **best** of the four on the tracer and the shipped absolute ε was the baseline it improved on (`max_r |ω_r/d_r − 1|` **3.2190 → 0.1294**). The same rules swap ends of the ranking depending on **where in the column** the face sits. Neither measurement contradicts the other; they are measurements of different places.

**Mechanism** [derivation, consistent with the numbers; not separately measured]. The transfer of §7.5 sets ε_j = σ_j²·(h_j/L)^q. At the wall the reconstructed quantity is a **deviation** that is small in SI units, so σ_j² is small, and σ_j²(h_j/L)^q falls **below** 1e−6. A smaller ε makes the weights **more** nonlinear — and it does so exactly at the face where the even deviation mirror (`src/hydro/hydro_forward.cpp:409-413`) puts a **kink** into the stencil, which is the one place in the column the indicators genuinely disagree. snapy's **absolute** ε, by contrast, is large relative to β on that small-magnitude row, so it **dominates the denominator and linearises the weights** back towards d_r. The property §7.5 records as a defect of the absolute ε — that it is not scale-free, so how nonlinear WENO5 is depends on the row's magnitude — is the **same** property that makes it the best rule here. It is not scale-free in the interior either; it is merely helping there instead of hurting.

**Consequence, and it is the reason this subsection exists: no ε recommendation in this note may be stated globally.** Every one is scoped **by row** (which variable, in which units, at what magnitude) **and by location** (interior face against wall face). The mesh-scaled rules that tighten the interior tracer from 3.2190 to 0.1294 (§7.5) **regress** the wall face on ρ − `dref` at N = 72 from the absolute ε's **1.000** to **0.096** (rel 1e−6), **0.164** (CS q = 2) and **0.840** (CS q = 1). On this evidence **the shipped absolute ε = 1e−6 is not the thing to change first**, and §7 recommends no ε change: §7.1's in-contract answer is "no mis-fire", and a rule that is better in one place and worse in another is not an improvement that can be adopted blind. §4.2's design statement — that under route A β stays dimensionless and the absolute ε keeps its uniform-grid meaning — carries this same scoping.

**Scope [H] — these are synthetic grids, not the `jupiter_gcm` column.** Every number above is on the §4.9 contract grids, built from the constant-lapse construction, **not** on Jiheng's face lists. The mechanism is the **deviation mirror**, which is a property of `hydro_forward.cpp:409-413` and not of any particular face list, so the **qualitative** conclusion — mesh-scaled ε worse at the wall, absolute ε best, ordering reversed against the interior — is **expected** to carry to the real contract grids. That expectation is a **hypothesis**: the **exact numbers on the real grids are unmeasured**. Two things remain outstanding for the same reason, the face lists not being available on this host: the **§4.8 route comparison** and **§7.5 on the `jupiter_gcm` grids**, both **under `shock: true`**, which is that deck's explicit setting (`examples/jupiter_gcm.yaml:88`). The ρ − `dref` row used here is the one row that is insensitive to that flag (`src/recon/reconstruct.cpp:99-100` against `:139-140`), which is why §7.7 stands while those two do not.

---

## 8. Acceptance criteria

**The core change is the reconstruction rewrite** of §4 (route A): per-face WENO5 and cp5 candidate rows, per-face linear weights d0/d1/d2, and per-face smoothness indicators β. Everything else in this note (grid key, ghosts, reference fix) exists to feed it or to keep it honest. The review and the gates below are written to be strict about that rewrite.

**Measured motivation.**
- **Thread (UU9SW7MHU, ts 1793657903), citing Xinyue's and Tianhao's reports:** with frozen uniform coefficients the order falls to **1.6–2.7** inside a stretched column, and the error at n = 40 is **many times route A's**; the sourced figure, with its scope, is Xinyue's and is given below. The same message gives the context: an earlier non-uniform-x1 attempt in this codebase family came out poor, *most likely* because the WENO coefficients were left uniform. That attribution is UU9SW7MHU's hypothesis and is recorded as such.
- **In this note** [measured offline]: frozen-coefficient rates are 1.66–1.93 under a fixed map (§1 item 2). In the contract band, §4.8 gives frozen rates of 3.24 / 2.52 / **2.09** on the tracer, against route A at 4.07 / 4.73 / **4.95**, with route A **105×** better at n = 40. On the velocity through cp5 the frozen rates are 2.69 / 2.09 / 2.01 and route A is **329×** better at n = 40, but those cp5 columns are `shock: false` numbers and §4.8 forbids quoting them for `jupiter_gcm`.
- **Xinyue's scoped figure: 195.6× at n = 40**, on the pressure deviation p − p_ref, through nonlinear WENO5, snapy's frozen coefficients against route A with Jiang–Shu weights, on the lapse column with dz = H/n. It is valid for **`shock: true` only** and must **not** be cited for `shock: false`, where that variable goes through cp5, which this does not measure. The ratio depends on n: **1.5× at n = 5, 26.5× at n = 20, 1570× at n = 80**. Like the 105× tracer figure, it is **not the same quantity** as the 329× velocity figure.

### 8.0 Two stages, order of work and stop rule

**Plan (Xi, via UU9SW7MHU, ts 1793683393):** the work is split into **two stages, each with its own gates and its own PR** against chengcli/snapy.
- **Stage 1 (§8.3) is Cartesian only.**
- **Stage 2 (§8.4) is the cubed sphere,** and it starts **only after stage 1 has passed** its gates.

1. **No code starts until Xi has seen this note** (UU9SW7MHU, ts 1793648649, ts 1793657903 and ts 1793683393). Phase 1 stays read-only until then.
2. The **review gate (§8.1)** passes before the stage-1 PR is opened.
3. The **hard gates (§8.2)** are written as tests first and run on main at 2d9fa419 to record their starting state (RED where main is known to fail, for example G4 at nx1 = 128). After that, **any hard-gate failure on an implementation branch stops the work** until it is understood and fixed. A gate is not relaxed to get a pass.
4. **Stage 2 starts only when every stage-1 gate in the gate-to-stage table (§8.2) has passed** and the stage-1 PR is merged.
5. Within each stage, the **end-to-end runs start early**: as soon as that stage's pieces run end to end, not after the other gates are green.
6. **Cost is measured in snapy,** not projected: kernel and step cost in stage 1 (§8.3), step cost on E1 in stage 2 (§8.4).

### 8.1 Review gate: independent re-derivation (UJ42UV0TW)

UJ42UV0TW derives the following **independently, from Shu's divided-difference form** (Shu 1998, eq. 2.20, the non-uniform c_rj; Appendix B), **without reading §4 first**:

| item | quantity to derive for arbitrary spacing | compare against |
|---|---|---|
| R1 | the three WENO5 candidate rows at a face, both one-sided states | §4.2, primitive-function form |
| R2 | the linear weights d0, d1, d2 | §4.2 closed form (a, b, c, e) |
| R3 | the smoothness indicators β_r: the integral, its h_i scaling, and the two-square factorisation | §4.2, β formula and storage choice |
| R4 | the cp5 row | §4.2, cp5 = Σ d_r p_r |

Then UJ42UV0TW compares **term by term** with the note **at its head sha** (e61f58e0 or newer, stated in the post) and posts **agree / disagree per item** R1–R4 in the thread. The gate passes when every item is "agree", or when each disagreement has been resolved by a commit to this note and re-checked at the new sha. The note authors do **not** do this derivation. The positivity statement under R2 is about reconstruction at a **face**; the CWENO remark about leaving [0, 1] concerns the **cell centre** (§4.2).

| item | result | at sha | post |
|---|---|---|---|
| R1–R4 | *PENDING (UJ42UV0TW)* | – | – |

### 8.2 Hard gates in code, and which stage runs them — any failure stops the work

Every gate is a ctest in snapy. Every gate runs on CPU and CUDA, and on MPS where available, because route A changes all three backends (§4.3). The grids, unless a gate says otherwise:
- (u) uniform;
- (g) geometric at local ratio **1.058**, in both directions (D1 is open, so both signs are tested). Ratio **1.2** is kept only as a labelled **stress case outside the contract**: the largest in-contract departure from 1 is about (R/c_p)/n ≈ 0.057 at n = 5 (§4.9's ratio = 1 − (ΓR_s/g)/n with Γ = g/c_p; R/c_p = 2/7 for the deck's `dry` species, cv_R = 2.5 at `examples/jupiter_gcm.yaml:8`) (review item 7);
- (j) Jiheng's n = 5 and n = 10 face lists, read by sha256 (70e36e85… and 5eff3ab4…, thread ts 1793656155);
- (r) one face list with an abrupt ratio jump (the junction case of §4.6 item 3);
- (v) a **varying-lapse column**: a troposphere under a stratosphere, so the local ratio changes with height (review item 13).

If the scope cut of §8.3 (review item 12) is confirmed, every stretched grid above is supplied as an explicit face list (§4.9 option B).

In stage 1 these are **Cartesian columns and 2-D Cartesian boxes** (stretched x1, uniform x2). In stage 2 they are a single cubed-sphere column and the `jupiter_gcm` deck.

ε is snapy's shipped absolute 1e−6 throughout. §7.7 recommends no ε change, and the gates do not test one.

**Gate-to-stage table.**

| gate / run | stage 1 (Cartesian columns and 2-D boxes) | stage 2 (cubed sphere) |
|---|---|---|
| G0 review gate (§8.1) | **must pass before the stage-1 PR** | inherited; the coefficients do not change between stages |
| G1 constants and linear data exact | **full gate** | **re-run** on gnomonic faces, to show the stage-2 fill does not change the coefficients built from `x1f` |
| G2 fifth order under a fixed refined map | **full gate**: (a), (b) and the frozen-state (c); the walls go to G8 | **re-run (c)** in a cubed-sphere column with reflecting walls |
| G3 uniform bitwise | **full gate**, including the existing `jupiter_gcm` deck unchanged | **re-run**: the gnomonic fill change must leave a uniform deck bitwise identical |
| G4 rest at round-off | **full gate**: uniform **and** stretched grids, including the varying-lapse column (v) | **re-run** in a cubed-sphere column; rest on the sphere is [H] until then (§8.6 row 11) |
| G5 mass/energy to round-off | **full gate** on closed Cartesian columns and boxes | **deck budgets**: uniform-deck baseline first (SLOT G5-B), then the stretched E1 runs |
| G6 convective growth rate vs linear EVP | **full gate**; EVP reference by Jiheng (§8.5 item 6) | – |
| G7 1 vs N x1 blocks | **full gate** | not applicable: the cubed sphere never splits x1 (§8.6 row 9) |
| G8 wall rows, separately | **full gate** | re-run at the cubed-sphere column's walls |
| G9 accuracy of the stage-1 reference | **full gate** | re-run on the cubed-sphere column (measure per §8.4) |
| G10 isobaric entropy blob | **full gate** | – |
| tall-column implicit test (§8.5 item 4) | `test_implicit_gravity_tall_column` (`tests/CMakeLists.txt:303`) | its cubed-sphere variant `test_implicit_gravity_tall_column_cubed` (`tests/CMakeLists.txt:306-307`) |
| E2 shock tube | **stage 1** | – |
| E3 gravity wave | **stage 1** | – |
| E1 `jupiter_gcm` | – | **stage 2** |
| C1 cost | **kernel and step**, Cartesian, CPU and CUDA | **step cost on E1**: stretched 30/59 against uniform 100 |

| gate | test | tolerance | pass criterion |
|---|---|---|---|
| **G1 constants and linear data exact on any grid** | Feed the per-face coefficient builder and the WENO5 and cp5 kernels exact cell averages of u ≡ c and u = α + β(x − x_f) on (u), (g), (j) and (r), and check every face and both sides. Also check that each candidate row and the cp5 row sum to 1, and that d_r > 0 on every face (§4.2). WENO5's nonlinear combination of three exact candidates is exact for linear data whatever the weights, so the nonlinear path is held to the same bound. | \|face − exact\| ≤ 8·2.22e−16·max\|u\|·Σ_k\|w_k\| over the stencil, the Σ\|w_k\| factor covering the s ≤ 16 jumps of grid (r) (review item 9); \|Σw − 1\| ≤ 4·2.22e−16 [tolerances proposed; route A's free-stream error was 4.4e−16, §4.6 item 2] | all faces, all grids, all backends |
| **G2 fifth order under a fixed stretching map, refined** | §8.5 item 2: fix X(ξ) and refine by subdividing ξ. (a) The reconstruction operator on a smooth profile. (b) The §4.8 contract-band case on the **raw** tracer row, where route A is visible, at the named levels **N = 72 and 144** (§4.8: route A 4.73 and 4.95; it reaches only 4.07 at N = 36) (review item 8). ρ′ and p′ are reference-limited and route A is invisible on them (§4.8). (c) The **spatial operator on a frozen state** with reflecting walls (or time steps with dt ∝ h^{5/3}), because RK3 at fixed CFL caps a running test at third order and there is no exact solution for a running column (review item 3); the ≥ 4.5 applies to the **interior norm**, and the wall rows are judged in G8. | observed order over the last two levels ≥ 4.5 [threshold proposed; offline route A reached 4.94 and 4.84 at N = 2048 (§8.5 item 2a) and 4.95 on the tracer at N = 144 (§4.8)] | (a), (b) and the interior norm of (c) all ≥ 4.5 |
| **G3 uniform grid bitwise identical** | A deck with neither `x1rat` nor `x1f` runs the uniform short-circuit (§4.5). The whole existing ctest suite, plus a fixed list of example decks for a fixed number of steps, compared with a build of 2d9fa419. | 0 bits: every output and restart tensor `torch.equal`, the same on CPU and CUDA | no difference anywhere |
| **G4 resting column at round-off** | §8.5 item 1: isothermal, adiabatic and varying-lapse (v) columns on (u), (g) (ratio 1.058; 1.2 as the stress case) and (j), at nx1 = 32, 64, 128, explicit and implicit-9, initial condition projected by `balance_column` at its default rtol 1e−10, which must converge. The uniform control is run **inside this gate** at the same nx1: §5 has no uniform nx1 = 32 control. The gate measures max\|v\|. It does not measure p − pref, which §7.4 shows is capped by the shipped top anchor (6e−4 relative, isothermal) without moving the fluid. | max\|v\|/c_s after 300 s ≤ K·ε = 2.22e−16 (machine epsilon), K stated with the test [K proposed: 1e3]. "Within 10× of uniform" is withdrawn: it is not round-off (review item 7) | every column and nx1. Main's measured starting state (§5, ratio 1.05): isothermal max\|v\| = 3.1e−7 m/s at nx1 = 128 |
| **G5 mass and energy conservation to round-off** | **Stage 1:** a closed Cartesian column and a closed 2-D Cartesian box (reflecting x1 walls, gravity only, no sedimentation, reactions or other forcing), with a non-rest perturbation, on (g) and (j), explicit and implicit-9, in each `gravity-work` mode (`src/forcing/const_gravity.cpp:28-36`). Track total mass Σ ρ_i V_i and total energy Σ (E_i + ρ_i Φ_i) V_i, with Φ = −g1·x1v, the E+PE that the gravity-work fixer books (`src/hydro/hydro_forward.cpp:949-950`, `:1144-1152`). Energy is first recorded the same way on the **uniform** Cartesian setup at 2d9fa419. **Stage 2:** the deck budgets of §8.4 (SLOT G5-B). | stage 1: mass relative drift ≤ 1e−13 per 1000 steps [proposed]; energy within 10× of the uniform Cartesian drift in the same mode [proposed]. Stage 2: see §8.4. Whether main conserves E+PE to round-off is **[H]** until those uniform baselines are measured. | stage 1: every grid and mode within bound; stage 2: as in §8.4 |
| **G6 convective growth rate vs linear EVP** | 2-D Cartesian box, compressible, inviscid, dry deck gas (`examples/jupiter_gcm.yaml:6-8`: cv_R 2.5, so γ = 1.4; μ = 2.112390 g/mol, R = 3936.0434 J/kg/K), g = 22 (`:126-128`), height L = 300 km (`:59-60`), periodic x2 of width L_x = 300 km. Both x1 walls reflecting with ghost rule (c). **Seed:** the EVP's vertical-mode-1 eigenfunction at k_x = 2π/L_x, cell-averaged onto the grid (§8.5 item 6). Two columns: **(i)** the jupiter_gcm dry linear fit, T = 600 K − 1.633333 K/km · z (superadiabatic by 2.28 %); **(ii)** the same troposphere under an isothermal stratosphere, tanh join at 200 km, width 25 km. Grids: the contract ladder (i) N = 30, 59, 118 (the (j) lists n5 and n10 plus the same map at 118) and (ii) N = 24, 48, 95; a uniform control at the same N; and, for (i), uniform 100 (the deck). Explicit RK3 is gated; implicit-9 is recorded. **Reference:** σ₁(i) = 1.361112242990e−3 s⁻¹, σ₁(ii) = 9.551947818189e−4 s⁻¹ (`evp_g6.py`, sha256 c719bcc0682649f625e2656eb3ff8d66fc3bab4d34732a6397e40a12c98bc376; jihenghu/snapy branch `data/280-jupiter-gcm-faces`, commit `711e33eef282a8b6a6d4b3a3836ec6c1cdf5f2f5`, blob `711dcab9f267c9d484a789476a71a93124d5784b`). | relative error E = σ_snapy/σ₁ − 1 at each grid ≤ T(grid), with T = max(\|E_FD2\|, C·N^−p, 10·max eps-bound), from table B4 (§8.5 item 6) [derived, not chosen]. Observed order on the contract ladder ≥ the FD2 order on the same ladder: (i) 1.61 over 30→59 and 1.91 over 59→118; (ii) 0.66 and 1.55. | every grid within T(grid) on both columns, and the uniform control within its own T at the same N. A stretched/uniform error ratio is recorded but not gated [H: route A should beat T on the stretched grids by a wider margin than on uniform; not tested, §8.5 item 6]. |
| **G7 1 vs N x1 blocks** | The same stretched column and box run on 1 block and split into N x1 blocks (explicit only: the implicit scheme refuses an x1 split, `src/hydro/hydro.cpp:428-431`). The seams must carry the reference consistently: the anchor relay (`src/hydro/hydro.cpp:524-548`, `:591-593`), the ghost-row exchange of pref/dref (`:595-654`) and the REF4 face pass after it (`:656-659`). | bitwise; or round-off with a **stated reason** (for example a reduction whose order changes across a seam) | identical, or the round-off difference and its reason are recorded |
| **G8 wall rows, tested separately** | At reflecting walls, the rest acceleration of the wall rows as a function of dz, reported separately from the interior, and the wall rows of G2(c)'s frozen-state test (review item 3). The wall stencils are one-sided per face (§8.3, Stage-1 reference, item 4). The even mirror of the deviation (`src/hydro/hydro_forward.cpp:408-420`) is only O(dz) accurate at the wall (stated in the thread and in review item 3; not re-derived here), so the wall rows are not allowed to hide behind the interior's order. | rest: the G4 bound (K·ε = 2.22e−16) at the wall rows; accuracy: observed order of the wall-row error ≥ 1 [proposed, matching the O(dz) mirror] (review item 11) | wall rows at rest within the G4 bound, and wall-row order ≥ 1 |
| **G9 accuracy of the stage-1 reference** | REF4's generalisation is not tested by G4, which holds for any rows that sum to 1 (review item 4). On a known hydrostatic column, measure \|p̄ − pref\|, \|ρ − dref\| and the face density dsf against the exact values on (g) and (j), interior and wall rows reported separately, under the fixed-map refinement of §8.5 item 2. | observed orders: \|p̄ − pref\| and dsf ≥ 3.5 in the interior [proposed: REF4's cubic and quartic are 4th order]; \|ρ − dref\| reported, since the kept binomial is first order on a stretched grid (§7.1) [threshold proposed: ≥ 0.9]; wall rows reported | interior orders meet the proposed thresholds; wall rows recorded |
| **G10 isobaric entropy blob** | Advect an isobaric entropy anomaly across the stretched n = 5 and n = 10 grids, comparing (a) today's index-space binomial, (b) the same 5-point smoother with weights in z, (c) no smoother. Report the L1 error, its order, and rest for each (review item 1; offline result in §8.3). | rest at round-off (G4 bound) for each variant | **lowest L1 error with rest intact** (review item 1): (a) must have the lowest L1 error or tie (b) within the ~2 % seen offline [band proposed]; if a run separates them, stage 1 switches to the fallback (b) |

### 8.3 Stage 1 — Cartesian only (its own PR)

**Scope (Xi, ts 1793683393).**
- **Grid key:** `x1rat` or an explicit face list (§2.2). dx1f, dx1v and x1v are **built from x1f** (today: scalar fill, `src/coord/cartesian.cpp:23-28`).
- **Route A:** WENO5/cp5 per-face coefficients on CPU and CUDA (§4.2–§4.3).
- **The hydrostatic reference:** `SNAP_WB_REF4`'s own pairing, generalised to non-uniform x1 spacing, and nothing else (Xi, ts 1793685084). It is specified in the paragraph *Stage-1 reference* below.
- **Cell-average states:** the REF4 cell pressure and the face density are cell-average constructions (the cubic's Gauss–Legendre cell average; the derivative of the quartic primitive), so the solver state and every gate's initial condition must be **cell averages**, not point values at x1v.
- **Ghost widths:** the per-boundary rule of §3 (D2).
- **Gates and runs:** G1–G10 on Cartesian columns and 2-D boxes (§8.2), plus a shock tube (E2) and a gravity wave (E3) on a stretched Cartesian grid, and the CUDA cost (C1).
- **Proposed scope cut (review item 12) — pending Xi's confirmation:**
  - Ship **§4.9 option B only** (explicit face list), with **ghost rule (c)** (mirrored widths) for reflecting walls. The other ghost rules of §3 and the **MPS** backend refuse the stretched path.
  - The F1 paths `jupiter_gcm` does not use refuse a stretched x1 with a `TORCH_CHECK` instead of being fixed in stage 1:
    - Cartesian diffusion (`src/forcing/diffusion.cpp`) and cubed-sphere diffusion (`src/forcing/diffusion_cubed_sphere.cpp:191`);
    - the dx²/12 curvature term (`src/hydro/hydro_forward.cpp:1023-1047`);
    - `bot_heat`/`top_cool` (`src/forcing/bot_heat.cpp:51-54`, `src/forcing/top_cool.cpp:51-54`).
  - The deck's forcing is `const-gravity` only (`examples/jupiter_gcm.yaml:126-128`). With the default `gravity-work: face`, the radial-exact work is on (`src/hydro/hydro.cpp:257-274`), which skips the curvature term (condition at `src/hydro/hydro_forward.cpp:1028-1029`).

**Stage-1 reference (Xi, ts 1793685084): `SNAP_WB_REF4` generalised to non-uniform x1, nothing else.** `SNAP_WB_REF4` exists at 2d9fa419 (`src/hydro/wb_ref4.cpp`, `src/hydro/wb_ref4.hpp`) behind an environment switch that is off by default (`src/hydro/wb_ref4.cpp:83-95`). Stage 1 takes its pairing as the reference on stretched grids:
1. **Cell pressure:** the cell average, by three-point Gauss–Legendre (exact for a cubic), of the cubic through the face pressures at faces i−1..i+2, built from the actual `x1f` (`src/hydro/wb_ref4.cpp:165-193`). The face pressures stay the hydrostatic scan's (`src/hydro/hydro_ref_x1_impl.h:42-59`). Xi's citation `:165-222` covers this block and the next; the cubic block ends at `:193`, not `:192`.
2. **Cell density: smoother kept** (review item 1; decision UU9SW7MHU, ts 1793694811). dref = pref × the smoothed ρ/p, with **today's index-space 5-point binomial (variant a) unchanged** (`src/hydro/hydro_ref_x1_impl.h:107`). This needs no new code and keeps uniform grids bitwise.
   - The kernel's own reason for the smoother stands (`src/hydro/hydro_ref_x1_impl.h:74-78`). With an unsmoothed local ρ/p, ρ′ = ρ(p − pref)/p, so an isobaric entropy anomaly leaves ρ′ ≈ 0 and travels in dsf. dsf is added identically to both face states (`src/hydro/hydro_forward.cpp:470-471`): a centred value with no upwinding.
   - **Fallback:** the same 5-point smoother with weights built in z (variant b), if a later gate (G10) separates the two.
   - REF4's own fallbacks keep the smoother, which resolves review item 6:
     - a guard reject keeps the kernel's smoothed dref (`src/hydro/wb_ref4.cpp:270-272`);
     - the face guard reads the ghost dref[is−1] (`:281`);
     - the cubic rows `E` (`:126-127`) feed only REF4's filter F.
   - Shipped REF4's main path applies its own index-space filter F = (−1, 4, 10, 4, −1)/16 (`:120-127`, `:263-272`). Whether variant (a)'s measurement below covers F as well as the kernel binomial is not stated in the decision. It is recorded as an open point (§9, B2).

   **Measured (Xinyue, ts 1793694770; offline replica, kinematic only):** blob-only L1 error on the stretched n = 5 / n = 10 grids. Rest is at round-off for all three variants.

   | variant | n = 5 | n = 10 | order |
   |---|---|---|---|
   | (a) index-space binomial (kept) | 1.26e−1 | 4.25e−2 | 1.6 |
   | (b) 5-point, weights in z (fallback) | 1.23e−1 | 4.34e−2 | 1.5 |
   | (c) no smoother | 1.74e−1 | 4.45e−2 | 2.0 |

   **Open measurement — not a gate, not a #280 work item** (UU9SW7MHU, ts 1793694811):
   - The blob errors above are **8–67×** larger than a no-reference WENO5 control (1.6e−2 / 1.7e−3).
   - The same reference runs on uniform grids today, so this is a property of the current well-balance, not of the stretched grid. It does not block stage 1.
   - **Pending:** Xinyue's check with σ = 8 and 16 cells on uniform nx1 = 30/59 and on n10, (a) against the no-reference control, L1 and order.
   - If the gap closes at 8+ cells it is recorded as a resolution limit. If it persists on the uniform grid it goes to Xi as a separate issue. **[SLOT OM1 — result: ____.]**
3. **Face density:** the 4th-order face value of dref, as the derivative at the face of the quartic primitive through five faces (four cells), with weights from the actual spacing (`src/hydro/wb_ref4.cpp:195-221`; applied after the x1 seam exchange, `:276-286` and `src/hydro/hydro.cpp:656-659`).
4. **Stencils clamped inside owned cells, one-sided at walls:**
   - The cubic window is shifted inside the owned faces at a clamped wall (`src/hydro/wb_ref4.cpp:174-178`), and so is the quartic window (`:202-206`). The clamped stencils need four owned cells next to a wall (`:112-115`).
   - The one-sidedness at a wall comes from these clamped windows. The cubic rows `E` (`:126-127`) only extend REF4's filter F past a clamped wall; they are not a wall stencil of their own.
5. **Guards kept as shipped:**
   - the cubic pressure must lie inside its cell's two face pressures, or the kernel's value stays (`:250-260`);
   - the face density must lie inside its two neighbouring cells' dref (`:281-285`);
   - cells with fewer than two cells per pressure scale height keep the kernel's values (`kMaxLogDrop`, `:25`, `:238-243`).
   - Where a guard rejects, the kernel's non-uniform log-mean (`src/hydro/hydro_ref_x1_impl.h:181-186`) is what remains.
6. **Switch and classification** (review item 5):
   - In REF4 only the cell-pressure step is gated by `!uniform` (`src/hydro/wb_ref4.cpp:169`, `:252`). The ρ/p filter (`:263-272`) and the face pass (`:276-286`) run on uniform grids too.
   - REF4 runs only when `SNAP_WB_REF4` is set (`:83-95`; `src/hydro/hydro.cpp:581`). `balance_column` applies it only under that switch **and** a non-uniform grid (`src/hydro/balance_column.cpp:73`, `:90`).
   - The stretched path therefore **turns the REF4 reference on without the environment switch**, and `balance_column` does the same on the same classification. Otherwise the G4 initial state is not a fixed point of the operator the solver applies.
   - Uniform grids keep today's reference (switch off), so G3 (bitwise uniform) is untouched.

**Measured for this reference** [measured offline, **single harness**]: Xinyue's harness (job-d434ee0e, the reconciliation report in this thread). Offline replica on Jiheng's n = 5 and n = 10 face lists, `shock: true`, variant-B ghosts (deviation mirror applied, §7.1). Against today's reference:

| quantity | n = 5 | n = 10 |
|---|---|---|
| interior ρ′, REF4 generalised | 8.75e−5 | 2.20e−5 |
| interior ρ′, today's reference | 4.76e−4 | 1.35e−4 |
| ρ′ improvement | **5.4×** | **6.1×** |
| p′ improvement | **199×** | **163×** |
| wall rows | 2.6× or better (Xi's summary: 2.6–35×) | |
| rest | ≤ 4.6e−15 | ≤ 5.6e−14 |

These are one harness's numbers, not yet reproduced in a second harness or in snapy. They motivate the choice and are **not** acceptance evidence; the stage-1 gates are.

**Closed (Xi, ts 1793685084), recorded and not reopened:**
- the arithmetic-mean face density (Tianhao) is **dropped**: +4–8 % worse than today in Xinyue's harness;
- the log-linear face density (Xinyue) is **dropped**: ~1.9× worse;
- Tianhao's 3.2–5.0× improvement for the arithmetic-mean form was **not reproduced** in Xinyue's harness. It is a known closed item: there will be no per-face dump hunt.

**Code sites in stage 1, at 2d9fa419** (each line re-read; the stage reason is given):

| site | file:line | stage-1 reason |
|---|---|---|
| Cartesian dx fill | `src/coord/cartesian.cpp:23-28` | the fill to build from x1f |
| shared ghost-face site | `src/coord/coordinate.cpp:322-324` (`linspace(gmin − nghost·dx, gmax + nghost·dx, …)`, sliced per block) | geometry-independent: the global face vector and its ghost rule (§3) are built here once for every geometry, so stage 2 inherits it |
| its consumer: WB deviation ghosts | `src/hydro/hydro_forward.cpp:403-420` (even index mirror of p′, ρ′) | the index mirror is a geometric mirror only with mirrored ghost widths (§3, D2) |
| its consumer: covariance velocity ghosts | `src/hydro/hydro_forward.cpp:443-451` (odd index mirror, opt-in `SNAP_X1_MASS_COVARIANCE`) | same reason |
| its consumer: dead isentropic ghost revision | `src/hydro/hydro.cpp:488`, `:508` read `dx1v` in `_revise_x1inner/outer_ghost` | **no stage work:** the call is commented out (`src/hydro/hydro_forward.cpp:356-359`). Recorded so that a revival uses the real ghost widths |
| x1 block offset and span | `ix1()` and `_offset(span, dx)` with scalar `dx1()` (`src/coord/coordinate.hpp:93`, `:126-128`); span check with `dx = (ghi − glo)/gnx` (`src/coord/coordinate.cpp:215-224`) | an x1 split exists only off the cubed sphere (`src/coord/coordinate.cpp:137`, `:264` set `lx1 = 0` there), so this is a stage-1 item (§2.2 index-based offsets) |
| bottom heating / top cooling | `src/forcing/bot_heat.cpp:51-54`, `src/forcing/top_cool.cpp:51-54` (`flux/(dx1f[il or iu]·depth)`) | **refuse a stretched x1** (`TORCH_CHECK`), review item 12, pending Xi's confirmation; if not confirmed, divide by the summed widths (F1) |
| other inventory fixes | diffusion `centered_derivative` and `face_average` (`src/forcing/diffusion.cpp:70-84`, `:99-108`); dx²/12 curvature correction (`src/hydro/hydro_forward.cpp:1023-1047`) | **refuse a stretched x1** (`TORCH_CHECK`), review item 12, pending Xi's confirmation; if not confirmed, fix (F1) |
| index-space smoothers in the reference | kernel binomial (`src/hydro/hydro_ref_x1_impl.h:107`, face mean `:195-198`); REF4 filter F (`src/hydro/wb_ref4.cpp:120-127`, `:263-272`) | **kept unchanged** (review item 1, ts 1793694811); a z-weighted 5-point smoother is the fallback (G10) |
| REF4 stencils | cubic cell pressure (`src/hydro/wb_ref4.cpp:165-193`); face dref (`:195-221`, applied `:276-286`) | generalised and made the stretched-grid reference |
| implicit face work | general `work_lo/hi` (`src/implicit/implicit_hydro.cpp:263-266`); Cartesian fast path gated at `:313-314`, ½ and ¼ exact for midpoint x1v (`src/implicit/vic_assemble_full_impl.h:101-108`) | no edit expected; exercised by the tall-column test |

**E2 — shock tube on a stretched Cartesian grid.** A Sod-type Riemann problem along x1, no gravity, `shock: true`, on (u), (g) and (r). Compare against the exact solution: the L1 error in ρ, the positions of the shock and the contact, and the overshoot at the shock, against the uniform run at the same finest Δz. [Pass thresholds to be proposed by the implementer before running.] No ε or shock result exists in this note (§7.5), so E2 is new evidence, not a check of an existing number.

**E3 — gravity wave on a stretched Cartesian grid.** A small-amplitude internal gravity wave in an isothermal or stably stratified Cartesian column or 2-D box on (g) and (j), explicit and implicit-9. Measure frequency, phase speed and amplitude decay against linear theory and against the uniform run. [Thresholds to be proposed before running.] This is the first non-rest test of the reference split (§5) and the ghost rule (§3) together.

**C1 — cost, measured in snapy.** The **11–17 %** of §4.4 is a **projection** from a standalone kernel pair onto snapy's kernel. It is **not a measurement** and is to be **replaced** by one. On the stage-1 branch, measure in snapy:
- the x1 reconstruction kernel time and the full step time, stretched against uniform at the same nx1;
- on CPU and CUDA;
- reporting the GPU model and its L2 size, including this machine's GTX 1080 Ti (smaller L2 than the RTX 5090, §4.4 caveat 2).

This item has no pass threshold, but the measured numbers must be in this note before the stage-1 merge.

**Open decision for Xi (stage 1), not answered here — XQ1: the YAML key or reviving the hook.**
- §2.2 proposes new keys. They would have to pass `check_keys` at `src/coord/coordinate.cpp:70` (`geometry`) and `:125-126` (`geometry/cells`), which today reject anything else (`src/input/check_keys.cpp:26`).
- The alternative is to revive `reset_coordinates(meshgens)` (`src/coord/coordinate.cpp:327-350`; Cartesian override `src/coord/cartesian.cpp:50-60`). Its only caller is `src/z.junk/initialize.cpp:163`, which is not compiled (`src/CMakeLists.txt:35-53`).

This note records the question for Xi and does not choose.

### 8.4 Stage 2 — cubed sphere (its own PR, only after stage 1 passes)

**Scope (Xi, ts 1793683393; geometry decision O3, ts 1793681865).**
- `GnomonicEquiangle` builds dx1f, dx1v and x1v **from x1f**, with `SphericalPolar` as the template (`src/coord/spherical_polar.cpp:59-62`). Today it uses the scalar fill: `dx = op->dx1()` at `src/coord/gnomonic_equiangle.cpp:33`, `dx1f` at `:35`, and `x1v`/`dx1v` at `:36-38`.
- `cell_volume` and `face_area2/3` are made consistent with a stretched x1f (`src/coord/gnomonic_equiangle.cpp:211-227`).
- Then the `jupiter_gcm` E1 runs.

**Stage 2 inherits unchanged from stage 1:**
- the grid key and the global face vector with its ghost rule (`src/coord/coordinate.cpp:322-324` site, §2.2, §3);
- the route-A coefficient builder and coefficients (§4.2);
- the CPU and CUDA kernels (§4.3);
- the stage-1 reference: `SNAP_WB_REF4` generalised to non-uniform x1, with today's index-space binomial kept (§8.3);
- the ghost widths;
- the implicit kernels (§6).

None of these are edited in stage 2.

**Cell measure (review item 10).** Route A (§4.2) and the REF4 cell average weight a cell by dz. The cubed-sphere conserved average weights it by r² dr (`src/coord/gnomonic_equiangle.cpp:219-227`).

For u = exp(−(r − r₀)/H) in one cell of width h = H/n at the `jupiter_gcm` bottom radius r₀ = 69 911 000 m (`examples/jupiter_gcm.yaml:59`), the two averages differ by ≈ h²/(6 r₀ H), relative [derivation; computed by Linfeng's worker with an exact-integral script, not in the repository]:

| H | relative difference at n = 40 |
|---|---|
| 19.7 km (110 K, dry R_s, g = 22) | 2.9e−8 |
| 107 km (600 K, dry R_s, g = 22) | 1.6e−7 |
| 119.6 km (the tall-column test's H_p, §6) | 1.8e−7 |

At n = 5 the difference is 1.9e−6 to 1.1e−5. The reviewer's ~1.8e−7 at n = 40 is reproduced with the last H. It is comparable in size to route A's n = 40 tracer error in §4.8 (1.208e−7, in that test's own normalisation). Stage 2 states which measure the reconstruction and the reference assume, ties the choice to XQ2, and uses the **same measure in every exact solution**.

**Stage 2 re-verifies:** G1, G2 (c), G3, G4 and the tall-column cubed-sphere variant on the cubed sphere (gate-to-stage table, §8.2); the deck budgets (G5, below); and the step cost on E1.

**Stage-2 edits and checks:** see the geometry table in §8.6.

**Open decision for Xi (stage 2), not answered here — XQ2: x1v as the face midpoint or the r² centroid.**
- Today gnomonic x1v is the **face midpoint** (`src/coord/gnomonic_equiangle.cpp:36-37`), and the gravity-work measure says so (`radial_mid`, `src/hydro/gravity_work_radial.hpp:17,23`, with its extra `x1_centroid_offset` diagonal, `:98-106`).
- `SphericalPolar` uses the **r² centroid** (`radial_centers`, `src/coord/spherical_polar.cpp:17-21`, used at `:61`).
- The choice also decides the form of `face_area2/3`. Today they are `x1v·dx1f`, which equals ½(rp² − rm²) only while x1v is the midpoint (comment at `src/coord/gnomonic_equiangle.cpp:230-233`).

This note records the question for Xi and does not choose.

**E1 — the real `jupiter_gcm` deck (lead decision O1, Xi ts 1793681865).** The **baseline is the deck as it runs today**: uniform, 100 levels (`examples/jupiter_gcm.yaml:67`). Compare it with **stretched n = 5** (30 levels, x1rat 1.058) and **stretched n = 10** (59 levels), all run to the same time (O5 below) to compare T(z), the winds, the energy budget and the redo counts. A **77-level uniform** run is **optional** and is quoted only as **"same n at the top"**: its Δz matches the stretched grid's finest cell (consistency table below). It is not the baseline.
- **Compare:** horizontal-mean T(z); rms horizontal winds and max |w|; the E+PE budget and the gravity-work-fixer booking (`src/hydro/hydro_forward.cpp:949-950`); and the number of redone steps (`check_redo`, the halving at `src/mesh/meshblock.cpp:534`).
- **Run length (lead decision O5, Xi ts 1793681865):** set by the uniform 100-level run's own spin-up. Run the baseline until its horizontal-mean T(z) and its global kinetic energy are both stationary, report that time, and run the n = 5 and n = 10 cases (and the optional 77-level case) to the **same** model time. **[SLOT O5 — NOT MEASURED YET: spin-up time = ____ s of model time; stationarity criterion used (window, tolerance on T(z) and KE) = ____.]** The criterion is stated together with the number when it is measured. It is not fixed here. The deck's own `tlim` (100.e5 s, `examples/jupiter_gcm.yaml:113`) is for reference only and is not the run length.
- **G5 deck budgets (lead decision, Xi ts 1793681865): uniform baseline first.** Measure the mass and energy budgets of the deck as it runs today, `nx1: 100`, at 2d9fa419, over the O5 run length. Those budgets are the baseline. Then measure the same budgets, the same way, on the n = 5 and n = 10 runs.
  - Budgets: Σ ρ_i V_i and Σ (E_i + ρ_i Φ_i) V_i, with Φ = −g1·x1v and V_i the cubed-sphere `cell_volume` (§8.6).
  - The deck sets no `gravity-work` key (`examples/jupiter_gcm.yaml:126-128`), so it runs the default `face` mode (`src/forcing/const_gravity.cpp:28`).
  - **[SLOT G5-B — uniform-deck baseline, NOT MEASURED YET: mass drift = ____ and energy drift = ____ (relative), over ____ s of model time, mode `face`.]**
  - Pass: the n = 5 and n = 10 drifts are within 10× of the filled baseline in the same mode [factor proposed].
- **C1 in stage 2:** step cost of the stretched n = 5 and n = 10 runs against the uniform 100-level baseline, CPU and CUDA.

**The deck at 2d9fa419**, read only: gnomonic-equiangle on a cubed-sphere layout (`examples/jupiter_gcm.yaml:56,73`); x1 from 69 911 000 to 70 211 000 m, a 300 km span (`:59-60`); `nx1: 100` (`:67`), `nghost: 3` (`:70`); `vertical: {type: weno5, scale: true, shock: true}` (`:88`); HLLC (`:92`); reflecting x1 walls (`:101-102`); RK3 with `cfl: 0.45` and `implicit-scheme: 9` (`:109-111`); `grav1: -22.` (`:128`); `Ps: 100.e5`, `Ts: 600.`, `Tmin: 110.` (`:184-186`).

**Consistency check** [derivation from those lines, not run]:

| quantity | value | note |
|---|---|---|
| deck's own uniform count | **100** cells, Δz = 3 000 m | `:67` — **the E1 baseline (O1, decided)** |
| 77 uniform cells | Δz = 3 896 m | |
| geometric q = 1.058, 30 cells over 300 km | finest 3 930 m, coarsest 20 161 m (ratio 5.13) | h_0 = L(q−1)/(q^n−1), §2.2 |
| 300 km / 3 930 m | 76.3 | so 77 is the smallest uniform count no coarser than the stretched grid's finest cell: the optional "same n at the top" comparison (O1), not the baseline |
| H/5 with dry R_s ≈ 3 936 J/kg/K (from the `dry` composition, `:7`) | 21 470 m at 600 K; 3 936 m at 110 K | moist molar mass ignored [H] |

The geometric grid's two ends fit dz ≤ H/5: 20 161 ≤ 21 470 if the coarse cell is at the bottom, and 3 930 ≤ 3 936 at the top. That requires cells growing **downward**, q = 1/1.058 in §2.2's +x1 convention (D1). In between, §4.9 applies: one ratio meets the contract only for a constant lapse rate. If the upper column is isothermal at Tmin, H/5 stays at 3 936 m there, and the second cell from the top is already 3 930·1.058 = 4 158 m. A single x1rat 1.058 therefore cannot satisfy n = 5 through an isothermal layer more than one cell thick [derivation; the deck's T(z) was not computed here].

Jiheng's n = 5 list (30 cells, sha256 70e36e8503fb9651912faaf159bdfc51c22f985e594e8d85e1d2f02f141f8c7e, ts 1793656155) was built top-down with dz ≤ H(centre)/5 from this deck's initial state. It is a geometric 1.058 grid only if its `r_dz_i_over_dz_i_minus_1` column is constant. That CSV is not on this host, so it was not checked. The n = 10 list has 59 cells (sha256 5eff3ab4b4c936049d8cca145f4ce7e29d5da6a4993db3a80f058cef09c15811, same message).

**Decided by the lead (Xi, ts 1793681865):**
- **O1:** the uniform control is the deck's own 100 levels; 77 is optional, "same n at the top".
- **O3:** the design covers x1 on the **cubed sphere**, the production geometry, as stage 2 (§8.6).
- **O5:** the run length is the baseline's spin-up time (SLOT O5 above).

**Still open (O2, §9), not resolved by assumption:** whether E1's stretched runs use Jiheng's face lists (option B) or a geometric x1rat 1.058 (option A).

### 8.5 Other acceptance criteria (unchanged in substance)

1. **Round-off rest** — the specification of G4. Resting isothermal, adiabatic and varying-lapse (v) columns on (u), (g) — local ratio 1.058, convention per D1, with 1.2 only as the out-of-contract stress case — and (j), at nx1 = 32, 64, 128, explicit and implicit-9, initial condition projected by `balance_column` at its default rtol 1e−10, which must converge. Pass when max|v|/c_s after 300 s is ≤ K·ε = 2.22e−16 [K proposed: 1e3, stated with the test]. The uniform control is run inside G4 at the same nx1 (§5 has none at nx1 = 32). Main's measured starting state (§5, ratio 1.05): it fails at nx1 = 128 (3.1e−7 m/s isothermal).
2. **WENO5 order (reworded)** — the specification of G2. Fix the stretching **map** and refine under it: X(ξ) = (q₀^{N₀ξ} − 1)/(q₀^{N₀} − 1) with N₀ = 64, refined by subdividing ξ. Equivalently, the per-cell ratio is q₀^{N₀/N}. A fixed per-cell ratio on a fixed domain is not a convergent family, because h_max tends to (r − 1)L/r (Tianhao §3.2; Xinyue B4).
   - 2a: a smooth profile converges at ≥ 4.5 over the last two levels [threshold proposed; offline route A reaches 4.94 and 4.84 at N = 2048].
   - 2b: the spatial operator on a frozen state with reflecting walls (or dt ∝ h^{5/3}), interior norm only; the walls go to G8 (review item 3).
3. **Bitwise uniform** — the specification of G3. A deck without `x1rat`/`x1f` gives bitwise the same output as 2d9fa419 on CPU and CUDA, and the existing ctest suite passes unchanged.
4. **Tall-column implicit test passes on a stretched grid,** through Courant 250 and including the new g·Δz_max/c_s² rung (§6). Stage 1 runs the Cartesian test; stage 2 runs its cubed-sphere variant (§8.2 table).
5. **Cost per step against uniform** — measured in snapy: stage 1 under C1 (§8.3), stage 2 on E1 (§8.4).
6. **G6 convective growth rate — specification** (Jiheng; accepted as proposed, UU9SW7MHU ts 1793695269).
   - *Physics:* linearised compressible Euler about the hydrostatic column, perturbations ∝ exp(i k_x x + σt), w = 0 at both walls.
     - Compressible, not anelastic, because snapy integrates the compressible equations, and an anelastic reference would build a filtering error into the comparison (its size was not computed).
     - Inviscid, because jupiter_gcm runs inviscid and the stretched-x1 diffusion path refuses at stage 1 (review item 12). So the fastest mode is the grid scale, and G6 tests **one seeded mode, not the fastest**: k_x = 2π/(300 km), vertical mode 1 (w has no zero in the bulk of the column).
   - *Reference:* `evp_g6.py` (numpy/scipy, kept outside snapy, sha256 c719bcc0682649f625e2656eb3ff8d66fc3bab4d34732a6397e40a12c98bc376; jihenghu/snapy branch `data/280-jupiter-gcm-faces`, commit `711e33eef282a8b6a6d4b3a3836ec6c1cdf5f2f5`, blob `711dcab9f267c9d484a789476a71a93124d5784b`). It has two independent solvers, a shooting solve of the two-point BVP in (w, p′/p₀) and Chebyshev collocation, which agree to ≤ 4e−13.
     - Reference values at the seed (shooting, rtol 1e−13): σ₁(i) = **1.361112242990126e−3** s⁻¹ and σ₁(ii) = **9.551947818189110e−4** s⁻¹.
     - Modes 2 and 3 at the seed: (i) σ₂ = 1.071984272e−3, σ₃ = 8.60427201e−4, so (σ₁−σ₂)/σ₁ = 0.2124; (ii) σ₂ = 6.070083879e−4, σ₃ = 4.236239303e−4, so (σ₁−σ₂)/σ₁ = 0.3645. This gap is why σ is measured by adjoint projection.
   - *Seed and measurement:*
     - Initialise the four mode-1 fields (ρ′, u, w, p′) as cell averages. The amplitude is a₀ such that max|w| = 1e−6·c_s(bottom) ≈ 1.8e−3 m/s, so that after e⁸ ≈ 3.0e3 of growth at the end of the fit it is ≈ 5.4 m/s ≈ 3e−3·c_s (linear regime [H]).
     - Measure â(t) = ⟨y₁, x̂_k(t)⟩, the k_x Fourier coefficient projected onto the EVP's left (adjoint) eigenvector. Take σ as the least-squares slope of ln|â| over t ∈ [3, 8]/σ₁.
     - *Window self-check:* refit over [4, 9]/σ₁ on the finest uniform control; if σ moves by more than T/10, move the window later.
     - *x2 self-check:* run the finest uniform control at nx2 = 64 and 128 per wavelength; if σ moves by more than T/10, raise nx2 for every run.
   - *Thresholds* (table B4) are T(grid) = max(\|E_FD2(grid)\|, C·N^−p, 10·max eps-bound):
     - E_FD2 is the error of a consistent second-order staggered discretisation of the same operator on **the same faces**;
     - C·N^−p is its asymptotic model from the two finest levels of each family;
     - the eps-bound is κ·eps·‖A‖/σ₁ of the discrete eigenproblem (max 9.6e−9, so the floor is 9.63e−8).

     The gate therefore requires the route-A scheme to be at least as accurate as consistent second order on the actual grid, and to converge at least as fast.

   **Table B4 — FD2 on the gate grids, and the derived thresholds** (Jiheng, offline):

   | column | grid | N | E_FD2 | model C·N^−p | **T(grid)** |
   |---|---|---|---|---|---|
   | (i) | (j) n5 | 30 | +2.236e−2 | 3.108e−2 | **3.11e−2** |
   | (i) | (j) n10 | 59 | +7.515e−3 | 8.067e−3 | **8.07e−3** |
   | (i) | contract map | 118 | +2.001e−3 | 2.025e−3 | **2.02e−3** |
   | (i) | uniform | 30 | −1.729e−2 | 1.260e−3 | **1.73e−2** |
   | (i) | uniform | 59 | −7.691e−4 | 3.679e−4 | **7.69e−4** |
   | (i) | uniform | 118 | +5.549e−5 | 1.042e−4 | **1.04e−4** |
   | (i) | uniform 100 (deck) | 100 | +3.185e−5 | 1.408e−4 | **1.41e−4** |
   | (i) | uniform 77 (n5 at top) | 77 | −1.323e−4 | 2.266e−4 | **2.27e−4** |
   | (i) | uniform 153 (n10 at top) | 153 | +5.308e−5 | 6.494e−5 | **6.49e−5** |
   | (ii) | contract n5 | 24 | −7.437e−3 | 2.246e−2 | **2.25e−2** |
   | (ii) | contract n10 | 48 | +4.717e−3 | 6.014e−3 | **6.01e−3** |
   | (ii) | contract n20 | 95 | +1.643e−3 | 1.643e−3 | **1.64e−3** |
   | (ii) | uniform | 24 | −1.784e−2 | 5.959e−3 | **1.78e−2** |
   | (ii) | uniform | 48 | −1.703e−3 | 1.232e−3 | **1.70e−3** |
   | (ii) | uniform | 95 | −2.610e−4 | 2.610e−4 | **2.61e−4** |

   - *Model fits* from the two finest levels: (i) contract map 27.449·N^−1.994 (236/472), uniform 0.61497·N^−1.820 (236/472); (ii) contract map 9.4394·N^−1.901 (95/189), uniform 8.1883·N^−2.274 (95/189).
   - *Observed FD2 orders on the contract ladder:* (i) 1.612, 1.909, 1.978, 1.994; (ii) 0.657, 1.545, 1.901.
   - *Why a model at all:* the uniform FD2 error changes sign between N = 59 and 118 in (i), so its raw value near the crossing is an accident.
   - *Floor:* 10·max eps-bound = 9.63e−8. It binds nowhere.

   **Not gated, recorded:**
   - At equal N, FD2 is far less accurate on the contract map than on a uniform grid for this box-scale mode: in (i) at N = 118 it is 2.0e−3 against 5.5e−5. The cause is the off-midpoint face in the staggered difference.
   - [H] route A's per-face finite-volume coefficients do not share this defect, so snapy should beat T on the stretched grids by a wider margin than on uniform. Not tested. This is why the stretched/uniform ratio is recorded, not gated.

   **Hypotheses [H], untested** (Jiheng):
   1. Linearity holds up to max|w| ≈ 3e−3·c_s, so nonlinear corrections to σ stay below T/10.
   2. With adjoint projection, the fit window [3, 8]/σ₁ leaves mode-2/3 contamination below T/10; the window self-check verifies it.
   3. nx2 = 64 per wavelength makes the x2 error below T/10; the nx2 self-check verifies it.
   4. For explicit RK3 at the deck CFL 0.45 (`examples/jupiter_gcm.yaml:110`), the time-discretisation error in σ is negligible (σ₁·dt ~ 1e−3). Implicit-9 is recorded, not gated, because the VIC solve is first order in time for the acoustic coupling (§6).
   5. G4-level rest noise (≤ 3.1e−7 m/s at nx1 128 on main, §5) does not bias σ at a seed amplitude of ≈ 1.8e−3 m/s (ratio 1.7e−4).
   6. The size of the anelastic difference against this compressible reference was not computed.
   7. Cell-averaging the continuum eigenfunction onto the grid is accurate enough that the seeding transient is covered by hypothesis 2.

**Kept consistent with the rest of the note:**
- the real-grid `shock: true` rerun of §4.8, §7.5 and §7.7 is still **PENDING**, and no gate quotes a number from it;
- the ε results stay scoped by row and location (§7.7), so no gate changes ε;
- the 105× (tracer) and 329× (velocity, `shock: false` only) figures of §4.8 and the scoped 195.6× above are quoted with their scopes;
- the §7.1 smoother table (`max |ρ − dref|/ρ` with the shipped binomial) measures the binomial that stage 1 now **keeps** (review item 1). It is context for G9's ρ − dref threshold, not a stage-1 acceptance number, and no "scan alone" figure is quoted;
- every threshold above marked [proposed] is a proposal for Xi and Cheng, not a measured value.

### 8.6 Geometry: what differs for x1 on the cubed sphere, and which stage handles it

**Decision (Xi, ts 1793681865; staged ts 1793683393):** the design covers the x1 direction on the **cubed sphere** (`gnomonic-equiangle` coordinates on a `cubed-sphere` layout), the production geometry of `examples/jupiter_gcm.yaml` (`:56`, `:73`), **as stage 2**. §1's "In scope: Cartesian x1 (vertical) columns" predates this decision. Stage 1 now covers it, stage 2 extends it, and §1 is outside this edit, to be updated by its owner in a separate commit.

**The table, at 2d9fa419** (each line re-read at that sha; folds in Tianhao's O3 inventory, thread ts 1793683205):

| # | piece | cubed sphere (`gnomonic-equiangle`) | Cartesian / base class | stage and action |
|---|---|---|---|---|
| 1 | dx1f / x1v / dx1v fill | scalar `dx = op->dx1()` (`src/coord/gnomonic_equiangle.cpp:33`); `dx1f = ones·dx` (`:35`); x1v = face midpoint and `dx1v = ones·dx` (`:36-38`) | scalar fill (`src/coord/cartesian.cpp:23-28`); spherical-polar derives all three from `x1f` (`src/coord/spherical_polar.cpp:59-62`) | Cartesian: **stage 1** edit. Gnomonic: **stage 2** edit, with spherical-polar as the template **Fill range (Tianhao's request):** `dx1f`, `x1v` and `dx1v` have nc1 = nx1 + 2·nghost entries (`src/coord/coordinate.hpp:59`), so indices 0..nc1−1 include both ghost layers. Today every entry, ghosts included, gets the scalar. The stretched fill builds `dx1f` = `diff` of the block's nc1 + 1 faces (`src/coord/coordinate.cpp:324`), and `x1v` from the same faces, over the full range 0..nc1−1, ghosts included. Face differences define `dx1v` only for 1..nc1−1, as x1v[i] − x1v[i−1]. **Stage 1 convention:** dx1v[0] = dx1f[0], matching spherical-polar. There, `center_distances` seeds dx1v from dx1f and overwrites only 1 onward (`src/coord/spherical_polar.cpp:30-38`, used at `:62`). **Stage 1 code change:** Cartesian's entry 0 is stale. dx1v is built as `ones·dx1()` (`src/coord/cartesian.cpp:24`, `:28`), and `reset_coordinates` rewrites only 1 onward (`:58-60`), so dx1v[0] keeps the construction-time scalar. The stretched fill must set dx1v[0] = dx1f[0] explicitly. Gnomonic has the same scalar seed (`src/coord/gnomonic_equiangle.cpp:38`) and gets the same convention in stage 2 |
| 2 | `reset_coordinates` | **no override** (`src/coord/gnomonic_equiangle.hpp:36-68`), so only the base runs, which rewrites `x1f` alone (`src/coord/coordinate.cpp:327-350`) | Cartesian override refreshes `dx1f`/`x1v`/`dx1v[1:]` (`src/coord/cartesian.cpp:50-60`) | **stage 1** decision XQ1 (§8.3); if the hook is revived, gnomonic needs an override in **stage 2** |
| 3 | shared ghost faces | the same global `linspace` with uniform ghost extension (`src/coord/coordinate.cpp:322-324`) | same site | **stage 1** (geometry-independent); stage 2 inherits |
| 4 | x1 width and centre distance | not overridden: base `center_width1` = `dx1f`, `center_distance1` = `dx1v` (`src/coord/coordinate.cpp:402-404`, `:414-416`); x2/x3 widths scale with x1v (`src/coord/gnomonic_equiangle.cpp:199-205`) | same base functions | base: **stage 1** (correct once the fill is); x2/x3 widths: **stage 2**, following x1v (XQ2) |
| 5 | x1 face area (`face_area1`) | r² × solid angle, `(x1f * x1f) * solid_angle_kj` (`src/coord/gnomonic_equiangle.cpp:207-209`) | dx2f·dx3f (`src/coord/coordinate.cpp:452-456`) | **already safe:** per face from `x1f` on any spacing. Stage 2 re-verifies, no edit |
| 6 | x2/x3 face areas (`face_area2/3`) | `(x1v * dx1f) * arc` (`src/coord/gnomonic_equiangle.cpp:211-217`) | dx3f·dx1f, dx2f·dx1f (`src/coord/coordinate.cpp:458-468`) | **no edit with midpoint x1v once dx1f = diff(x1f)**; only a centroid choice (XQ2) needs one, because `x1v·dx1f` = ½(rp² − rm²) only for midpoint x1v (`:230-233`) (review item 14 nit) |
| 7 | cell volume | `dx1f (rp² + rp·rm + rm²)/3 × solid angle`, rm and rp from `x1f` (`src/coord/gnomonic_equiangle.cpp:219-227`) | dx1f·dx2f·dx3f (`src/coord/coordinate.cpp:470-475`) | **stage 2:** consistent once `dx1f = rp − rm` comes from x1f (row 1); verify. It is also the V_i of the G5 deck budgets |
| 8 | x1 face second moment / centroid shift | `face_moment2_x1` and `face_centroid_shift_x1` (`src/coord/gnomonic_equiangle.cpp:229-243`) only call the base helpers `radial_face_moment2_` (`src/coord/coordinate.cpp:481-494`) and `radial_face_centroid_shift_` (`:502-523`) | `dx1f²/12` (`src/coord/coordinate.cpp:477-479`); zero shift (`:496-500`) | **already safe, no edit:** both helpers compute h = rp − rm and r̄ = (rm + rp)/2 directly from `x1f` and never read the scalar fill. Stage 2 re-verifies |
| 9 | x1 block offset | `lx1 = 0` on the cubed-sphere layout (`src/coord/coordinate.cpp:137`, `:264`), so x1 is never split | `ix1()` with scalar `dx1()` (`src/coord/coordinate.hpp:93`, `:126-128`); span check (`src/coord/coordinate.cpp:215-224`) | **stage 1** only (§8.3); nothing in stage 2 |
| 10 | bottom heating / top cooling | `src/forcing/bot_heat.cpp:51-54`, `src/forcing/top_cool.cpp:51-54` | same code | **stage 1**: refuse a stretched x1 (`TORCH_CHECK`), review item 12, pending Xi's confirmation; `jupiter_gcm` does not use them (`examples/jupiter_gcm.yaml:126-128` lists only `const-gravity`) |
| 11 | geometric source and pressure-gradient correction | `forward()` (`src/coord/gnomonic_equiangle.cpp:415-460`) subtracts `(p_{i+1} − p_i)/dx1f_i` from the area-weighted pressure divergence (`:444-455`) | Cartesian has no geometric source | **stage 2** re-verify: pairs with the scan's per-cell `dx1f` (§5) for rest on the sphere [H until G4 runs there] |
| 12 | implicit face work | general `work_lo/hi` from `x1v − x1f` (`src/implicit/implicit_hydro.cpp:263-266`); the ½/¼ fast path is Cartesian-only (`:313-314`) | Cartesian fast path (`src/implicit/vic_assemble_full_impl.h:101-108`) | no edit in either stage; stage 2 re-verifies via the cubed-sphere tall-column test |
| 13 | gravity-work measure | `radial_mid`: r² dr measure, x1v the face midpoint (`src/hydro/gravity_work_radial.hpp:17,23`); `x1_centroid_offset` (`:98-106`; used at `src/implicit/implicit_hydro.cpp:361-364`) | `plain` (`src/hydro/gravity_work_radial.hpp:15,21`) | **stage 2**, tied to XQ2 |
| 14 | diffusion | cubed-sphere path: one scalar `h = op->dx1()` with index-space Lagrange weights (`src/forcing/diffusion_cubed_sphere.cpp:37-62`, `:191`) | `src/forcing/diffusion.cpp` per-cell widths, with the F1 caveats | **refuse a stretched x1** (`TORCH_CHECK`), review item 12, pending Xi's confirmation; otherwise **stage 2** (F1) |
| 15 | the deck | `type: gnomonic-equiangle` (`examples/jupiter_gcm.yaml:56`), `layout: cubed-sphere` (`:73`), `nx1: 100` (`:67`) | – | **stage 2**: E1 |

**Reconciliation:** this table now folds in Tianhao's O3 inventory (ts 1793683205):
- face_area1 split from face_area2/3;
- the fill lines :33, :35 and :36-38;
- the ghost-face site and its consumers;
- `bot_heat`/`top_cool`;
- `ix1()`/`dx1()` and the span check.

Row 8 was re-read: the moments row now cites the helpers it calls and needs no edit. **[SLOT O3-R — item-by-item sign-off by Tianhao on this table: ____.]**

---

## 9. Open items and owners

| # | item | owner | state |
|---|---|---|---|
| X1 | **Xi sees this note before any code starts** (§8.0) | UU9SW7MHU takes it to Xi | open — blocks all code |
| S1 | stage 1, Cartesian (§8.3), its own PR | implementer unassigned (review item 14 names none), after X1 and G0 | not started |
| S2 | stage 2, cubed sphere (§8.4), its own PR, only after every stage-1 gate passes | implementer unassigned (review item 14 names none), after S1 | not started |
| XQ1 | **for Xi (stage 1):** YAML key (`check_keys` at `src/coord/coordinate.cpp:70`, `:125-126`) or revive `reset_coordinates` (only caller in `src/z.junk/initialize.cpp:163`, not compiled) | Xi | **open — not answered by this note** |
| XQ2 | **for Xi (stage 2):** gnomonic x1v as face midpoint (today) or r² centroid (as `SphericalPolar`); it also decides the `face_area2/3` form and the gravity-work measure (§8.4, §8.6 rows 6 and 13), and the cell measure the reconstruction and the exact solutions use (§8.4, review item 10) | Xi | **open — not answered by this note** |
| G0 | review gate §8.1: independent re-derivation of R1–R4 from Shu's divided-difference form, then a term-by-term comparison at the head sha | UJ42UV0TW | requested (ts 1793657903) |
| TXT | text edits for review items 2–14 (one patch on 918287c) | Linfeng (text); Tianhao commits after a hash and scope check | this patch |
| G1–G10 | hard-gate tests of §8.2, written first and run on 2d9fa419 for their starting state; staged per the gate-to-stage table | implementer unassigned (review item 14 names none), after X1 | not started |
| G6-EVP | G6 EVP reference: compressible inviscid linear EVP, seeded k_x = 2π/(300 km) vertical mode 1, adjoint projection, per-grid thresholds T(grid) from FD2 with an eps floor, stretched/uniform ratio recorded and not gated; columns (i) the jupiter_gcm dry linear fit and (ii) the varying-lapse column (§8.2 G6, §8.5 item 6) | Jiheng (accepted ts 1793694441) | **accepted as proposed (ts 1793695269)**; `evp_g6.py` cited by sha256 c719bcc0…; committed as jihenghu/snapy `data/280-jupiter-gcm-faces` 711e33eef282a8b6a6d4b3a3836ec6c1cdf5f2f5 |
| B1 | review item 1: index binomial vs z-weighted vs none (isobaric entropy blob) | Xinyue (accepted ts 1793694442) | **closed (ts 1793694811):** smoother kept, (b) is the fallback, the test is gate G10 |
| B2 | whether variant (a)'s blob measurement covers REF4's own filter F on the REF4 path (§8.3, Stage-1 reference, item 2) | Xinyue / Linfeng | open |
| OM1 | 8–67× blob-error gap to the no-reference WENO5 control; σ = 8/16-cell check on uniform nx1 = 30/59 and n10 | Xinyue | **open measurement — not a gate, not a #280 work item** (ts 1793694811); SLOT OM1 |
| SC | scope cut of review item 12: option B with ghost rule (c) only; the other ghost rules and MPS refuse; the unused F1 paths refuse a stretched x1 | Xi | **pending Xi's confirmation** |
| REF | stage-1 reference = `SNAP_WB_REF4` generalised to non-uniform x1 (cubic cell p; dref with today's index-space binomial kept, per B1; 4th-order face dref; one-sided walls) (§8.3) | Xi (decision) | **decided (ts 1793685084; smoother per ts 1793694811)** |
| DEN | density-reference round: arithmetic-mean and log-linear face formulas dropped; Tianhao's 3.2–5.0× not reproduced and not chased | Xi | **closed (ts 1793685084)** |
| E1 | stage 2: `jupiter_gcm` uniform 100-level baseline against stretched n = 5 (30 levels) and n = 10 (59 levels) (§8.4) | unassigned (review item 14 names none) | blocked on S1, O2 and the face lists reaching the runner |
| E2, E3 | stage 1: shock tube and gravity wave on a stretched Cartesian grid (§8.3) | unassigned (review item 14 names none) | not started; thresholds to be proposed first |
| C1 | cost measured in snapy: stage 1 kernel and step, CPU and CUDA, including a smaller-L2 GPU (§8.3); stage 2 step cost on E1 (§8.4); replaces the 11–17 % projection | Tianhao / Linfeng | not started (supersedes Q4) |
| O1 | stage 2: uniform control for E1 is the deck as it runs today, 100 levels (`examples/jupiter_gcm.yaml:67`); 77 levels optional, quoted only as "same n at the top" (§8.4) | Xi | **decided (ts 1793681865)** |
| O2 | E1 stretched grid: Jiheng's n = 5 face list (option B) or a geometric x1rat 1.058 (option A). A single ratio cannot satisfy n = 5 through an isothermal Tmin layer more than one cell thick (§8.4, §4.9) | Jiheng / Tianhao | **open — not checked; the CSV is not on this host** |
| O3 | geometry scope: x1 on the cubed sphere as stage 2 (§8.6); §1's Cartesian-only scope line to be updated by its owner | Xi (decision); Linfeng + Tianhao reconcile the §8.6 table | **decided (ts 1793681865; staged ts 1793683393)**; Tianhao's inventory folded in, sign-off pending (SLOT O3-R) |
| O4 | the unscoped "190× route A at n = 40" figure (ts 1793657903) | Xinyue / Tianhao | **closed:** §8 now cites Xinyue's scoped 195.6× (p − p_ref, WENO5, `shock: true` only, n = 40, n-dependent); the unscoped 190× is not used |
| O5 | stage 2: E1 run length = the uniform 100-level run's spin-up time (horizontal-mean T(z) and global KE stationary); stretched runs go to the same time (§8.4) | Xi (decision); measurement Jiheng (accepted ts 1793694441) | **decided (ts 1793681865)**; number not measured (SLOT O5) |
| G5-B | stage 2: uniform-deck mass and energy budgets, measured first as the G5 deck baseline (§8.4) | Xi (decision); measurement unassigned (review item 14 names none) | **decided (ts 1793681865)**; not measured (SLOT G5-B) |
| P1 | real-grid `shock: true` rerun of §4.8, §7.5 and §7.7 on Jiheng's lists (posted ts 1793656155); informs both stages | Tianhao | **PENDING** |
| D1 | `x1rat` direction convention; whether to add option B (`x1f` list) in the stage-1 PR. §4.9 makes option B a contract requirement for realistic T(z) | Linfeng proposes; Xi/Cheng decide | open; if SC is confirmed, only option B ships and the `x1rat` key is not part of stage 1 |
| D2 | ghost-width rule per boundary type (§3); stage 1 | Linfeng + Tianhao | proposed; if SC is confirmed, only rule (c) ships |
| D3 | uniform classification from the grid key instead of the per-block probe; stage 1. REF4 engages on the same classification (§8.3, Stage-1 reference, item 6) | Linfeng + Xinyue | proposed |
| D4 | route-A layout (CPU index, MPS, CUDA global rows), cp5 per-face rows; stage 1 | Tianhao | drafted; checked by G0 |
| D5 | rung values; Courant defined on Δz_min or Δz_max | Jiheng | pending |
| Q1 | §7: which variables WENO5 sees | Tianhao + Xinyue | answered at 2d9fa419 (§7.2); real-grid rerun is P1 |
| Q2 | log1p form of the kernel's log-mean (§5) | Xinyue | **superseded** as the stage-1 cell pressure by REF (ts 1793685084); the log-mean remains only where REF4's guards reject (`src/hydro/wb_ref4.cpp:250-260`, `:238-243`). Whether its round-off matters there is [H] |
| Q3 | Käppeli & Mishra equations with page/equation numbers | Xinyue | pending |
| Q5 | Wang, Feng & Spiteri (2008) content; novelty not claimed | Tianhao | unread |
| F1 | other uniform-spacing fixes from the inventory. **Stage 1:** diffusion `centered_derivative` (`src/forcing/diffusion.cpp:70-84`) and `face_average` (`:99-108`); `bot_heat`/`top_cool` budgets (`src/forcing/bot_heat.cpp:51-54`, `src/forcing/top_cool.cpp:51-54`); the dx²/12 curvature correction (`src/hydro/hydro_forward.cpp:1023-1047`). **Stage 2:** cubed-sphere diffusion scalar h (`src/forcing/diffusion_cubed_sphere.cpp:191`, §8.6 row 14) | unassigned | if SC is confirmed, these paths refuse a stretched x1 with a `TORCH_CHECK` instead of being fixed |
| R1 | critic review of this note as a whole (distinct from G0) | UJ42UV0TW | after the note lands |
| H1 | hosting: happysky19/snapy `doc/280-stretched-x1`; Tianhao's worker is the single pusher | Tianhao | hosted |

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
