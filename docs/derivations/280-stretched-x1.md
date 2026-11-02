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
- **Thread (UU9SW7MHU, ts 1793657903), citing Xinyue's and Tianhao's reports:** with frozen uniform coefficients the order falls to **1.6–2.7** inside a stretched column, and the error is **190× route A at n = 40**. The same message gives the context: an earlier non-uniform-x1 attempt in this codebase family came out poor, *most likely* because the WENO coefficients were left uniform. That attribution is UU9SW7MHU's hypothesis and is recorded as such.
- **In this note** [measured offline]: frozen-coefficient rates are 1.66–1.93 under a fixed map (§1 item 2). In the contract band, §4.8 gives frozen rates of 3.24 / 2.52 / **2.09** on the tracer, against route A at 4.07 / 4.73 / **4.95**, with route A **105×** better at n = 40. On the velocity through cp5 the frozen rates are 2.69 / 2.09 / 2.01 and route A is **329×** better at n = 40, but those cp5 columns are `shock: false` numbers and §4.8 forbids quoting them for `jupiter_gcm`.
- **The 190× figure does not appear in this note**, and its source report is not cited here yet (open item O4, §9). Until it is traced, the in-note figures are the 105× (tracer, valid under either `shock` setting) and the 329× (velocity, `shock: false` only).

### 8.0 Order of work and stop rule

1. **No code starts until Xi has seen this note** (UU9SW7MHU, ts 1793648649 and ts 1793657903). Phase 1 stays read-only until then.
2. The **review gate (§8.1)** passes before any implementation PR is opened against chengcli/snapy.
3. The **hard gates (§8.2)** are written as tests first and run on main at 2d9fa419 to record their starting state (RED where main is known to fail, for example G4 at nx1 = 128). After that, **any hard-gate failure on the implementation branch stops the work** until it is understood and fixed. A gate is not relaxed to get a pass.
4. The **end-to-end runs (§8.3) start early**: as soon as the grid key (§2) and route A (§4) run end to end, not after the other gates are green.
5. **Cost (§8.4) is measured in snapy,** not projected.

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

### 8.2 Hard gates in code — any failure stops the work

Every gate is a ctest in snapy. Every gate runs on CPU and CUDA, and on MPS where available, because route A changes all three backends (§4.3). The grids, unless a gate says otherwise:
- (u) uniform;
- (g) geometric at local ratio 1.058 and 1.2 in both directions (D1 is open, so both signs are tested);
- (j) Jiheng's n = 5 and n = 10 face lists, read by sha256 (70e36e85… and 5eff3ab4…, thread ts 1793656155);
- (r) one face list with an abrupt ratio jump (the junction case of §4.6 item 3).

ε is snapy's shipped absolute 1e−6 throughout. §7.7 recommends no ε change, and the gates do not test one.

