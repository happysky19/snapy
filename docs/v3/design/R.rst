:orphan:

V3 lane R: flux register, monitor and the hydro stage
=====================================================

Revision 2.6, 2026-11-17: Cheng's 22:20 EST
ruling accepts the per-column FP64 retry (4.5, section 11); A's
``step_field {1, 2, 3}`` on immersed-solid decks is agreed (4.2 "X and A").
Revision 2.5:
section 11 only, answered items closed with cites. Revision 2.4:
``R.rst`` text only, on skeleton rev 4.3
(``97c62312490c3e290d597a2d188785252773bd21``). ``flux_register.hpp`` is
unchanged since ``4c59162ae37080d0ab307b2823742b44f46da7c3`` in declarations
and line numbers, so the freeze stands and no client re-cites. Revision 2.3
was comments and text on revision 2.2 (``4c59162a``), and RULING V3-3,
which closes R-C1; its one declaration change is in ``hydro_stage.hpp``
(item 10), which no client calls. Revision 2.2 amended revision 2.1
(``6df93fda``) after reading X revision 3
(``100bc9b33514ebffd8c92b22c93cf25bc5c382d9``).
Owner: Tianhao Le (backup owner). Reviewers: Xinyue Wang and Zoey Hu. Design
only: no implementation change. Declarations are in ``docs/v3/skeleton/R/``
(not built): ``flux_register.hpp`` (rev 4.2, 117 lines) and
``hydro_stage.hpp`` (82 lines), 199 lines in all.

Every ``path:line`` is at chengcli/snapy
``9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410`` unless another commit is named.
Bare ``:N`` means ``src/hydro/hydro_forward.cpp:N``. "Measured" means a
line count read at the pin with ``git show <pin>:<file> | sed -n 'a,bp'``
and ``b - a + 1``; "estimate" means a design target, not counted code.
Nothing in this revision was built, compiled, syntax-checked, tested or
timed. A claim that needs a run is marked **hypothesis**.

**Changes in revision 2.4** (from ``97c62312``; ``R.rst`` only). Matrix
rows 73, 103 and 104.

1. ``after_combine`` has one runner, X's ``StageExecutor::after_combine(int
   stage, double dt)`` (``stage_executor.hpp:80-81``, ``X.rst:1285-1293``
   at ``00dee910``). Skeleton rev 4.3 (``97c62312``) removed
   ``HydroStage::after_combine(u, reg)``, which had no stage or ``dt``; the
   pin's ops need both (``meshblock.cpp:907-908, 950-951, 989``).
   The rev 2.2 mismatch and request to X (4.2 "X and A") are closed, and
   the stage driver's four ``after_combine`` lines leave section 9:
   3,493 -> 2,757 (was 2,761), 37 under 2,794.
2. L-3 (S and O): ``boundary(dim)`` sums the fluid domain's boundary faces,
   S's ``FaceKind`` ``wall``, ``outflow`` and ``custom``, plus every
   immersed-solid face with fluid on one side, all rows (4.2 O). No
   declaration changes; ``flux_register.hpp:97`` ("outward") stays.
3. Recorded from skeleton rev 4.3: ``hydro_stage.hpp:61-62`` puts I's
   gravity-work remainder before A's m1, the pin's order (``I.rst:299-303``
   at ``7604ada0``).

**Changes in revision 2.3** (from ``4c59162a``; Cheng's batch of nine and
Zoey's requests 5, 6, 12 and 13). Header comments are edited in place, so
every ``flux_register.hpp:N`` and ``hydro_stage.hpp:N`` citation still holds.
Client heads read: C ``559dd0b7``, X ``0fe47c6f``, O ``dfa8ecd0``, A
``2b0ac426``, EF ``5e30b31b`` (rev 3.6), S ``d03e4888``, K (kintera) ``fc619eec``.

1. ``derived`` (``:34``) is not hydro only: K's ``element/<name>`` rows
   (4.2 K) are derived rows of the hydro register too.
2. ``after_combine`` (``:22``; ``hydro_stage.hpp:67-70``): A's closure runs
   every stage (``meshblock.cpp:983-990``; several blocks:
   ``mesh.cpp:370-383``). The order at the pin is in 4.2 "X and A".
3. Retry causes are EF's four names (4.5). ``minima()`` and the other FP64
   monitor values are FP32 on MPS (section 6). Solid faces: tangential
   momentum is free-slip, and S calls ``set_prescribed`` on every register
   instance, hydro and each Scalar (3.5).
4. K's two solve counters, ``thermo.temp_solve`` and ``thermo.pres_solve``
   (``:36``; 4.2 K).
5. Only ``retry_flags()`` is read in X's step-end read. O reads the rest in
   ``observe`` and sums in ``flush`` (4.1 item 6).
6. ``riemann.central`` (any kept part) is valid until the next
   ``begin_stage`` (``:35``; 4.1 item 4).
7. R-C4: ``AmountKind::floor`` (``:28``) names EF only. C's face floors post
   counts (4.2 C).
8. Ruling V3-2: from R's PR R-1, the monitor's census counts accepted
   steps only, which is what ``begin_step`` (``:48``) and ``rollback``
   (``:86``) give. Before R-1 the existing meters stay as at the pin and
   include rejected attempts; there is no interim hook. No header change.
9. Mesh fixer lines are lane X's (ruling V3-1); R's table books none
   (section 9).
10. R-C1 closed by RULING V3-3 (4.2 C). ``hydro_stage.hpp:45-48``:
    ``covariance(faces, dim, reg)`` becomes ``build_covariance(faces,
    dim)``, called in C's ``before_solve`` hook, and
    ``post_covariance(dim, reg)``, called after the solve. The file stays
    82 lines.

**Changes in revision 2.2** (from ``6df93fda``). Matrix rows 97-102.

* ``begin_stage`` returns to ``(int, harp::IntegratorWeight const&)``, and
  ``weights()`` returns ``harp::IntegratorWeight const&``. ``RegisterWeights``
  is removed. X rev 3 calls ``begin_stage(int stage,
  harp::IntegratorWeight const&)`` (``X.rst:141-146`` at ``100bc9b3``) and
  moves IMEX-ARK out of this round (``X.rst:639-683``, ``StageTableau``
  removed from ``pyharp_integrator.hpp``). ``RegisterWeights`` existed
  only for ARK. If Cheng accepts X9, R adds separate explicit and implicit
  weights then (the rev 2.1 design is kept in 3.4 as a note).
* X's "``reset_step``" (``X.rst:153-155``, ``:693-694``) is R's
  ``begin_step()``. Answer to X's open question: yes, the step is zeroed
  once in X's ``kStepStart``, before the radial ``post_split``, and
  ``begin_stage(0)`` zeroes nothing (unchanged since rev 2).
* ``after_combine`` is entered after **each** stage's combine, not only the
  last. Request to X (4.2 X).

**Changes in revision 2.1** (from ``175af2fc``). Matrix rows 81-96.

* ``begin_stage(int, harp::IntegratorWeight const&)`` becomes
  ``begin_stage(int, RegisterWeights const&)``. The new struct
  ``RegisterWeights {carry, explicit_w, implicit_w}`` carries both of X's
  stage forms: Shu-Osher ``{w1_s, w2_s, w2_s}``, and X's proposed IMEX-ARK
  ``{1, bex_i, bim_i / gamma_i}`` (X rev 2 ``034ef405``, section 3, and its
  question in section 11). ``weights()`` lets a poster read its
  ``stage_weight``. R no longer names a pyharp type.
* ``AmountKind::diagnostic`` is new, for amounts that change no row:
  ``chem.elements``, ``vic.momentum_t.top``.
* The 4.2 K answer was wrong in revision 2. It said lane K had no design;
  K rev 1 is on UCzhangxi/kintera ``v3-design/K``
  ``f61d0d8069943bc71632be32d3224a2a782a5e29``, and I had searched only snapy
  forks. Revision 2 also called the saturation adjustment "chemistry". 4.2 K
  now follows K's own names.
* The transposed panel edges of Xi's note 11 (as quoted by lane S) are
  written into 4.2 S. ``replace``'s ``peer`` is S's mapped slab.
* R-C1 is open again: S rev 1.1 keeps the in-place rotation
  (``coord_rotation.hpp:37-40`` at ``d03e4888``).
* O's text at ``c12f78bb`` asks for exactly the rev 2 names; the
  differences are listed in 4.2 O.

**Changes in revision 2** (from ``3490d7e1``). Matrix rows 55-80; the
names are settled in section 4.2, ``retry_flags`` in 4.5.

* Cheng's ruling V3-1 (deletions are counted by the lane that owns the
  file) is applied: all of D4 is R's, A's remaining 25 + 15 lines stay in
  R's "after", and ``:988`` stays. The "under A's convention" alternative
  and conflict K8 are removed. S accepted D7 at rev 1.1
  (``d03e48880dc28b33eca6c62ff6ad8ad162bdcdb2``, section 9). R stands at
  3,493 -> 2,761 against 2,794 (section 9).
* ``begin_step()`` is new: X's step-start call. It zeroes the step sums and
  the monitor, so the radial ``post_split`` before stage 0 survives.
  ``begin_stage(0)`` no longer resets anything, and
  ``RegisterMonitor::reset_step()`` is removed.
* ``cell_amount`` takes the stage weight and an ``AmountKind``. The register
  carries every amount through the same ``w1`` recursion as the step field.
* New: ``AmountKind``, ``derived_amount``, ``derived_total``,
  ``record_min``, ``flag_retry``, ``RegisterMonitor::row_names``,
  ``amount_names``, ``kind``, ``counter_names``, ``minima``; the
  ``RegisterRequest`` fields ``row_names``, ``derived``, ``retry``.
* ``RegisterMonitor::counter(name)`` is replaced by ``counter_names()`` and
  ``counters()`` (int64). ``boundary(dim)`` is stated as area-integrated.
* The stage skeleton settles C's R-C1 and R-C3 and adds K's chemistry to
  ``after_combine``.

**Every name or signature changed since ``543ff84f`` (rev 1).**

