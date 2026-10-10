# T1L cov+W convective-onset growth-rate error: validation gate, per-term ablation, analytic coefficient

Read-only analysis of `UCzhangxi/snapy` branch `next/curved-gravity-work-wb`.

| item | value |
|---|---|
| code read | `37dce4efdd8b1bdf9f08a91edf8fd3da38384672` (tree `708c4e71c56e9ee232c5e6c253822059cfd33523`) |
| base | `chengcli/snapy` main `aea71ed852effb09e6aa155dd26349f1210ef556`; `git merge-base HEAD aea71ed` → `aea71ed…` |
| verification | `git -C finalhead-20261009/wt-head rev-parse HEAD` → `37dce4efdd8b1bdf9f08a91edf8fd3da38384672`, clean tree (`git status --porcelain` empty) |
| drivers | `data_in/F0C8AM8K5QU/run_t1l.py`, `data_in/F0C852221RU/evp_t1l.py`, `data_in/F0C7RKD1AJ3/fit_t1l.py` (copied to `drivers/`, unmodified) |
| repository writes | **none**. No commit, branch, push, PR, issue, comment or review. No build was run. |
| python | `snapy-kintera130/.venv-kintera130-py311/bin/python` (3.11.13, numpy 2.4.6, sympy 1.14.0, torch 2.10.0+cu128) |

**Build disclosure.** I did not build snapy. For the discrete hydrostatic base state (`snapy.balance_column`) and
the grid metrics, and for an independent cross-check operator, I reused the CPU extension that was already
built at this exact sha in my own earlier folder (`finalhead-20261009/pyb-cpu`, `PYTHONPATH=…/lib.linux-x86_64-cpython-311`).
The operator `L_h` whose eigenvalues are reported below is my own numpy reimplementation
(`t1lmodel.py`), written from the source listed in the table of §2.

Deck parameters are taken from `evp_t1l.py` at eps = 1e-3:
`beta = 0.2867142857142857`, `Ra = 65004.00032826061`, `mu = 1.2403091799880253e-4`,
`K = 4.341082129958089e-4`, `kx = 2.221441469079183`, box 1 H × 2√2 H, nx = 2 nz, two reflecting walls,
`gravity-work: face`, `non-hydrostatic: 1`, `weno5`, `SNAP_WB_REF4=1`, `SNAP_FLUX_COVARIANCE=1`.

Continuous reference growth rate

```
Omega = 0.016697580061064126        (evp_t1l.py, Chebyshev)
        n=48  0.016697580060988027
        n=64  0.016697580060637245
        n=96  0.016697580061064126
        n=128 0.016697580061714290     -> converged to ~1e-10
```
(`out/evp_e1e-3.json`, produced by `./py.sh evp_run.py`.)

---

## 1. Validation gate — **PASSED**

`L_h` assembled column by column in numpy from the semi-discrete update (mass-flux face density including
the reconstruction and the face reference `dsf`; momentum pressure gradient with its cell/face reference;
energy flux; face gravity work; curvature flux; the x2 covariance correction; dynamic viscosity and
conduction), linearised about the **discrete** hydrostatic base state, with **both wall rows written out
explicitly** (`fill_ghosts`, the clamped reference stencils, and the zeroed wall curvature flux are all
present — nothing was dropped). Leading eigenvalue of the single x-Fourier mode the deck uses.

Command: `./py.sh t_model2.py {16,32,64,128}` → `out/model_vs_snapy*.log`.

| nz | Omega_h (numpy L_h) | rel_err = Omega_h/Omega − 1 | same, compiled solver | max&#124;ΔM&#124;/&#124;M&#124; |
|---:|---|---|---|---|
| 16 | 0.01800539269092138 | **+7.832348e-02** | +7.832803e-02 | 7.27e-08 |
| 32 | 0.016896061344470248 | **+1.188683e-02** | +1.188792e-02 | 5.94e-08 |
| 64 | 0.01673071383773235 | **+1.984346e-03** | +1.984897e-03 | 6.01e-08 |
| 128 | 0.016703761558430796 | **+3.702032e-04** | +3.703312e-04 | 6.00e-08 |

The "compiled solver" column is the same operator obtained by central-differencing one explicit RK stage of
the built extension at this sha (`./py.sh sweep.py <nz> covW`, `out/sweep.jsonl`). The two independent
assemblies agree to 6e-8 relative on the whole matrix, which is the finite-difference floor (eps = 1e-6).