| gate | test | tolerance | pass criterion |
|---|---|---|---|
| **G1 constants and linear data exact on any grid** | Feed the per-face coefficient builder and the WENO5 and cp5 kernels exact cell averages of u ≡ c and u = α + β(x − x_f) on (u), (g), (j) and (r), and check every face and both sides. Also check that each candidate row and the cp5 row sum to 1, and that d_r > 0 on every face (§4.2). WENO5's nonlinear combination of three exact candidates is exact for linear data whatever the weights, so the nonlinear path is held to the same bound. | \|face − exact\| ≤ 8·2.22e−16·max\|u\| over the stencil; \|Σw − 1\| ≤ 4·2.22e−16 [tolerances proposed; route A's free-stream error was 4.4e−16 to 6.7e−16, §4.6 item 2] | all faces, all grids, all backends |
| **G2 fifth order under a fixed stretching map, refined** | Criterion of §8 item 2 below: fix X(ξ) and refine by subdividing ξ. (a) The reconstruction operator on a smooth profile. (b) The §4.8 contract-band case on the **raw** tracer row, where route A is visible. ρ′ and p′ are reference-limited and route A is invisible on them (§4.8). (c) A running column with reflecting walls, to expose the ghost rule (§3). | observed order over the last two levels ≥ 4.5 [threshold proposed; offline route A reached 4.94 and 4.84 at N = 2048 (§8 item 2a) and 4.95 on the tracer at n = 40 (§4.8)] | (a), (b) and (c) all ≥ 4.5; (c) records the wall faces separately |
| **G3 uniform grid bitwise identical** | A deck with neither `x1rat` nor `x1f` runs the uniform short-circuit (§4.5). The whole existing ctest suite, plus a fixed list of example decks for a fixed number of steps, compared with a build of 2d9fa419. | 0 bits: every output and restart tensor `torch.equal`, the same on CPU and CUDA | no difference anywhere |
| **G4 resting column at round-off** | §8 item 1 below: isothermal and adiabatic columns on (g) at nx1 = 32, 64, 128 and on (j), explicit and implicit-9, initial condition projected by `balance_column` at its default rtol 1e−10, which must converge. The gate measures max\|v\|. It does not measure p − pref, which §7.4 shows is capped by the shipped top anchor (6e−4 relative, isothermal) without moving the fluid. | max\|v\|/c_s after 300 s within 10× of the uniform control at the same nx1 [threshold proposed] | every column and nx1. Main passes at 32 and fails at 128 (3.1e−7 m/s isothermal, §5) |
| **G5 mass and energy conservation to round-off** | A closed column (reflecting x1 walls, gravity only, no sedimentation, reactions or other forcing) with a non-rest perturbation, on (g) and (j), explicit and implicit-9. Track total mass Σ ρ_i V_i and total energy Σ (E_i + ρ_i Φ_i) V_i, with Φ = −g1·x1v, the E+PE that the gravity-work fixer books (`src/hydro/hydro_forward.cpp:949-950`, `:1144-1152`), in each `gravity-work` mode (`src/forcing/const_gravity.cpp:28-36`). | mass: relative drift ≤ 1e−13 per 1000 steps [proposed]. Energy: first record the same drift on the **uniform** grid at 2d9fa419; the stretched grid must be within 10× of it [proposed]. Whether main conserves E+PE to round-off in every mode is **[H]** until that uniform baseline is measured. | mass within bound on every grid; energy within 10× of the uniform baseline in the same mode |

### 8.3 End-to-end runs, started early

**E1 — the real `jupiter_gcm` deck: 30-level stretched (x1rat 1.058) against 77-level uniform**, run long enough to compare T(z), the winds, the energy budget and the redo counts.
- **Compare:** horizontal-mean T(z); rms horizontal winds and max |w|; the E+PE budget and the gravity-work-fixer booking (`src/hydro/hydro_forward.cpp:949-950`); and the number of redone steps (`check_redo`, the halving at `src/mesh/meshblock.cpp:534`).
- **Run length:** not set here (open item O5). The deck's own `tlim` is 100.e5 s (`examples/jupiter_gcm.yaml:113`).

**The deck at 2d9fa419**, read only: gnomonic-equiangle on a cubed-sphere layout (`examples/jupiter_gcm.yaml:56,73`); x1 from 69 911 000 to 70 211 000 m, a 300 km span (`:59-60`); `nx1: 100` (`:67`), `nghost: 3` (`:70`); `vertical: {type: weno5, scale: true, shock: true}` (`:88`); HLLC (`:92`); reflecting x1 walls (`:101-102`); RK3 with `cfl: 0.45` and `implicit-scheme: 9` (`:109-111`); `grav1: -22.` (`:128`); `Ps: 100.e5`, `Ts: 600.`, `Tmin: 110.` (`:184-186`).

**Consistency check** [derivation from those lines, not run]:

| quantity | value | note |
|---|---|---|
| deck's own uniform count | **100** cells, Δz = 3 000 m | `:67` — **not 77** |
| 77 uniform cells | Δz = 3 896 m | |
| geometric q = 1.058, 30 cells over 300 km | finest 3 930 m, coarsest 20 161 m (ratio 5.13) | h_0 = L(q−1)/(q^n−1), §2.2 |
| 300 km / 3 930 m | 76.3 | so 77 is the smallest uniform count no coarser than the stretched grid's finest cell; it is **not** the deck's count |
| H/5 with dry R_s ≈ 3 936 J/kg/K (from the `dry` composition, `:7`) | 21 470 m at 600 K; 3 936 m at 110 K | moist molar mass ignored [H] |

