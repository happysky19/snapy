:orphan:

V3 lane R: flux register, monitor and the hydro stage
=====================================================

Revision 1.1, 2026-11-17. Owner: Tianhao Le (backup owner). Reviewers:
Xinyue Wang and Zoey Hu. Design only: no implementation change.
Declarations are in ``docs/v3/skeleton/R/`` (not built):
``flux_register.hpp`` (rev 2, 117 lines) and ``hydro_stage.hpp`` (75 lines),
192 lines in all.

Every ``path:line`` is at chengcli/snapy
``9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410`` unless another commit is named.
Bare ``:N`` means ``src/hydro/hydro_forward.cpp:N``. "Measured" means a
line count read at the pin with ``git show <pin>:<file> | sed -n 'a,bp'``
and ``b - a + 1``; "estimate" means a design target, not counted code.
Nothing in this revision was built, compiled, syntax-checked, tested or
timed. A claim that needs a run is marked **hypothesis**.

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

* C: happysky19 ``v3-design/C`` ``2d6aef4dd15f14d1cc5c1d8d38166182b6eea9e0``;
* X: UCzhangxi ``v3-design/X`` ``77c65d5a``;
* A: JiachenLiu-Atmos ``v3-design/A`` ``b6a40897``;
* O: JiachenLiu-Atmos ``v3-design/O`` ``b66b6745`` (rev 2; the head is now
  ``d69b5442``, not re-read);
* I: XinyueWang05 ``v3-design/I`` ``c6f9d957``;
* S: XinyueWang05 ``v3-design/S`` ``48b2328dea564a9a4e7db35c782fc6e74b3e5b7a``;
* EF: zoeyzyhu ``v3-design/EF`` ``1a529719``;
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
  transfer through physical boundary faces;
* the prescribed mask and values from lane S.

**3.2 Phases.** ``sweep`` < ``reconcile`` < ``limit`` < ``divergence`` <
``pre_implicit`` < ``implicit`` < ``post_implicit``, then ``end_stage``,
then, after X's RK combine, ``after_combine``. This is the pin's order;
nothing is reordered. The post-implicit source phase is ``post_implicit``,
as in A's ``SourcePhase::post_implicit``.