**Against the measurement to reproduce (+1.18e-2 at nz32, +1.98e-3 at nz64):**

```
nz32:  +1.188683e-02 / 1.18e-2 - 1 = +0.74 %
nz64:  +1.984346e-03 / 1.98e-3 - 1 = +0.22 %
```

Both well inside the 10 % gate. **The measured numbers are the semi-discrete eigenvalue error of this
scheme.** They are not a fit-window artefact, not a seed transient and not a time-stepping error (§4).

### 1a. Shape of the error — it is dz² + dz³, not dz² log dz

Local orders `log2(y_i/y_{i+1})`: **2.720, 2.583, 2.422** — drifting downward, the signature of a second-order
term with a large third-order companion.

Fits of the four-point ladder (`./py.sh orderfit.py` → `out/orderfit.log`), reported with the worst relative
residual over the four points:

| model | coefficients | max rel resid |
|---|---|---|
| c2·dz² + c3·dz³ | c2 = +4.274, c3 = +252.4 | 3.0e-02 |
| c2·dz² + c3·dz³ + c4·dz⁴ | c2 = **+4.01**, c3 = **+265.7**, c4 = −145.1 | 2.0e-03 |
| a·dz² + b·dz²·log(dz) | a = +49.65, b = +10.68 | **1.4e+00** |
| b·dz²·log(dz) alone | b = −6.858 | 4.5e+00 |
| c2·dz² alone | c2 = +19.54 | 2.2e+00 |
| c3·dz³ alone | c3 = +321.9 | 5.9e-01 |

Two-point exact (dz², dz³) fits on consecutive pairs converge monotonically:

```
(16,32)  c2 = +4.2934  c3 = +252.12
(32,64)  c2 = +4.0836  c3 = +258.83
(64,128) c2 = +4.0029  c3 = +263.996
```

**The data support `rel_err = c2 dz² + c3 dz³` with c2 → 4.00 and c3 → 264–266. They reject `dz² log dz`
in any combination** (residuals of order 1, i.e. the model cannot fit the ladder at all).

**Why the ratio is 5.96 and not 4.** With c2 = 4.00, c3 = 264 the dz³ term carries 67 % of the error at nz32
and 51 % at nz64:

```
nz32: 4.00/1024 + 264/32768 = 3.906e-3 + 8.057e-3 = 1.196e-2
nz64: 4.00/4096 + 264/262144 = 9.766e-4 + 1.007e-3 = 1.983e-3   -> ratio 6.03
```
against the measured 5.96. **Yes — a dz³ contamination fully explains the 5.96 ratio (log2 = 2.58).** No
anomaly, no log term, nothing unexplained.

---

## 2. Per-term numerical ablation on `L_h`

One discrete ingredient at a time replaced by its exact continuous counterpart (or switched off), the rest
of the operator untouched; the leading eigenvalue is re-measured. Table entries are
`rel_err(ablated) − rel_err(baseline)`.

Command: `./py.sh ablate.py 16 32 64` and `./py.sh ablate.py 128` → `out/rows.jsonl`, `out/rows128.jsonl`;
tables by `./py.sh analyse2.py`, `./py.sh analyse3.py` → `out/analyse2_final.log`, `out/analyse3_final.log`.

