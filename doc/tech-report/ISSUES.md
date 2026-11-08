# Known gaps in sources/ (decided when the sources were prepared)

1. The gravity-work draft's Fig. 6 plots Mach/Courant boxes whose numbers were removed. Drop the figure; any replacement is regenerated from a committed script on snapy runs.
2. The draft's T1 numbers lack a deck and a sha. Mark them "missing evidence". The chapter author reruns them on the pinned sha or removes them.
3. The WB-reference spec numbers refer to an unresolved historical revision (full identifier unavailable; missing evidence). The chapter author re-measures them with tests/test_wb_ref4_order.py at the pinned sha.
4. The H2-dissociation EOS note cites a deck outside snapy. Drop that citation and keep the EOS physics with kintera evidence only.
5. Numbers from one-step harness runs on commits not in snapy were removed. The 1/R chapter rebuilds its table from the in-snapy closure run.
6. Carried over:
   - the S39-derived caption A/B swap and the "500.5x vs 50,050 %" wording;
   - ISSI deck naming;
   - Appendix A of the gravity-work draft, which is to be rebuilt from snapy evidence;
   - the figs/fig7* figures, which never ship.
7. Derivations that exist only as commit messages (e.g. #284, #285, #288) are re-derived from the code at the pinned sha, each with an executable check.
8. Local symbol, chapter 9 (`_x1profile.qmd`): $\varsigma$ for the $x_1$ profile of a diffusion coefficient
   (`nu_scale_x1`, `kappa_scale_x1`); NOTATION.md has none, and $s$ is the centroid slope. For the editor to add
   to NOTATION.md §8.
9. Local symbol, chapter 9 (`_relax.qmd`): $\alpha_{\mathrm f}$ for the at-face extrapolation weight of
   `relax-bot-temp` (code `a`). For the editor to add to NOTATION.md §8.
10. Local symbol, chapter 9 (`_sponge.qmd`): $\zeta$ for the depth fraction of a cell inside a sponge layer (code
    `eta`); $\eta$ is taken (NOTATION.md §1, §10). For the editor to add to NOTATION.md §8.
11. Local symbols, chapter 9 (`_framework.qmd`): $M$ (number of installed forcing modules), $\mathbf S^{m}$ (source
    of module $m$), $(\nabla\cdot\mathbf F)_i$ (discrete flux divergence, code `_div`), $\Delta\mathbf U^{[m]}_i$
    (increment after module $m$), $\Delta\rho_{\mathrm{d}}^{\mathrm{forc}}$ (`_forcing_dry`), and $b_k$, $B_k$,
    $\delta_k$, $\delta_{\mathrm{mach}}$ for the round-off bound of a floating-point sum. NOTATION.md has $\mathcal L$
    but no source vector or divergence symbol. For the editor to add the first five to NOTATION.md §7.

## Chapter 1 local transfer notation (draft)

`book/chapters/01-overview/_stage.qmd` proposes $J^{\mathrm d}_{i+1/2}$ for the time-integrated implicit dry transfer [kg] and $J^{\mathrm{tr}}_{n,i+1/2}$ for its upwind passive-tracer transfer [kg]. These avoid collision with $P$ (corrected potential energy) and $G$ (total mass flow). Superscripts $\mathrm{base}$, $\mathrm{entry}$ and $\mathrm{source}$ (with $\mathrm{carry}$ for the selected ratio) identify source-free, entry and source quantities. The editor should add or replace these in NOTATION and then remove the scheme's local-symbol note. Chapter 1 contains no new runtime measurement.

8. Chapter 12 local symbols awaiting notation integration: lateral face variance
   $\sigma^{2,\mathrm{face}}_i$ and cell-to-lateral-face centroid offset $\delta^{\mathrm{face}}_i$
   in the flux-covariance section. Neither replaces the cell variance or cell-minus-midpoint offset.
   Delete the local-symbol note when these enter NOTATION.md.
9. Chapter 12 distinguishes the mass-covariance setup guard from missing numerical accuracy evidence.
   The coverage matrix needs new runtime evidence for its explicitly listed combinations.

10. Chapter 2 local notation for editor reconciliation: species energy $e_n(T)$; tabulated constant
   capacity $c_{v,n}^{\mathrm{ref}}$; integration temperature $T_{\mathrm{int}}$; rotor level $J$,
   Boltzmann constant $k_{\mathrm B}$, and normalized finite-ensemble brackets; shallow-water depth-like
   state $d_{\mathrm{sw}}$; reaction extent $\zeta_k$, linearized residual $\mathbf b$, Jacobian $\mathsf J$,
   KKT multipliers $\boldsymbol\lambda$, and flux-only increment $\Delta\mathbf U^{\mathrm{flux}}$; the round-off
   derivations add the face product $[A\mathbf F_1]_{i+1/2}$, the kinetic energy density $K$, the Mach number
   $\mathrm{Ma}$, the thermal energy $\rho e_{\mathrm{th}}$, the magnitude sum $\Xi$, the volumetric heat capacity
   $\Psi(T)$ with $\Upsilon=\max\lvert\mathrm d\Psi/\mathrm dT\rvert/\Psi_{\min}$, contraction factor $\varsigma$, Newton error
   $\psi$, intermediate temperature $T_{\mathrm{mid}}$, residual magnitude sum $\Xi_U$ and rounding count $N_{\mathrm{rnd}}$, the
   compressibility $Z_n$, the
   isothermal speed $c_T$ and the shallow-water depth $D_{\mathrm{sw}}$. Owners: Chapter 2 / editor. Remove local
   notes when settled.
11. NOTATION section 2a's sentence describes the API tensor `V` as molar concentration, but at the pinned
   snapy code `MoistMixtureImpl::_adiabatic_index` multiplies `V` by inverse molar mass before using it.
   Chapter 2 describes `V` as partial mass densities and reserves the existing concentration symbol for
   the converted tensor. Editor should reconcile that sentence without changing the mathematical symbols.
12. Chapter 2 source inventory corrects the commented-out 14-variable test in OUTLINE section 2.3.
    The draft does not treat it as active coverage. Publication follow-ups: compiled H2 heat-capacity plot,
    moist-mixture temperature-map regression, active-set evidence, editor skeleton integration and renders.
13. PDF only: every `@sec-ch05` reference renders as a bare "1" instead of "Chapter 5" (the chapter 12 opening reads
    "in Chapter 4, 1 and Chapter 6"); the HTML renders "Chapter 5". In the PDF build's .tex that sentence reads
    `Chapter~\ref{sec-ch04}, 1 and Chapter~\ref{sec-ch06}`: the "1" is a literal written before LaTeX runs, not a
    `\ref`. `\label{sec-ch05}` sits correctly on its `\chapter`, and the render prints no crossref warning. The
    tip's CI PDF (run 38359493479, at fc0c6b69) already shows it. It reproduces in a minimal book (index, chapters 4,
    5, 6 and 12, `eval: false`, Quarto 1.10.19, lualatex) and persists with the chapter 5 file reduced to its heading
    `# Hydrostatic and well-balanced treatment {#sec-ch05}` plus one line of text, so chapter 5's content is ruled
    out. Hypothesis, untested: the cause is outside chapter 5 (another chapter's content, the book configuration,
    or Quarto's crossref resolution in the single-document PDF pass). Next step: bisect the other chapters of the
    minimal book and the `_quarto.yml` options.


## Chapter 11 local notation and evidence

The boundary schemes propose these local symbols for notation-table integration:
`outflow`: $\mathbf W^{\mathrm{bg}}$ (saved initial boundary state, separate from the hydrostatic reference),
$v_{\mathrm{out}}$ (outward velocity), $Z_{\mathrm{ac}}$ (acoustic impedance), $a_\pm$ (acoustic perturbations),
$d_{\mathrm{ent}}$ (advected density combination), $\alpha_{\mathrm{bc}}$ (shared admissibility factor), and
$\delta q$ (difference from the saved boundary background; not the centroid offset $\delta_i$).
`solids`: $D_i(b,l)$ (minimum prefix flip count), $m_b$ (minimum run length),
$\mathrm{cost}_i(b)$ (candidate flip cost), and $\mathsf H$ (normal reflection matrix).
Remove the local-symbol notes once the shared notation table incorporates these concepts.

Runtime gaps: outflow/WB/VIC and corner combinations, periodic solid closure, scalar/diffusion coupling
through solids, and at least three-resolution wall-reference convergence. These are missing evidence,
not measured defects. The source tests and report formula checks are separated in the Chapter 15 catalogue.

## Chapter 10 local symbols (draft)

Owners: chapter 10 / editor. Each scheme file lists its symbols in a "Local symbols" line; remove that line when the
symbol enters NOTATION.md.
- `_borrow.qmd`: $\mathcal V_c\subset\mathcal V$, the parent-vapour set of condensate $c$ ($\mathcal P$ is the potential energy).
- `_redo.qmd`: $f_\iota$, $\iota=0..5$, the six redo flags, and $c_{\mathrm{redo}}=\sum_\iota2^\iota f_\iota$ the cause word.
- `_fixvapor.qmd`: $\mathcal M$, the window of $x_1$ cells one scan step of the column repair rewrites; $D$, the
  deficit of the upward branch.
- `_kinetics.qmd`: $\dot{\boldsymbol\omega}$, reaction rates; $\mathsf J_{\dot\omega}$, their concentration Jacobian
  (subscripted to stay apart from chapter 2's $\mathsf J$); $\zeta_k$, the evaporation extent; $[n=c(k)]$, the
  indicator that replaces a Kronecker $\delta$ ($\delta$ is reserved).
- `_tracer.qmd`: $b$, the tracer upper bound; $F_n$, $F_{\mathrm d}$, the $x_1$ face fluxes of tracer $n$ and of dry air;
  $F^{\mathrm c}_n$, the complement flux ($G$ is the mass flow); $J^{\mathrm d}_{i-1/2}$, the implicit dry transfer as in
  chapter 1 ($M$ is the domain mass).
- `_sed.qmd`: $a_n$ particle radius, $\rho_{\mathrm p,n}$ particle density, $\beta_n$ Cunningham factor, $\lambda$ mean
  free path, $\mathrm{Kn}$ Knudsen number, and $m$, $d$, $\epsilon$ for the background gas's molecular mass, diameter
  and Lennard-Jones well depth ($k_{\mathrm B}$ as in chapter 2).

## Chapter 6 local symbols (draft)

Owners: chapter 6 / editor. Each scheme file lists its symbols in a "Local symbols" line; remove that line when the
symbol enters NOTATION.md.
- `_cell.qmd`: $\rho^{\mathrm{hs}}_i$, the hydrostatic-correction density of chapter 5 (code `rho_grav`).
- `_face.qmd`: $m_i=\rho_iv_{1,i}$, the $x_1$ mass flux density at cell $i$ (code `rhov`).
- `_fixer.qmd`: $\varpi_s$, the weight of stage $s$'s increment in the step (code `cw`); not $c_s$, the sound speed.
- `_vic.qmd`: $\mathbf e_m$, the unit row vector of the normal-momentum unknown; $[\mathsf X]_\rho$, $[\mathsf X]_E$,
  the mass and energy rows of a block $\mathsf X$.
- NOTATION section 5 describes $F^{\mathrm{ref}}$ (code `bflux1`) as "the reference-state part of the $x_1$ mass
  flux"; in the code it is the Riemann solver's $x_1$ mass flux before the positivity limiter and sedimentation
  (src/hydro/hydro_forward.cpp:405-408@e894700ff7aee30b52882e5202b16461413780b0). Chapter 6 uses the code's
  meaning; the editor should reword the NOTATION entry.
- NOTATION section 7 writes the gravity source Jacobian as $\mathsf\Phi$, but the PDF's sans-serif font has no
  sans capital Phi (U+1D6F7): the render drops the glyph. `_vic.qmd` writes it $\boldsymbol\Phi$ (STYLE 5, bold
  Greek); the editor should change the NOTATION entry to match.

- ch15 notation proposal: `\zeta_{15}` is a dimensionless convergence exponent and `\psi_{15}` its positive error coefficient (density units / m^exponent) in the verification-metric derivation. Both are local pending editor registration; neither $\zeta$ nor $\psi$ appears in NOTATION. They replace the conflicting convergence symbols: $\nu$ is kinematic viscosity, $\nu_{nk}$ a stoichiometric coefficient, and $C$ the Courant number.
- ch15 also uses `\mathbf n` for the dimensionless outward unit normal in the divergence theorem; proposed notation entry, defined locally and not used as a species index.

## Chapter 4 local symbols (draft)

Owners: chapter 4 / editor. Each scheme file lists its symbols in a "Local symbols" line after its At-a-glance box;
remove that line when the symbol enters NOTATION.md.
- Reconstruction: $D_-, D_+, D_i$ (PLM differences and slope); $c_l$, $n_{\mathrm s}$, $\eta_n$ (stencil weights, width,
  rounding factor); $\mathcal W_\ell, Q_\ell, \beta_\ell, d_\ell, \omega_\ell, \alpha_\ell$, $\epsilon_{\mathrm W}$, $\mathcal A_q$, $\zeta_{\mathrm{ex}}$ (WENO
  candidates, indicators, weights, floor, stencil scale, critical-point offset; $\ell$ indexes candidates because $k$
  is the $x_3$ index); $a_0, a_1, \dots$ (Taylor coefficients).
- Riemann solvers: $v_\perp, v_{\parallel,1}, v_{\parallel,2}$ (face-frame velocities); $p_f$, $v_f$ (face pressure and
  velocity); $\rho_{\mathrm{av}}, \gamma_{\mathrm{av}}, c_{\mathrm{av}}$; $\hat H$ (specific total enthalpy);
  $\lambda^{\mathrm L}, \lambda^{\mathrm R}, \lambda_{\mathrm c}, p_{\mathrm c}, p_{\mathrm{pv}}, \zeta^{\mathrm K}, \lambda_{\mathrm{tiny}}, \mathbf D, \mathcal J^{\mathrm K}, \Pi^{\mathrm K}, \alpha_{\mathrm c}$ (HLLC); $f$ for the $x_1$ seam
  face (chapter 3 writes $s$, which NOTATION reserves for the centroid slope); $\mathcal Q$ a set of cells (divergence);
  $\varrho_{\mathrm K}$, superscript $\mathrm{Roe}$, $\lambda_\mp, \lambda_0, \alpha_\mp, \alpha_0, \alpha_\parallel, \mathbf r_\ell$, $a_{\mathrm{LF}}$ (Roe);
  $\boldsymbol\psi$, $\mathbf f$, $a$ (plume-roe). $d_{\mathrm{sw}}$ is chapter 2's local symbol, reused.
- Sources and 4B: $p^{\mathrm{sh}}$ (shifted pressure; the code's `p*`, renamed because the star is the thermodynamic
  reference state); $\partial^{\mathrm h}_1$, $\partial^{\mathrm w}_1$ (centred and one-sided $x_1$ differences);
  $\sigma^2_{\mathrm A,i}$ (`face_moment2_x1`); $y_{\mathrm d}$; for the buoyancy ratio $y_{\mathrm v}, X_{\mathrm v},
  \mu_{\mathrm{mix}}, \alpha_{\mathrm v}, \Gamma, b, \Upsilon$ and the superscripts $\mathrm{ex}$, $\mathrm{err}$.
- Radial $x_1$ reconstruction (`_x1volume.qmd`): $\mathcal X$ (the $x_1$ volume coordinate, $x_1^3/3$ on a radial
  grid, whose face increments are appendix A's $V^{(1)}_i$), $\Delta\mathcal X_i$, $\hat{\mathcal X}$ (that coordinate
  shifted to the target face and scaled by the target cell's increment) and $\mathbf c^{\mathrm L}_f,
  \mathbf c^{\mathrm R}_f$ (the per-face coefficient rows). $\mathcal X$ is calligraphic because $V_i$ and
  $V^{(1)}_i$ are the cell volume and its $x_1$ factor, and $v$ is a velocity. The candidate index $\ell$ and
  $Q_\ell, \beta_\ell, d_\ell, \alpha_\ell, \epsilon_{\mathrm W}$ are reused from the WENO section unchanged.
  NOTATION.md has no symbol for the volume coordinate; the editor owns whether it gains one in §1 next to
  $V^{(1)}_i$, after which the local-symbol entry is deleted from the section.
- Overlap for the editor: chapter 12 writes the same face moments as $\sigma^{2,\mathrm{face}}_i$ and
  $\delta^{\mathrm{face}}_i$, chapter 3 as `face_moment2_x1` and $x_{1,i} - x^{\mathrm A}_{1,i}$; chapter 4 follows chapter 3
  and writes the moment $\sigma^2_{\mathrm A,i}$. One form should enter NOTATION.md §1.

## Chapter 9 drop-in local symbols (draft)

The eight non-framework active forcing sections now define their local symbols after the glance boxes.
The editor owns registration of these definitions; NOTATION.md is unchanged. In particular the drop-ins
use $n_{\mathrm{dep}}$ for deposition depth, $L_{\mathrm{spg}}$ and $\alpha_{\mathrm{spg}}$ for sponge width and stage drag,
$\mathsf D$ and $\ell$ for the user-forcing dictionary and module index, $\boldsymbol\Pi$ and $K_{\Delta t}$ for viscous
stress and the time-step coefficient, $\alpha_{\mathrm f}$ for wall extrapolation, and $c_0$, $\eta$ for the constant
profile product and its relative face excess. The full units and meanings are in the eight local-symbol paragraphs.

## Chapter 7 local symbols, partial VIC (draft)

`_vic-assembly.qmd` defines, for the $m_a$ fold of the partial system: $a\in\{2,3\}$ for a tangential direction;
$\tilde m_{a,i}$ for the part of the explicit tangential-momentum increment that the explicit mass increment does
not carry; $\mathsf A_i[m_a]$, $\mathsf B_i[m_a]$, $\mathsf C_i[m_a]$ for the $m_a$ columns of the full blocks restricted
to the rows $(\rho,\rho v_1,E)$; $\mathsf A^{(3)}_i$ and $\mathsf A^{\mathrm f}_i$ (and the same for $\mathsf B$, $\mathsf C$) for the
$(\rho,\rho v_1,E)$ blocks before and after the fold; $\mathbf e_\rho$ for the density column; and $\mathbf f^{\mathrm{tan}}_i$
for the right-hand-side term the sweep subtracts. `_vic-redistribute.qmd` defines $\mathcal T^{\mathrm c}_{i+1/2}$ for the
total clamped face transfer and $v_{a,\mathrm{don}}$ for the donor's tangential velocity. The editor owns registration;
NOTATION.md is unchanged.

## Chapter 9 cubed-sphere diffusion local symbols (draft)

`book/chapters/09-diffusion-forcing/_csdiffusion.qmd` defines, after its glance box: $\mathbf X$ (Cartesian position),
$\mathbf a_j$, $\mathbf a^j$ (covariant basis of $(x_1,x_2,x_3)$ and its reciprocal), $\hat{\mathbf n}$ (unit face
normal), $\mathbf t$ (traction), $K_{\mathrm c}$ (conductivity; $k$ is the reaction index), $\Delta n_{\mathrm s}$ (normal
distance across a block edge; $\sigma$ is the cell variance), $\mathcal G^{ab}$ (inverse unit-sphere panel metric;
$g_{ab}$ is the normalised panel metric), $b_{\mathrm{SD}}$ (the SDIRK stage coefficient; $\gamma$ and $\beta$ are taken)
and $\mathsf M$, $\mathsf K$, $\mathbf S$ (the radial solve's matrices and source). NOTATION.md is unchanged; the
editor owns their registration.
