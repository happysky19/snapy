:orphan:

V3 lane R: flux register, monitor and the hydro stage
=====================================================

Revision 1, 2026-11-17. Owner: Tianhao Le (backup owner; Linfeng Li did
not take the lane). Reviewers: Xinyue Wang and Zoey Hu. Design only: no
implementation change. Declarations are in ``docs/v3/skeleton/R/`` (not
built): ``flux_register.hpp`` (118 lines, rev 1.1) and ``hydro_stage.hpp``
(72 lines), 190 lines in all.

Every ``path:line`` is at chengcli/snapy
``9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410`` unless another commit is named.
Bare ``:N`` means ``src/hydro/hydro_forward.cpp:N``. "Measured" means a
line count read from the pin with ``git show <pin>:<file> | sed -n 'a,bp'``;
"estimate" means a design target, not counted code. Nothing in this
revision was built, compiled, syntax-checked, tested or timed. A claim that
needs a run is marked **hypothesis**.

Changes from the header at ``543ff84f`` (rev 1):

* ``begin_stage`` now has X's exact signature,
  ``begin_stage(int stage, harp::IntegratorWeight const& w)``. The full stage
  table is given once at ``reset()``, so the register computes every
  ``c_s`` without a new argument (section 4.3, conflict K2).
* ``riemann.central`` is stated as built from the face states after the
  immersed-solid step (``:1090``, ``:1124``), which is the pin's ``cen2``
  (``:1108``). This is R's reading of "post-terrain states" (K4).
* ``kRegister`` is FP64 except on MPS, which has no FP64 (``wide`` at
  ``src/mesh/meshblock.cpp:1057``).
* The positivity form is ``scale()``. C's ``(theta - 1) F`` is withdrawn
  (K1). The namespace is ``snap`` (K3).

.. contents::
   :local:
   :depth: 1


1. Scope and pins
-----------------

**Files (baseline 3,493 lines, measured).**

.. list-table::
   :header-rows: 1

   * - file
     - lines at the pin
   * - ``src/hydro/hydro_forward.cpp``
     - 1,698
   * - ``src/hydro/hydro.cpp``
     - 971
   * - ``src/hydro/hydro.hpp``
     - 490
   * - ``src/hydro/hydro_options.cpp``
     - 201
   * - ``src/hydro/register_forcing_modules.cpp``
     - 85
   * - ``src/hydro/x1_mass_covariance.hpp``
     - 48
   * - **total**
     - **3,493**

I could not read the study plan's file list. This set is inferred: it is the
part of ``src/hydro`` that no other lane claims. C claims the reference,
dispatch and balance files (``C_lines.csv``). EF claims
``flux_positivity.*``. I claims ``gravity_work*.hpp`` (``I.rst`` section 1).
The set sums to 3,493 exactly. Ceiling: 3,493 x 0.8 = 2,794.4, so
**2,794**, with the new register included.