| # | term | source at 37dce4ef | nz32 | nz64 | local log2 order (16→32, 32→64, 64→128) | fitted c2, c3 (fine 3) |
|---|---|---|---:|---:|---|---|
| — | **baseline rel_err** | — | **+1.1887e-02** | **+1.9843e-03** | 2.72 / 2.58 / 2.42 | +4.077, +259.0 |
| A1 | face reference density `dsf` → ρ_a(z_f) | `src/hydro/wb_ref4.cpp:276-286` (+`:195-219` weights), `src/hydro/hydro_ref_x1_impl.h:161-167` | −2.8162e-03 | −6.6434e-04 | 2.25 / 2.08 / 2.02 | −2.565, −10.2 |
| A2 | LMARS impedance ρ̄c̄ → √(γ p ρ) | `src/riemann/lmars_impl.h:34-43` | −3.08e-10 | +3.73e-11 | — | 0, 0 |
| A3 | x1 energy-flux enthalpy → exact | `src/riemann/lmars_impl.h:28-31,61,76` | +3.0837e-03 | +8.4916e-04 | 1.39 / 1.86 / 1.97 | +3.785, −20.1 |
| A4 | covariance correction OFF | `src/hydro/hydro_forward.cpp:92-95,130-137,148-149` (call `:547-548`) | −1.4624e-01 | −3.5157e-02 | 2.31 / 2.06 / 2.01 | **−138.5**, −359.9 |
| A5 | covariance `d1[h]` → exact dh/dz | `src/hydro/hydro_forward.cpp:111,131-133` | −5.44e-12 | +1.03e-11 | — | 0, 0 |
| A6 | face gravity work → cell form | `src/hydro/hydro_forward.cpp:757-759,798-805,838-839` | −1.0846e-02 | −1.6015e-03 | 2.92 / 2.76 / 2.59 | −2.027, −290.5 |
| A7 | curvature flux OFF (face work kept) | `src/hydro/hydro_forward.cpp:778-797` | +1.1521e-01 | +3.1214e-02 | 1.65 / 1.88 / 1.96 | **+137.5**, −625.6 |
| **A8** | **wall rows of the curvature flux: zeroed → one-sided 2nd difference** | **`src/hydro/hydro_forward.cpp:785-790`** (`curv_flux1.select(-1,0).zero_()` / `select(-1,n).zero_()`) | **−8.2217e-03** | **−1.0243e-03** | **3.04 / 3.00 / 3.00** | **+0.026, −270.2** |
| A9 | vertical reconstruction C5 → C7 | `src/recon/cp5.cpp:13-17`, `src/recon/reconstruct.cpp:75-76,133-143` | −3.1337e-03 | −9.0789e-04 | 1.99 / 1.79 / 1.64 | −4.360, +36.9 — **invalid, see note** |
| A10 | `SNAP_WB_REF4` OFF | `src/hydro/wb_ref4.cpp:118-132,195-230,233-286` | −1.4784e-02 | −1.9710e-03 | 2.84 / 2.91 / 2.87 | −0.987, −452.9 |
| A11 | discrete base state → cell averages of the analytic profile | `run_t1l.py` `--ic avg`, `snapy.balance_column` | −3.8086e-03 | −9.5915e-04 | 1.92 / 1.99 / 2.00 | −3.956, +1.8 |

Full ladder with the "implied pure coefficient" diagnostics (value × nz² and value × nz³) is in
`out/analyse2_final.log`. The decisive column is value × nz³ for A8:

```
A8 x nz^3:   -276.36 (16)   -269.41 (32)   -268.52 (64)   -268.49 (128)
```
flat to 0.01 % between nz64 and nz128, with a fitted dz² part of +0.026 — i.e. **A8 is a pure dz³ term with
coefficient −268.5**.

### Note on A9 (invalid test)

The C7 stencil I substituted does not fit inside the array at the two wall faces, so its ablation is
contaminated by a boundary-stencil artefact — confirmed by its first-order projection having a wall-cell
share of exactly 1.000 (`out/projectall.log`). **A9 does not measure the reconstruction order and should be
ignored.** The clean statement about the reconstruction comes from the compiled solver instead: running the
identical deck with `type: cp5` rather than `weno5` (`out/sweep.jsonl`) gives

```
nz32  weno5 +1.1887923e-02   cp5 +1.1886825e-02   difference 1.1e-06  (0.009 % of the error)
nz64  weno5 +1.9848973e-03   cp5 +1.9843522e-03
```
so the nonlinear WENO5 weights contribute ~0.01 % of the growth-rate error; the scheme is, for this smooth
base state, its linear C5 counterpart. (Deck `card.yaml:20-21` sets `weno5` for both directions and
`reconstruct.cpp:75-76` builds both interpolators from the same option, so **all** rows use weno5 — my
numpy `L_h` uses C5 throughout and still matches the compiled weno5 operator to 6e-8.)

### Which terms cancel

- **A4 and A7 are the two giants and they very nearly cancel.** At nz128, switching the covariance correction
  off shifts the eigenvalue by −142.6 dz² and switching the curvature flux off by +131.5 dz²; their sum is
  −11.1 dz², i.e. they cancel to 8 % of their individual size. In the fitted dz² coefficients the
  cancellation is sharper still: c2(A4) = −138.5 against c2(A7) = +137.5, cancelling to −1.0 (99 %), with
  the residue sitting in their dz³ parts.
  Switching **both** off (`./py.sh combo.py`, `out/combo.log`) leaves a clean second-order error for the
  whole scheme:
  ```
  cov off + curv off, rel_err x nz^2:  nz32 -4.4462   nz64 -4.1076   nz128 -4.0256
  ```