.. list-table::
   :header-rows: 1
   :widths: 34 33 33

   * - name
     - at ``543ff84f``
     - at rev 2
   * - ``StageWeights``
     - struct ``{w0, w1, w2}``
     - removed (X owns the weights)
   * - ``FluxRegister::reset``
     - ``(coord, policy, nvar, StageWeights, RegisterRequest)``
     - ``(coord, policy, nvar, RegisterRequest)``
   * - ``begin_stage``
     - ``(int, StageWeights const&)``
     - ``(int, harp::IntegratorWeight const&)``, X only (rev 2.1 briefly had
       ``RegisterWeights``; removed in rev 2.2)
   * - ``weights()``
     - none
     - ``harp::IntegratorWeight const& weights() const``
   * - ``begin_step``
     - none
     - ``()``, X's step start
   * - ``RegisterPhase``
     - seven phases
     - ``+ after_combine``
   * - ``SeamRule``
     - none
     - ``{mean, owner_copy}``
   * - ``replace``
     - ``(dim, name, seam)``
     - ``(dim, faces, peer, SeamRule)``; ``peer`` already in this face's
       dim, basis and outward sign
   * - ``set_prescribed``, ``apply_prescribed``
     - none
     - ``(dim, mask[nvar, faces...], value)``, ``(dim)``; books
       ``boundary.prescribed``
   * - ``part_slot``
     - none
     - ``(dim, part)``
   * - ``add``
     - in place
     - in call order; also copies into a requested part of the same name
   * - ``scale``
     - ``factor`` unstated
     - ``factor`` ``[faces...]`` or ``[rows, faces...]``
   * - ``cell_amount``
     - ``(name, vol_du)``
     - ``(name, vol_du, stage_weight, AmountKind)``
   * - ``AmountKind``
     - none
     - ``{flux_correction, cell_source, floor, fixer, diagnostic}``
   * - ``derived_amount``, ``derived_total``
     - none
     - ``(name, row, value, stage_weight, kind)``, ``(row, value)``
   * - ``count``, ``record_min``, ``flag_retry``
     - none
     - ``(name, n)``, ``(name, v)``, ``(cause, any)``
   * - ``post_split``
     - ``(dim, name, flux, weight, dt)``
     - unchanged signature; now never scaled by later ``w1``
   * - ``monitor()``
     - none
     - ``RegisterMonitor& monitor()``
   * - ``RegisterRequest``
     - ``{keep, step_field}``
     - ``{row_names, derived, keep, counters, retry, step_field}``
   * - ``RegisterMonitor``
     - ``amounts, boundary, domain_total, counters, retry_flags``
     - ``+ rollback, row_names, amount_names, kind, counter_names,
       minima``; ``counters`` int64; ``retry_flags`` int32;
       ``boundary`` area-integrated; ``domain_total`` fluid cells
   * - ``Fixer::apply``
     - ``(u, sums, dt, stage_weight, reg)``
     - unchanged; ``stage_weight`` is the combined stage's ``w2``, posts
       ``cell_amount(..., 1.0, AmountKind::fixer)``
   * - parts
     - none named
     - ``riemann.central@2/@3``, ``riemann.pstar`` (companion),
       ``pressure_base1@1`` (split path), ``vic.mass_total@1``,
       ``vic.mass_dry@1``, ``vic.momentum_t@1``, ``covariance.dry@2/@3``,
       ``mass.dry.limited@1/@2/@3`` (scalars); no x1 Riemann-only row
   * - stage skeleton
     - ``Sweep`` class
     - C's free functions; ``HydroStage::covariance``,
       ``after_combine``; ``StageInputs::weight``

**Changes in revision 1.2** (from ``e0e9adee``, kept for the record).
Matrix rows 41-54.

* Lane C's sweep is two free functions, ``reconstruct_faces`` and
  ``solve_faces`` (C ``sweep.hpp:21-26`` at ``2d6aef4d``). R's stage no
  longer declares a ``Sweep`` class.
* The #289 covariance is R's: its code is in R's file
  (``hydro_forward.cpp:41-289``), and C rev 5 calls it another lane's post
  (``C.rst:776``). R posts it with ``add(d, "covariance", ...)``.
* Panel seams follow lane S rev 1 (``fe1612b1``) row 16r: the lower-rank
  block's copy, with momentum rotated by coord. Header: ``SeamRule::owner_copy``.
* Decisions from the home thread are adopted:

  * ``vic.momentum_t@1`` is a kept per-face part;
  * the monitor tracks AAM by named source, posted by A with
    ``cell_amount``;
  * x2/x3 momentum is in the panel face basis;
  * FP32 on CUDA uses FP32 parts and FP64 step accumulation, and MPS has its
    own contract (section 6).

* (Rev 1.2 flagged A's 169 booked lines; ruling V3-1 settles them for R,
  see revision 2.)
* New D7: ``hydro.cpp:344-377`` (``_x1_ghost_rows``, 34 lines), which S's
  transport takes (S section 9). S accepted it at rev 1.1.

**Changes in revision 1.1** (from ``1bc247f9``), after Zoey's notes (7
agree, 1 conflict, 8 request), Xinyue's notes (6/3/9), the program
manager's eight additions, lane C rev 5 (``2d6aef4d``), lane I rev 2
(``c6f9d957``), lane A rev 2 (``b6a40897``) and lane S's exchange table
(``48b2328d``). The numbered matrix is section 4.4.

* Units citation corrected. The pin forms area-integrated rates,
  ``Phi = A F1 + M/dt`` (``:1641``, ``:1646``), not per-area posts.
* Frame defined as the output of coord's ``flux2global<d>_``
  (``src/coord/coordinate.hpp:353-361``).
* Stage weights have one owner: X's ``begin_stage(stage, w)``. ``reset()``
  no longer takes a stage table. ``end_stage`` runs the integrator's own
  recursion (section 3.4).
* New in the header: ``boundary.prescribed`` (``set_prescribed``,
  ``apply_prescribed``), ``replace`` with own and peer entries and a
  ``SeamRule``, ``part_slot``, ``count``, ``RegisterMonitor::reset_step``
  and ``rollback``, ``RegisterPhase::after_combine``, the counters list.
* No x1 Riemann-only row. ``bflux1`` belongs to ``gravity-work: cell``,
  which Cheng removed (``I.rst`` rev 2, rulings (a), (b)).
* ``cen2`` citation: ``_flux2 - cen2`` is read at ``:1358-1359``.
* Deletions recounted (section 9): gravity work 217, of which the fixer
  and cell form are lane I's 133 exactly; total 1,269.


1. Scope and pins
-----------------

**Files (baseline 3,493 lines, measured).** ``hydro_forward.cpp`` 1,698;
``hydro.cpp`` 971; ``hydro.hpp`` 490; ``hydro_options.cpp`` 201;
``register_forcing_modules.cpp`` 85; ``x1_mass_covariance.hpp`` 48.
1,698 + 971 + 490 + 201 + 85 + 48 = 3,493. The set is inferred: it is the
part of ``src/hydro`` that no other lane claims (C: reference, dispatch and
balance files; EF: ``flux_positivity.*``; I: ``gravity_work*.hpp``). I have
not seen the study plan's list. Ceiling: 3,493 x 0.8 = 2,794.4, so
**2,794**, the register included.