**Owned by lane R.** The flux register and its monitor (requirements 1-10).
The x1 seam reconciliation rule (the transport is lane S's). The hydro stage
order. Option parsing for ``dynamics/*`` keys that stay in Hydro.

**Read, owned elsewhere.** C's skeleton (happysky19 ``v3-design/C``
``a7155840``; local rev 5 ``71c47dcd``, not pushed). X: UCzhangxi
``v3-design/X`` ``77c65d5a``. A: JiachenLiu-Atmos ``v3-design/A``
``2c9589c6``. O: JiachenLiu-Atmos ``v3-design/O`` ``b66b6745``. I:
XinyueWang05 ``v3-design/I`` ``66cbcc7c``. EF: zoeyzyhu ``v3-design/EF``
``1a529719``. pyharp ``src/integrator/integrator.hpp:19-29`` at pyharp main
``6bc01d53`` (not pinned by any lane).

**Inputs taken as provisional.** Linfeng's draft ``fd3d68a`` was posted in
the home thread. I could not see its text: it is on no fork and was cut from
my context. I use it only as EF records it (``EF.rst`` section 4, Q1-Q5) and
as A attributes it (R-1, R-2). The seven questions of the 12:29 post were
not visible to me either, so section 4 answers by topic, 1-7.


2. Concepts and current sites
-----------------------------

``HydroImpl::forward`` (``:370-1696``) is one 1,327-line function. Its
phases at the pin:

.. list-table::
   :header-rows: 1

   * - step
     - lines
     - what touches a face flux
   * - (1) primitives
     - ``:383-615``
     - none; conversion-order 4 (C's ``:417-504``)
   * - (2) x1 flux
     - ``:616-987``
     - riemann into ``_flux1`` (``:845``); ``bflux1`` clone (``:846-849``);
       sedimentation added in place (``:861-866``); x1 seam average
       (``:868-946``)
   * - (3.A/B) x2/x3 states
     - ``:988-1049``
     - AAM full's refusal (``:992-995``) and ``central`` lambda
       (``:997-1003``)
   * - (4.A/B) x2/x3 flux
     - ``:1050-1153``
     - ``cen2``/``cen3`` (``:1108``, ``:1141``); riemann (``:1109``);
       covariance added (``:1110``)
   * - (4.C) positivity
     - ``:1154-1252``
     - carry then scale, in place (``:1233-1237``)
   * - (5) divergence
     - ``:1254-1305``
     - divergence; AAM flux form (``:1288-1298``)
   * - (6) forcing
     - ``:1306-1552``
     - ``_aam_mass_flux = F - cen`` (``:1354-1362``), cleared (``:1391``);
       gravity work rebuilds the x1 mass row (``:1422-1425``)
   * - (7) implicit
     - ``:1554-1616``
     - ``dt_corr = w2_s dt`` for 3+ stages (``:1568-1583``)
   * - (8) x1 mass-flux w
     - ``:1624-1680``
     - ``Phi = A F1 + mc/dt`` (``:1641``, ``:1646``)
   * - fixer weight
     - ``:1682-1693``
     - ``c_s = w2_s prod w1_t`` (``:1685-1691``)

**Face-flux storage today.** ``_flux1/2/3`` are module buffers
(``hydro.cpp:250-270``). They are rewritten in place by every contributor,
so no part can be read after the next one acts. That is why the pin clones
``bflux1`` (``:847``), ``fadv`` (``:863``) and ``f1_pre`` (``:1230``), and
calls the solver four extra times for ``central`` (``:1000-1001``).

**Stage weights today.** The integrator combines ``u <- w0 u0 + w1 u + w2
du`` (``src/mesh/meshblock.cpp:901``). The step weight of stage ``s`` is
``w2_s prod_{t>s} w1_t``, computed only by the gravity-work fixer
(``:1685-1691``).

**Resets today.** At stage 0 of each step (``meshblock.cpp:713``, ``:726-735``).
The redo path is ``apply_redo`` (``meshblock.cpp:1456``), and the single host
read is ``read_redo_flags`` (``meshblock.cpp:1565-1566``).


3. Target design
----------------

**3.1 Register.** One ``FluxRegister`` per block (``flux_register.hpp``).
Per active direction ``d`` it holds:

* the **stage total** ``T_d`` (``nvar`` rows, ``Quantity::kFlux``);
* the **kept parts** that a reader asked for at ``reset()``, each one summed
  row, or a companion such as ``riemann.pstar`` (``kGauge``);
* on request, the **step field** ``S_d`` (``kRegister``);
* the **boundary sums**: per row, FP64, area-weighted, the outward step
  transfer through physical boundary faces.

Posts write ``T_d`` in place. That keeps today's in-place rounding and adds
no copy (requirement 9). A contributor that needs its own increment later
asks for it as a kept part. Otherwise the increment is visible only as an
FP64 monitor amount.

**3.2 Stage order** (``RegisterPhase``). ``sweep`` < ``reconcile`` <
``limit`` < ``divergence`` < ``pre_implicit`` < ``implicit`` <
``post_implicit``, then ``end_stage``. This is the pin's order (section 2);
nothing is reordered. The name of the post-implicit source phase is
``post_implicit``, the same as A's ``SourcePhase::post_implicit``.

**3.3 Hydro stage** (``hydro_stage.hpp``). ``HydroImpl::forward`` becomes a
driver that calls the lanes' ops in phase order. It holds no flux buffer, no
fixer state and no AAM state. It builds the ``RegisterRequest`` from the
lanes' needs.

**3.4 What goes from R's files** (counted in section 9): C's moved ranges,
EF's limiter and sedimentation block, the gravity-work fixer and cell path,
the AAM machinery that A moves to its sources, and the x1 seam block. The
seam block becomes ``replace()`` plus S's exchange.

**3.5 Bitwise targets** (hypotheses until the gates in section 5 run).

* The sweep, reconcile, limit and divergence phases keep the pin's
  operation order on ``T_d``, so they are bitwise.
* ``central`` moves from two extra solver calls (``:1000-1001``) to C's
  kernel. A's gate H1 bounds it at 1e-14 relative.
* EF's settling part is a declared rounding change (``EF.rst`` section 4,
  point 4).


4. Flux-register contract
-------------------------

4.1 Contract answers, by topic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Units and frame.** A post is a flux density per unit face area and
   time, at the step ``dt``, before stage weights. It is in global
   components after coord's rotation. Face ``i`` lies between cells ``i-1``
   and ``i``. The divergence applies ``face_area<d>`` and the cell volume
   (``src/coord/coordinate.cpp:706-735``). Lane I divides its
   A·dt-integrated transfers by ``A_f dt`` once. Today's
   ``Phi = A F1 + mc[IVZ]/dt`` (``:1641``, ``:1646``) shows the same unit.
2. **Names and parts.** Every post is named. A part is a field only if
   requested. Unrequested parts are FP64 monitor amounts. There is no
   per-face read by kind.
3. **Weights and dtype.** ``T_d`` is ``kFlux``. ``end_stage(dt)`` adds
   ``c_s dt T_d`` to ``S_d`` and the boundary sums, with
   ``c_s = w2_s prod_{t>s} w1_t`` in host double. ``kRegister`` is FP64, or
   FP32 on MPS (``meshblock.cpp:1057``).
4. **Corrections.** ``add()`` is in place, in post order. ``scale()``
   multiplies ``T_d`` rows in place. ``replace()`` applies the seam rule.
   Kept parts are reconciled with the total but never scaled: ``cen2`` is
   unscaled at ``:1356``, and so is ``bflux1`` at ``:1431``.
5. **Reads.** ``total(d)`` at the caller's phase, ``kept()``,
   ``step_field()`` and the boundary sums. The register never calls the EOS.
6. **Monitor.** Lane R owns it: per-post amounts, counters, domain totals
   and retry flags. It is stacked into X's one step-end read
   (``meshblock.cpp:1566``).
7. **Reset.** ``begin_stage(0)`` zeroes the step. ``rollback()`` zeroes
   everything; it sits in X's reset list (``meshblock.cpp:735``). Nothing is
   written to restart.

4.2 Client questions
~~~~~~~~~~~~~~~~~~~~

**EF (Zoey), Q1-Q5.**

* Q1, the 108-line split. ``:858-866`` (9) and ``:1154-1252`` (99) are
  R's deletion. EF counts only its new code. Agreed with ``EF.rst``
  section 1.
* Q2, per-kind parts. Each post has FP64 monitor amounts. A per-face field
  exists only if requested. EF may request ``sedimentation@1`` on species
  rows instead of keeping its own buffer. The storage is the same; EF
  chooses.
* Q3, scale posts. ``scale()`` multiplies the running total, which is
  bitwise with ``f.mul_(where(f > 0, th_lo, th_hi))``
  (``flux_positivity.cpp:99-121``). The carry is ``add()`` in post order:
  x1 advected part, then settling part (``flux_positivity.cpp:154-159``).
  Agreed with EF's point 2.
* Q4, x1 seam average. It is a ``replace()`` in the ``reconcile`` phase:
  after sedimentation (``:861-866``) and before positivity (``:1154``), as
  the comment at ``:1157-1159`` requires. It acts on ``T_1``, ``riemann.pstar``
  and the kept x1 parts.
* Q5, EOS calls. None from the register. EF's typed ``EosInterface``
  decision stands.

**I (Xinyue).** The names are accepted. Units are per unit face area and
time, before stage weights (answer 1).

* ``vic.mass_dry``: ``add()`` on row IDN of ``T_1``.
* ``vic.mass_species``: ``add()`` on rows ICY...
* ``vic.momentum_t``: ``add()`` on the two tangential rows.
* ``vic.mass_total``: a kept summed row. It is not added again, because it
  equals dry plus species.
* ``vic.cell``: ``cell_amount()`` only, because X keeps the register
  face-only (conflict K5).
* ``vic.mass_clamped``: a floor amount (requirement 7), not a post.
* Explicit and ``vic`` stay apart. ``total(1)`` read in ``pre_implicit``
  is explicit. ``kept("vic.mass_total")`` after ``implicit`` is the
  implicit part.
* Phase name: ``post_implicit``. It follows the solve (``:1554-1616``) and
  covers today's readers (``:1618-1680``). Posts in ``implicit`` do not
  enter ``du`` through R; lane I applies its own ``du`` as today.
* R-4, energy as a face transfer: accepted if gate G-R7 shows that the wall
  residual is round-off. **Hypothesis.**

**A (Jiachen).**

* ``riemann.central`` is **one** summed mass row: dry plus all species of
  ``1/2 (F(w_L) + F(w_R))``. A's R-1 asked for ``1 + ny`` rows; the one
  row is enough because the consumer sums them
  (``gnomonic_equiangle.cpp:690-694``, per ``C.rst``).
* It is built in C's kernel from the solver's own face states, after the
  immersed-solid step (``:1090``, ``:1124``). The pin's ``cen2`` uses the
  same states (``:1108``). It is valid until the next ``begin_stage``.
* Densities are **totals** on the perturbation path. This is moot at the
  pin, which refuses full under perturbation flux (``:993-995``).
* Split radial conduction: ``post_split(dim, name, flux, 0.5, dt)`` for each
  half step (``begin_step``, ``meshblock.cpp:715``; ``finish_step``,
  ``:905``; ``diffusion_radial.cpp:7-13``). It goes to the step field and
  the monitor. It is not part of a stage total.
* Fixer base class: ``snap::Fixer``. ``AxialClosureFixer : Fixer``. Its
  ``apply`` posts its amount with ``cell_amount``.

**O (Jiachen).**

* R's monitor owns the domain totals per row (L-6). O's ``BudgetConsumer``
  reads them and owns the cycle line's format.
* Face-area weighting: ``total``, ``kept`` and ``step_field`` are
  densities, so the reader multiplies by ``face_area<d>`` (as
  ``diagnostics.hpp:18`` already assumes). Monitor amounts and boundary sums
  are already area-weighted (faces) or volume-weighted (cells), in FP64.
* Single increments: amounts only, not fields (L-2: a read-only register
  view for user outputs is ``total``/``step_field``).
* L-3: the outward boundary transfer is direct, after reconciliation.
* L-4: the step field is ``kRegister`` (FP64 except on MPS). The budget
  needs no cast.
* L-5: X's ``decide_retry`` calls ``rollback()``. ``observe`` runs after
  accept and before the next ``begin_stage(0)``.

**X (Xi).**

* ``begin_stage(stage, w)`` with host-double weights: adopted with X's
  signature (K2).
* Reset on rollback: yes, in X's registered reset list.
* FP64 step accumulator: yes, except on MPS.
* Corrections are applied per stage, before ``end_stage``.
* The monitor joins the stacked retry read.

4.3 Conflicts, resolved or flagged
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**K1, positivity form (C).** Resolved: ``scale()``. ``F + (theta - 1) F``
is not bitwise ``theta F`` in floating point. EF needs bitwise
(``EF.rst`` section 4, point 1). Lane C's ``(theta - 1) F`` rule
(``C.rst`` rev 4.1, section 4 "Ordering", item 4) must change in C's next
revision. I own both lanes, so this goes into C rev 5 before it is pushed.

**K2, X's stage weight.** Resolved without changing X. ``c_s`` needs
``w1_t`` for ``t > s`` (``:1689-1690``), which one ``IntegratorWeight``
lacks. ``reset()`` takes ``std::vector<harp::IntegratorWeight>`` (the
``pintg->stages`` vector, ``:1686``). ``begin_stage(stage, w)`` keeps X's
signature; ``w`` must equal ``stages[stage]`` (a debug check). X's graph
key bakes in ``c_s`` per stage, as X states.

**K3, namespace.** Resolved for R: ``snap``, as X's and C's skeletons use.
A's and EF's drafts use ``snap::v3``. Request to A and EF: use ``snap``.
V3 replaces code in place, so a ``v3`` namespace would outlive the
migration.

**K4, "post-terrain states".** Flagged. ``terrain`` does not occur in
``src`` at the pin (``git grep -i terrain <pin> -- src``: no output). R
reads it as the face states after the immersed-solid step
(``pib->forward``, ``:1090``, ``:1124``). That is what ``cen2`` uses
(``:1108``). **Request to A**: confirm, or name the step.

**K5, cell increments.** Resolved: monitor amounts only. X keeps the
register face-only (``X.rst`` section 4, "No added full-field copy").

**K6, deletion counts.** See section 9: R's counts are 142/223 for gravity
work and 50/254 for AAM, against the reported 112/133/236 and 47/15.


5. Invariants and gates
-----------------------

None of these has run. Each states how it would be checked.

.. list-table::
   :header-rows: 1

   * - id
     - invariant
     - check
     - tolerance
   * - G-R1
     - Sum of posts equals the pin's in-place ``_flux1/2/3`` at the end of
       each phase
     - debug compare against a main build, every deck in ``tests/``
     - bitwise (EF settling part excepted)
   * - G-R2
     - Seam faces single-valued after ``reconcile`` (requirement 5)
     - max difference of the two entries, ``test_sedimentation_cubed_seam``
       decks
     - 0
   * - G-R3
     - Step field equals the sum over stages of ``c_s dt T_d``
     - recompute on host in FP64 for rk3, 10 steps
     - 1e-15 relative
   * - G-R4
     - Budget closes: ``dTotal + boundary - sum(fixer) = 0``
     - O's ``BudgetConsumer`` on ``test_conservation_budget.cpp`` decks
     - 1e-12 relative per row
   * - G-R5
     - Rollback leaves the register and monitor zero
     - inject NaN, as in X's rollback gate
     - exact zero
   * - G-R6
     - No host read in a segment; register storage address fixed
     - X's capture check (graph replay) with the register on
     - capture succeeds
   * - G-R7
     - The vic energy wall residual is round-off (I R-4)
     - per-column residual on #369's rest deck
     - < 1e-13 relative, else stays a cell amount
   * - G-R8
     - ``riemann.central`` matches ``cen2``/``cen3``
     - A's H1 on the #363 deck
     - 1e-14 relative


6. FP32 contract
----------------

* ``T_d``, kept parts and posts: ``kFlux`` (FP32 in an FP32 run).
* ``riemann.pstar``: ``kGauge``, FP64 in every precision.
* Step field, boundary sums and monitor amounts: ``kRegister`` and
  ``kReduction``, FP64 except on MPS. A post is cast once, inside
  ``end_stage`` (step) or inside the post (amount).
* AAM full still refuses FP32 at the pin (``:993-995``). R does not assume
  that stays (A's G10).
* **Hypothesis:** FP64 accumulation of FP32 stage totals changes no FP32
  state bit, because the state update still uses ``du`` from ``T_d``.


7. CUDA-graph contract
----------------------

* Storage is fixed at ``reset()``, from X's ``StateStore``. Addresses are
  part of X's ``store_generation``.
* ``c_s`` is a host double fixed per stage, baked into a stage graph.
  ``dt`` is a host double (X's ``GraphKey``).
* Posts, ``scale``, ``replace`` and ``end_stage`` are device ops. The
  exchange inside ``reconcile`` is X/S's pack, host, unpack.
* No host read: the monitor is read only in X's step-end read.
* ``post_split`` runs outside stages, in X's step-start and step-end phases.


8. Cross-repository interface changes and merge order
-----------------------------------------------------

* pyharp: none. R reads ``harp::IntegratorWeight``
  (``integrator.hpp:20-29`` at pyharp main ``6bc01d53``).
* kintera, commux: none.
* Merge order (snapy):

  1. R-1, the register with no reader, posts equal to today's buffers
     (G-R1);
  2. C's sweep posts and EF's limiter posts;
  3. I's ``vic.*`` and gravity work on the register;
  4. A's sources by phase and ``riemann.central``;
  5. O's consumers;
  6. deletion of the fixer, cell path and AAM leftovers.


9. Line budget
--------------

Every range was read at the pin. Each count is ``b - a + 1``. No range is
counted twice: the overlaps checked are listed after the table.

.. list-table:: Deletions from R's files, counted once
   :header-rows: 1

   * - group
     - ranges
     - lines
   * - D1, moved to C
     - ``:291-368`` (78), ``:417-504`` (88), ``:668-820`` (153),
       ``hydro.cpp:605-872`` (268)
     - **587**
   * - D2, EF's block
     - ``:858-866`` (9), ``:1154-1252`` (99)
     - **108**
   * - D3, gravity work (fixer, cell path, explicit block to I's
       ``GravityWork``)
     - ``:1412-1537`` (126), ``:575-580`` (6), ``:846-849`` (4),
       ``:1584-1598`` (15), ``:1608`` (1), ``:1682-1693`` (12);
       ``hydro.cpp:122-145`` (24), ``:287-293`` (7), ``:322-327`` (6);
       ``hydro.hpp:273-274`` (2), ``:296-314`` (19), ``:480`` (1)
     - **223**
   * - D4, AAM to A
     - ``:989-1003`` (15), ``:1108`` (1), ``:1141`` (1), ``:1288-1298``
       (11), ``:1316-1363`` (48), ``:1390-1391`` (2), ``:1624-1680`` (57);
       ``hydro.hpp:53-55`` (3), ``:89-133`` (45), ``:219-236`` (18),
       ``:462-466`` (5); ``hydro.cpp:27-37`` (11), ``:55-76`` (22);
       ``hydro_options.cpp:56`` (1), ``:68-79`` (12), ``:175-176`` (2)
     - **254**
   * - D5, x1 seam block to ``replace()`` and S
     - ``:868-946`` (79)
     - **79**
   * - **total**
     -
     - **1,251**

Sums: 78 + 88 + 153 + 268 = 587. 9 + 99 = 108.
D3: 126 + 6 + 4 + 15 + 1 + 12 = 164 in ``hydro_forward.cpp``;
24 + 7 + 6 = 37 in ``hydro.cpp``; 2 + 19 + 1 = 22 in ``hydro.hpp``;
164 + 37 + 22 = 223.
D4: 15 + 1 + 1 + 11 + 48 + 2 + 57 = 135; 3 + 45 + 18 + 5 = 71;
11 + 22 = 33; 1 + 12 + 2 = 15; 135 + 71 + 33 + 15 = 254.
Total: 587 + 108 + 223 + 254 + 79 = 1,251.

**Overlaps checked.**

* D3's ``bflux1`` seam lines ``:902``, ``:907``, ``:917`` lie inside D5, so
  they are counted in D5 only.
* ``:988`` is the (3.A) heading, not AAM, and stays. A's table counts
  ``:988-1003``, 16 lines.
* C's ranges end at ``:820`` and ``hydro.cpp:872``, and touch no other
  group. D2 ``:858-866`` and D5 ``:868-946`` are disjoint. D4 ``:1624-1680``
  and D3 ``:1682-1693`` are disjoint.

**Reconciling the reported counts.**

* **Gravity-work fixer and cell path: 142.** That is D3 without the
  explicit face-work part of ``:1412-1537``.

  * Inside the block: ``:1416-1417`` (2), ``:1426-1434`` (9),
    ``:1505-1534`` (30), ``:1536`` (1), so 42.
  * Outside the block: ``:575-580`` (6), ``:846-849`` (4), ``:1584-1598``
    (15), ``:1608`` (1), ``:1682-1693`` (12), plus ``:902``, ``:907``,
    ``:917`` (3), so 41.
  * ``hydro.cpp`` 37 and ``hydro.hpp`` 22.
  * 42 + 41 + 37 + 22 = 142.

  The reported 112 (the earlier lane R draft), 133 (Xinyue) and 236
  (Linfeng) could not be reproduced: their ranges were not available to me.
  **Hypothesis:** 236 includes ``meshblock.cpp`` lines, which are outside R's
  files. ``I.rst`` section 9 lists ``meshblock.cpp:997-1003, 1036-1109,
  1336-1337``, 83 lines; 236 - 83 = 153 is not my 142, so this is
  unconfirmed. R counts only its own files. The meshblock lines are X/mesh's
  to count.

* **AAM options: 50.**

  * Jiachen's 47: ``hydro.hpp:53-55`` (3), ``:89`` (1), ``:106-133`` (28),
    ``:224`` (1); ``hydro_options.cpp:56`` (1), ``:68-79`` (12), ``:176``
    (1). 3 + 1 + 28 + 1 + 1 + 12 + 1 = 47. Checked line by line: all are
    AAM option lines.
  * Linfeng's 12 + 3: ``hydro_options.cpp:68-79`` (12, inside Jiachen's) and
    the closure check ``hydro.cpp:67-69`` (3, not in Jiachen's).
  * Union: 47 + 3 = 50.
  * Both are inside D4 (254). D4 also counts the transport documentation
    ``hydro.hpp:90-105``, the accessors and state, the mode predicates, the
    ``central`` lambda and step 8, because A moves all of AAM out of Hydro
    (``A.rst`` section 2.2 lists 237 lines in R's files and does not count
    them in A's baseline). 237 - 1 (``:988``) + 3 + 1 + 12 + 2 = 254.

**After (estimate, not code).**

.. list-table::
   :header-rows: 1

   * - item
     - lines
   * - baseline
     - 3,493
   * - deletions D1-D5
     - -1,251
   * - kept, unchanged or edited in place
     - 2,242
   * - register and monitor (``flux_register.hpp`` about 120, ``.cpp``
       about 260)
     - +380 (estimate)
   * - stage-driver calls: C sweep about 40, EF about 15, seam about 12,
       gravity about 30 (``I.rst`` section 9), sources and implicit about 23
     - +120 (estimate)
   * - **after**
     - **2,742 (estimate) against the 2,794 ceiling: 52 to spare**

**Conditions.**

* D3 depends on I refusing ``gravity-work: cell`` (``I.rst`` section 3,
  decision 1).
* D4 depends on A moving AAM out of Hydro.
* Without D4: 2,742 + 254 = 2,996, which is over the ceiling.

**Margin candidate, not counted.** The seven 6-line verbose timing blocks
outside D1-D5 (``:505-510``, ``:850-855``, ``:1112-1117``, ``:1145-1150``,
``:1299-1304``, ``:1547-1552``, ``:1610-1615``), 42 lines. X's
``StageExecutor::report()`` would replace them if it reported per-op time.
That needs X's agreement.


10. Migration
-------------

1. **R-1**: the register and monitor. ``_flux1/2/3`` become views of
   ``T_d``, with no reader changed (bitwise, G-R1).
2. **R-2**: C posts through ``slot``/``post_slot``. ``central`` is a kept
   part. ``:997-1003``, ``:1108`` and ``:1141`` are deleted (G-R8).
3. **R-3**: EF posts (``add``/``scale``). ``fadv``/``fsed1`` and
   ``f1_pre`` are deleted (bitwise on species rows, G-R1).
4. **R-4**: the seam ``replace()`` with S's exchange; D5 is deleted (G-R2).
5. **R-5**: I's ``vic.*``. Gravity work reads the register; D3 is deleted
   after I refuses ``cell`` (G-R7).
6. **R-6**: A's ``pre_implicit``/``post_implicit`` sources and
   ``AxialClosureFixer : Fixer``; D4 is deleted.
7. **R-7**: O's consumers on the monitor and step field (G-R4).

Each step is one PR and keeps every existing test (``tests/CMakeLists.txt``).


11. Open questions to other lanes
---------------------------------

* **A (Jiachen):** K4, confirm that "post-terrain" means post-immersed-solid
  (``:1090``). Confirm that A moves all 254 lines of D4, including the
  transport documentation ``hydro.hpp:90-105``. Use namespace ``snap``.
* **EF (Zoey):** keep your own settling buffer, or request
  ``sedimentation@1``? Use namespace ``snap``.
* **I (Xinyue):** the 133-line count's ranges, to reconcile with R's 142.
  Confirm ``vic.mass_clamped`` as a floor amount. Gate G-R7 for energy.
* **X (Xi):** K2: is the stage table at ``reset()`` acceptable? Who counts
  the ``meshblock.cpp`` fixer lines (83, by I's ranges)? Can ``report()``
  carry per-op time (margin candidate)?
* **C (Tianhao):** rev 5 switches positivity to ``scale()`` (K1) and uses
  ``slot``/``post_slot``/``keep``.
* **S (Xinyue):** the seam exchange carries the ``T_1`` rows,
  ``riemann.pstar``, ``pressure_base1`` and the kept x1 parts, as the pin's
  ``pack`` does (``:903-912``).
* **O (Jiachen):** none open. L-1 to L-6 are answered in 4.2.


12. Skeleton index
------------------

.. list-table::
   :header-rows: 1

   * - file
     - lines
     - declares
   * - ``docs/v3/skeleton/R/flux_register.hpp``
     - 118
     - ``RegisterPhase``, ``RegisterRequest``, ``FluxRegister``,
       ``RegisterMonitor``, ``Fixer``
   * - ``docs/v3/skeleton/R/hydro_stage.hpp``
     - 72
     - ``StageInputs``, ``HydroStage``
   * - **total**
     - **190**
     - under the 300-line limit