- **A2 and A5 are numerically dead** (1e-11 and below): the LMARS acoustic impedance and the two-point
  gradient inside the covariance correction contribute nothing to this mode.
- The remaining second-order players are small and of mixed sign and do **not** add up to one dominant term:
  A1 −2.6, A3 +3.6, A10 −1.0 (dz² part), A11 −3.9. **I therefore name no single term for the dz² coefficient
  4.00** — the ablation set is not a partition of the error and the honest reading is that c2 is a sum of
  several comparable contributions.

### The dominant term, isolated

Applying **only** the A8 wall closure to the otherwise untouched scheme (`out/analyse3_final.log`):

| nz | rel_err baseline | rel_err with A8 | × nz² |
|---:|---|---|---:|
| 16 | +7.83235e-02 | +1.08526e-02 | +2.7783 |
| 32 | +1.18868e-02 | +3.66512e-03 | +3.7531 |
| 64 | +1.98435e-03 | +9.60034e-04 | +3.9323 |
| 128 | +3.70203e-04 | +2.42177e-04 | +3.9678 |

local order of the residual: 1.566, 1.933, **1.987**.

**Changing two numbers at the wall turns a drifting 2.4–2.7-order error into a clean second-order error with
coefficient 4.00** — exactly the c2 = 4.00 the global two-term fit of the untouched scheme predicted.

### Additivity and robustness

`./py.sh combo.py 32 64 128` → `out/combo.log`:

- A8 and A10 combined vs the sum of their separate shifts: nonlinearity **+0.58 %, +0.10 %, +0.01 %** at
  nz 32/64/128 — the ablations are additive, as first-order perturbation theory requires.
- The A8 coefficient is unchanged by the reference scheme: with `SNAP_WB_REF4` on it is
  −269.41 / −268.52 / −268.49; with it off, −265.09 / −267.76 / −268.39.

---

## 3. Analytic coefficient of the dominant term

### 3a. Symbolic truncation (sympy, `./py.sh trunc.py` → `out/trunc.log`)

With `h = dz`, `m = ρ w` the vertical mass flux, and `grav1 = −1`, the booked face gravity work in cell *i* is

```
book_i = -(M_i + M_{i+1})/2  +  (1/12)(m_{i+1} - 2 m_i + m_{i-1})      (interior)
```
(`hydro_forward.cpp:757-759` gives `φ_c div M − div(φ M) = (M_i+M_{i+1})/2 · grav1`; `:778-797` adds
`−grav1 · div H` with `H_f = (h/12)(m_f − m_{f−1})`), and the quantity it must equal is `−⟨m⟩_i`, the exact
cell average. Expanding:

```
interior cell:      book + <m> =  h^4 (168 f'''' + 11 h^2 f^(6)) / 20160  =  h^4 m''''/120 + O(h^6)
bottom wall cell:   book + <m> = +h m'/12  -  h^2 m''/24 + 5 h^3 m'''/288 + ...
top wall cell:      book + <m> = -h m'/12  -  h^2 m''/24 - 5 h^3 m'''/288 + ...
```

**The face form is fourth-order accurate in every interior cell and only FIRST-order accurate in the two
cells against the walls**, because `curv_flux1` is zeroed on the wall faces
(`hydro_forward.cpp:785-790`). The wall defect is `± (h/12) ∂_z(ρ w)`, plus at the bottom, minus at the top.

### 3b. First-order perturbation theory

Definition used (`./py.sh projectall.py`, `./py.sh wallterm.py`, `./py.sh wallsplit.py`):

```
dOmega_k = Re[ <psi_L, T_k psi_R> / <psi_L, psi_R> ]
```
with `T_k = L_h − L_h^{(k ablated)}`, `psi_R` the right eigenvector of `L_h` for the leading (real)
eigenvalue and `psi_L` the matching eigenvector of `L_h^H`. **Inner product:** the plain Euclidean form
`<a,b> = Σ conj(a_j) b_j` over all `4·nz` primitive rows (ρ, v1, v2, p) of the single Fourier mode. On this
uniform grid the cell volume `dz` is a constant factor that cancels between numerator and denominator, so
no volume weight is needed. **Boundary contributions are not separate terms:** the two wall cells are
ordinary rows 0 and nz−1 of `L_h`, carrying the reflecting-wall ghost closure
(`fill_ghosts`: v1 odd, ρ even, p from the wall temperature) inside the matrix, and they are summed with
exactly the same weight as every interior row.