The geometric grid's two ends fit dz ≤ H/5: 20 161 ≤ 21 470 if the coarse cell is at the bottom, and 3 930 ≤ 3 936 at the top. That requires cells growing **downward**, q = 1/1.058 in §2.2's +x1 convention (D1). In between, §4.9 applies: one ratio meets the contract only for a constant lapse rate. If the upper column is isothermal at Tmin, H/5 stays at 3 936 m there, and the second cell from the top is already 3 930·1.058 = 4 158 m. A single x1rat 1.058 therefore cannot satisfy n = 5 through an isothermal layer more than one cell thick [derivation; the deck's T(z) was not computed here].

Jiheng's n = 5 list (30 cells, sha256 70e36e8503fb9651912faaf159bdfc51c22f985e594e8d85e1d2f02f141f8c7e, ts 1793656155) was built top-down with dz ≤ H(centre)/5 from this deck's initial state. It is a geometric 1.058 grid only if its `r_dz_i_over_dz_i_minus_1` column is constant. That CSV is not on this host, so it was not checked. **Open (O1–O3, §9), not resolved by assumption:**
- whether 77 or 100 is the intended uniform control;
- whether E1's stretched run uses Jiheng's face list (option B) or a geometric x1rat 1.058 (option A);
- that the deck is gnomonic, while §1 scopes the change to Cartesian columns.

**E2 — shock tube on the stretched grid.** A Sod-type Riemann problem along x1: Cartesian, no gravity, `shock: true`, on (u), (g) and (r). Compare the L1 error in ρ against the exact solution, the position of the shock and the contact, and the overshoot at the shock against the uniform run at the same finest Δz. [Pass thresholds to be proposed by the implementer before running.] No ε or shock result exists in this note (§7.5), so E2 is new evidence, not a check of an existing number.

**E3 — gravity wave on the stretched grid.** A small-amplitude internal gravity wave in an isothermal or stably stratified column on (g) and (j), explicit and implicit-9. Measure frequency, phase speed and amplitude decay against linear theory and against the uniform run. [Thresholds to be proposed before running.] This is the first non-rest test of the reference split (§5) and the ghost rule (§3) together.

### 8.4 Cost, measured in snapy

The **11–17 %** of §4.4 is a **projection** from a standalone kernel pair onto snapy's kernel. It is **not a measurement** and is to be **replaced** by one. On the route-A branch, measure in snapy:
- the x1 reconstruction kernel time and the full step time;
- stretched against uniform at the same nx1, and stretched against the uniform count of E1;
- on CPU and CUDA;
- reporting the GPU model and its L2 size, including this machine's GTX 1080 Ti (smaller L2 than the RTX 5090, §4.4 caveat 2).

This item has no pass threshold, but the measured numbers must be in this note before any merge.

### 8.5 Other acceptance criteria (unchanged in substance)

1. **Round-off rest** — the specification of G4. Resting isothermal and adiabatic columns on x1rat 1.05 and 1.1 (convention per D1) at nx1 = 32, 64, 128, explicit and implicit-9, initial condition projected by `balance_column` at its default rtol 1e−10, which must converge. Pass when max|v|/c_s after 300 s is within 10× of the uniform control at the same nx1 [threshold proposed]. Main today passes at 32 and fails at 128 (3.1e−7 m/s isothermal).
2. **WENO5 order (reworded)** — the specification of G2. Fix the stretching **map** and refine under it: X(ξ) = (q₀^{N₀ξ} − 1)/(q₀^{N₀} − 1) with N₀ = 64, refined by subdividing ξ. Equivalently, the per-cell ratio is q₀^{N₀/N}. A fixed per-cell ratio on a fixed domain is not a convergent family, because h_max tends to (r − 1)L/r (Tianhao §3.2; Xinyue B4).
   - 2a: a smooth profile converges at ≥ 4.5 over the last two levels [threshold proposed; offline route A reaches 4.94 and 4.84 at N = 2048].
   - 2b: the same test in a running column with reflecting walls, to expose the ghost rule (§3).
3. **Bitwise uniform** — the specification of G3. A deck without `x1rat`/`x1f` gives bitwise the same output as 2d9fa419 on CPU and CUDA, and the existing ctest suite passes unchanged.
4. **Tall-column implicit test passes on a stretched grid,** through Courant 250 and including the new g·Δz_max/c_s² rung (§6).
5. **Cost per step against uniform** — measured in snapy, §8.4.

**Kept consistent with the rest of the note:**
- the real-grid `shock: true` rerun of §4.8, §7.5 and §7.7 is still **PENDING**, and no gate quotes a number from it;
- the ε results stay scoped by row and location (§7.7), so no gate changes ε;
- every threshold above marked [proposed] is a proposal for Xi and Cheng, not a measured value.

---

## 9. Open items and owners

| # | item | owner | state |
|---|---|---|---|
| X1 | **Xi sees this note before any code starts** (§8.0) | UU9SW7MHU takes it to Xi | open — blocks all code |
| G0 | review gate §8.1: independent re-derivation of R1–R4 from Shu's divided-difference form, then a term-by-term comparison at the head sha | UJ42UV0TW | requested (ts 1793657903) |
| G1–G5 | hard-gate tests of §8.2, written first and run on 2d9fa419 for their starting state | implementer, after X1 | not started |
| E1 | `jupiter_gcm` 30-level stretched vs uniform, early (§8.3) | to be assigned | blocked on O1–O3 and X1 |
| E2, E3 | shock tube and gravity wave on the stretched grid (§8.3) | to be assigned | not started; thresholds to be proposed first |
| C1 | cost measured in snapy, CPU and CUDA, including a smaller-L2 GPU (§8.4); replaces the 11–17 % projection | Tianhao / Linfeng | not started (supersedes Q4) |
| O1 | uniform control for E1: 77 (the smallest count no coarser than the stretched grid's finest cell, §8.3) or the deck's own 100 (`examples/jupiter_gcm.yaml:67`) | UU9SW7MHU / Jiheng | **open — mismatch with the deck** |
| O2 | E1 stretched grid: Jiheng's n = 5 face list (option B) or a geometric x1rat 1.058 (option A). A single ratio cannot satisfy n = 5 through an isothermal Tmin layer more than one cell thick (§8.3, §4.9) | Jiheng / Tianhao | **open — not checked; the CSV is not on this host** |
| O3 | the deck is gnomonic-equiangle (`examples/jupiter_gcm.yaml:56`); §1 scopes the change to Cartesian columns. Extend the scope or run E1 on a Cartesian analogue? | Xi / Cheng | open |
| O4 | source of the "190× route A at n = 40" figure (ts 1793657903): not in this note (§4.8 has 105× tracer, 329× velocity `shock: false`) | UU9SW7MHU / Xinyue / Tianhao | open |
| O5 | E1 run length (the deck's `tlim` is 100.e5 s, `examples/jupiter_gcm.yaml:113`) | to be assigned with E1 | open |
| P1 | real-grid `shock: true` rerun of §4.8, §7.5 and §7.7 on Jiheng's lists (posted ts 1793656155) | Tianhao | **PENDING** |
| D1 | `x1rat` direction convention; whether to add option B (`x1f` list) in the first PR. §4.9 makes option B a contract requirement for realistic T(z) | Linfeng proposes; Xi/Cheng decide | open |
| D2 | ghost-width rule per boundary type (§3) | Linfeng + Tianhao | proposed |
| D3 | uniform classification from the grid key instead of the per-block probe | Linfeng + Xinyue | proposed |
| D4 | route-A layout (CPU index, MPS, CUDA global rows), cp5 per-face rows | Tianhao | drafted; checked by G0 |
| D5 | rung values; Courant defined on Δz_min or Δz_max | Jiheng | pending |
| Q1 | §7: which variables WENO5 sees | Tianhao + Xinyue | answered at 2d9fa419 (§7.2); real-grid rerun is P1 |
| Q2 | log1p Q in snapy (all three backends), and `SNAP_WB_REF4` round-off on thin cells | Xinyue (fix branch, after X1) | hypothesis |
| Q3 | Käppeli & Mishra equations with page/equation numbers | Xinyue | pending |
| Q5 | Wang, Feng & Spiteri (2008) content; novelty not claimed | Tianhao | unread |
| F1 | other uniform-spacing fixes from the inventory: diffusion `centered_derivative` (`src/forcing/diffusion.cpp:70-84`) and `face_average` (`:99-108`), cubed-sphere diffusion scalar h (`src/forcing/diffusion_cubed_sphere.cpp:191`), `bot_heat`/`top_cool` budgets (`src/forcing/bot_heat.cpp:52-54`, `src/forcing/top_cool.cpp:52-54`), the dx²/12 curvature correction (`src/hydro/hydro_forward.cpp:1023-1047`). The cubed-sphere diffusion item matters for E1 (O3) | unassigned | listed |
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