**3.3 Posts.** ``slot``/``post_slot`` for the first post (C's riemann);
``part_slot`` for a requested part written in place by the kernel (C's
``riemann.central``, ``riemann.pstar``; C rev 5 question R8: no copy);
``add`` for an increment (C's covariance, EF's sedimentation and carry,
I's ``vic.*``); ``scale`` for a multiply (EF's withhold); ``replace`` for a
shared face; ``apply_prescribed`` for walls and solids; ``keep`` for a
computed one-row part (I's ``vic.mass_total``, one row copied);
``cell_amount`` and ``count`` for the monitor.

``add`` acts on ``T_d`` in call order and is never fused or pre-summed.
That keeps the pin's ``E = (E - c_adv) - c_sed`` rounding
(``flux_positivity.cpp:154-159``). ``scale`` multiplies the rows in place,
as ``f.mul_(where(f > 0, th_lo, th_hi))`` does (``flux_positivity.cpp:99-121``).

**3.4 Step transfer.** ``begin_stage(s, w)`` gives this stage's weights.
``end_stage(dt)`` updates ``S <- w1_s S + w2_s dt T_s`` and the same for
the boundary sums. Unrolled over the stages, the coefficient of ``T_s`` is
``w2_s prod_{t>s} w1_t``, the weight at ``:1685-1691``. So no lane needs
the whole stage table. **Hypothesis:** the recursion and the product form
differ only in FP64 rounding (gate G-R3).

**3.5 boundary.prescribed.** Lane S gives, per direction, the mask of
physical wall faces and immersed-solid faces and the prescribed rows
(default: zero for mass, species, energy and scalars; the momentum rows
keep the solver's wall pressure). ``apply_prescribed(d)`` runs after
``reconcile`` and again after ``post_implicit``, before any phase reads the
total. The change it makes is booked as the named correction
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
   reconciled and prescribed but never scaled.
5. **Reads.** ``total(d)`` at the caller's phase, ``kept()``,
   ``step_field()``, monitor views. No EOS call.
6. **Monitor.** Per-post FP64 amounts (area-weighted for faces,
   volume-weighted for cells), named counters, fluid-cell domain totals and
   retry flags. All are on device, read once in X's step-end read.
7. **Reset.** ``begin_stage(0)`` calls ``RegisterMonitor::reset_step()``.
   ``FluxRegister::rollback()`` zeroes the register and calls
   ``RegisterMonitor::rollback()``; X's ``decide_retry`` calls it on every
   block. Nothing is written to restart.

4.2 Client answers
~~~~~~~~~~~~~~~~~~

**EF (Zoey).**

* Q1: ``:858-866`` (9) and ``:1154-1252`` (99) are R's deletion.
* Q2: per-post amounts. A field only on request. EF keeps its own settling
  buffer (Zoey's note).
* Q3: ``scale``, with the carry as ordered ``add`` calls before it.
* Q4: ``replace`` in ``reconcile``, after sedimentation and before
  positivity.
* Q5: no EOS call.
* EF's R4 (hydro mass flux without covariance): the Scalar module requests
  ``covariance.dry@2`` and ``@3``, as the pin keeps ``_cov_dry``
  (``:1106``); R4 = summed total mass row minus that part.
* EF's 12 status counters are ``count()`` names, listed by EF in
  ``RegisterRequest::counters``.
* EF's renames (``reg.add``, ``reg.scale``, string names, ``Fixer``
  subclasses) match the header.

**I (Xinyue).**

* Posts ``vic.mass_dry`` (IDN), ``vic.mass_species`` (ICY..),
  ``vic.momentum_t`` (IVY, IVZ) by ``add`` on x1.
* Kept: ``vic.mass_total@1`` and ``vic.mass_dry@1`` (I's R-1: accepted).
* Monitor amounts: ``vic.cell``, ``vic.mass_clamped``,
  ``vic.momentum_t.top`` (I's R-2: accepted as I defines it).
* Dims are numbered 1, 2, 3 for x1, x2, x3 (I's R-3).
* Phase: ``post_implicit``.
* ``retry_flags`` takes the OR of I's per-column status after any retry.
  Only columns that still fail set it. The per-column FP64 retry is still
  open (Cheng's ruling (c)).
* Energy as a face transfer stays a **hypothesis** (gate G-R7); until then
  it is in ``vic.cell``.

**A (Jiachen).**

* ``riemann.central@2/@3`` is one summed mass row. It comes from the states
  after ``pib->forward`` (``:1089-1090``, ``:1123-1124``), the tensor that
  both ``cen2`` (``:1108``) and the solver (``:1109``) read. A rev 2 found
  the same one tensor (``A.rst`` R-1 at ``b6a40897``). Densities are totals.
* Split radial conduction: ``post_split(..., 0.5, dt)`` per half
  (``meshblock.cpp:715``, ``:905``).
* Fixer base: ``snap::Fixer``.
* A's R-3 (an AAM budget row needs ``r K . m``): A registers a derived row
  at ``reset()`` with its own device reducer, and posts its amounts with
  ``cell_amount``. R adds no AAM code. **Request to A:** confirm.

**O (Jiachen).** R's monitor owns the fluid-cell domain totals. O formats
the cycle line. Readers multiply densities by ``face_area<d>``; monitor
amounts are already weighted. A single increment is an amount, not a field.
The boundary transfer is direct, after reconciliation and
``boundary.prescribed``. ``observe`` runs after accept and before the next
``begin_stage(0)``.

**X (Xi).** ``begin_stage(stage, w)`` with host doubles is the only weight
input. ``rollback`` is in the reset list. FP64 accumulator (FP32 on MPS).
Corrections are per stage, plus the ``after_combine`` phase for fixers that
run after the combine (``meshblock.cpp:907-909``, ``:983-990``). The
monitor joins the stacked retry read.

**C (Tianhao), rev 5 questions R8-R12.**

* R8: ``part_slot`` gives a writable view, so there is no copy.
* R9: there is no ``riemann.mass@1``; the cell form is gone.
* R10: ``count(name, n)``.
* R11: ``pressure_base1`` is a companion, reconciled by ``replace`` as the
  pin's message carries it (S row 9).
* R12: ``snap``.

**S (Xinyue).**

* ``replace(d, faces, peer, rule)`` takes S's peer entry for each shared
  face. ``SeamRule::mean`` is the pin's x1 rule.
* x2/x3 seams need no ``replace`` while both sides solve identical
  exchanged states (S rows 11-12). Gate G-R2 checks that.
* S supplies the ``boundary.prescribed`` mask and values.

4.3 Conflicts
~~~~~~~~~~~~~

* **K1, positivity form.** Resolved. C rev 5 adopts ``scale()``
  (``C.rst`` at ``2d6aef4d``, section 4 "Ordering", item 4, and its R3).
  My rev 1 statement that C rev 5 was unpushed was stale.
* **K2, weights.** Resolved with one owner: ``begin_stage(stage, w)`` and
  the recursion of 3.4. ``reset`` takes no table.
* **K3, namespace.** Resolved: ``snap``. A rev 2 and C rev 5 use it, and EF
  follows R.
* **K4, "post-terrain".** Resolved at the source level. ``terrain`` occurs
  nowhere in ``src`` at the pin, and A rev 2 reads one tensor at
  ``:1089-1090``. A's separate check is pending.
* **K5, cell increments.** Monitor amounts only (X keeps the register
  face-only).
* **K6, same-process x1 seams. Flagged.** The pin averages only process
  seams (``:880-888``). Requirement 5 asks one rule per shared face. R
  keeps the pin's scope (bitwise). Gate G-R10 measures the same-process
  difference; Cheng and S decide.
* **K7, frame of the carry's momentum rows. Flagged.** The carry adds donor
  velocity times mass (``:1234``, cell ``u/rho``) to post-rotation face
  rows. **Hypothesis:** the cell and face components agree for x1. On
  cubed-sphere x2/x3 faces they may not; gate G-R12.
* **K8, AAM lines counted twice. Flagged.** A rev 2's section 9 counts
  ``hydro_forward.cpp`` AAM ranges 136 -> 25 and ``hydro.cpp`` 33 -> 15 in
  A's own budget. R's D4 counts the same lines. R proposes C's convention:
  R counts the deletion, and A counts only its new code. The 25 + 15 lines
  then sit in R's "after" (section 9). Request to A.


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
       (G-R11)
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
     - ``reset_step``, ``rollback``
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
     - K8


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
     - shared faces single-valued after ``reconcile``
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
     - ``A_f total(1)`` equals ``Phi`` (``:1641``, ``:1646``)
     - compare in ``post_implicit``
     - 1 ulp (I-4 rounding)
   * - G-R12
     - carry momentum frame
     - compare the carry's rows against the pin on a cubed-sphere deck with
       the limiter on
     - bitwise


6. FP32 contract
----------------

* ``T_d``, parts and posts: ``kFlux`` (FP32 in an FP32 run).
* ``riemann.pstar`` and ``pressure_base1``: ``kGauge``, FP64.
* ``S_d``, boundary sums, amounts and counters: FP64, or FP32 on MPS
  (``meshblock.cpp:1057``). One cast per post or per ``end_stage``.
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

* pyharp: none (reads ``harp::IntegratorWeight``). kintera, commux: none.
* Merge order (snapy):

  1. R-1, the register with no reader (G-R1, G-R3);
  2. C's and EF's posts;
  3. the seam ``replace`` and ``boundary.prescribed`` with S (G-R2, G-R9);
  4. I's ``vic.*`` and gravity work, with I-7's deletions (D3);
  5. A's phases and ``Fixer`` (D4, after K8);
  6. O's consumers (G-R4).


9. Line budget
--------------

Every range was read at the pin. No line is in two groups.

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
   * - **total**
     -
     - **1,269**

Arithmetic: D1 78 + 88 + 153 + 268 = 587. D2 9 + 99 = 108. D3
126 + 6 + 4 + 15 + 1 + 12 = 164; 10 + 8 + 7 + 6 = 31; 2 + 19 + 1 = 22;
164 + 31 + 22 = 217. D4 15 + 1 + 1 + 11 + 48 + 2 + 57 = 135;
3 + 45 + 18 + 5 = 71; 11 + 22 = 33; 1 + 12 + 2 = 15;
135 + 71 + 33 + 15 = 254. Total 587 + 108 + 217 + 254 + 79 + 24 = 1,269.

**Gravity work, reconciled.** Lane I's table (``I.rst`` at ``c6f9d957``,
section 10) gives R exact ranges.

* Fixer, 110:

  * ``hydro.hpp:273-274, 296-314, 480`` (22);
  * ``hydro.cpp:126-135, 138-145, 287-293, 322-327`` (31);
  * ``:1416-1417, 1507-1533, 1584-1598, 1608, 1682-1693`` (57).

* Cell form, 23: ``:575-580, 846-849, 1426-1434, 1505-1506, 1534, 1536``.
* 110 + 23 = 133. I re-read every range: each line is fixer or cell code.

D3 contains all 133. The other 84 lines are the explicit face-work part of
``:1412-1537``, which moves to I's ``GravityWork``.

* **My rev 1 figures, 142 and 223.** I counted ``hydro.cpp:122-145`` (24)
  where 18 is right: ``:122`` (``gw``, read at ``:148``) and ``:123-125``
  (the ``cell``/``face`` check, edited) stay, and so do ``:136-137``
  (``nm``, ``wrap``, read by the face warning). I also counted ``:902``,
  ``:907``, ``:917`` (the ``bflux1`` seam lines), which belong to D5.
  142 - 6 - 3 = 133. 223 - 6 = 217.
* **Xinyue's thread figures, 109 R + 20 cell, X 123, I 11.** Her published
  table has R 110 + 23 and X 124; the X change is the blank
  ``meshblock.cpp:1110``. I could not see the ranges behind 109 and 20, so
  I use the published 133.
* **112 and 236.** No ranges were available. Not used.
* X's 124 and I's lines are outside R's files.

**AAM, reconciled.**

* 15 (Linfeng) = ``hydro_options.cpp:68-79`` (12) + ``hydro.cpp:67-69``
  (3).
* 47 (Jiachen; ``A.rst`` 10.2 "R: 47 lines") = ``hydro.hpp:53-55`` (3),
  ``:89`` (1), ``:106-133`` (28), ``:224`` (1); ``hydro_options.cpp:56``
  (1), ``:68-79`` (12), ``:176`` (1).
* 50 = 47 + ``hydro.cpp:67-69``, the union, because 15 and 47 share the 12.
* 254 = D4. It contains all 50, and adds the accessors, state, predicates,
  the ``central`` lambda, the flux-form call, the Coriolis gate and step 8:
  A's ranges in R's files, less the ``:988`` heading, plus the option lines
  outside them.
* So 15 is in 50, 47 is in 50, 50 is in 254. Each line is counted once.
  See K8 for A's table.

**After (estimate, not code).**

.. list-table::
   :header-rows: 1

   * - item
     - lines
   * - baseline
     - 3,493
   * - deletions D1-D6
     - -1,269
   * - kept
     - 2,224
   * - register and monitor (header 117, ``.cpp`` about 283)
     - +400 (estimate)
   * - stage driver: C 40, EF 15, seam 12, gravity 30 (``I.rst`` rev 1
       s9), implicit 10, prescribed 4, ``after_combine`` 4
     - +115 (estimate)
   * - A's lines left in R's files (``A.rst`` rev 2 s9: 25 + 15)
     - +40 (A's estimate)
   * - AAM mode key (off/transport/exact stays in Hydro)
     - +8 (estimate)
   * - **after**
     - **2,787 (estimate), ceiling 2,794: 7 to spare**

**Conditions and margin.**

* D3 rests on Cheng's rulings (a) and (b).
* D4 rests on A moving AAM out of Hydro and on K8.
* The margin is thin. One candidate, not counted: the seven 6-line verbose
  timing blocks outside D1-D6 (``:505-510``, ``:850-855``, ``:1112-1117``,
  ``:1145-1150``, ``:1299-1304``, ``:1547-1552``, ``:1610-1615``), 42
  lines, if X's ``report()`` takes per-op time. That would give 2,745.


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
6. **R-6**: A's phases, ``Fixer``; D4 (after K8); m1 from ``A_f total(1)``
   (G-R11).
7. **R-7**: O's consumers (G-R4).

Each step is one PR and keeps every existing test.


11. Open questions to other lanes
---------------------------------

* **A:** K8 (who counts the 168 AAM lines in R's files); confirm the
  derived AAM row (4.2 A) and that all of D4 leaves Hydro.
* **S:** K6 (same-process x1 seams); the mask and values for
  ``boundary.prescribed``; K7's frame on panel seams.
* **X:** the ``after_combine`` phase in your schedule; per-op time in
  ``report()`` (margin); who counts the 124 meshblock fixer lines.
* **I:** gate G-R7; confirm the 133 ranges stay as published.
* **EF:** the names of the 12 counters.
* **Xinyue:** the five notes not visible to me (matrix row 28).
* **Cheng:** I's ruling (c), which decides what ``retry_flags`` carries.


12. Skeleton index
------------------

.. list-table::
   :header-rows: 1

   * - file
     - lines
     - declares
   * - ``docs/v3/skeleton/R/flux_register.hpp``
     - 117
     - ``RegisterPhase``, ``SeamRule``, ``RegisterRequest``,
       ``FluxRegister``, ``RegisterMonitor``, ``Fixer``
   * - ``docs/v3/skeleton/R/hydro_stage.hpp``
     - 75
     - ``StageInputs``, ``HydroStage``
   * - **total**
     - **192**
     - under 300