For the dominant term the analytic source is written straight from §3a into the energy row of the two wall
cells and multiplied by (γ−1) to convert the conserved-energy tendency to the pressure row of `L_h`:

```
(T_8 psi_R)[p-row, cell 0]      = + (gamma-1) (h/12) d_z(rho_0 w)|_{cell 0}
(T_8 psi_R)[p-row, cell nz-1]   = - (gamma-1) (h/12) d_z(rho_0 w)|_{cell nz-1}
```
with `d_z` a one-sided three-point difference of the discrete eigenmode.

| nz | analytic dΩ/σ (closed form) | measured −A8 | ratio | analytic × nz³ |
|---:|---|---|---:|---:|
| 32 | +8.235292e-03 | +8.2217e-03 | 1.00165 | +269.85 |
| 64 | +1.024061e-03 | +1.0243e-03 | 0.99976 | +268.45 |
| 128 | +1.280193e-04 | +1.280263e-04 | 0.99995 | +268.48 |

**The closed form reproduces the ablation to 0.17 %, 0.02 % and 0.005 %.**

Per-wall split (`out/wallsplit.log`):

```
nz=32   bottom +4.41006e-03 (53.6%)   top +3.82524e-03 (46.4%)
nz=64   bottom +5.50726e-04 (53.8%)   top +4.73335e-04 (46.2%)
nz=128  bottom +6.90753e-05 (54.0%)   top +5.89441e-05 (46.0%)
```
**The two walls ADD, they do not cancel** — the local truncation signs are opposite but so is the sign of
`∂_z(ρw)` in the mode at the two ends.

**Why a first-order local defect gives a third-order eigenvalue error.** Three factors of `dz`: one from
the defect itself (`h m'/12`), one from the single-cell measure relative to the column, and one because the
adjoint energy component vanishes linearly at the wall. Measured (`out/wallsplit.log`):

```
|L_p[0]|/max x nz   = 1.3002 (nz32)  1.2958 (nz64)  1.2966 (nz128)
|L_p[-1]|/max x nz  = 1.8482 (nz32)  1.8409 (nz64)  1.8406 (nz128)
```
constant to 0.3 % — the wall adjoint is exactly proportional to `dz`.

### 3c. First-order theory for every term

`./py.sh projectall.py 64 128` → `out/projectall.log`. Ratio of first-order prediction to exact ablation:

| term | nz64 ratio | nz128 ratio | wall-cell share of the projection |
|---|---:|---:|---:|
| A1 | 0.978 | 0.994 | 0.002 / 0.000 |
| A3 | 1.031 | 1.007 | 0.001 / 0.000 |
| A4 | 0.985 | 0.996 | 0.000 |
| A6 | 0.984 | 0.994 | 0.648 / 0.482 |
| A7 | 1.015 | 1.004 | −0.032 / −0.016 |
| **A8** | **1.001** | **1.000** | **1.000 / 1.000** |
| A9 | 1.006 | 1.004 | 1.000 (artefact, see §2 note) |
| A10 | 1.001 | 1.000 | 0.012 |

Perturbation theory is accurate to ≤3 % for every term, so the ablation table can be read as a linear
decomposition. A8 draws exactly 100 % of its effect from the two wall cells; A10 draws only 1 % from them,
so **`SNAP_WB_REF4`'s contribution is not a wall effect** and is a different, mixed-order mechanism that I
did not resolve further (it is not the dominant term — see §5 for what is left open).

---

## 4. Sensitivity to the fit window

`fit_t1l.py` fits `ln|A_w|` over `t ∈ [1,5]/σ_EVP` with sub-windows `[1,3]` and `[3,5]`, where `A_w` is the
mass-weighted projection of the x-Fourier coefficient of w onto the EVP mode. I reproduced that fit exactly,
on the **exact linear evolution of my own discrete operator** seeded with the same EVP mode from
`modes/mode_e1e-03_n<nz>.npz`, sampled 40 times per e-fold as the driver does
(`./py.sh fitwindow.py 32 64 128` → `out/fitwindow.log`):