**Owned by lane R.** The ``FluxRegister`` class and its ``RegisterMonitor``.
The seam rule (lane S moves the peer entry) and the ``boundary.prescribed``
rule (lane S supplies the mask and values). The stage order. The
``dynamics/*`` keys that stay in Hydro.

**Read, owned elsewhere (heads read through the GitHub API).**

* C rev 5.1: happysky19 ``v3-design/C``
  ``ab14e5a7cd021387d6422de6cc36d9514e12a8cb``;
* X rev 2: UCzhangxi ``v3-design/X`` ``034ef405dd3e0385493dc8fab9fcf1e03482db13``
  (read for rev 2.1: sections 3, 4, 11; ``stage_executor.hpp``,
  ``meshblock_parts.hpp``, ``pyharp_integrator.hpp``). It cites R at
  ``543ff84f``;
* A rev 3 part 1: JiachenLiu-Atmos ``v3-design/A``
  ``9ee837563561d0f21dc5cc34afeb03258e001290`` (it cites R at ``543ff84f``);
* O: JiachenLiu-Atmos ``v3-design/O`` ``c12f78bbfe131808274f1e338f40eafd04a860c8``
  (read for rev 2.1: sections 3.2, 4, and the R-O notes);
* I rev 2: XinyueWang05 ``v3-design/I``
  ``8c2ba2261a7c25821c64b58670af68c4d5907cbb``;
* S rev 1.1: XinyueWang05 ``v3-design/S``
  ``d03e48880dc28b33eca6c62ff6ad8ad162bdcdb2``;
* EF: zoeyzyhu ``v3-design/EF`` ``b58e12bb42133a3830f8f07f3aaf1cbb06663763``;
* K rev 1: UCzhangxi/kintera ``v3-design/K``
  ``f61d0d8069943bc71632be32d3224a2a782a5e29`` (``K.rst`` sections 3.5, 3.6,
  4, 11; ``chemistry_source.hpp``). It cites R at ``543ff84f``;
* pyharp ``src/integrator/integrator.hpp:19-29`` at main ``6bc01d53``.

**Inputs I could not read.** Linfeng's ``fd3d68a`` text, the 12:29 seven
questions, and the full text of three agree and two request notes of
Xinyue's (only her summary reached me). Section 4.4 marks them.


2. Concepts and current sites
-----------------------------

``HydroImpl::forward`` (``:370-1696``) is one 1,327-line function.

.. list-table::
   :header-rows: 1

   * - step
     - lines
     - what touches a face flux
   * - (1) primitives
     - ``:383-615``
     - conversion-order 4 (C's ``:417-504``)
   * - (2) x1 flux
     - ``:616-987``
     - riemann into ``_flux1`` (``:845``); ``bflux1`` (cell form,
       ``:846-849``); sedimentation in place (``:861-866``); x1 seam average,
       process seams only (``:868-946``; S row 9)
   * - (3.A/B) x2/x3 states
     - ``:988-1049``
     - face-state seam sync (``:1005-1048``; S rows 11-12); AAM full refusal
       (``:992-995``) and the ``central`` lambda (``:997-1003``)
   * - (4.A/B) x2/x3 flux
     - ``:1050-1153``
     - immersed-solid face states (``:1089-1090``, ``:1123-1124``);
       ``cen2``/``cen3`` (``:1108``, ``:1141``); riemann (``:1109``);
       covariance (``:1110``)
   * - (4.C) positivity
     - ``:1154-1252``
     - carry then scale, in place (``:1233-1237``)
   * - (5) divergence
     - ``:1254-1305``
     - divergence; AAM flux form (``:1288-1298``)
   * - (6) forcing
     - ``:1306-1552``
     - ``_aam_mass_flux`` (``:1354-1362``; ``_flux2 - cen2`` at
       ``:1358-1359``), cleared (``:1391``); gravity work rebuilds the x1
       mass row (``:1422-1425``)
   * - (7) implicit
     - ``:1554-1616``
     - ``dt_corr = w2_s dt`` for 3+ stages (``:1568-1583``)
   * - (8) x1 mass-flux w
     - ``:1624-1680``
     - ``Phi = A F1`` (``:1639-1641``) ``+ mc[IVZ]/dt`` (``:1646``): an
       area-integrated rate, mass per time
   * - fixer weight
     - ``:1682-1693``
     - ``w2_s prod_{t>s} w1_t`` (``:1685-1691``)

**Storage today.** ``_flux1/2/3`` and ``_face_pressure1`` are module buffers
(``hydro.cpp:248-271``). Each contributor rewrites them in place, so the pin
clones ``bflux1`` (``:847``), ``fadv`` (``:863``) and ``f1_pre``
(``:1230``), and calls the solver four extra times for ``central``
(``:1000-1001``).

**Seams today.** x1: the average runs only across process seams
(``:880-888``; a same-process seam is not averaged, ``:881``). It averages
``_flux1``, ``_face_pressure1``, ``bflux1`` and ``pressure_base1``
(``:903-919``), after sedimentation. x2/x3: both sides solve the same
exchanged face states (``:1005-1048``), so there is no flux average.

**Weights, resets, retry today.** The combine is ``u <- w0 u0 + w1 u + w2
du`` (``src/mesh/meshblock.cpp:901``). The stage-0 resets are
``meshblock.cpp:713-745``. The single host read is ``read_redo_flags``
(``meshblock.cpp:1565-1566``), fed by the stacked tensor at
``meshblock.cpp:1058-1061``. MPS has no FP64 there (``:1057``).


3. Target design
----------------

**3.1 Register.** One ``FluxRegister`` for the hydro rows, and one per
Scalar module for its rows. R owns the class; each module owns its
instance. Per active direction ``d`` it holds:

* the stage total ``T_d`` (``nvar`` rows, ``kFlux``), written in place;
* the requested parts (one row each, ``kFlux``) and companions
  (``riemann.pstar``, ``pressure_base1``, ``kGauge``);
* on request, the step field ``S_d`` (``kRegister``);
* the boundary sums: per row, FP64, area-weighted, the outward step
  transfer through the fluid domain's boundary faces (4.2 O, ``boundary(dim)``);
* the prescribed mask and values from lane S.

**3.2 Phases.** ``sweep`` < ``reconcile`` < ``limit`` < ``divergence`` <
``pre_implicit`` < ``implicit`` < ``post_implicit``, then ``end_stage``,
then, after X's RK combine, ``after_combine``. This is the pin's order;
nothing is reordered. The post-implicit source phase is ``post_implicit``,
as in A's ``SourcePhase::post_implicit``.

**3.3 Posts.** ``slot``/``post_slot`` for the first post (C's riemann);
``part_slot`` for a requested part written in place by the kernel (C's
``riemann.central``, ``riemann.pstar``; C rev 5 question R8: no copy);
``add`` for an increment (R's own #289 covariance, EF's sedimentation and carry,
I's ``vic.*``); ``scale`` for a multiply (EF's withhold); ``replace`` for a
shared face; ``apply_prescribed`` for walls and solids; ``keep`` for a
computed one-row part (I's ``vic.mass_total``, one row copied);
``cell_amount`` and ``count`` for the monitor.

``add`` acts on ``T_d`` in call order and is never fused or pre-summed.
That keeps the pin's ``E = (E - c_adv) - c_sed`` rounding
(``flux_positivity.cpp:154-159``). ``scale`` multiplies the rows in place,
as ``f.mul_(where(f > 0, th_lo, th_hi))`` does (``flux_positivity.cpp:99-121``).

**3.4 Step transfer.** ``begin_step()`` (X, step start) zeroes ``S_d``,
the boundary sums, the amounts, the counters, the minima and the retry
flags. Then the step-start ``post_split`` runs (the first radial half,
``meshblock.cpp:715``), before ``u0`` is saved (``meshblock.cpp:721``). So
it enters the step with its own weight, not scaled by any ``w1``, and goes
to a direct part of the sums. ``begin_stage(s, w)`` gives this stage's
weights. ``end_stage(dt)`` updates ``S <- w1_s S + w2_s dt T_s``. The
boundary sums and every amount follow the same recursion, ``A <- w1_s A +
sum_k (w_k a_k)``, where ``w_k`` is the ``stage_weight`` passed with each
amount: ``w2_s`` for an amount of this stage's ``du``, and 1.0 for a change
already applied to ``u``. Amounts posted after ``end_stage(s)``, in
``after_combine``, are scaled by the later stages' ``w1`` only, which is how
a change to ``u_s`` reaches the step's result. The final step sum is
``direct + sum_s w2_s prod_{t>s} w1_t (dt T_s)``, the weight at
``:1685-1691``. So no lane needs the whole stage table. **Hypothesis:** the
recursion and the product form differ only in FP64 rounding (gates G-R3,
G-R14).

**IMEX-ARK (X9), a note only since rev 2.2.** X rev 3 moves ARK out of this
round and the header declares no ARK weights. Were X9 accepted: at the step end, ``u = u0 + dt sum_i (bex_i
kex_i + bim_i kim_i)``, with ``kim_i = (u_i - rhs) / (gamma_i dt)``. X fills
``RegisterWeights`` as ``{1, bex_i, bim_i / gamma_i}``. Posts keep one unit,
per area per time at the step ``dt``:

* explicit posts enter ``S`` with ``bex_i dt``;
* the ``vic.*`` posts (``M_f / (A_f dt)``, made in phase ``implicit``)
  enter with ``(bim_i / gamma_i) dt``. That equals ``bim_i dt`` times the
  stage rate ``M_f / (A_f gamma_i dt)``.

In the Shu-Osher form ``explicit_w = implicit_w``, so one stage total
suffices. In the ARK form R keeps the x1 rows of the ``implicit`` posts as
a second x1 stage total, one x1 face field allocated only in that mode.
**Hypothesis**: the ARK weights and the amounts' ``after_combine``
semantics (no per-stage combine in ARK) are a proposal until Cheng accepts
X9 and X confirms ``bim_i / gamma_i``.

**3.5 boundary.prescribed.** Lane S gives, per direction, the mask of
physical wall faces and immersed-solid faces and the prescribed rows
(default: zero for mass, species, energy and scalars; normal momentum
keeps the solver's mirrored wall flux). Tangential momentum is free-slip:
no momentum row is prescribed (EF's decision, ``EF.rst`` section 4 at
``5e30b31b``, ``EF.rst:765-767``; S's ``PrescribedFaces``, ``seam_register.hpp:52-65`` at
``d03e4888``). S builds the mask per register instance with that instance's
``nvar`` and calls ``set_prescribed`` (``supply_prescribed``,
``seam_register.hpp:67-69``) on the hydro register and on each Scalar
module's register, whose mask sets every scalar row. That second call is a
request to S rev 2. R makes the call and the name is
``boundary.prescribed``; S's draft names it ``bc.solid_face``.
``apply_prescribed(d)`` runs after ``reconcile``, and
``apply_prescribed(1)`` runs again at the start of ``post_implicit``
(4.2 I), before any phase reads the total. The change it makes is booked as the named correction
``boundary.prescribed``. ``domain_total`` sums fluid cells only. EF's
``fix_vapor`` column break stays in EF. **Hypothesis:** at the pin the
solver already returns zero mass flux on these faces, from the reflected
states of ``pib->forward``, so the correction is round-off (gate G-R9). If
it is not, this is a declared result change.

**3.6 Hydro stage** (``hydro_stage.hpp``). ``HydroImpl::forward`` becomes a
driver that calls the lanes in phase order. It holds no flux buffer, no
fixer state and no AAM state.

**3.7 Requirement 9 (no added full-field copy per stage).** The register
adds the parts and step fields a reader requests, one row each, plus
``S_d`` only on request. It removes the ``bflux1``, ``fadv`` and
``f1_pre`` clones and the four central solves. Memory per kept row is
``nc3 nc2 nc1 b`` bytes per direction. That is the formula only; nothing
was profiled.


4. Flux-register contract
-------------------------

4.1 Contract answers, by topic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Units.** A post is a flux density per unit face area and time, at X's
   step ``dt``, before stage weights. The pin's ``Phi`` is an
   area-integrated rate (``:1641``, ``:1646``); a reader forms it as
   ``A_f total(1)``. ``vic.*`` posts ``M_f / (A_f dt)`` with the step
   ``dt``, never ``dt_corr`` (``:1568-1583``), as ``:1646`` divides
   ``mc`` by ``dt`` today. So no stage weight is applied twice.
2. **Frame.** The output of coord's ``flux2global<d>_``
   (``coordinate.hpp:353-361``): the one rotation, owned by coord (lane
   S), and the frame the divergence reads. On the cubed sphere that is
   lane S's panel basis, not a Cartesian one. The mass rows are
   frame-free.
3. **Weights and dtype.** ``T_d`` and parts: ``kFlux``. ``S_d``, boundary
   sums, amounts: FP64, FP32 on MPS (``meshblock.cpp:1057``). X owns the
   weights (section 3.4).
4. **Corrections.** ``add`` in order, ``scale`` in place, ``replace`` for
   shared faces, ``apply_prescribed`` for walls and solids. Kept parts are
   reconciled and prescribed but never scaled. A kept part is written in
   its stage's ``sweep`` (``riemann.central`` by C's kernel) and stays
   valid until the next ``begin_stage``; only ``replace`` and
   ``apply_prescribed`` change it meanwhile. A reads ``riemann.central`` in
   ``divergence`` and ``pre_implicit`` of the same stage (``A.rst:287-289``
   at ``2b0ac426``). The pin's own copy lives only inside the stage
   (``_aam_mass_flux``, set at ``:1356-1362``, cleared at ``:1391``).
5. **Reads.** ``total(d)`` at the caller's phase, ``kept()``,
   ``step_field()``, monitor views. No EOS call.
6. **Monitor.** One per register instance. Rows (``row_names()``), FP64
   amounts with an ``AmountKind``, area-integrated boundary sums,
   fluid-cell domain totals, int64 counters, FP64 minima and int32 retry
   flags, all on device (FP32 for the FP64 values on MPS, section 6). Only
   ``retry_flags()`` is read in X's step-end read (``X.rst:104``,
   ``:207-211`` at ``0fe47c6f``). O reads the amounts, boundary sums,
   domain totals, counters and minima in ``observe`` after the accept, and
   makes the sum over blocks and ranks and the host read in ``flush``
   (``O.rst`` 11.7 at ``dfa8ecd0``).
7. **Reset.** ``begin_step()`` zeroes the step and the monitor.
   ``FluxRegister::rollback()`` zeroes the register and calls
   ``RegisterMonitor::rollback()``; X's ``decide_retry`` calls it on every
   block. Nothing is written to restart.

4.2 Client answers
~~~~~~~~~~~~~~~~~~

**I (Xinyue, ``8c2ba226``).**

* Posts in ``implicit``, in this order: ``add(1, "vic.mass_dry", {IDN},
  f)``, ``add(1, "vic.mass_species", {ICY..}, f)``, ``add(1,
  "vic.momentum_t", {IVY, IVZ}, f)``.
* **Post-and-keep order, settled.**

  1. The three ``add`` calls. Each one also copies its summed rows into the
     requested part of the same name in the same call (``vic.mass_dry@1``,
     ``vic.momentum_t@1``), so no later call can reorder them.
  2. ``keep(1, "vic.mass_total", f)``.
  3. The ``cell_amount`` calls.
  4. The per-column status (4.5).

  ``post_implicit`` starts with ``apply_prescribed(1)`` on the total and on
  every x1 kept part. Only after it do A's m1, I's gravity-work remainder
  and the tracer transfer read.
* **The stage weight of ``cell_amount`` (I's R-4), settled.** The
  signature is ``cell_amount(name, V du, stage_weight, kind)``. For
  ``vic.cell`` I passes ``w2_s``, the ``w2`` of the ``w`` that X gave
  ``begin_stage``, because the amount is part of this stage's ``du``.
  ``end_stage`` then scales by the later ``w1_t``, so the step amount is
  ``c_s V du`` with ``c_s = w2_s prod_{t>s} w1_t`` (``:1685-1691``,
  section 3.4).
* **Kinds.**

  * ``vic.cell`` is ``cell_source``.
  * ``vic.mass_clamped`` is ``flux_correction``: the posted transfers are
    already the clamped ones, so its effect is inside ``boundary(1)``, and
    it is reported, not re-added. This is R's classification, and I to
    confirm, because ``I.rst`` calls it a floor amount.
  * ``vic.momentum_t.top`` is ``diagnostic`` (rev 2.1): it reports a face
    value of a posted transfer and changes no row.
* **How the scheme-9 top value survives ``boundary.prescribed``, settled.**
  ``vic.momentum_t`` is posted under scheme 9 as the bottom-up prefix sum,
  top face included, as I proposes (I's R-2). It survives
  ``apply_prescribed(1)`` in ``post_implicit`` for two reasons:

  * S's mask sets only the mass, species, energy and scalar rows, and
    leaves the momentum rows unset (``seam_register.hpp:52-60`` at
    ``d03e4888``);
  * I posts ``vic.momentum_t.top`` as an amount in ``implicit``, before
    ``post_implicit``, so the diagnostic never reads the prescribed total.

  EF chose free-slip (``EF.rst:765-767`` at ``5e30b31b``), so no
  momentum row is prescribed and the top face of ``vic.momentum_t`` is not
  zeroed. A confirms that ``.top`` does not enter the axial torque
  (``A.rst`` 11.2 (c) at ``2b0ac426``). Prescribing tangential momentum
  later would need A's and I's agreement.
* ``total(1)`` includes the vic posts after ``implicit``. The phase is
  ``post_implicit``. Energy as a face transfer stays a **hypothesis**
  (G-R7). ``retry_flags`` is in 4.5.

**O (Jiachen; R-O1 to R-O3 as carried by the program manager; O's head
``c12f78bb`` was not re-read).**

* **R-O1, ``row_names()``.** The conserved rows come first, in row order,
  from ``RegisterRequest::row_names``: Hydro's from its EOS, and a Scalar
  module's from its scalar names. The derived rows follow, from
  ``RegisterRequest::derived`` (hydro instance only). Who supplies what:

  * conserved rows of ``domain_total``: R, from the state over fluid
    cells;
  * ``e+pe``: I, with ``derived_total("e+pe", ...)`` from
    ``GravityWork::potential`` at step end, and its amounts by
    ``derived_amount``;
  * ``aam``: A, with the same two calls;
  * scalars: each Scalar module's own register instance and monitor (EF's
    Q-R-b).

  ``boundary(dim)`` covers the conserved rows. A derived row's owner posts
  its boundary transfer as ``derived_amount("<row>.boundary.<dim>", row,
  value, w, AmountKind::cell_source)``, inflow positive, so O's budget
  formula needs no special case. That convention is R's proposal; A and I
  to confirm.
* **R-O2.** ``counter_names()`` lists ``RegisterRequest::counters`` in
  order. ``counters()`` is int64 ``[ncounters]`` on device. ``minima()``
  is FP64, one entry per ``record_min`` name (EF's ``pos_min``).
* **R-O3, ``AmountKind``.** ``flux_correction`` is a face change already
  inside ``boundary``; it is reported, never added. ``cell_source``,
  ``floor`` and ``fixer`` are added. The budget is ``delta domain_total +
  sum_d boundary(d) - sum(amounts of kind cell_source, floor, fixer) =
  residual``.
* **``boundary(dim)``.** Area-integrated: the sum over the fluid domain's
  boundary faces of ``A_f S_d``, outward from the fluid positive, FP64 (FP32
  on MPS), in units of the row's conserved quantity. ``S_d`` already carries
  ``dt`` and the stage weights. It includes ``boundary.prescribed`` and
  ``post_split`` entries. **The face set (L-3, rev 2.4; S's and O's proposal,
  agreed):**

  * a block face whose S ``FaceKind`` (``exchange.hpp:17-25`` at
    ``d03e4888``) is ``wall``, ``outflow`` or ``custom``, when its interior
    cell is fluid. Never ``interior``, ``seam_x1``, ``panel`` or
    ``periodic``: those are shared faces whose two entries cancel over the
    blocks (``replace``). The pin's ``is_physical_boundary`` is true for
    any face with a bc function, the slab x1 periodic copy included
    (``meshblock_options.cpp:235-240``; ``S.rst:135-142``), so R reads S's
    ``FaceKind``, not that predicate;
  * every immersed-solid face with exactly one solid neighbour, outward
    from the fluid cell; a face between two solid cells is not counted;
  * all rows. On a wall or solid face the mass, species, energy and scalar
    rows are prescribed to zero (3.5), and the normal momentum keeps the
    mirror flux: the pin reflects only the normal velocity
    (``bc/internal_boundary.cpp:78-91``), and S's mask leaves the momentum
    rows unset (``seam_register.hpp:52-57`` at ``d03e4888``). That flux is
    the wall's pressure force. ``domain_total`` sums fluid cells only
    (3.5), so without the solid faces O's momentum identity
    (``O.rst:808``, ``:970`` at ``4afdbf37``) would not close on solid
    decks.

  R takes the block-face kinds through coord (``reset``,
  ``flux_register.hpp:43-44``; at the pin coord reaches its block's faces,
  ``coordinate.cpp:555-558``) and the solid
  side from the solid field its stage already gets
  (``StageInputs::solid``, ``hydro_stage.hpp:27``). The ``set_prescribed``
  mask marks a face when either neighbour is solid, so it cannot give the
  side. Both are inside R's own classes, so no ``flux_register.hpp``
  declaration changes; ``flux_register.hpp:97`` ("area-integrated,
  outward") stays.
* ``observe`` runs after accept and before the next ``begin_step()``.
* **Checked against O's text at ``c12f78bb``** (rev 2.1):

  * R-O1, R-O2 and R-O3 (``O.rst:695-704``) ask for exactly
    ``row_names()``, an int64 ``counter_names()``/``counters()``, an
    ``AmountKind kind(name)`` and an area-integrated ``boundary(dim)``. That
    is what rev 2 declares. The area is applied once, to ``step_field``
    only (``O.rst:668-675``).
  * O's budget rows (``mass``, ``species/<n>``, ``energy`` (E+PE),
    ``aam``, ``scalar/<n>``; ``O.rst:412-413``) are O's labels over R's
    rows: ``mass`` is the IDN row plus the species rows, ``energy`` is the
    derived ``e+pe`` row, and ``aam`` is the derived ``aam`` row.
  * O's fixer list (``O.rst:414-415``) has ``gravity_work``. Cheng's rulings
    (a) and (b) removed that fixer, so it has no poster. O's ``positivity``
    and ``vic_clamp`` are ``flux_correction`` in R: reported, not
    re-added. That matches O's own rule for flux-type fixers.
  * O says R resets at ``begin_stage(0)`` (``O.rst:690-691``). Since rev 2
    it is ``begin_step()``.

**EF (Zoey, ``b58e12bb``, Q-R-a to Q-R-i).** Q1-Q5 stand as in rev 1.2.

* **a.** Write calls:

  * ``count(name, n)`` adds into an int64 counter;
  * ``record_min(name, v)`` keeps an FP64 minimum;
  * ``flag_retry(cause, any)`` ORs into an int32 flag.

  The names are declared in ``RegisterRequest::counters`` and ``retry``.
  ``EfStatus``'s slots move to the monitor in R-1. Until then ``EfStatus``
  stays EF's device tensor in X's stacked read.
* **b.** Passive scalars are their own ``FluxRegister``: one per Scalar
  module, ``nvar`` = its scalars, with its own monitor.
* **c.** At the pin the scalars read ``phydro->flux<d>()`` after the hydro
  forward, when the IDN row is the post-reconcile one (positivity scales
  species only, and the carry writes IPR and momentum;
  ``flux_positivity.cpp:99-121``, ``:124-167``). In V3 the hydro
  ``total(1)`` also holds the vic posts by then. So the Scalar module
  requests ``mass.dry.limited@1/@2/@3``: a one-row part that the hydro
  register fills with ``total(d)[IDN]`` as ``limit`` ends.

  * R3 reads that part.
  * R4 is ``mass.dry.limited@d - covariance.dry@d``, the same operation as
    ``scalar.cpp:161`` (**hypothesis**: bitwise, because the operands are
    the same values).
* **d.** The theta sync is an exchange inside ``limit``. X splits ``limit``
  into the read, S's exchange (pack, host, unpack) and the posts. Any phase
  may hold an X exchange; ``reconcile`` is only the phase that owns
  ``replace``.
* **e.** ``cell_amount`` in ``after_combine`` passes ``stage_weight =
  1.0``: the change is already in ``u``. Later stages' ``w1`` still apply
  (section 3.4). ``vol_du`` is either a per-row field ``[nrows,
  cells...]``, already times the cell volume, which the register sums, or
  a summed ``(nrows,)``.
* **f.** Local floors and repairs are **not** ``Fixer`` subclasses. They
  post ``cell_amount(..., AmountKind::floor)`` directly. ``Fixer`` is for
  corrections that need a global collective; X's registry lists only
  those.
* **g.** ``factor`` is ``[faces...]``, broadcast over ``rows``, or
  ``[rows, faces...]``, per row.
* **h.** EF's names are adopted: ``sedimentation`` (a post);
  ``positivity.carry``, ``positivity.withhold``, ``scalar.upper_bound`` and
  ``scalar.positivity.withhold`` (``flux_correction``); ``eos.floor``,
  ``eos.borrow`` and ``eos.fix_vapor`` (``floor``).
* **i.** Open. R keeps the pin's behaviour: no second ``replace`` after the
  carry. The carry may be two-valued at internal x1 seams (**hypothesis**,
  as EF says), and the same holds at panel seams (S's K7). G-R2 is extended
  to the end of ``limit``. If it fails, S's second ``replace`` in
  ``limit`` is the fix (lanes X and EF).

**X and A.**

* **Step-start hook.** ``begin_step()`` is X's step-start call. It runs
  before the radial ``post_split``, so the stage-0 reset no longer erases
  it (pin: ``begin_step`` of diffusion at ``meshblock.cpp:715``, ``u0``
  saved at ``:721``).
* **``after_combine``.** ``RegisterPhase::after_combine``, run by X's hook
  after the combine (``meshblock.cpp:901``) and before boundaries. Its
  order at the pin, every stage: EF's conserved limiter F1 (``:907-909``,
  every stage when hydro has species or there are scalars, else the last
  only), the scalar combine (``:920-923``), S's solid fill when a solid
  field exists (``:936-938``), then A's closure (``:983-990``; with several
  blocks after all blocks, ``mesh.cpp:370-383``). On the last stage X's
  ``finish_step`` (``:903-905``) comes first, and, when thermo has
  reactions (``:950-951``), EF's F1b (``:952``) and K's saturation
  adjustment (``:954-972``) come after the solid fill and before A's
  closure. Naming the hook in X's schedule is X's (row 49).
* **``Fixer::apply``** receives ``stage_weight`` = ``w2`` of the stage just
  combined, passed by X. A's closure applies ``-w2 dt R`` with it, and
  posts its change with ``cell_amount(..., 1.0, AmountKind::fixer)``.
* **A's ``step_field`` request (rev 2.6): agreed.** A requests
  ``step_field = {1}``, and ``{1, 2, 3}`` on decks with immersed solids,
  so that ``aam.boundary.<d>`` follows the ``boundary(dim)`` face set of
  4.2 O (``A.rst:904-914`` at ``c405d491``); ``RegisterRequest::step_field``
  already takes the dims and ``step_field(dim)`` is a const read
  (``flux_register.hpp:38``, ``:84``), so no header change, and the added
  memory, ``nvar`` rows of one ``kRegister`` face field per added
  direction, allocated at ``reset()`` (3.1, 3.7), is a **hypothesis** until
  measured.
* ``begin_stage(stage, w)`` remains the only weight input. ``rollback`` is
  in X's reset list. Accumulation is FP64, FP32 on MPS.
* **Checked against X rev 2 at ``034ef405``** (rev 2.1):

  * X still cites R at ``543ff84f``: ``reset(..., weights, req)`` and
    ``begin_stage(int, StageWeights const&)`` (``X.rst`` section 4). Both
    are superseded. ``RegisterWeights`` answers X's ARK question in section
    11: yes, the implicit posts are their own increment (``vic.*``), weighted
    by ``implicit_w`` (section 3.4).
  * **Step start.** X has no ``begin_step`` hook. Its ``StepReset`` list
    runs "at stage 0" (``meshblock_parts.hpp``), which at the pin follows
    the radial ``begin_step`` (``meshblock.cpp:714-716`` before
    ``:722-738``). Request to X: R's ``StepReset`` entry ``"register"``
    calls ``begin_step()`` and must run **before** the step-start radial
    ``post_split``. Otherwise that post is erased.
  * **After combine.** X has no named hook. R reads it as R's op
    ``"hydro.after_combine"`` scheduled after X's ``"rk.combine"`` op in the
    same compute segment, with the fixers in X's ``GlobalCorrection``
    phase. Request to X: name it in the schedule. (Superseded: X's runner,
    rev 2.4.)
  * **Retry.** X's ``RetryFlag`` is a 0-d tensor per cause in one dtype.
    R's ``retry_flags()`` slots map one to one onto them.
* **Checked against X rev 3 at ``100bc9b3``** (rev 2.2):

  * X cites R at ``3490d7e1``. ``begin_stage(int, harp::IntegratorWeight
    const&)`` (``X.rst:141-146``) now matches R's header again
    (``flux_register.hpp:49`` at rev 2.2).
  * Reset: X's ``ResetPhase {kStepStart, kStageZero, kRollback}`` and
    ``StageExecutor::step_start(dt)`` (``meshblock_parts.hpp``,
    ``stage_executor.hpp`` at ``100bc9b3``) run the register's step zeroing
    first in ``kStepStart``, then the radial ``post_split``; ``rollback()``
    is a ``kRollback`` entry; a retry reruns ``step_start``. That is R's
    ``begin_step()`` (``flux_register.hpp:48``). Request: rename X's
    ``reset_step`` to ``begin_step``.
  * ``Fixer::apply`` gets that stage's ``w2`` (``meshblock_parts.hpp``,
    ``GlobalCorrection``; ``X.rst:162-167``), as R states
    (``flux_register.hpp:105-116``).
  * **after_combine, closed (rev 2.4).** X rev 3.9 (``00dee910``) enters
    ``RegisterPhase::after_combine`` after **every** stage's combine, after
    ``finish_step`` on the last, with one runner,
    ``StageExecutor::after_combine(int stage, double dt)``
    (``stage_executor.hpp:80-81``, ``X.rst:1285-1293``), in the order above.
    R has no ``after_combine`` op: ``HydroStage::after_combine(u, reg)`` is
    removed at skeleton rev 4.3 (``97c62312``). Amounts posted there carry
    their ``stage_weight`` and are scaled by later ``w1`` (3.4).
  * Amounts: X sums R's FP64 amounts over blocks and ranks after the
    accept (``X.rst:104``, ``:160-161``); O says it sums in ``flush``
    (``O.rst`` at ``c12f78bb``). One of them, not both: X and O to agree.

* **Checked against A rev 3 part 1 at ``9ee83756``** (rev 2.1):

  * A cites R at ``543ff84f``. Its R-6 contract is ``stage_weight = w2_s``
    for ``Fixer::apply`` (``A.rst:339-346``), which rev 2 states.
  * A posts ``aam.closure`` and ``aam.x1_wall`` with ``cell_amount``
    (``A.rst:337``, ``:556``). Request: the momentum-row change stays a
    ``cell_amount`` (weight 1.0, ``fixer``). The AAM values go on the
    derived row with ``derived_amount(name, "aam", ...)``. ``aam.x1_wall``
    is the name for rev 2's ``"<row>.boundary.<dim>"`` convention
    (``cell_source``, inflow positive).
  * V3-1 is the same in A (``A.rst:783-792``): R counts 136 + 33 less
    ``:988``, and 25 + 15 stay in R's "after".

**S (Xinyue, ``d03e4888``).**

* **The prescribed mask has a row dimension**: bool ``[nvar, faces...]``,
  with value ``[nvar, faces...]`` (``seam_register.hpp:59-60``). That is
  settled in the header.
* **Transposed panel edges (Xi's note 11, as lane S quoted it in the home
  thread; read at the pin, a proposal until S rev 2).** Of the 12 panel
  edges only 6 are identity:

  * 1B-5R and 3L-4T swap x2/x3 and reverse along the edge;
  * 1T-3R and 4B-5L swap x2/x3 and negate the normal;
  * 2B-5B and 2T-3T reverse along the edge and negate the normal.

  So a raw copy of mass, energy, species and scalars is wrong on the
  non-identity edges, and with an O(1) sign error where the normal is
  negated. Momentum also needs the rotation. R's rule: ``replace``'s
  ``peer`` is S's slab **already mapped** into this block's face dim, face
  order along the edge, outward normal sign (every flux row times -1 where
  the normals are opposite) and covariant basis (momentum through
  ``PanelRotation::panel_to_panel_rows_``). ``owner_copy`` then copies the
  mapped slab. The API is unchanged. The amount ``reconcile.panel`` is
  ``sum A_f (mapped peer - own)`` per row, computed after the mapping, with
  kind ``flux_correction``. S rev 2 (18:00 EST) declares the per-row edge
  map, with gates on 2T-3T, 1T-3R and 3L-4T and a test over all 24 sides.
  G-R13 uses those edges. The request for ``peer_dim``/``normal_sign`` in
  ``SeamEntry`` stands.
* D7 is accepted unconditionally (S.rst at ``d03e4888``, section 9).
* K6 is settled by S rev 1.1: every x1 seam, process or same-process, takes
  ``replace(1, ..., SeamRule::mean)``.
* S counts no hydro deletions (S.rst section 9). See 9 for R-C2.

**C (Tianhao, ``ab14e5a7``).**

* The sweep is C's two free functions, with no ``Sweep`` class. The #289
  covariance is R's (``C.rst:44-46``). ``riemann.mass@1`` is dropped
  (``C.rst:47-49``).
* **R-C1** (``C.rst:1798-1817`` at ``559dd0b7``). **Closed (rev 2.3,
  RULING V3-3).** C's ``solve_faces`` runs ``FaceFloor``, the solid step,
  ``before_solve(faces, d)``, then the rotation and the Riemann solve into
  ``slot(d, "riemann")`` (``sweep.hpp:23-28`` at ``559dd0b7``; ``FaceHook``
  is ``std::function<void(FaceStates const&, int)>``). R's
  ``build_covariance(faces, d)`` runs in that hook and builds the #289
  increment from the post-solid, unrotated states into a fixed
  per-direction buffer (the pin's ``dcov``). ``post_covariance(d, reg)``
  runs after the solve and calls ``add(d, "covariance", ...)``, so nothing
  is posted before C's ``riemann`` slot. This is the pin's order: ``wlr2``
  after ``pib->forward`` (``:1089-1090``), ``dcov`` built (``:1099-1100``),
  the solve (``:1109``), then ``add_cov`` (``:1110``). No face-state copy
  is added for the hydro covariance. S's ``prim2local_``/``flux2global_``
  stay functions the solver calls, "unchanged in V3"
  (``coord_rotation.hpp:37-40``, ``S.rst:118-122`` at ``d03e4888``), so S
  has no ordering of its own here. The pin's scalar covariance rows keep
  their own clones of the seam rows (``_cov_wl``/``_cov_wr``,
  ``:1103-1106``, ``:1136-1139``); this ruling does not change them.
* **R-C2** (``C.rst:1718-1723``). Resolved: ``hydro.cpp:727-776`` is
  counted once, in R's D1. C counts no deletion of it, and neither does S
  (S.rst section 9, last paragraph). Request to S: relabel "C's 50" as R's
  D1.
* **R-C3** (``C.rst:1724-1728``). Adopted: ``part_slot(1,
  "pressure_base1")``, written by C's ``WellBalancedX1``. It is requested
  as ``pressure_base1@1`` on the split path only, and reconciled by
  ``replace`` as a companion.
* **Counter names.** C's five are adopted: ``face_floor.rho``,
  ``face_floor.p``, ``face_floor.species``, ``riemann.pstar_clamp`` and
  ``riemann.llf`` (``C.rst:1086-1088``).
* **R-C4, closed.** C's face-state floors change face states, not cells,
  and post ``count()`` only (``C.rst:898-901``, ``:1818-1822`` at
  ``559dd0b7``). ``AmountKind::floor`` names EF only (``:28``). A face floor
  books no ``cell_amount``.
* **Moved citations.** Rev 1.2 cited ``C.rst:776`` and ``:978-981`` at
  ``2d6aef4d``. At ``ab14e5a7`` those statements are revised, and the
  citations above are at ``ab14e5a7``.

**K (Xi, UCzhangxi/kintera ``f61d0d80``, ``K.rst`` section 4).**

* **Phase:** ``after_combine`` on the last stage, when thermo has
  reactions (``meshblock.cpp:950-951``). That is after S's solid fill
  (``:936-938``) and EF's F1b (``:952``), before A's closure (``:983-990``)
  and X's step-end read (``K.rst`` section 4, "Ordering").

  * The saturation adjustment is in ``src`` at the pin
    (``meshblock.cpp:949-981``; species rows written at ``:972``).
  * The chemistry step exists at the pin only in an example driver
    (``examples/run_hydro.cpp:171-198``, per ``K.rst`` 3.6). It follows the
    saturation adjustment, in its own eager FP64 segment.
* **Names (K's question, adopted):**

  * ``thermo.saturation``: ``cell_source`` on the species rows;
  * ``chem.species``: ``cell_source``, ``del_rho`` per species row;
  * ``chem.energy``: ``cell_source`` on the energy row, zero today;
  * ``chem.elements``: ``diagnostic``. Its rows are elements, not conserved
    variables, so K declares them as derived rows ``element/<name>`` in
    ``RegisterRequest::derived`` and posts with ``derived_amount``. That
    answers K's question whether an amount may have element rows.
* **Volume weight:** ``vol_du`` is the row change times ``cell_volume`` over
  the interior cells (the ``part`` the pin uses, ``meshblock.cpp:967-968``),
  zero on rows not changed. ``stage_weight`` is 1.0, because the change is
  applied to ``u``. K's text calls ``cell_amount(name, vol_du)`` at
  ``543ff84f``; the rev 2 signature adds ``(1.0, kind)``.
* **Failures:** K writes slot 4 of X's retry stack; R's ``flag_retry`` is
  not used (``K.rst:206-212`` at ``fc619eec``).
* **Counters:** ``thermo.temp_solve`` and ``thermo.pres_solve``, declared in
  ``RegisterRequest::counters`` and posted once per step with
  ``count(name, failures()[1])`` and ``count(name, failures()[2])`` in the
  last ``after_combine`` (``K.rst:212-217`` at ``fc619eec``). They are not
  retry causes.

4.3 Conflicts
~~~~~~~~~~~~~

* **K1, positivity form.** Resolved: ``scale()`` (C rev 5).
* **K2, weights.** Resolved: ``begin_stage(stage, w)``, the recursion of
  3.4 and ``cell_amount``'s ``stage_weight``.
* **K3, namespace.** Resolved: ``snap``.
* **K4, "post-terrain".** Resolved: post-solid states (``:1089-1090``),
  confirmed by A (``A.rst`` 11.2 (a) at ``2b0ac426``).
* **K5, cell increments.** Resolved: monitor amounts only.
* **K6, same-process x1 seams.** Resolved by S rev 1.1 (``mean`` on every
  x1 seam). G-R10 measures the change.
* **K7, the carry's momentum frame.** Still flagged: G-R12, and S's K7
  paragraph.

4.4 Resolution matrix
~~~~~~~~~~~~~~~~~~~~~

Z = Zoey's notes on ``543ff84f`` (line numbers there), X = Xinyue's, P =
the program manager's eight additions, C = lane C rev 5, I = lane I rev 2.

.. list-table::
   :header-rows: 1
   :widths: 5 12 43 40

   * - #
     - note
     - point
     - resolution (rev 1.1)
   * - 1
     - Z agree
     - units fit the sedimentation post
     - kept
   * - 2
     - Z agree
     - no per-face read by kind; EF keeps its settling buffer
     - kept
   * - 3
     - Z agree
     - ``scale()`` over ``(theta-1)F``
     - kept; C rev 5 agrees (K1)
   * - 4
     - Z agree
     - stage weights ``c_s``
     - kept; computed by the recursion (3.4)
   * - 5
     - Z agree
     - the 108 lines
     - kept (D2)
   * - 6
     - Z agree
     - no EOS call
     - kept
   * - 7
     - Z agree
     - namespace
     - ``snap`` (K3)
   * - 8
     - Z conflict
     - ``Phi`` is area-integrated, mass per time
     - fixed: answer 1, header item 1
   * - 9
     - Z request
     - name x1 upwind (``bflux1``) and x2/x3 central apart
     - x2/x3 ``riemann.central@2/@3``; no x1 row (cell form removed)
   * - 10
     - Z request
     - carry adds never pre-summed
     - stated (3.3)
   * - 11
     - Z request
     - exact scope of ``replace``
     - stated (section 2, 4.2 S): ``T_1`` (sedimentation inside),
       ``riemann.pstar``, ``pressure_base1``; process seams; K6
   * - 12
     - Z request
     - counter slots for EF's 12
     - ``count`` and ``RegisterRequest::counters``
   * - 13
     - Z request
     - step-end phase for fixers
     - ``after_combine``
   * - 14
     - Z request
     - scalar register instance
     - one per Scalar module (3.1)
   * - 15
     - Z request
     - solid rule, fluid-only totals
     - ``boundary.prescribed`` (3.5)
   * - 16
     - Z request
     - frame of the carry's momentum rows
     - flagged K7, gate G-R12
   * - 17
     - X conflict
     - vic citation per area vs ``kg/s``
     - fixed: answer 1
   * - 18
     - X conflict
     - FP64 on MPS
     - FP32 on MPS (answer 3)
   * - 19
     - X conflict
     - "global components" vs S's panel basis
     - ``flux2global<d>_`` output (answer 2)
   * - 20
     - X request
     - which ``dt`` vic divides by
     - step ``dt``, never ``dt_corr``
   * - 21
     - X request
     - Coriolis/metric read the register
     - ``A_f total(1)`` in ``post_implicit`` replaces ``:1636-1646``
       (G-R11; in I-4 since 2026-11-19)
   * - 22
     - X request
     - solid-faces rule
     - ``boundary.prescribed``
   * - 23
     - X request
     - ``replace`` with own and peer entries; same-process seams
     - two entries plus ``SeamRule``; K6
   * - 24
     - X request
     - ``retry_flags`` after the per-column retry
     - OR of the still-failing columns (4.2 I)
   * - 25
     - X request
     - a requirement-9 slot
     - 3.7
   * - 26
     - X request
     - drop the ``bflux1`` rationale
     - dropped
   * - 27
     - X agree (3)
     - ``post_implicit`` placement; gravity work after limiting; no fixer
       slot
     - kept
   * - 28
     - X (5 notes)
     - three agree and two request notes not visible to me
     - **open**: to be checked against Xinyue's text
   * - 29
     - P
     - monitor reset/rollback member
     - ``rollback``; ``begin_step`` (rev 2; ``reset_step`` removed)
   * - 30
     - P
     - one owner for the stage weights
     - ``begin_stage`` only
   * - 31
     - P
     - O's area weighting, single increments
     - 4.2 O
   * - 32
     - P
     - A's total vs anomaly
     - totals
   * - 33
     - P
     - 236 and AAM 15 vs 47
     - section 9
   * - 34
     - P
     - vic energy transfer
     - hypothesis, G-R7
   * - 35
     - P
     - solid-face rule
     - ``boundary.prescribed``
   * - 36
     - P
     - ``cen2`` at ``:1358``
     - fixed: ``:1358-1359``
   * - 37
     - C R8-R12
     - part slots, ``riemann.mass``, counters, ``pressure_base1``,
       namespace
     - 4.2 C
   * - 38
     - I R-1..R-3
     - ``vic.mass_dry@1``, ``momentum_t.top``, dim numbers
     - accepted (4.2 I)
   * - 39
     - A R-1, R-3
     - post-terrain; AAM budget row
     - K4; derived row (4.2 A)
   * - 40
     - A rev 2 s9
     - AAM lines in A's and R's tables
     - V3-1: R's (section 9)
   * - 41
     - C rev 5
     - ``Sweep`` class vs free functions
     - C's ``reconstruct_faces``/``solve_faces``; stage header fixed
   * - 42
     - C rev 5
     - covariance named another lane's (``C.rst:776``)
     - R owns #289 (``:41-289``); ``add(d, "covariance")``
   * - 43
     - C rev 5
     - ``riemann.mass@1`` for the cell form
     - not needed; request C to drop it
   * - 44
     - A rev 2
     - 169 AAM lines in R's files booked to A
     - V3-1: all of D4 is R's
   * - 45
     - S rev 1
     - panel seam row 16r
     - ``SeamRule::owner_copy``
   * - 46
     - S rev 1
     - ``bc.solid_face`` by ``add`` vs ``boundary.prescribed``
     - R calls ``apply_prescribed``; name ``boundary.prescribed``; S renames
   * - 47
     - S rev 1
     - same-process x1 seams
     - settled by S rev 1.1 (``mean`` on every x1 seam)
   * - 48
     - S rev 1
     - replaced amount as a monitor name
     - ``reconcile.x1``, ``reconcile.panel``
   * - 49
     - X
     - ``after_combine`` in X's schedule
     - **open**: X's segment list (``X.rst`` section 3 at ``77c65d5a``)
       has the combine, limiter and global fixer segments but no named hook
   * - 50
     - P (thread)
     - ``vic.momentum_t@1`` per face
     - kept part
   * - 51
     - P (thread)
     - AAM by named source
     - monitor named sources; A posts by ``cell_amount``
   * - 52
     - P (thread)
     - CUDA FP32 parts, MPS contract
     - section 6
   * - 53
     - S rev 1 s9
     - ``hydro.cpp:344-377`` to S's transport
     - D7, accepted by S at ``d03e4888``
   * - 54
     - X (Xinyue)
     - notes whose text I never had
     - **open**: 3 of her 6 agree notes and 2 of her 9 requests; I have
       only the topics of the other 13
   * - 55
     - Cheng V3-1
     - deletions by file owner; D4 all R's; ``:988`` stays
     - section 9; K8 removed
   * - 56
     - program manager
     - header freeze, change list since ``543ff84f``
     - revision 2 table above
   * - 57
     - I R-4
     - ``c_s`` on ``cell_amount``
     - ``stage_weight`` argument; recursion (3.4)
   * - 58
     - I
     - post-and-keep order
     - 4.2 I: adds, keep, amounts, status
   * - 59
     - I R-2
     - scheme-9 top value vs ``boundary.prescribed``
     - momentum rows unmasked; ``.top`` posted in ``implicit``
   * - 60
     - O R-O1
     - ``row_names()``; E+PE, AAM, scalar rows
     - ``row_names``, ``derived_total``, ``derived_amount``
   * - 61
     - O R-O2
     - ``counter_names()``; counter dtype
     - int64 counters; FP64 ``minima()``
   * - 62
     - O R-O3
     - flux correction vs cell source
     - ``AmountKind``
   * - 63
     - O
     - ``boundary(dim)`` area-integrated?
     - yes; outward, FP64
   * - 64
     - EF Q-R-a
     - counter and retry write call
     - ``count``, ``record_min``, ``flag_retry``
   * - 65
     - EF Q-R-b
     - scalar register instance
     - one per Scalar module
   * - 66
     - EF Q-R-c
     - phase of the scalars' hydro total
     - ``mass.dry.limited@d`` at the end of ``limit``
   * - 67
     - EF Q-R-d
     - theta sync phase
     - an exchange inside ``limit``
   * - 68
     - EF Q-R-e
     - ``cell_amount`` after the combine
     - weight 1.0; field or ``(nrows,)``
   * - 69
     - EF Q-R-f
     - local floors as ``Fixer``
     - no: ``AmountKind::floor``
   * - 70
     - EF Q-R-g, h
     - factor shape; post names
     - 4.2 EF
   * - 71
     - EF Q-R-i
     - carry at internal seams
     - **open**; G-R2 extended
   * - 72
     - X, A
     - step-start hook for ``post_split``
     - ``begin_step()``
   * - 73
     - X, A
     - ``after_combine`` hook
     - phase; X's ``StageExecutor::after_combine(stage, dt)`` runs it
       (``HydroStage::after_combine`` removed, rev 2.4)
   * - 74
     - X, A
     - ``w2`` to ``Fixer::apply``
     - ``stage_weight`` = combined stage's ``w2``
   * - 75
     - S
     - prescribed mask row dimension
     - ``[nvar, faces...]``
   * - 76
     - S (Xi note 11)
     - transposed panel edges
     - ``peer`` mapped by S; G-R13; request ``peer_dim``, ``normal_sign``
   * - 77
     - C R-C1
     - covariance face states
     - post-solid, unrotated; closed by V3-3 (rev 2.3)
   * - 78
     - C R-C2
     - 50 lines at ``hydro.cpp:727-776``
     - once, in R's D1
   * - 79
     - C R-C3
     - ``pressure_base1`` poster
     - ``part_slot(1, "pressure_base1")`` by C
   * - 80
     - K
     - chemistry phase and weighting
     - superseded by rows 90-91
   * - 81
     - X rev 2
     - two tableaux vs R's weights
     - superseded by row 97 (rev 2.2)
   * - 82
     - X rev 2 s11
     - implicit fluxes as their own increment
     - yes: ``vic.*`` with ``implicit_w``
   * - 83
     - X rev 2
     - stale R citation (``543ff84f``)
     - request to X
   * - 84
     - X
     - ``StepReset`` order vs radial ``post_split``
     - request: ``register`` before the split
   * - 85
     - X
     - ``after_combine`` hook
     - R op after ``rk.combine``; X names it
   * - 86
     - X
     - ``RetryFlag`` per cause
     - one to one with ``retry_flags()`` slots
   * - 87
     - O ``c12f78bb``
     - R-O1 to R-O3 as written
     - match rev 2
   * - 88
     - O
     - ``gravity_work`` fixer row
     - no poster (removed by rulings (a), (b))
   * - 89
     - O
     - reset at ``begin_stage(0)``
     - ``begin_step()``
   * - 90
     - K ``f61d0d80``
     - names; element rows
     - adopted; ``element/<name>`` derived rows, ``diagnostic``
   * - 91
     - K
     - phase and volume weight
     - ``after_combine``, last stage; interior ``cell_volume``; 1.0
   * - 92
     - A rev 3
     - R-6 ``stage_weight``
     - ``w2_s`` (as rev 2)
   * - 93
     - A rev 3
     - AAM amounts via ``cell_amount``
     - AAM on derived row ``aam`` via ``derived_amount``
   * - 94
     - S/Xi note 11
     - transposed panel edges
     - S maps the slab; ``reconcile.panel`` after mapping
   * - 95
     - C R-C1 vs S
     - unrotated states need in-kernel rotation
     - closed by V3-3: C's ``before_solve`` hook, R posts after the solve
   * - 96
     - R
     - rev 2's K section wrong
     - corrected (rev 2.1)
   * - 97
     - X rev 3
     - ``begin_stage`` argument
     - ``harp::IntegratorWeight`` again; ``RegisterWeights`` removed
   * - 98
     - X rev 3
     - ``reset_step`` from ``kStepStart``
     - yes; R's name is ``begin_step()``
   * - 99
     - X rev 3
     - ``Fixer::apply`` stage ``w2``
     - matches
   * - 100
     - X rev 3
     - ``after_combine`` last stage only
     - **open**: R enters it after each combine
   * - 101
     - X rev 3
     - ARK out of scope
     - R declares no ARK weights; 3.4 note
   * - 102
     - X / O
     - who sums the amounts over blocks
     - **open**: X or O, not both
   * - 103
     - X rev 3.9
     - ``after_combine`` caller, stage argument
     - X's runner; R's op removed (rev 2.4)
   * - 104
     - S / O L-3
     - faces in ``boundary(dim)``
     - ``wall``, ``outflow``, ``custom``, fluid-side solid faces; all rows


4.5 retry_flags (lane I's proposal (c))
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``retry_flags()`` is int32, one 0/1 slot per cause named in
``RegisterRequest::retry``, set on device by ``flag_retry(cause, any)``
(an OR). It is read once in X's stacked step-end read
(``meshblock.cpp:1058-1061``, ``:1565-1566``). X's ``decide_retry`` redoes
the step if any slot is set, as today.

Causes: ``implicit.column`` (I), and EF's four, ``ef.floor_patch``,
``ef.nan``, ``ef.vapor_fail`` and ``ef.heat_capacity`` (``EF.rst`` section
4, ``:677-678`` at ``5e30b31b``; today the limiter marks ``meshblock.cpp:1052-1056`` and
slots 6 and 7, ``:1571-1577``). Lane X maps each name to a cause bit
(``X.rst:200-206`` at ``0fe47c6f`` still names ``eos.limiter_mark``). K's
failures stay slot 4 of X's stack (4.2 K).

Written on lane I's proposal (c), accepted by Cheng at 22:20 EST
2026-11-17 (``I.rst`` section 10(c) at ``8c2ba226``). The FP32 solve fails
per column. Only the failed columns are retried in FP64, inside the stage.
``implicit.column``
is set only if a column also fails in FP64.

**Transition (I-5, rulings of 2026-11-19; ``I.rst`` rev 2.6 section 10).**
I-5 declares ``implicit.column`` in the hydro register's
``RegisterRequest::retry`` and flags it with the OR of lane I's
``col_status``. Until I-6, that is the OR after the whole-block FP64
fallback (``hydro.cpp:536-541`` at I-4), the meaning of the pin's latch.
``picorr->solve_failed_tensor()`` is the same OR on the device, so slot 5
of X's stacked read is unchanged until a lane X step, which lane X names,
reads ``retry_flags()`` in its place; I-5 does not make that switch.

**I-6 (lane R's rulings of 2026-11-19; I-6 is not merged).** When I-6
makes the FP64 retry per column, two rules hold:

1. Lane I's ``fp64_fallbacks`` buffer and the register's
   ``implicit.fp64_columns`` counter both count the retried columns, so
   they agree.
2. ``implicit.column`` flags each column whose last solve failed: for a
   retried column, its FP64 solve. ``solve_failed_tensor()`` follows that
   result, so slot 5 keeps its meaning until lane X switches it.

.. list-table:: What changes
   :header-rows: 1
   :widths: 25 37 38

   * - item
     - pin
     - rev 2 on proposal (c)
   * - FP32 solve failure
     - the whole block re-solves in FP64 (``I.rst`` 10(c))
     - only the failed columns re-solve; the other columns keep FP32. That
       is a result change beyond round-off in steps with a failing column
       (``I.rst`` 10(c); size a **hypothesis**)
   * - redo trigger
     - ``picorr->solve_failed_tensor`` in the stacked read
       (``meshblock.cpp:1053-1054``)
     - ``flag_retry("implicit.column", ...)``, same meaning: the FP64
       solve also failed
   * - host reads
     - one step-end read
     - one step-end read (unchanged)
   * - ``fp64_fallbacks`` meter
     - counts blocks
     - ``count("implicit.fp64_columns", n)`` counts the retried columns,
       as does ``fp64_fallbacks`` (I-6 rule 1 above)
   * - Cheng's ruling
     -
     - (c) accepted, 22:20 EST: row 1 stands. ``flag_retry`` with cause
       ``implicit.column`` stays as written, per column; no header change.


5. Invariants and gates
-----------------------

None of these has run. Each says how it would be checked.

.. list-table::
   :header-rows: 1

   * - id
     - invariant
     - check
     - tolerance
   * - G-R1
     - posts reproduce the pin's in-place ``_flux1/2/3`` after each phase
     - debug compare against a main build, decks in ``tests/``
     - bitwise (EF settling part excepted)
   * - G-R2
     - shared faces single-valued after ``reconcile`` (and, for EF's
       Q-R-i, after ``limit``)
     - own vs peer, process x1 seams and x2/x3 panel seams
       (``test_sedimentation_cubed_seam.cpp``)
     - 0 (x1); round-off (x2/x3, **hypothesis**)
   * - G-R3
     - the recursion equals ``sum c_s dt T_s``
     - host FP64 recompute, rk3, 10 steps
     - 1e-15 relative
   * - G-R4
     - budget closes
     - O's ``BudgetConsumer``, ``test_conservation_budget.cpp`` decks
     - 1e-12 relative per row
   * - G-R5
     - rollback zeroes the register and monitor
     - NaN injection, as X's rollback gate
     - exact
   * - G-R6
     - capturable; fixed addresses
     - X's capture check
     - capture succeeds
   * - G-R7
     - vic energy wall residual is round-off
     - per-column residual on #369's rest deck
     - < 1e-13 relative, else ``vic.cell``
   * - G-R8
     - ``riemann.central`` equals ``cen2``/``cen3``
     - A's H1, #363 deck
     - 1e-14 relative
   * - G-R9
     - ``boundary.prescribed`` amount
     - wall and solid decks
       (``tests/test_implicit_stratified_solid.py``, per ``I.rst``)
     - round-off, else a declared change
   * - G-R10
     - same-process x1 seam difference
     - ``|F_own - F_peer|`` with 2 blocks in one process
     - measured, for K6
   * - G-R11
     - ``A_f total(1)`` equals ``Phi`` (``:1641``, ``:1646``); run in I-4
     - compare in ``post_implicit``
     - at most 4 ulp of the larger operand (RULINGS I-4.gr11)
   * - G-R12
     - carry momentum frame
     - compare the carry's rows against the pin on a cubed-sphere deck with
       the limiter on
     - bitwise
   * - G-R13
     - transposed panel edges: after ``owner_copy`` both sides hold equal
       non-momentum rows with the mapped sign
     - a cubed-sphere deck whose seams include an x2/x3 transposed edge
     - bitwise (non-momentum); S's 1e-14 (momentum)
   * - G-R14
     - amounts recursion equals ``sum_s c_s a_s`` plus the direct and
       ``after_combine`` entries
     - host FP64 recompute, rk3, with a radial ``post_split`` and a fixer
     - 1e-15 relative


6. FP32 contract
----------------

* ``T_d``, kept parts and posts: ``kFlux``. In a CUDA FP32 run they are
  FP32 storage.
* ``riemann.pstar`` and ``pressure_base1``: ``kGauge``, FP64.
* CUDA and CPU: ``S_d``, boundary sums, amounts, domain totals and minima
  are FP64; counters are int64 and retry flags int32. A
  post is cast once, inside the post (amounts) or inside ``end_stage``
  (step).
* **MPS contract** (MPS has no FP64, ``meshblock.cpp:1057``):

  * ``S_d``, boundary sums, amounts, domain totals and minima are FP32;
    counters stay int64 and retry flags int32 (**hypothesis**: the MPS
    backend supports the int64 adds and sums they need);
  * the recursion of 3.4 runs in FP32;
  * G-R3 on MPS is 1e-6 relative per step, and G-R4 is reported, not gated
    at 1e-12;
  * an MPS budget is labelled FP32 by O;
  * a compensated (two-term) FP32 sum is an option, not adopted;
  * both tolerances are **hypotheses**.

* **Hypothesis:** FP64 accumulation changes no FP32 state bit, because
  ``du`` still comes from ``T_d``.


7. CUDA-graph contract
----------------------

* Storage, masks and part slots are fixed at ``reset()`` (X's
  ``store_generation``). ``set_prescribed`` is redone per solid-mask
  version, which invalidates graphs.
* The weights are host doubles fixed per stage, baked into a stage graph;
  ``dt`` is in X's ``GraphKey``.
* Posts, ``scale``, ``replace``, ``apply_prescribed`` and ``end_stage`` are
  device ops. The peer entry is X/S's pack, host, unpack.
* There is no host read. ``post_split`` and ``after_combine`` run in X's
  step phases.


8. Cross-repository interface changes and merge order
-----------------------------------------------------

* pyharp: none. R reads ``harp::IntegratorWeight`` (pyharp
  ``integrator.hpp:20-29``) through X's ``begin_stage``.
  kintera: K posts through R's calls (4.2 K). commux: none.
* Merge order (snapy):

  1. R-1, the register with no reader (G-R1, G-R3);
  2. C's and EF's posts;
  3. the seam ``replace`` and ``boundary.prescribed`` with S (G-R2, G-R9);
  4. I's ``vic.*`` and gravity work, with I-7's deletions (D3);
  5. A's phases and ``Fixer`` (D4);
  6. O's consumers (G-R4).


9. Line budget
--------------

Every range was read at the pin. No line is in two groups. Cheng's ruling
V3-1 (kickoff thread): a deletion is counted by the lane that owns the
file. All of D4 is therefore R's; A counts only its new code, and A's
remaining 25 + 15 lines in R's files stay in R's "after". ``:988``, the
(3.A) heading, stays. The mesh fixer lines (``meshblock.cpp``,
``meshblock.hpp``, ``mesh.cpp``) are in lane X's files, so X counts them
once (gw1, gw2, d, hp, M; ``X.rst:1040-1044`` at ``0fe47c6f``) and this
table books none of them.

.. list-table:: Deletions from R's files
   :header-rows: 1

   * - group
     - ranges (lines)
     - total
   * - D1, to C
     - ``:291-368`` (78), ``:417-504`` (88), ``:668-820`` (153),
       ``hydro.cpp:605-872`` (268)
     - **587**
   * - D2, EF's block
     - ``:858-866`` (9), ``:1154-1252`` (99)
     - **108**
   * - D3, gravity work
     - ``:1412-1537`` (126), ``:575-580`` (6), ``:846-849`` (4),
       ``:1584-1598`` (15), ``:1608`` (1), ``:1682-1693`` (12);
       ``hydro.cpp:126-135`` (10), ``:138-145`` (8), ``:287-293`` (7),
       ``:322-327`` (6); ``hydro.hpp:273-274`` (2), ``:296-314`` (19),
       ``:480`` (1)
     - **217**
   * - D4, AAM
     - ``:989-1003`` (15), ``:1108`` (1), ``:1141`` (1), ``:1288-1298``
       (11), ``:1316-1363`` (48), ``:1390-1391`` (2), ``:1624-1680`` (57);
       ``hydro.hpp:53-55`` (3), ``:89-133`` (45), ``:219-236`` (18),
       ``:462-466`` (5); ``hydro.cpp:27-37`` (11), ``:55-76`` (22);
       ``hydro_options.cpp:56`` (1), ``:68-79`` (12), ``:175-176`` (2)
     - **254**
   * - D5, x1 seam block
     - ``:868-946`` (79)
     - **79**
   * - D6, flux buffers
     - ``hydro.cpp:248-271`` (24)
     - **24**
   * - D7, x1 ghost-row relay to S (accepted, S rev 1.1)
     - ``hydro.cpp:344-377`` (34)
     - **34**
   * - **total**
     -
     - **1,303**

Arithmetic: D1 78 + 88 + 153 + 268 = 587. D2 9 + 99 = 108. D3
126 + 6 + 4 + 15 + 1 + 12 = 164; 10 + 8 + 7 + 6 = 31; 2 + 19 + 1 = 22;
164 + 31 + 22 = 217. D4 15 + 1 + 1 + 11 + 48 + 2 + 57 = 135;
3 + 45 + 18 + 5 = 71; 11 + 22 = 33; 1 + 12 + 2 = 15; 135 + 71 + 33 + 15 =
254. Total 587 + 108 + 217 + 254 + 79 + 24 + 34 = 1,303.

**Overlaps checked.**

* ``:902``, ``:907`` and ``:917`` (``bflux1`` in the seam message) are in D5
  only.
* ``:988`` (the (3.A) heading) stays.
* D7 (``hydro.cpp:344-377``) touches no other group. ``x1_neighbors``
  (``:335-342``) stays.
* S's 149 hydro lines (S section 9) are D7 34 + D5's ``:882-946`` 65 +
  C's ``hydro.cpp:727-776`` 50, inside D1. Each is counted once, here or
  in C.

**Gravity work.** The fixer and cell form are lane I's published table,
133 lines (``I.rst`` at ``c6f9d957``, section 10): fixer 110, cell form 23.
D3 holds all 133, plus the 84 explicit face-work lines of ``:1412-1537``
that move to I's ``GravityWork``.

* My rev 1 figure of 142 = 133 + 6 ``hydro.cpp`` lines that stay
  (``:122-125``, ``:136-137``) + 3 seam lines (in D5).
* Xinyue's thread figures (109 + 20) differ from her published 110 + 23. I
  could not see their ranges.
* 112 and 236: no ranges were available.

**AAM (D4) by file, after V3-1.**

.. list-table::
   :header-rows: 1

   * - file
     - D4 ranges
     - lines
     - A's booking at ``b6a40897`` (before V3-1)
   * - ``hydro_forward.cpp``
     - ``:989-1003``, ``:1108``, ``:1141``, ``:1288-1298``,
       ``:1316-1363``, ``:1390-1391``, ``:1624-1680``
     - 15 + 1 + 1 + 11 + 48 + 2 + 57 = 135
     - 136 = 135 + ``:988``, which stays
   * - ``hydro.cpp``
     - ``:27-37``, ``:55-76``
     - 11 + 22 = 33
     - 33
   * - ``hydro.hpp``
     - ``:53-55``, ``:89-133``, ``:219-236``, ``:462-466``
     - 3 + 45 + 18 + 5 = 71
     - not booked by A
   * - ``hydro_options.cpp``
     - ``:56``, ``:68-79``, ``:175-176``
     - 1 + 12 + 2 = 15
     - not booked by A
   * - **total**
     -
     - **254**
     - A's 169 contain R's 168; A counts none of them after V3-1

A's "after" for these files (``A.rst:766-767``, ``:776`` at ``b6a40897``:
25 in ``hydro_forward.cpp``, 15 in ``hydro.cpp``) is R's +40 below.
Linfeng's 15 AAM option lines and Jiachen's 47 share 12; their union of 50
lies inside D4.

**S/R overlap.** S's 149 hydro lines (S.rst section 9 at ``d03e4888``) are
R's D7 (34) + D5's ``:882-946`` (65) + D1's ``hydro.cpp:727-776`` (50) =
149. S counts none of them as its deletions. C counts no deletion either
(R-C2), so each line is counted once, in R. D5 is ``:868-946`` (79): the 65
plus ``:868-881`` (14, the seam block's comment and gate).

**After (estimate, not code).**

.. list-table::
   :header-rows: 1

   * - item
     - lines
   * - baseline
     - 3,493
   * - deletions D1-D7
     - -1,303
   * - kept
     - 2,190
   * - register and monitor (header 118, ``.cpp`` about 282)
     - +400
   * - stage driver: C 40, EF 15, seam 12, gravity 30, implicit 10,
       prescribed 4, covariance 5, x1 relay call 3 (``after_combine`` is
       X's runner, rev 2.4)
     - +119
   * - A's lines left in R's files (``A.rst:766-767``, ``:776``: 25 + 15)
     - +40
   * - AAM mode key (off/transport/exact)
     - +8
   * - **after (estimate)**
     - **2,757: 37 under 2,794**

3,493 - 1,303 = 2,190; 2,190 + 400 + 119 + 40 + 8 = 2,757; 2,794 - 2,757 =
37. Rev 2's header is still 118 lines, so the register estimate is
unchanged. ``begin_step``, the K chemistry post, the derived-row posts and
the ``after_combine`` runner are in X's, K's, I's and A's files, not R's.

**Margin candidate, not counted.** The seven 6-line verbose timing blocks
(``:505-510``, ``:850-855``, ``:1112-1117``, ``:1145-1150``,
``:1299-1304``, ``:1547-1552``, ``:1610-1615``), 42 lines, if X's
``report()`` takes per-op time.


10. Migration
-------------

1. **R-1**: the register and monitor. ``_flux1/2/3`` become views of
   ``T_d`` (G-R1, G-R3).
2. **R-2**: C's slot and part-slot posts; ``central`` lambda and
   ``:1108``/``:1141`` deleted (G-R8).
3. **R-3**: EF's ``add``/``scale``; ``fadv``, ``fsed1``, ``f1_pre`` deleted.
4. **R-4**: seam ``replace`` with S, then ``boundary.prescribed``
   (G-R2, G-R9, G-R10).
5. **R-5**: I's ``vic.*``; gravity work reads the register; D3 with I-7.
6. **R-6**: A's phases, ``Fixer``; D4. (m1 from ``A_f total(1)`` and
   G-R11 moved to I-4, ruling 2026-11-19: once I-4 posts ``vic.*`` into
   ``total(1)``, the pin's separate ``mc / dt`` term in m1 would count the
   implicit transfer twice.)
7. **R-7**: O's consumers (G-R4).

Each step is one PR and keeps every existing test.


11. Open questions to other lanes
---------------------------------

Checked at rev 2.5 against: X ``36d4986fcf17da330f8678946401a7f39ee9db81``
(UCzhangxi/snapy), S ``4b96f4ea9a63fd6152e319a70930559cdfda0871``
(jihenghu/snapy, rev 2.1), I ``fa3ad5e6ef4ab51f40b6a53889d9f3b7ec62cadb``
(zoeyzyhu/snapy) and C ``bcac27c97a9efc1de2cb2041e6b709f07eedcefe``.

* **A:** answered at ``2b0ac426`` (``A.rst`` 11.2): K4 confirmed,
  ``aam.boundary.1``, and ``vic.momentum_t.top`` does not enter the torque.
  The lifetime of ``riemann.central`` is in 4.1 item 4. Nothing open.
* **I:** closed. ``vic.mass_clamped`` is ``flux_correction`` with
  ``stage_weight = w2_s``, and lane I confirms R's classification
  (``I.rst:396-400``). The ``e+pe`` derived row is confirmed
  (``I.rst:1271-1275``) and gate G-R7 is confirmed, specified and not run
  (``I.rst:1276-1278``). G-R7 stays a gate.
* **O:** agreed at ``dfa8ecd0`` (``O.rst`` 11.7); its request on 4.1 item
  6 is made. Nothing open.
* **EF:** answered at ``5e30b31b`` (rev 3.6): the cause names (4.5) and
  free-slip (3.5). Q-R-i stays on gate G-R2 (hypothesis). The solid-fill
  and K wording is fixed in rev 3.6: S's solid fill every stage when a
  solid field exists (``EF.rst:516``, ``:556-558``; pin
  ``meshblock.cpp:936-938``), K at ``:954-972`` (``EF.rst:520``).
* **S:** closed at rev 2.1. The per-row edge map is ``PanelEdge``
  (``peer_dim``, ``reversed``, ``normal_sign``) in ``SeamEntry``
  (``seam_register.hpp:37-49``; ``S.rst:109-112``, 4.1 at ``:1096-1165``),
  anchored by gate G-S13 (``S.rst:1412``), which feeds G-R13. "C's 50" is
  R's D1 (``S.rst:125-126``). K7 is gate G-S-K7 (``S.rst:119-122``,
  ``:1426``), a gate, not a contract change. R-C1 needed nothing from S
  (V3-3).
* **X:** closed at ``36d4986f``. EF's four causes map to bits: the
  ``ef.floor_patch``, ``ef.vapor_fail`` and ``ef.heat_capacity`` causes to
  bit 2, ``ef.nan`` to bit 3, and ``implicit.column`` to bit 5
  (``X.rst:224-232``; names at ``:1249-1250``). X's ``BlockInit`` calls
  ``StateStore::register_storage`` on R's tensors after ``reset()``
  (``X.rst:192-196``, ``:1226-1227``). ``set_prescribed`` copies into the
  buffers allocated at ``reset()``, and only
  ``StageExecutor::bump_config_generation()`` changes the
  ``config_generation`` key (``X.rst:196-201``). X books the mesh fixer
  lines and R books none (``X.rst:686``, ``:1113``, ``:1295``). X's
  ``after_combine`` runner is in 4.2 "X and A" (rev 2.4).
* **C:** closed at ``bcac27c9``. R-C1 is settled by V3-3, and
  ``build_covariance(faces, dim)`` runs in C's ``before_solve`` hook
  (``C.rst:1023-1031``, ``:1892-1896``). Older change-list wording in
  ``C.rst`` is marked superseded in C rev 6.3.
* **K:** answered at ``fc619eec``: slot 4 of X's stack and the two solve
  counters (4.2 K).
* **Cheng (closed, rev 2.6):** lane I's (c), the per-column FP64 retry, is
  accepted (22:20 EST). Row 1 of the 4.5 table stands; ``implicit.column``
  stays per column.
* **Still open:** Xinyue's five notes whose text I never had (row 54).


12. Skeleton index
------------------

.. list-table::
   :header-rows: 1

   * - file
     - lines
     - declares
   * - ``docs/v3/skeleton/R/flux_register.hpp``
     - 117
     - ``RegisterPhase``, ``SeamRule``, ``AmountKind``,
       ``RegisterRequest``,
       ``FluxRegister``, ``RegisterMonitor``, ``Fixer``
   * - ``docs/v3/skeleton/R/hydro_stage.hpp``
     - 82
     - ``StageInputs``, ``HydroStage``
   * - **total**
     - **199**
     - under 300