| nz | eigenvalue rel_err | fit `[1,5]` rel_err | window shift | fit `[1,3]` | fit `[3,5]` | spread (σ35−σ13)/σ |
|---:|---|---|---|---|---|---|
| 32 | +1.188683e-02 | +1.181019e-02 | −7.664e-05 (−0.64 %) | +1.167467e-02 | +1.188054e-02 | +2.059e-04 |
| 64 | +1.984346e-03 | +1.973109e-03 | −1.124e-05 (−0.57 %) | +1.952089e-03 | +1.983735e-03 | +3.165e-05 |
| 128 | +3.702032e-04 | +3.682264e-04 | −1.977e-06 (−0.53 %) | +3.644041e-04 | +3.701330e-04 | +5.729e-06 |

- The fit window biases the answer **low by 0.5–0.6 % of the error**, consistently; it does not change any
  conclusion. Notably `+1.181e-2` and `+1.973e-3` are, if anything, closer to Xi's quoted `+1.18e-2` and
  `+1.98e-3` than the bare eigenvalues are.
- Sub-window spread is **1.5–1.7 % of the error** at every resolution, so window stability is not a concern.
- The wall-excluded projection `A_w,nowall` gives +1.180999e-02 (nz32) and +1.973106e-03 (nz64) against the
  full projection's +1.181019e-02 and +1.973109e-03 — a difference of 2.0e-07 and 3e-09 in rel_err, i.e.
  1.7e-05 and 1.5e-06 of the error. The measurement does not depend on including the wall cells, even
  though the error is generated there.
- Seed contamination: the spectral gap is `(λ1−λ2)/σ = 0.81` and `|c2/c1|` at t = 0 is only
  3.9e-3 / 3.8e-4 / 2.1e-5 at nz 32/64/128, decaying to 1.8e-3 / 1.7e-4 / 9.4e-6 by the start of the window.
- Time discretisation (rk3, fixed dt at C_z ≈ 0.400): `./py.sh rk3check.py` → `out/rk3check.log` gives
  `(ln R(λdt)/dt − λ)/σ ≈ 1e-12` at every resolution. **Negligible.**

---

## 5. Answers to the questions asked

1. **Did the gate pass?** Yes. `L_h` gives +1.188683e-02 at nz32 and +1.984346e-03 at nz64, i.e. +0.74 % and
   +0.22 % from the measured +1.18e-2 and +1.98e-3. Ladder: +7.832348e-02 (16), +3.702032e-04 (128).
2. **Dominant term.** The **wall rows of the curvature flux that accompanies the face gravity work**,
   `src/hydro/hydro_forward.cpp:785-790` (the two `curv_flux1.select(-1, …).zero_()` calls), with the face
   work itself at `:757-759` and the curvature flux at `:778-797`.
   **Coefficient: −268.5 dz³ in relative growth-rate error** (equivalently the scheme's error contains
   **+268.5 dz³**, i.e. `+4.483 dz³` in absolute growth rate), stable to 0.01 % between nz64 and nz128 and
   to 0.1 % with `SNAP_WB_REF4` off. Closed form: the booked work exceeds the exact cell average by
   `± (dz/12) ∂_z(ρw)` in the bottom/top wall cell, which through first-order perturbation theory gives
   +269.85 / +268.45 / +268.48 dz³ at nz 32/64/128 — within 0.17 % / 0.02 % / 0.005 % of the ablation.
3. **Which terms cancel.** The covariance correction against the curvature flux: fitted dz² coefficients
   −138.5 and +137.5 cancel to −1.0 (99 %); the full shifts at nz128 are −142.6 and +131.5 dz², cancelling
   to −11.1 (92 %). With both switched off the scheme's error is a clean −4.03 dz². A2 (LMARS impedance)
   and A5 (the covariance's two-point gradient) are identically negligible at 1e-11.
4. **Does dz³ contamination explain the 5.96 ratio?** Yes, completely. c2 = 4.00, c3 = 264 reproduces the
   ladder and gives a 32→64 ratio of 6.03 against the measured 5.96; the dz³ term is 67 % of the error at
   nz32 and 51 % at nz64. `dz² log dz` is rejected (residuals of order 1).
5. **Fit-window sensitivity.** −0.5 to −0.6 % of the error from the `[1,5]`/σ window; 1.5–1.7 % sub-window
   spread; <1e-8 from excluding the wall cells; ~1e-12 from the time discretisation.

### Explicitly not established (labelled HYPOTHESIS or open)

- **The dz² coefficient 4.00 is not attributed to any single term.** A1 (−2.6), A3 (+3.6), A11 (−3.9) and the
  A4/A7 residual (≈ −10 for the pair) are comparable and of mixed sign.
- **HYPOTHESIS (untested closed form):** `SNAP_WB_REF4`'s contribution (A10: c2 = −1.0, c3 = −453 on the fine
  three, only 1 % wall-cell share) comes from the clamped quartic face stencil
  (`wb_ref4.cpp:195-219`, `s` clamped to `[is, iu-3]`) changing the reconstructed face mass flux over a
  band several cells wide, not from the outermost rows. I did not expand it symbolically: step 3 was scoped
  to the dominant terms and A10 is not the dz³ driver (A8's coefficient is unchanged when A10 is applied).
- **A9 is an invalid ablation** (C7 stencil truncated at the wall faces). Use the compiled weno5-vs-cp5
  comparison instead: the WENO nonlinearity is 0.009 % of the error.
- A11 at nz128 needed `balance_column` rtol relaxed from 1e-14 to 2e-14 (residual 1.157e-14, 3 sweeps);
  all other runs used 1e-14.
- Everything here is the **semi-discrete operator of the T1L deck at eps = 1e-3 in Cartesian geometry**. I
  ran no production simulation and make no claim about curved geometry, other eps, or the nonlinear regime.

---

## 6. Reproduction

All scripts live in `t1l-theory-20261009/`; `./py.sh` sets
`PYTHONPATH=finalhead-20261009/pyb-cpu/lib.linux-x86_64-cpython-311`, `SNAP_WB_REF4=1`,
`SNAP_FLUX_COVARIANCE=1` and runs the py311 interpreter.

> **Path note added when this was committed to the repository.** The report above is byte-identical
> to what I wrote when the numbers were produced, except for this paragraph. The scripts now live in
> `docs/derivations/t1l-onset-error/` and this file in `docs/derivations/`. Every path named in the
> report (`t1l-theory-20261009/`, `finalhead-20261009/`, `snapy-kintera130/`, `data_in/`, `out/`,
> `modes/`, `probe/`, `drivers/`) was relative to my scratch workspace on dungeon3,
> `/home/tianhaol/fridica-snapy/worker1/`, and none of those directories is part of this repository.
> The only file whose contents I changed is `py.sh`, whose three absolute paths — the prebuilt CPU
> extension at `finalhead-20261009/pyb-cpu/lib.linux-x86_64-cpython-311`, the interpreter at
> `snapy-kintera130/.venv-kintera130-py311/bin/python`, and the working directory
> `t1l-theory-20261009` — are now the environment variables `T1L_PYB` and `T1L_PY` and the script's
> own directory. The `out/` logs, the `modes/` and `probe/` data and the built extension are not
> committed, and the three driver scripts `run_t1l.py`, `evp_t1l.py` and `fit_t1l.py` that
> `t1lsnap.py` imports from `drivers/` are Xi Zhang's and are not redistributed here. No number,
> claim or limit in the report was changed.

```
./py.sh evp_run.py                     # continuous eigenvalue      -> out/evp_e1e-3.json
./py.sh evp_modes.py                   # EVP modes at each nz       -> modes/
./py.sh sweep.py <nz> <tag>            # compiled-solver operator   -> out/sweep.jsonl, out/M_n*.npy
./py.sh t_model2.py 16|32|64|128       # numpy L_h vs compiled      -> out/model_vs_snapy*.log
./py.sh orderfit.py                    # order of the gate numbers  -> out/orderfit.log
./py.sh ablate.py 16 32 64  ;  ./py.sh ablate.py 128    # ablation  -> out/rows.jsonl, out/rows128.jsonl
./py.sh a11_128.py                     # A11 at nz128, rtol 2e-14   -> out/a11_128.log
./py.sh analyse2.py ; ./py.sh analyse3.py               # tables    -> out/analyse*_final.log
./py.sh trunc.py                       # sympy truncation           -> out/trunc.log
./py.sh wallterm.py 32 64 128          # analytic wall coefficient  -> out/wallterm.log
./py.sh wallsplit.py 32 64 128         # per-wall split, adjoint    -> out/wallsplit.log
./py.sh projectall.py 64 128           # 1st-order PT, all terms    -> out/projectall.log
./py.sh combo.py 32 64 128             # additivity, A8/A10         -> out/combo.log
./py.sh fitwindow.py 32 64 128         # fit-window sensitivity     -> out/fitwindow.log
./py.sh rk3check.py                    # time discretisation        -> out/rk3check.log
```
