V3 lane I: vertical implicit solver and gravity work
=====================================================

:Lane: I (vertical implicit solver and gravity work)
:Owner: Xinyue Wang (alternate: Tianhao Le)
:Revision: 2.3 (section 11 brought up to date: every question to lanes A, C,
           S and X answered and closed; lane R's confirmation and rev 2.4
           recorded; X's answers applied to sections 6, 7 and the skeleton). Revision 2.2: Tianhao's two rev 2.1 findings: the gravity-work remainder
           moves to ``post_implicit``; ``vic.momentum_t@1`` is the third kept
           part). Revision 2.1: re-cite to lane R's frozen header; backup owner Zoey Hu from
           18:00 EST 2026-11-17, while Xinyue is rate limited). Revision 2:
           lane R's provisional header, Cheng's rulings, Tianhao's 15 notes.
:Pin: chengcli/snapy ``9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410``

Every ``file:line`` below is at the pin unless it says otherwise. Lines
cited for #369 are at that PR's head
``c382f0da7b84dbc14219053758054f874669cc84`` (open, merge base
``cbf86830``). A claim I have not tested is marked **hypothesis**. A change in
results beyond round-off is marked **FOR CHENG** until Cheng rules. The
section titles and the register requirements R1-R10 follow the brief as
Cheng resent it in the lane I thread. Gates and costs are specified here,
not run: this round is design only.

**Lane R's header.** Section 4 and the skeleton use the names and
signatures of lane R's **frozen** register header,
``docs/v3/skeleton/R/flux_register.hpp`` rev 4.2, with ``hydro_stage.hpp``
and ``docs/v3/design/R.rst`` rev 2.2, at happysky19/snapy ``v3-design/R``
``4c59162ae37080d0ab307b2823742b44f46da7c3`` (checked with ``git ls-remote``). They are cited below as
``R.hpp:<line>`` and ``R.rst:<line>``. Revision 2 was written against the
provisional headers rev 1 and rev 1.1. Revision 2.1 moves every citation
to the frozen header and applies what changed for lane I:

#. ``cell_amount(name, vol_du, stage_weight, AmountKind kind)`` takes four
   arguments (``R.hpp:67-70``). ``stage_weight`` is ``w2_s`` for an amount
   of this stage's ``du``, and ``1.0`` for a change already applied to
   ``u``.
#. Phase ``implicit`` is: the ``add()`` posts, then ``keep()``, then the
   ``cell_amount()`` calls (``R.hpp:20``; ``R.rst:478-485``).
#. ``vic.momentum_t.top`` is ``AmountKind::diagnostic`` (``R.hpp:30``), and
   ``apply_prescribed(1)`` runs first in ``post_implicit`` (``R.hpp:21``;
   ``R.rst:485-487``).
#. ``begin_stage(int, harp::IntegratorWeight const&)`` (``R.hpp:49``).
   There is no ``StageWeights``, and ``reset`` takes no stage table
   (``R.hpp:43-44``).
#. ``flag_retry(cause, any)`` writes the retry cause (``R.hpp:78``): lane
   I's is ``"implicit.column"`` (``R.hpp:37``; ``R.rst:1251-1262``). The
   "what changes" row for question (c) stays (section 10(c);
   ``R.rst:1264-1285``).

It also takes in Tianhao's answers. ``vic.mass_dry`` is a second kept part.
The scheme-9 top value of ``vic.momentum_t`` is minus the column sum. A
solve direction ``dir`` (0-based in the kernels) posts to register dim
``d = dir + 1``.

**Rulings (Cheng's decision, 2026-11-17).** (a) ``gravity-work: cell`` is
removed. (b) The global gravity-work fixer is removed. Both are settled
design below. (c) The per-column FP64 retry is still open: it stays as
proposed and keeps its FOR CHENG row in section 10.

.. contents::
   :local:
   :depth: 1


1. Scope and pins
-----------------

**Scope.** Lane I covers ``src/implicit/*`` (12 files),
``src/hydro/gravity_work.hpp``, ``src/hydro/gravity_work_radial.hpp`` and
``src/forcing/const_gravity.cpp``. In revision 2 it also takes
``src/math/lubksb.h`` (71) and ``src/math/ludcmp.h`` (95), which lane O
moves into ``src/implicit``; their only includer is
``implicit/forward_sweep_impl.h:14-15`` (section 9). The lane reads its
callers but does not own them: ``src/hydro/hydro_forward.cpp:1412-1690``,
``src/hydro/hydro.cpp:479-549`` and ``src/mesh/meshblock.cpp:1036-1110``.

**Pins.**

- snapy ``9e5de2d4`` (checked with ``git rev-parse``).
- #369 ``c382f0da`` (open). It is the only open PR this lane builds on.

**The brief's numbers, checked at the pin.**

.. list-table::
   :header-rows: 1

   * - number
     - brief
     - at the pin
     - command
   * - ``src`` lines
     - 42,677
     - 42,677, confirmed
     - ``git ls-files 'src/*.cpp' 'src/*.hpp' 'src/*.h' 'src/*.cu' 'src/*.cuh' | xargs cat | wc -l``
       (all tracked files give 43,629: that also counts ``CMakeLists.txt`` and ``*.cpp_``)
   * - lane baseline
     - 2,655
     - 2,655, confirmed (2,337 + 26 + 224 + 68)
     - ``wc -l src/implicit/* src/hydro/gravity_work.hpp src/hydro/gravity_work_radial.hpp src/forcing/const_gravity.cpp``
   * - ``.item<>``
     - 103
     - 103 lines (105 occurrences), confirmed
     - ``grep -E '\.item<' <C++ files above> | wc -l``
   * - hard FP64 dtype
     - 135
     - 135 only with ``torch::kFloat64|torch::kDouble|at::kDouble|kFloat64``. ``kFloat64`` alone gives 134. ``kFloat64|kDouble`` gives 136, because it also counts ``c10::kDouble`` at ``src/coord/coordinate.hpp:405``.
     - ``grep -E`` with the pattern on the left
   * - ``set_``/``set_data``
     - 41
     - 41 only with ``\.set_|set_data``. That pattern counts 3 comment lines in ``src/utils/tensor_cast_cache.hpp`` and misses ``p->set_(v)``. ``(\.|->)set_(data)?\(`` gives 39 real calls.
     - ``grep -E`` with the pattern on the left

In the lane's own files: 7 ``.item<>`` lines (one of them commented out, at
``implicit_hydro.cpp:205``), 11 FP64 literals and 2 ``set_data`` calls
(``implicit_hydro.cpp:157,183``).

**Not checked.**

- ``gh`` has no valid credentials for the API here. I read the PRs through
  the public REST API (bodies) and their squash commits on main, and #369
  through its fetched head.
- The Slack threads 1794169013.322299 (gravity-work booking) and
  1794212148.557499 (amplification analysis) and the earlier implicit
  inventory were not readable. I could not reproduce the inventory's "191
  copy lines" in the partial/full Jacobian pair. My own count:
  ``vic_assemble_full_impl.h`` has 118 lines, and 68 of them also appear in
  ``vic_assemble_partial_impl.h`` (206 lines). The assembly drivers add
  ``implicit_dispatch.cpp:24-137`` (114 lines) and ``.cu:32-143`` (112).


2. Concepts and current sites
-----------------------------

**VIC.** The vertically implicit correction solves the x1 column linearised
about the stage state. Its 3x3 (partial: rho, m1, E) or 5x5 (full) block
tridiagonal system is ``(I/dt + J) dq = du/dt``. J is built from Roe ``|A|``
and the flux Jacobians.

**Gravity work G.** G is the energy the x1 mass transfer gains or loses in
the potential :math:`\Phi=-g_1 x_1`. It has two parts: the face work W and,
where the grid has an x1 measure, the corrected-PE work K (#297, #345).
Section 4 defines it.

**Wall and solid rows.** These are the column ends: reflecting walls and
solid surfaces. **Well-balanced reference.** This is the hydrostatic part
taken out of the explicit RHS.

Current sites:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - concept
     - sites at the pin
   * - stage call, stage-weighted operator dt
     - ``hydro_forward.cpp:1554-1616`` (dt weight ``:1568-1583``, rk with 3 or more stages only)
   * - FP32/FP64 boundary, whole-block FP64 retry
     - ``hydro.cpp:502-543``
   * - frame projection / de-projection
     - ``implicit_hydro.cpp:254-259`` / ``:558-561``
   * - grid caches (three copies of one set of factors)
     - ``implicit_hydro.cpp:262-294`` (``_g_*``), ``implicit_hydro.hpp:127-133`` (``_rx_*``), ``hydro.hpp:434`` (``_pe_work``)
   * - matrix choice, a bit test of ``scheme``
     - ``implicit_hydro.hpp:36-42``, ``implicit_hydro.cpp:97-111, 427, 489``
   * - face-work flag bits in ``dir``
     - ``implicit_dispatch.hpp:32-35``, ``implicit_hydro.cpp:330-337``
   * - Jacobian assembly, partial / full
     - ``vic_assemble_partial_impl.h:42-200`` / ``vic_assemble_full_impl.h:17-112``
   * - gravity-work rows of the energy row
     - ``vic_gravity_work_impl.h:23-48``; corrected-PE rows ``implicit_hydro.cpp:365-425``; Woodbury wall third points ``:436-472``
   * - solve, back-substitution, redistribution
     - ``forward_sweep_impl.h:29-132``; ``vic_redistribute_impl.h:30-225``
   * - post-solve gravity-work remainders
     - projection/clamp ``implicit_hydro.cpp:522-556``; corrected-PE ``:569-594``
   * - host reads in the stage
     - ``implicit_hydro.cpp:477, 479, 485, 487``; ``implicit_hydro.hpp:104``; ``implicit_dispatch.cpp:255``; ``hydro.cpp:530``
   * - device failure latch
     - ``implicit_hydro.cpp:599-615``; read in ``check_redo`` at ``meshblock.cpp:1549-1551``
   * - explicit face work (two formulas) and corrected-PE work
     - ``hydro_forward.cpp:1447-1452`` (Cartesian, ``gravity_work.hpp:12-24``), ``:1453-1465`` (curved), ``:1470-1495`` (K)
   * - ``gravity-work: cell`` (non-Riemann flux split, Roe-diffusion work)
     - ``const_gravity.cpp:28-32``; ``hydro_forward.cpp:579-580, 846-849, 902, 907, 917, 1426-1434``; ``vic_gravity_work_impl.h:37-41``
   * - global E+PE fixer
     - ``const_gravity.cpp:33-38`` (lane I); lane R: ``hydro.hpp:273-274, 296-314, 480``, ``hydro.cpp:126-135, 138-145, 287-293, 322-327``, ``hydro_forward.cpp:1416-1417, 1507-1533, 1584-1598, 1608, 1682-1693``; lane X: ``meshblock.hpp:217-222``, ``meshblock.cpp:724-730, 993-1004, 1036-1110, 1336-1337, 1477, 1502``, ``mesh.cpp:363, 384-402`` (section 10, table)
   * - readers of the implicit transfers
     - Coriolis/metric m1 ``hydro_forward.cpp:1637-1653`` (#355); AAM ``:1668-1669``; tracer donor transfer ``meshblock.cpp:786-806``
   * - solid and wall rows
     - ``implicit_dispatch.cpp:118-130, 216-235``; ``vic_assemble_full_impl.h:107-111``; ``implicit_hydro.cpp:405-420``; #369 surface rows ``_rs_*``
   * - well-balanced reference in the RHS
     - ``hydro_forward.cpp:837, 1380-1382, 1394-1400``; operator gravity ``implicit_hydro.cpp:326-329``

Default: ``gravity-work: face`` since #303 (``const_gravity.cpp:28``). No
``*.yaml`` file in the repository sets ``gravity-work``
(``grep -rln gravity-work --include=*.yaml examples tests`` is empty), so
every shipped deck runs ``face``.


3. Target design
----------------

**Decisions.**

#. **One gravity-work form, the default and the only choice.** It is the
   face work W plus the corrected-PE work K, with K = 0 where the grid has no
   measure (cylindrical, ``X1Measure::none``: plain face work and a warning,
   as now). Its operator row is generated from the booked work (section 4).
   ``gravity-work: cell`` is refused, and the global fixer is removed.
   **Settled: Cheng's decision, 2026-11-17** (rulings (a), (b)). Why:

   - it is what every shipped deck runs;
   - E+P closes by construction (#297, #345);
   - the fixer that ``cell`` needs has a documented tall-column instability
     (#284 "Limit", #285 "Limits") and adds a global reduction per step.
#. **``scheme`` is no longer a bit field.** Only 0, 1 and 9 are accepted
   (``implicit_hydro.cpp:97-111``), and bit 3 is the only bit with a
   meaning. V3 has ``enum class VicMatrix {partial = 3, full = 5}``.
   ``implicit-scheme: 1 | 9`` maps onto it in ``from_yaml``; 0 means no
   module. With one gravity form, the ``dir`` flag bits disappear and
   ``dir`` is the direction again, inside ``VicParams``.
#. **One Jacobian assembly.** The partial kernel copies {IDN, IVX+dir, IPR}
   out of the same 5x5 ``Am``, ``Ap`` and ``FluxJacobian`` objects the full
   kernel uses (``partial:80-137`` against ``full:52-88``). Its ``Phi``
   and ``Bnd`` are restrictions of the full ones (``partial:70-74``,
   ``full:39-46``). The block sums are entrywise (``partial:144-149``,
   ``full:95-100``). So V3 assembles 5x5 once and, for N = 3, restricts
   and folds the tangential momenta (``partial:159-199``) under
   ``if constexpr``.
#. **Wall and solid rows live in the column operator**, through one
   ``ColumnSegments`` per block. Its scope (Tianhao's note 15):

   - The general case is any solid mask. Each column holds its list of fluid
     runs, as the pin's redistribution already walks them
     (``implicit_dispatch.cpp:216-235``). Solids at the top or in strides
     are supported at the pin (``tests/test_implicit_stratified_solid.py:99``)
     and stay supported.
   - The single-segment fast path is taken when every column has one fluid
     run that reaches the top wall: no solid, or #369's per-column floor
     from ``X1Wall`` depth. Only in that path are the corrected-PE wall
     rows the Woodbury rows at ``k0`` (first fluid cell, #369) and
     ``k1 = nx1 - 1``.
   - Any other shape keeps the pin's per-cell masking of the K rows
     (``rx_fluid``, ``implicit_hydro.cpp:405, 412-420``) with Woodbury at
     the physical wall cells, unchanged (**hypothesis**: bitwise).

   The assembly flags, ``k0``/``k1`` and the per-depth ``GravityWork`` rows
   all read ``ColumnSegments``. **Ownership (rev 2.3, agreed with lane
   S):** ``ColumnSegments`` is lane I's type. It owns the surface rows and
   ``k0``/``k1``. Lane S keeps the face set, ``PrescribedFaces``
   (``seam_register.hpp:69-86`` at jihenghu/snapy ``v3-design/S``
   ``c505fb879a841a9a5a17736b3f4d2826d6081ecf``). Both are built from the
   same solid mask and mask version. S rev 2 defines none of
   ``ColumnSegments``, ``X1Wall``, ``k0`` or ``k1`` (checked by grep);
   ``X1Wall`` is #369's and not at the pin.
#. **No reference row** in the operator. A contract test replaces it
   (section 5).
#. **One kernel definition.** The plumbing that is duplicated across 9
   CPU and 9 CUDA stubs becomes one ``vic_stage<Launch>`` template.
   ``CpuColumns`` (also used for MPS through ``OnHost``) and
   ``CudaColumns`` instantiate it. Two stubs remain: ``vic_stage`` and
   ``donor_cap``.

**Types and ownership.**

.. list-table::
   :header-rows: 1

   * - type (skeleton)
     - owner
     - holds
   * - ``GravityWork`` (``gravity_work.hpp``)
     - ``HydroImpl``, one per block
     - grid-only coefficients of G; ``apply``, ``apply_seam``, ``rows``, ``potential``
   * - ``VerticalImplicitImpl`` (``vertical_implicit.hpp``)
     - ``HydroImpl`` (submodule ``icorr``)
     - options, ``ColumnSegments``, scratch, per-column and block ``status``, meters
   * - ``VicIncrement``
     - ``VerticalImplicitImpl``; its face fields are posted to lane R's ``FluxRegister`` in phase ``implicit``
     - face transfers (dry mass, species, tangential momenta under both matrices), the kept ``vic.mass_total``, monitor amounts (``vic.cell``, ``vic.mass_clamped``)
   * - ``ColumnSegments``
     - ``VerticalImplicitImpl``, rebuilt per solid-mask version
     - fluid runs per column, the single-segment flag, ``k0``/``k1``
   * - ``VicParams``, ``VicColumn``, ``vic_stage`` (``vic_kernels.hpp``)
     - ``src/implicit`` dispatch
     - kernel scalars, unpacked per-column operands, the launcher template

**Data flow of one stage** (the solve's position in the stage does not
change):

.. code-block:: text

   phase sweep..divergence (C, R): riemann, sedimentation, seam replace,
          positivity; du += div(total)            [R.hpp:14-18]
     |
   phase pre_implicit: forcings (w-free Coriolis rows into du, #355);
          GravityWork.apply(total(1) mass rows) = G[M_exp] -> du_E
     |
   phase implicit: VerticalImplicit::forward(du, w, gamma, dt, gw, reg)
          assemble(N; rows()) -> solve (+Woodbury, per column)
          -> redistribute -> de-project
          -> reg.add(1, "vic.mass_dry" | "vic.mass_species" | "vic.momentum_t")
             (each add also fills its requested part: vic.mass_dry@1, vic.momentum_t@1)
          -> reg.keep(1, "vic.mass_total")
          -> reg.cell_amount("vic.cell", Vdu, w2_s, cell_source),
             ("vic.mass_clamped", .., flux_correction), ("vic.momentum_t.top", .., diagnostic)
          -> per-column status (device); reg.flag_retry("implicit.column", any)
     |
   phase post_implicit (A, I, R): apply_prescribed(1) first, on the total and
          every x1 kept part (R.rst:486-488); then, in the pin's order:
          I's remainder G[kept vic.mass_total] - R dq -> du_E;
          A's m1 from total(1); axial source from kept vic.momentum_t;
          tracer transfer from kept vic.mass_dry
     |
   end_stage: S = w1 S + w2 dt T -> FP64 step accumulator (R.hpp:85)


4. Flux-register contract
-------------------------

**Calls and phase.** Lane R's header gives the phases (``R.hpp:14-23``)
and the calls (``R.hpp:41-88``). The solve runs in phase ``implicit``
(``R.hpp:20``: "add() posts, then keep(), then cell_amount()"), after
``pre_implicit``, where the gravity work reads the limited x1 total
(``R.hpp:19``). Its readers run in ``post_implicit`` (``R.hpp:21``), after
``apply_prescribed(1)`` (``R.rst:486-488``): lane I's gravity-work
remainder, lane A's m1 rows and axial source, and the tracer transfer. Lane I uses ``add`` for posts, ``keep``
for a kept part, and ``cell_amount`` for monitor amounts. It uses no
``slot``/``post_slot`` (those are for the first post of a stage, the
Riemann flux), no ``scale``, no ``replace`` (the solve posts no seam face,
R5) and no ``post_split``. Register dims are 1..3 for x1..x3; a solve
direction ``dir`` (0-based) posts to ``d = dir + 1``, so the vertical solve
posts to ``d = 1`` (Tianhao; ``R.rst`` 4.2 row 38, "dim numbers",
accepted).

**Posts** (phase ``implicit``, in this declared order):

.. list-table::
   :header-rows: 1
   :widths: 26 30 44

   * - name and call
     - rows, quantity
     - source at the pin
   * - ``vic.mass_dry``: ``reg.add(1, "vic.mass_dry", {IDN}, f)``
     - dry-gas x1 face transfer after the availability clamp
     - ``vic_redistribute_impl.h:119-147`` (``MASS(IVX+(dir+1)%3)``)
   * - ``vic.mass_species``: ``reg.add(1, "vic.mass_species", {ICY..ICY+ny-1}, f)``
     - species x1 face transfers after the clamp
     - ``vic_redistribute_impl.h:156-175``
   * - ``vic.momentum_t``: ``reg.add(1, "vic.momentum_t", {IVY, IVZ}, f)``
     - tangential-momentum x1 face transfers, **both matrices**: donor
       transfers under scheme 1; the prefix sum from the bottom wall of the
       solve's tangential cell increments under scheme 9, as
       ``gnomonic_equiangle.cpp:536-545`` builds them today
     - scheme 1 ``vic_redistribute_impl.h:186-201``; scheme 9
       ``vic_redistribute_impl.h:217-218`` (``delta(2), delta(3)``)

**Kept parts** (three, all on x1; ``R.rst:167, 187, 479-481``): ``vic.mass_total``,
``vic.mass_dry`` and ``vic.momentum_t``.

``vic.mass_total`` through ``reg.keep(1, "vic.mass_total",
f)``, requested as ``"vic.mass_total@1"`` (``R.hpp:35, 66``;
``R.rst:166-167, 482``). It is the
dry + species total each face moved after the clamps
(``vic_redistribute_impl.h:88-89, 144, 172``). The gravity-work remainder
reads it in ``post_implicit``, after ``apply_prescribed(1)``, and lane I
checks that it equals the sum of the two mass posts.
``vic.mass_dry`` is a **second kept part** (Tianhao): lane I requests
``"vic.mass_dry@1"``. The tracer donor transfer needs the implicit dry
transfer alone (``meshblock.cpp:786-806``). The ``add`` of ``vic.mass_dry``
copies its rows into the requested part in the same call (``R.hpp:56``;
``R.rst:479-481``), so no separate ``keep`` is made for it.
``vic.momentum_t`` is the **third kept part**: lane I requests
``"vic.momentum_t@1"`` (``R.rst:167, 187, 479-481``; R rev 2.3
``2b4c5775`` ``R.rst:207, 227``). Its ``add`` fills the part in the same call. Lane A's
axial source reads it per face in ``post_implicit``. Under scheme 9 that
includes the top face, whose value is also the ``diagnostic`` amount
``vic.momentum_t.top``.

**Monitor amounts**, through ``reg.cell_amount(name, V du, stage_weight,
kind)`` (``R.hpp:67-70``), made after the posts and the ``keep``. Revision
1's ``vic.cell`` and ``vic.mass_clamped`` were posts; lane R's header makes
them monitor amounts, and lane I adopts that:

- ``vic.cell`` (``AmountKind::cell_source``, ``stage_weight = w2_s``,
  because it is part of this stage's ``du``; ``R.rst:488-494``):
  :math:`V_i(du_i - du_{0,i})` for the rows that are not face
  transfers: x1 momentum, energy without gravity work, and under scheme 9
  the tangential momenta. The solve still writes ``du`` itself
  (``vic_redistribute_impl.h:205-225``), so nothing reads this as a field.
  It is no correctness loss: the only per-cell reader of the correction
  outside lane I is the ``implicit`` output diagnostic
  (``output/load_diag_output_data.cpp:220-221``). It keeps
  ``correction()`` as an output-only accessor (lane O), not a register
  read.
- ``vic.mass_clamped`` (``AmountKind::flux_correction``, ``stage_weight =
  w2_s``): :math:`V_i` times the divergence of (moved - requested), with
  the code's sign (``implicit_hydro.cpp:527-528``: ``moved =
  _mass_corr[IVZ] - requested``). Revision 2 called it a floor amount;
  lane I confirms lane R's classification (``R.rst:499-502``; section 11).
  The posted transfers are already the clamped ones, so its effect is
  inside ``boundary(1)``, and it is reported, not re-added. The
  gravity-work remainder needs no per-face clamp field, because it reads
  the kept ``vic.mass_total``.
- ``vic.momentum_t.top`` (scheme 9 only; ``AmountKind::diagnostic``,
  ``R.hpp:30``): the top-face value of the bottom-up prefix sum, which is
  **minus the column sum** (Tianhao). At the pin ``Phi = -T.cumsum(-1)``
  with :math:`P = 0` at the bottom face (``gnomonic_equiangle.cpp:539-542``).
  It is made as an amount in ``implicit``, before ``post_implicit``, so it
  never reads the prescribed total (``R.rst:505-519``). **Hypothesis:** it is not zero under scheme 9, because the w-free
  Coriolis rows pass through the solve (#355). It is posted as the top face
  of ``vic.momentum_t``, exactly as today's ``axial_x1_source_`` uses it
  (``gnomonic_equiangle.cpp:541-544``), so lane A reads the same values,
  and it is also reported here so that the monitor's x1 boundary sum is
  explained.

**Energy.** Energy stays in ``vic.cell``. It becomes a face transfer
``vic.energy`` only if the column residual of the linearised wall flux is
round-off; the mass row shows such a residual, removed in proportion to mass
(``vic_redistribute_impl.h:65-71``). That condition is a **hypothesis**, as
lane R records it (``R.rst:521-523``). Lane R's gate G-R7 decides it: the
per-column residual on #369's rest deck below 1e-13 relative, else energy
stays ``vic.cell`` (``R.rst:1331-1334``). That gate is specified, not run. The x1
momentum has a gravity source and wall pressure, so it is never a
telescoping face transfer.

**Frame and units** (Tianhao's note 14, ``R.hpp:4-5``). The two cells
across an x1 face share (j, k), so the cell frame is the face frame. Posts
are made after ``flux2global1_`` (``implicit_hydro.cpp:561``), in the
explicit x1 flux's global components. The solve computes its transfers
integrated over area and the stage, in mass per stage
(``vic_redistribute_impl.h:82-89``), with the stage's full ``dt``: today
``hydro_forward.cpp:1641, 1646`` adds ``mc[IVZ] / dt`` to ``area * f1``,
not ``/ dt_corr``. Each face field is posted as a flux density per unit
face area per unit time at the step ``dt``, **before stage weights**:
:math:`f = M_f / (A_f\,\Delta t)`, with ``face_area1``. That is lane C's
``riemann`` convention and the header's (``R.hpp:4-5``). Lane I applies no
weight. ``end_stage`` runs :math:`S = w_1 S + w_2\,\Delta t\,T` with the
posts in ``T`` (``R.hpp:85``), into the step accumulator, ``kRegister``:
FP64, FP32 on MPS (``R.rst:1372-1378``). Monitor
amounts are volume-integrated per stage. **Hypothesis:** no x1 face the
solve posts has :math:`A_f = 0`. A spherical-polar face at r = 0 would; lane
I would post zero there and set the column's status bit, which is unchecked.

**Reads.**

- ``GravityWork::apply`` reads ``reg.total(1)`` mass rows (IDN + species)
  in ``pre_implicit`` for :math:`M^{\rm exp}`. The remainder reads
  ``reg.kept(1, "vic.mass_total")`` in ``post_implicit``, after
  ``apply_prescribed(1)`` and before lane A's m1 (``R.hpp:82-83``;
  ``R.rst:486-488``). It is booked by ``VerticalImplicit::book_remainder``
  (skeleton) from the solve's fixed ``du0`` (the pin's ``R dq`` uses ``du -
  du0``, ``implicit_hydro.cpp:564-594``).
  This replaces the rebuilt ``vertical_mass_flux1`` at
  ``hydro_forward.cpp:1422-1425``.
- In ``post_implicit``, after ``apply_prescribed(1)`` on the total and every
  x1 kept part (``R.rst:486-488``), and after the remainder: lane A's m1 reads ``reg.total(1)`` mass rows
  (explicit + vic, today ``hydro_forward.cpp:1637-1646``); the axial source
  reads the kept ``vic.momentum_t`` (today ``picorr->correction()``, ``:1668-1669``);
  the tracer transfer reads ``reg.kept(1, "vic.mass_dry")``.
- ``mass_correction()`` stops being public. ``correction()`` stays as an
  output-only accessor for the ``implicit`` diagnostic
  (``load_diag_output_data.cpp:220-221``, lane O).
- **Not read by the solve** (Tianhao's note 10). The VIC reads only the
  cell ``w``, the EOS ``gamma``, the solid mask and the explicit ``du``
  (``implicit_hydro.cpp:303-322``). It reads neither the Riemann face
  pressure p* nor the well-balanced reference: ``grep`` for
  ``face_pressure``, ``pressure_base``, ``rho_grav`` and ``_hydro_ref`` in
  ``src/implicit`` matches only a comment (``implicit_hydro.cpp:326``). The
  skeleton keeps that contract: ``VicColumn`` has no p* or reference
  operand. Changing it needs lane C's and lane I's agreement.
- **The non-hydrostatic ``rho_grav`` correction** (Tianhao's note 11).
  It is computed in the x1 sweep (``hydro_forward.cpp:825-832``), shifted by
  the split reference (``:834-838``) and, under ``SNAP_X1_CENTROID_EXACT``,
  rebuilt from p* (``:961-983``). It is applied at ``:1539-1545``. All of
  these lines are in ``hydro_forward.cpp``, outside lane C's moved ranges
  (C.rst §9: ``:668-820``), so they are lane R's. Lane I's gravity work reads
  ``rho_grav`` only in the cell work it subtracts when
  ``non-hydrostatic < 1`` (``:1500-1504``). So p* reaches gravity work
  indirectly, only on that switch path. The operator itself linearises the
  full gravity whatever ``non-hydrostatic`` is (``implicit_hydro.cpp:326-329``).

**Corrects.** Only the energy row: the gravity-work remainder after the
solve. It is the one place a booked energy depends on the registered
transfer.

**G as one function of the registered x1 mass** (W and K written apart,
Tianhao's note 6). With :math:`M_f` the x1 mass through face :math:`f` in
the stage and cell :math:`i` between faces :math:`l` and :math:`u`:

.. math::

   W_i[M] = \frac{g_1 (x_u - x_i)\,M_u - g_1 (x_l - x_i)\,M_l}{V_i},
   \qquad
   K_i[\Delta\rho] = g_1\sigma_i^2\, s_i[\Delta\rho] + g_1(r_{c,i}-x_{1v,i})\,\Delta\rho_i,

and :math:`G = W[M] + K[\Delta\rho]` with :math:`\Delta\rho_i = (M_l - M_u)/V_i`.

- W is ``gravity_work_from_face_mass`` (``gravity_work.hpp:12-24``). It is
  local to the two faces of a cell.
- K is ``corrected_pe_work`` (``gravity_work_radial.hpp:190-205``). The
  slope :math:`s_i` is the three-point stencil on cells :math:`i-1, i, i+1`,
  one-sided at the walls (``gravity_work_radial.hpp:76-98``). Its second
  term exists only on gnomonic-equiangle (``:172-176``).
- Written on :math:`M` through :math:`\Delta\rho`, K would reach four faces
  (a five-point row in cells). It is not written that way. **In the
  operator, K acts on the density unknown** :math:`\delta\rho` (column 0 of
  each block), which the continuity row gives directly. It enters as three
  bands on that column (``implicit_hydro.cpp:409-420``), plus the two
  one-sided wall third points by Woodbury (``:436-472``; per column under
  #369). The block tridiagonal structure is unchanged.
- The curved formula at ``hydro_forward.cpp:1453-1465`` equals W
  algebraically:
  :math:`[\Phi_i(M_u-M_l) - (\Phi_u M_u - \Phi_l M_l)]/V_i = [(\Phi_i-\Phi_u)M_u-(\Phi_i-\Phi_l)M_l]/V_i`.

Both parts are linear.

**The energy row equals the booked work by construction.** The operator's
energy row is :math:`R = R_W + R_K`:

- :math:`R_W = \sum_f (\partial W/\partial M_f)(\partial M^{\rm lin}_f/\partial\delta q)`,
  with the linearised transfer
  :math:`M^{\rm lin}_f(\delta q)=\Delta t A_f[\tfrac12(m_{f-}+m_{f+})-\tfrac12B^\rho_f(\delta q_{f+}-\delta q_{f-})]`
  (#288 derivation). The first factor is ``GravityWork::rows()`` face
  weights; the second is the mass row of the assembled ``|A|`` and flux
  Jacobians (``vic_gravity_work_impl.h:23-48`` receives them as
  ``am``/``ap``).
- :math:`R_K = \partial K/\partial \delta\rho`: the three K bands and the
  two wall third points of ``rows()`` on column 0.

The booked total for the stage is

.. math::

   G[M^{\rm exp}] + R\,\delta q + \big(G[M^{\rm imp}] - R\,\delta q\big)
   = G[M^{\rm exp}+M^{\rm imp}] = G[M^{\rm register}],

with :math:`M^{\rm imp}` the kept ``vic.mass_total``. The last bracket is the
one post-solve call. It vanishes wherever no clamp or projection acted. In
that case :math:`R_W\,\delta q = W[M^{\rm lin}(\delta q)]` and
:math:`R_K\,\delta q = K[\delta\rho]` with :math:`\delta\rho` the density
change the transfers make. It generalises #345's identity for K to W and K
together, and it replaces ``implicit_hydro.cpp:522-556`` and ``:569-594``.

**How the four PRs broke the pairing.** Each time the booked work gained a
term, the row was edited separately:

- **#284.** Face work was booked outside the operator while the matrix had
  the cell work. A tall rest column blew up at Courant about 66 (#283).
- **#285.** It put the Cartesian face work in the row. Curved grids still
  "linearize cell work and replace it after the solve" (#288 body).
- **#288.** It added curved weights. The matrix energy defect fell from
  6.64e-4 to below 3e-16.
- **#297.** It added K to the booked work but not to the row, so a rest
  column grew at Courant 197-250 (#296). The tridiagonal part entered the
  row in f256ab5, and the wall third points only in #345 (wall mode from
  :math:`N\Delta t\approx 119`-149 before).

**Ordering constraints** (lane R's phases, ``R.hpp:14-23``):

#. Explicit x1: ``riemann`` (``hydro_forward.cpp:845``), then sedimentation
   (``:861-866``), then the x1 seam replace (``:868-946``), then positivity
   (``:1154-1252``), then the divergence (``:1254``). This is the pin's order,
   with positivity after the seam average as at ``:1154-1164``. Only after
   all of it does ``pre_implicit`` book :math:`G[M^{\rm exp}]`.
#. The w-free Coriolis rows enter ``du`` in ``pre_implicit``, before the
   solve (#355 commit 6; ``hydro_forward.cpp:1378-1385``).
#. Every ``vic.*`` post and the ``keep`` are made before ``implicit`` ends,
   and so before any ``post_implicit`` reader (``hydro_forward.cpp:1618-1680``).
#. ``post_implicit`` starts with ``apply_prescribed(1)`` on the total and
   every x1 kept part (``R.rst:486-488``). Then lane I books the
   gravity-work remainder, and only then do lane A's m1, the axial source
   and the tracer transfer run. That is the pin's order for ``du[IPR]``:
   the remainder is added at ``implicit_hydro.cpp:551-555, 578-594`` and
   ``hydro_forward.cpp:1604, 1621``, before m1 at ``:1645-1653``.
   **Hypothesis:** reading the prescribed kept ``vic.mass_total`` changes
   the remainder at most by round-off at the top wall face. The pin's
   bottom-face transfer is exactly zero and its top face telescopes to
   zero up to round-off (``vic_redistribute_impl.h:70-71, 117``). A solid
   face is merged as the mirror in the assembly
   (``vic_assemble_partial_impl.h:38-39``).
#. Implicit posts are made after the divergence. They never enter ``du``
   through the register (``R.hpp:18``), because the solve writes ``du``
   itself. They do enter the stage total, which ``end_stage`` accumulates
   (R3). The solve's own ``dt`` stays stage-weighted for 3 or more stages
   (``hydro_forward.cpp:1568-1583``), unchanged.
#. A failed column posts zero transfers and sets its own status bit. The
   restore of ``du`` and ``w`` (``implicit_hydro.cpp:606-611``) happens
   before the post.

**Traceability to the ten register requirements.**

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - requirement
     - where lane I meets it
   * - R1 one owner, frame, area weighting
     - Lane I owns no face flux. The solve posts its transfers into the register (this section, "Posts") instead of keeping ``_mass_corr``. Frame: global components after ``flux2global1_`` (``implicit_hydro.cpp:561``). Area: posted per unit face area per unit time, lane C's ``riemann`` convention, before stage weights ("Frame and units").
   * - R2 named increments, declared order, total and parts
     - Three posts in declared order (``vic.mass_dry``, ``vic.mass_species``, ``vic.momentum_t``), three kept parts (``vic.mass_total``, ``vic.mass_dry``, ``vic.momentum_t``), monitor amounts ``vic.cell``, ``vic.mass_clamped`` and ``vic.momentum_t.top``. Parts are reportable through the monitor's per-post amounts (``R.hpp:90-102``); ``vic.mass_total`` = dry + species is checked.
   * - R3 stage weights into the step transfer
     - Lane I posts the stage transfer, unweighted. ``end_stage`` adds :math:`c_s\,\Delta t` times it, with :math:`c_s = w_{2,s}\prod_{t>s} w_{1,t}`, into the FP64 step accumulator (``R.hpp:85``; ``R.rst:488-494``). These are the weights the fixer uses today (``hydro_forward.cpp:1682-1691``); that fixer code is deleted (section 10).
   * - R4 divergence and flux-derived terms read the register
     - G reads ``total(1)`` and the kept ``vic.mass_total``, and no longer rebuilds ``vertical_mass_flux1`` (``hydro_forward.cpp:1422-1425``). m1, the axial source and the tracer transfer read the register in ``post_implicit``. The linearised fluxes inside the operator are its unknowns, not a rebuilt registered flux.
   * - R5 seams, reconciliation, single-valuedness, rotation in coord
     - N/A for the implicit post: the solve refuses an x1 split (``hydro.cpp:486-491``), so it posts no seam face. The explicit G at an x1 seam reads the reconciled register M; ``apply_seam`` takes the neighbour's Δρ from the existing ghost exchange (``hydro_forward.cpp:1484-1493``). Rotation: the solve calls coord's ``prim2local1_``/``flux2global1_`` and owns none.
   * - R6 device monitor, no host reads in a segment
     - Lane I contributes, all on device, to lane R's ``RegisterMonitor`` (``R.hpp:90-102``): the ``cell_amount`` entries; the per-column status, OR-reduced and written with ``flag_retry("implicit.column", any)`` (``R.hpp:78``) into ``retry_flags()``; the clamp residual, dry clamp and FP64-fallback meters; and ``GravityWork::potential`` for the E+P term. In-stage host reads go from 6 to 0 (section 7).
   * - R7 fixers and floors register what they added
     - The availability clamps, including the 4096-ulp species keep (``vic_redistribute_impl.h:151-155``), are floors in effect, but their change is booked as ``cell_amount("vic.mass_clamped", ..., w2_s, AmountKind::flux_correction)`` (``R.hpp:67-70``; ``R.rst:499-502``), because the posted transfers already carry it. The global gravity-work fixer is removed (Cheng, 2026-11-17), so there is nothing of it to register.
   * - R8 FP32 dtype, graph-capturable storage
     - The solve dtype follows section 6. Posts are in ``Quantity::kFlux``, the stage-total dtype; the step accumulator is ``kRegister``, FP64 in both precisions except on MPS, where it is FP32 (``R.rst:1372-1378``). Scratch is fixed per (shape, dtype, device) (section 7).
   * - R9 no added full-field copy per stage
     - V3 adds no copy. It removes ``w_in = w.clone()`` (``implicit_hydro.cpp:480``) and the ``rx_mass0`` clone (``:421``). ``_du0`` (one ``du``-sized copy, ``:212``) already exists and stays. Memory: the posts add into the register's existing x1 total, and the three kept parts are 4 x1 face rows (mass total, mass dry, and the two tangential momenta). Together they replace ``_mass_corr`` (nvar cell fields), so the net is ≤ 0. **How cost will be measured** (specified, not run): ``examples/jupiter_gcm_dry`` C48 x 100 on one GPU, minimum of 3 interleaved runs of 30 timed steps against the pin, as #358 measured; GPU time of the implicit kernels from a profiler; bytes of the scratch and register slots counted from the shapes. **Hypothesis:** within the #358 spread.
   * - R10 rebuilt, not in restart
     - Met at the pin and kept. Restart writes the ``Variables`` map, the reference and the times (``restart.cpp:26-123``: variables ``:31-38``, reference ``:44-66``, times ``:70-99``), not the module buffers. The register resets at ``begin_step()`` and ``rollback()`` (``R.hpp:48, 86``). V3's scratch is unregistered and ``ColumnSegments`` and ``GravityWork`` are rebuilt from the grid and the mask.


5. Invariants and gates
-----------------------

Every gate here is **specified, not run**: this round is design only.

**Invariants.**

- I1 rows = apply, written apart for W and K (Tianhao's note 6). For random
  :math:`\delta q`, ``R_W·δq == W[M_lin(δq)]`` and
  ``R_K·δρ == K[δρ]`` to round-off, for every ``X1Measure`` and every
  solid depth, with the wall third points included.
- I2 booked = G[register M] per stage. With the post-solve remainder, the
  energy increment from gravity equals ``apply`` of ``total(1)`` mass rows
  at stage end.
- I3 mass telescoping: ``vic.mass_total`` closes to zero at both walls of
  every fluid segment (the clamp-residual meter, ``implicit_hydro.cpp:495-518``).
- I4 the correction is linear in the explicit increment (softened from
  revision 1). The solve maps ``du`` to a correction through a fixed
  operator, and the only other input terms vanish with ``du``: the m_t
  fold (``vic_assemble_partial_impl.h:38-41``) and ``rx_tri(rx_mass0)``
  (``implicit_hydro.cpp:421-424``). So a rest column's correction is of the
  size of its explicit residual. It is exactly zero only where that
  residual is exactly zero. Lane C's rest gate is a tolerance, not zero:
  ``max |v|/c <= 1e-12`` (``C.rst:1284-1287`` at happysky19/snapy
  ``v3-design/C`` ``bcac27c97a9efc1de2cb2041e6b709f07eedcefe``). Lane C
  gives no ``du`` bound per reference mode (C-N5, answered). So I4's gate
  is that rest-velocity gate, and I4 stays a **hypothesis**.
- I5 no reference row (rewritten, Tianhao's note 5). The operator is a
  first-order Roe linearisation of the **full, unsplit** flux on the cell
  states. It is built from ``CopyPrimitives`` on cell ``w``
  (``vic_assemble_full_impl.h:53, 73``) and ``RoeAverage``/``FluxJacobian``
  (``flux_decomposition_impl.h:38-130``), with the full gravity whatever
  ``non-hydrostatic`` is (``implicit_hydro.cpp:326-329``). It
  differentiates neither the reconstruction nor the reference. The default
  reference is rebuilt from each stage's ``w`` by ``_hydro_ref_x1``
  (``hydro.cpp:606-608``), called at ``hydro_forward.cpp:682``, before the
  solve (``hydro_forward.cpp:1607``, into ``hydro.cpp:526``). So within the
  solve it is a constant of the RHS. Lane C agrees: no reference row
  (rev 2.3). A
  reference row would differentiate a term the operator never models, so
  none is added. The well-balance is a property of the RHS (lane C); the
  operator only has to map it as I4 says.

**Gates, existing** (specified; each is re-run on the changed PRs):

- the #348 harness: 16 implicit decks x CPU/CUDA, ``hydro_u`` bytes;
- ``test_conservation_budget`` (E+P rows);
- the large-Courant tall column (#345);
- #369's "floor == wall" and rest-with-terrain rows, re-run and unchanged
  on each PR. They are not a gate by themselves (lane S); the bitwise gate
  of I-1 and I-2 is the #348 harness, pin against PR (section 10);
- ``test_fp32_implicit.py`` and ``test_fp32_jupiter.py`` (fallback counts).

**Gates, new** (specified):

- I1 as two unit tests (W and K) that go RED if one side is edited alone;
- I2 on a tall column, schemes 1 and 9;
- I4 on each of lane C's reference modes, with lane C's rest gate
  ``max |v|/c <= 1e-12`` (``C.rst:1284-1287``; **hypothesis**);
- a sync-counter test: no host read between assemble and the last post;
- a per-column status test: one NaN column is retried in FP64 and the
  others keep FP32 (section 10(c)).


6. FP32 contract
----------------

- **Policy unchanged:** ``auto | float32 | float64``. FP32 is allowed only
  on Cartesian ideal-moist (``hydro.cpp:502-507``). The RHS master and the
  energy offset stay FP64 at the boundary (``:508-511``).
- **G in FP32.** The coefficients difference the geometry before the cast
  (``gravity_work.hpp:9-11``), for all grids. The curved explicit formula,
  which differences the potential after the cast, is gone.
- **Fallback, per column.** Today a failed FP32 block is re-solved whole in
  FP64 from ``rhs64`` (``hydro.cpp:529-535``). In V3, after the FP32 stage,
  the FP64 stage is launched once more without a condition. A column
  predicate makes every column whose status bit is clear return at once.
  The FP64 launch takes ``rhs64`` and the FP64 primitive ``wi64``, as today.
  I chose a second launch over an FP64 path inside the FP32 kernel because
  the K = 2 kernel is already register-bound (#358 runs it at 64 threads).
  The result change is in section 10(c).
- **Map to lane X's rows** (Tianhao's note 13). The row names are those of
  lane X's ``PrecisionPolicy`` as lane C cites them (``kPrimitive``,
  ``kReference``, ``kGauge``, ``kFlux``, ``kRegister``). ``kImplicit`` is
  lane X's row for the solve (``precision_policy.hpp:21`` at UCzhangxi/snapy
  ``v3-design/X`` ``89415a6c3a97d0f54016db6e843cdd08d4eaf359``). The FP64
  retry is that row forced to FP64, and the posts stay ``kFlux``, whose
  dtype a retry must not change (``X.rst:1014-1016``):

  .. list-table::
     :header-rows: 1

     * - lane I quantity
       - X row
       - FP32 run
       - FP64 run
     * - RHS master ``du``, energy offset, ``rhs64``
       - ``kPrimitive`` / ``kGauge``
       - FP64
       - FP64
     * - solve inputs ``w``, ``gamma`` (cast), blocks a, b, c, delta, z0, z1
       - ``kImplicit`` (X's row; follows ``implicit-precision``)
       - FP32 (Cartesian ideal-moist only)
       - FP64
     * - the FP64 retry stage
       - ``kImplicit`` forced FP64
       - FP64
       - FP64
     * - ``GravityWork`` coefficient masters
       - ``kReference`` (master, cast per use)
       - FP64 master
       - FP64
     * - ``vic.*`` posts and kept parts
       - ``kFlux`` (stage total)
       - FP32
       - FP64
     * - step accumulator, monitor amounts
       - ``kRegister``
       - FP64
       - FP64
     * - meters (clamp residual, dry clamp, fallbacks)
       - accumulation type
       - FP64 (FP32 on MPS)
       - FP64
     * - status
       - not a float
       - ``int32``
       - ``int32``

- **FP64 literals.** The registered FP64 scratch (``implicit_hydro.cpp:126-136``)
  becomes unregistered scratch on ``w.options()``. ``GeoKey`` goes, and
  with it ``implicit_hydro.hpp:141``. That leaves one literal, the MPS-aware
  accumulation type (``implicit_hydro.cpp:24-26``), which the status kernel
  takes over. ``set_data`` (``:157, 183``) goes.


7. CUDA-graph contract
----------------------

- **No host read inside the solve segment.** Removed: ``implicit_hydro.cpp:477,
  479, 485, 487``, ``implicit_hydro.hpp:104`` and ``implicit_dispatch.cpp:255``
  (``donor_cap``: an always-run sweep on CPU, device-predicated on CUDA).
  ``hydro.cpp:530`` moves into the predicate.
- **Per-column status** (Tianhao's note 8). Each column has its own
  ``int32`` status ``col_status[nc3, nc2]`` (``VicStatusBit``), written by
  the column's kernel thread with no atomics. The FP64 retry stage reads
  ``col_status`` per column as its predicate: a column with
  ``kVicSingular`` or ``kVicResultNonfinite`` set and ``kVicFp64Retried``
  clear is retried, and every other column returns. The block status is an
  OR-reduction of ``col_status`` after the retry, written with
  ``flag_retry("implicit.column", any)`` (``R.hpp:78``) into lane R's
  ``retry_flags()`` (``R.hpp:102``). It reaches X's one stacked step-end
  read (``meshblock.cpp:1566``) as cause bit 5. Lane I makes no read of its
  own (``X.rst:1019-1022``). The failure log
  (``implicit_hydro.cpp:219-239``) reads ``col_status`` on a redo only.
- **dt is a host double, keyed in X's ``GraphKey``** (rev 2.3, lane X's
  answer 3, ``X.rst:1017-1018`` and ``:489``; replaces revision 2's device
  scalar, Tianhao's note 12). ``VicParams`` carries ``dt`` by value; a
  changed ``dt`` recaptures, and a device ``dt`` is refused in V3. The
  stage weight in the operator's dt (``hydro_forward.cpp:1568-1583``) is a
  per-stage constant in the same key.
- **FP64 retry: a predicated second FP64 launch, always run** (lane X's
  answer 1, ``X.rst:1011-1013``). There are no CUDA conditional nodes, so
  the launch count is fixed and eager runs the same ops as the replay.
- **Fixed storage.** a, b, c, delta, z0, z1, du0 and ``col_status`` are
  allocated once per
  (shape, dtype, device) and never ``set_data``-replaced.
  ``ColumnSegments`` and the ``GravityWork`` rows change only when the mask
  version or the grid key changes, which ends a captured segment.
- **Fixed launches.** Assemble, solve (Woodbury 2x2 in the kernel, in
  place of the ~12 small host launches at ``implicit_hydro.cpp:446-472``),
  redistribute, the predicated FP64 stage, the remainder. The count does
  not depend on the data.
- **No segment boundary** for the solve (lane X's answer 5,
  ``X.rst:1023-1028``). It runs in the hydro forward's compute segment,
  which starts after the stage's unpack and ends at the next exchange. A
  mask or grid change bumps ``config_generation`` and recaptures.


8. Cross-repository interface changes and merge order
-----------------------------------------------------

**Python (snapy bindings).**

- ``ConstGravityOptions.gravity_work`` keeps working; ``"cell"`` is refused
  when the Hydro module is built.
- ``gravity_work_fixer`` is removed with the option: the binding
  ``python/csrc/pyforcing.cpp:29`` and the stubs ``python/snapy/forcing.pyi:61-70``
  go, and the ``"cell"`` docstring at ``forcing.pyi:54`` is edited. The C++
  setter call in ``test_lu_failure.cpp:228`` is removed with it.
- ``ImplicitOptions.scheme`` (``python/snapy/implicit.pyi:55-60``) stays an
  int spelling of ``VicMatrix``.
- The buffers ``hydro.icorr.{a,b,c,delta,du0,corr,mass_corr}`` leave
  ``named_buffers``. User stage forcings see the module's buffers
  (``meshblock.cpp:58-67``), and ``test_fp32_implicit.py:49`` reads
  ``buffer("a")``. The meters (``fp64_fallbacks``, ``clamp_residual``,
  ``dry_clamp_step``) stay.

**YAML.**

- ``forcing/const-gravity/gravity-work: cell`` is refused.
- ``gravity-work-fixer: false`` is still parsed by ``const_gravity.cpp``
  (lane I) with a deprecation warning, so decks that spell it keep running.
  ``true`` is refused. Inline test YAML uses ``false``
  (``test_lu_failure.cpp:109``).
- ``integration/implicit-scheme: 1|9`` is unchanged.

**pyharp** reads the ``integration`` block too (``implicit_hydro.cpp:33-38``).
Its keys do not change, so nothing changes for pyharp. kintera,
pyminichem and pydisort are not touched.

**Merge order.**

#. #369 (open; it keeps priority). V3 rebases on it.
#. Lane R's register.
#. The lane I PRs in the order of section 10, the ones that need no
   register first.
#. Lane A's m1 register read, after I-4.


9. Line budget
--------------

Baseline: 2,655 lines (section 1), plus 166 lines of ``src/math`` that lane O
moves into ``src/implicit``. That move is counted as cut by neither lane
(agreed with Jiachen), so the baseline becomes 2,821. The "after" numbers
are estimates for the design, not counts of written code.

.. list-table::
   :header-rows: 1

   * - file (pin)
     - now
     - after
     - delta
     - deletions named
   * - ``implicit/implicit_hydro.hpp``
     - 158
     - 96
     - -62
     - ``GeoKey`` (:137-152), ``_rx_*`` (:127-133), ``_g_*``, ``_solve_failed`` and ``solve_failed()`` (:101-116), the scheme bit test (:36-42); rev 2.2: +1 for the ``book_remainder`` declaration (a target)
   * - ``implicit/implicit_hydro.cpp``
     - 627
     - 423
     - -204
     - scheme-0 path (:179-188); grid caches (:262-294); host screens and ``reject`` (:219-252, 474-488); two remainders become one call (:522-556, 569-594); Woodbury 2x2 moves into the kernel (:446-472); ``set_data`` resizes (:139-168); rev 2.2: +3 for ``book_remainder`` as its own method in ``post_implicit`` (a target)
   * - ``implicit/implicit_dispatch.hpp``
     - 37
     - 25
     - -12
     - 9 stubs (:16-24) become 2; ``kVicFaceWork``, ``kVicDiffusiveCell``, ``kVicCartesianFaceWork`` (:32-35)
   * - ``implicit/implicit_dispatch.cpp``
     - 313
     - 200
     - -113
     - per-stub operand unpacking (:24-235), replaced by one ``vic_stage<CpuColumns>``
   * - ``implicit/implicit_dispatch.cu``
     - 307
     - 90
     - -217
     - the CUDA copies of the same stubs (:32-289) and the unused ``cuda_utils.h`` include (:15, lane O's item, counted here only); the launcher, instantiation and registration remain
   * - ``vic_assemble_partial_impl.h`` + ``vic_assemble_full_impl.h``
     - 324
     - 220
     - -104
     - the second assembly (``full`` 118 lines) and the 3x3 extractions (``partial:91-93, 109-111, 124-126, 135-137``)
   * - ``implicit/vic_gravity_work_impl.h``
     - 50
     - 25
     - -25
     - the Cartesian 0.25 branch (:29-36) and the diffusive-cell branch (:37-41)
   * - ``implicit/forward_sweep_impl.h``
     - 138
     - 140
     - +2
     - (the column predicate is added)
   * - ``implicit/flux_decomposition_impl.h``
     - 130
     - 130
     - 0
     -
   * - ``implicit/vic_redistribute_impl.h``
     - 232
     - 232
     - 0
     - (named slots replace the ``MASS(IVX+(dir+k)%3)`` reuse)
   * - ``implicit/vic_solve_failure.h``
     - 21
     - 25
     - +4
     - (status bits are added)
   * - ``hydro/gravity_work.hpp`` + ``gravity_work_radial.hpp``
     - 250
     - 215
     - -35
     - two headers merge into one; free ``corrected_pe_work``/``_seam`` (:197-222) become ``GravityWork`` methods
   * - ``forcing/const_gravity.cpp``
     - 68
     - 45
     - -23
     - the ``cell`` and fixer options and checks (:28-38); rev 2.1: the
       ``SourceTerm`` migration (section 11, lane A) drops the
       ``forward`` wrapper (:43-47, -5, a target); ``forward_split``
       becomes ``apply`` with the same body
   * - ``math/lubksb.h`` -> ``implicit/lubksb.h``
     - 71
     - 71
     - 0
     - moved in by lane O, counted by neither lane; kept as is
   * - ``math/ludcmp.h`` -> ``implicit/ludcmp.h``
     - 95
     - 95
     - 0
     - moved in by lane O, counted by neither lane; kept as is (the #361 FP32 pivot lives here)
   * - **total**
     - **2,821**
     - **2,032**
     - **-789 (-28.0%)**
     - target: at least 20% (at most 2,256). Without the move: 2,655 -> 1,866 (-29.7%). Rev 2 was 2,033 (-788); rev 2.1 adds the ``SourceTerm`` migration (-5); rev 2.2 adds ``book_remainder`` (+4)

The deletions that rulings (a) and (b) cause outside lane I's files are
listed by owner in section 10 ("Outside-lane deletions"). They are counted
in lane R's (136), lane X's (124) and lane A's (18) tables, not here. None of their lines is in the
2,655-line baseline (checked: no range falls in ``src/implicit``,
``gravity_work*.hpp`` or ``const_gravity.cpp``), so the lane I total above
needs no correction.

Revision 1 listed these sites only roughly, and two of its pointers were
wrong. ``meshblock.cpp:997-1003`` is really ``:993-1004``. "The explicit
face-work block ``hydro_forward.cpp:1412-1537`` becomes about 30 lines" also
overlapped the fixer and ``cell`` lines inside that block. Neither was in
lane I's -788. The remaining rewrite of that block around
``GravityWork::apply`` sits in lane R's file and is lane R's line count.


10. Migration
-------------

**PR sequence.** Each line gives: what changes; bitwise, rounding or beyond
round-off; and why.

#. **I-1 one assembly, ``VicMatrix``.** Bitwise (**hypothesis**): each entry
   of the partial blocks is the same scalar expression as before. Gate:
   pin against PR in the #348 harness, with #369's "floor == wall" re-run
   and unchanged.
#. **I-2 one kernel definition (``vic_stage<Launch>``, 2 stubs).** Bitwise
   (**hypothesis**): it changes the plumbing only, and the per-column bodies
   are untouched. Gate: as I-1.
#. **I-3 ``GravityWork``: one cache, one W formula, rows from the
   coefficients, one remainder call.** Rounding (**hypothesis**). Three
   things move round-off: the Cartesian 0.25 branch becomes the general
   weights (equal values, other operation order); the curved explicit W
   becomes difference-first; and the remainder is computed in another order.
   It should reduce the large-origin cancellation #288 measured (3e-12 at
   r = 7e7 m). Gate: a tolerance against the pin on the #348 decks. Lane
   I's own analysis gives no derived bound, so the tolerance is a **target
   that lane I owns**: the per-step relative difference of the energy row
   of ``hydro_u`` at most 1e-11, about 3x #288's 3e-12. It is to be set
   from the first measurement before I-3 merges.
#. **I-4 posting to the register** (after lane R). Rounding
   (**hypothesis**): the posts are divided by :math:`A_f\,\Delta t` and
   readers multiply back, where today ``hydro_forward.cpp:1646`` adds
   ``mc / dt`` directly.
#. **I-5 device status and the Woodbury 2x2 in the kernel.** Rounding on
   CUDA (**hypothesis**: FMA contraction); bitwise on CPU.
#. **I-6 per-column FP64 retry.** See (c).
#. **I-7 removing ``gravity-work: cell`` and the global fixer** (settled,
   Cheng 2026-11-17). See (a) and (b). The lane I part is
   ``const_gravity.cpp`` and ``src/implicit``. The lane R and lane X parts
   are in their own PRs (table below), merged together with I-7 so that no
   commit leaves a dangling ``gravity_work_fixer()`` call.

**Options and paths removed.**

- ``gravity-work: cell``;
- ``gravity-work-fixer: true`` (``false`` is a deprecated no-op);
- ``kVicFaceWork``, ``kVicDiffusiveCell`` and ``kVicCartesianFaceWork``;
- the scheme-0 module (Python only: from YAML it already returns ``nullptr``,
  ``implicit_hydro.cpp:91``);
- the whole-block FP64 retry;
- the ``fixgrav=`` cycle meter (``meshblock.cpp:1336-1337``).

**What each removal changes in results.**

(a) **Refusing ``gravity-work: cell``.** **Settled: Cheng's decision,
2026-11-17.**

- Decks on ``face``, which is every shipped ``*.yaml``: bitwise
  (**hypothesis**, gated by #348). Every removed branch is gated on
  ``gw_cell`` or ``gravity_work() == "cell"``
  (``hydro_forward.cpp:579-580, 1427, 1430, 1470, 1505``;
  ``implicit_hydro.cpp:335-337``; ``const_gravity.cpp:28-38``).
- A deck or script that selects ``cell``: refused at Hydro construction. If
  moved to ``face``, it changes **beyond round-off**:

  - energy, entropy drift and the conserved quantity (E+P instead of
    E+ρΦ). The #284 table, moving isentropic column at nz 64 / 128:
    entropy drift 1.97 / 0.473 with cell + fixer against 1.11 / 0.235 with
    face (measured in #284 on the face form of that time, before
    corrected PE; at the pin face also books K);
  - tall-column behaviour (#285: 4.49x top density with cell + fixer on a
    coarse 40H column, against a stable face column at the pin per the
    #345 large-Courant test).

  Periodic-x1 gravity decks lose the alternative the current warning names
  (``hydro.cpp:146-156``).
- Affected tests: all of these select ``cell`` and are re-targeted to
  ``face`` or deleted.

  - ``test_conservation_budget.cpp:178-180, 190`` (rows ``a_cell_s0/1/9``,
    ``c_cell_s9``);
  - ``test_flux_covariance_seams.py:59-60``;
  - ``test_implicit_gravity_tall_column.py:61-63, 202-212``
    (``cell-global-fixer`` arm);
  - ``test_implicit_stratified_solid.py:163, 170, 222, 252-299``;
  - ``test_mps_matches_cpu.py:203-204`` ("bubble cell work fixer");
  - ``test_gravity_work_fixer.py`` (whole file, 247 lines;
    ``tests/CMakeLists.txt:351, 828``);
  - ``run_straka_redo.cmake:1-5`` (``tests/CMakeLists.txt:613``), which
    runs straka on cell + fixer at CFL 1.5. Its outcome depends on the
    form ("a 1-ulp change flips the outcome", ``:5``), so it is re-recorded
    on face. The result is a **hypothesis** until run.

(b) **Removing the global gravity-work fixer.** **Settled: Cheng's
decision, 2026-11-17.**

- With ``face`` the fixer is already off: ``hydro.cpp:128`` forces it false
  and ``gravity_work_fixer()`` requires ``cell`` (``hydro.cpp:322-326``).
  Removing it is therefore **bitwise** for every face deck (**hypothesis**;
  the code it removes is not executed for face, ``meshblock.cpp:997-1004``,
  ``hydro_forward.cpp:1507, 1598, 1608, 1682``).
- For cell decks it goes away with (a), so there is no case where the fixer
  is removed and cell kept.
- Lost: the ``fixgrav=`` meter and the boundary-mass refusal
  (``meshblock.cpp:1097-1103``); the E+PE defect diagnostic becomes the E+P
  monitor (R6).
- The redo signal is not lost, because ``check_redo`` reads the solve latch
  itself (``meshblock.cpp:1549-1551``).
- Decks that spell ``gravity-work-fixer: false`` keep running bitwise,
  with a deprecation warning: ``test_lu_failure.cpp:109``,
  ``test_stencil_cache_small_block.py:54`` and
  ``test_implicit_gravity_tall_column.py:57``. The C++ setter call
  ``test_lu_failure.cpp:228`` is deleted, because the option goes.

**Outside-lane deletions (rulings (a), (b)).** These lines are counted in
lane R's, lane X's or lane A's table, **not here**. They are exact inclusive ranges at
the pin, one entry per line, with no line in two rows (checked by a script
over the ranges). "Edited" lines change but are not deleted, and they are
not counted.

.. list-table::
   :header-rows: 1
   :widths: 10 50 8 32

   * - owner
     - range at the pin
     - lines
     - what
   * - R
     - ``src/hydro/hydro.hpp:273-274``
     - 2
     - ``gravity_work_fixer()`` declaration
   * - R
     - ``src/hydro/hydro.hpp:296-314``
     - 19
     - ``gravity_work_defect``, ``gravity_work_fix``, ``add_``/``commit_``/``drop_gravity_work_fix``, ``gravity_work_wall_mass``
   * - R
     - ``src/hydro/hydro.hpp:480``
     - 1
     - ``_gwfix_d, _gwfix_total, _gwfix_pending, _gwfix_wall``
   * - R
     - ``src/hydro/hydro.cpp:126-135, 138-145``
     - 18
     - fixer reset, the grav2/grav3 and periodic-x1 checks (``:136-137`` stay: the face warning reads ``nm``, ``wrap``)
   * - R
     - ``src/hydro/hydro.cpp:287-293``
     - 7
     - ``_gwfix_*`` ``register_buffer``
   * - R
     - ``src/hydro/hydro.cpp:322-327``
     - 6
     - ``HydroImpl::gravity_work_fixer()``
   * - R
     - ``src/hydro/hydro_forward.cpp:1416-1417, 1507-1533, 1584-1598, 1608, 1682-1693``
     - 57
     - the stage E+PE defect, wall-mass meter, implicit ``epe`` lambda and the stage-weight accumulation into ``_gwfix_d``
   * - R
     - ``src/hydro/hydro_forward.cpp:575-580, 846-849, 902, 907, 917, 1426-1434, 1505-1506, 1534, 1536``
     - 26
     - ``cell``: ``bflux1``, ``gw_cell``, the ``bflux1`` rows of the x1 seam average (``:902, 907, 917``; inside lane R's seam block ``:868-946``, R.rst:1479), ``F - F^R`` split, the ``cell`` branch (``:1535`` stays as the only branch)
   * - **R total**
     -
     - **136**
     - hydro.hpp 22, hydro.cpp 31, hydro_forward.cpp 83. Lane R's own count at revision 1 was 142: the difference is ``hydro.cpp:122-125`` (lane I treats these as edited: they keep accepting ``face``) and ``:136-137`` (they stay, because the face warning at ``:148-152`` reads ``nm`` and ``wrap``)
   * - X
     - ``src/mesh/meshblock.hpp:217-222``
     - 6
     - ``gravity_work_fixer_sums``, ``apply_gravity_work_fixer`` declarations, ``defer_gravity_work_fixer``
   * - X
     - ``src/mesh/meshblock.cpp:724-730``
     - 7
     - step-start reset and commit
   * - X
     - ``src/mesh/meshblock.cpp:993-1004``
     - 12
     - single-block step-end call (``:992`` stays: it is the ``apply_boundaries`` comment)
   * - X
     - ``src/mesh/meshblock.cpp:1036-1110``
     - 75
     - ``gravity_work_fixer_sums`` and ``apply_gravity_work_fixer``, with the blank line after them (``:1110``, in the set lanes X and O settled)
   * - X
     - ``src/mesh/meshblock.cpp:1336-1337``
     - 2
     - ``fixgrav=`` print (if cycle printing is lane O's, it moves there; count it once)
   * - X
     - ``src/mesh/meshblock.cpp:1477, 1502``
     - 2
     - ``check_redo``: ``drop_`` / ``commit_gravity_work_fix``
   * - X
     - ``src/mesh/mesh.cpp:363, 384-402``
     - 20
     - ``defer_gravity_work_fixer``; multi-block sum, reduction and apply
   * - **X total**
     -
     - **124**
     - meshblock.hpp 6, meshblock.cpp 98, mesh.cpp 20; the set lanes X and O settled (revision 1 of this table had 123, without the blank ``:1110``)
   * - A
     - ``src/forcing/forcing.hpp:48``
     - 1
     - the ``gravity-work-fixer`` line of ``ConstGravityOptionsImpl::report``
   * - A
     - ``src/forcing/forcing.hpp:56-58``
     - 3
     - the ``"cell"`` entry of the ``gravity_work`` doc comment
   * - A
     - ``src/forcing/forcing.hpp:60-62``
     - 3
     - the ``gravity_work_fixer`` option and its comment
   * - A
     - ``python/csrc/pyforcing.cpp:29``
     - 1
     - the ``gravity_work_fixer`` binding
   * - A
     - ``python/snapy/forcing.pyi:61-70``
     - 10
     - the two ``gravity_work_fixer`` stubs and the blank line before them
   * - **A total**
     -
     - **18**
     - forcing.hpp 7, pyforcing.cpp 1, forcing.pyi 10; **counted in lane A, not here** (agreed with Jiachen, 2026-11-17)

Edited, not counted:

- ``hydro.cpp:123-125`` (accept ``face`` only), ``:146-147, 157`` (the
  warning no longer names ``cell``), ``:324, 331``;
- ``hydro.hpp:290-291`` (comment);
- ``hydro_forward.cpp:1412-1414`` (comment), ``:1470`` (``!gw_cell &&``
  goes), ``:1535`` (dedent);
- ``meshblock.hpp:225``, ``meshblock.cpp:1476`` (comments);
- ``forcing.hpp:47``, ``pyforcing.cpp:28`` (the line terminator) and
  ``forcing.pyi:54`` (docstring), all lane A's.

``docs/derivations/curved-gravity-work-weight.md:429, 433, 521, 525`` name
the fixer and ``cell``; they are docs, not ``src``, and are edited with I-7.

(c) **Per-column FP64 retry.** **FOR CHENG** (still open with Cheng; kept
as proposed)

- A step where no FP32 column fails: **bitwise**. The predicated FP64
  launch does no column work.
- A step where a column fails: the failed columns get an FP64 solve from
  the same ``rhs64``/``wi64``, as today, so they are bitwise to today's
  retry for that column (**hypothesis**: the column solve does not depend on
  its neighbours, ``implicit_dispatch.cpp:137-160``). The other columns of
  the block keep their FP32 solution where today they are re-solved in
  FP64, so they change **beyond round-off**. The size of the change is the
  FP32-FP64 solve gap: #361 measured 5.2e-6 in w after 1000 steps (CPU),
  and ``test_fp32_implicit.py:52-54`` bounds it per solve at 2e-6
  (relative). The size per failing step is a **hypothesis**.
- The ``fp64_fallbacks`` meter changes meaning from blocks to columns.
- Affected tests: ``test_fp32_implicit.py:58-60``. It asserts
  ``fallbacks > 0`` and finiteness at ``dt = 1e9``; both should still hold
  (**hypothesis**).
- Unaffected by construction: ``test_fp32_compute.py:48``,
  ``test_fp32_jupiter.py:147`` and the ``test_fp32_science.py`` fallback
  check, which require zero fallbacks.
- No shipped deck runs the FP32 solve by default: ``precision: auto``
  picks FP32 only under ``dynamics/precision: float32`` (``hydro.cpp:502-503``).


11. Open questions to other lanes
---------------------------------

**Lane R (Tianhao; frozen header rev 4.2 ``4c59162a``).** Lane R's
section 4.2 (``R.rst:472-523``) settles lane I's R-1 to R-4:

- R-1, **settled**: ``vic.mass_dry@1`` is a second kept part, filled by its
  ``add`` call (``R.rst:479-481``; row 38).
- R-2, **settled**: ``vic.momentum_t`` is posted under scheme 9 as the
  bottom-up prefix sum, top face included. Its top value, minus the column
  sum, is the ``diagnostic`` amount ``vic.momentum_t.top``
  (``R.rst:505-519``).
- R-3, **settled**: ``d = dir + 1``; the vertical solve posts to ``d = 1``.
- R-4, **settled**: ``cell_amount`` takes ``stage_weight``. Lane I passes
  ``w2_s`` for ``vic.cell`` and ``vic.mass_clamped`` (``R.rst:488-494``).

**Rev 2.3: lane R confirmation.** Tianhao confirmed (lane R thread) that
both of his lane I conflicts are closed at rev 2.2 ``7604ada0``: the
gravity-work remainder follows ``apply_prescribed(1)`` and precedes lane A's
m1, and ``vic.momentum_t@1`` is the third kept part. Lane R's head is now
``97c62312490c3e290d597a2d188785252773bd21``. Against R rev 2.3
``2b4c5775`` it changes only ``hydro_stage.hpp``: its ``post_implicit``
comment puts I's remainder before A's m1, and ``HydroStage::after_combine``
is removed because X's executor runs it. Against the frozen ``4c59162a``,
``flux_register.hpp`` differs in comments only (lines 22, 28, 34-36, 96-98
and 101). No signature changed and no line moved. Lane I keeps citing R at
``4c59162a``. No lane I citation or skeleton line refers to
``hydro_stage.hpp`` lines or to ``HydroStage::after_combine``. R is now at
rev 2.4 ``a15af81660f75b53f3e905b7ee15aa935ada855c``, which changes
``R.rst`` only: ``flux_register.hpp`` is unchanged against ``97c62312``,
so there is no re-cite. R agreed the ``boundary(dim)`` face set
(``R.rst:39-42, 632-645`` at ``a15af816``): S's ``wall``, ``outflow`` and
``custom`` faces with a fluid interior, plus every immersed-solid face
with fluid on one side, all rows, outward from the fluid.

**Rev 2.2 round notes, answering Tianhao's two findings on rev 2.1**
(``a379fe39``; the PM upheld both):

1. *Gravity-work remainder read too early.* Lane I read
   ``kept(1, "vic.mass_total")`` in ``implicit``, before
   ``apply_prescribed(1)``. **Changed:** the remainder now runs in
   ``post_implicit`` after ``apply_prescribed(1)`` (``R.rst:486-488``; the
   same text at ``R.rst:542-544`` in rev 2.3 ``2b4c5775``), and before lane
   A's m1, which is the pin's order for ``du[IPR]``. See section 4,
   "Reads" and "Ordering constraints", and ``book_remainder`` in the
   skeleton. **No conflict with the pin.** At the pin the walls carry
   (round-off-)zero transfer, so the change is at most round-off at the top
   face (**hypothesis**).
2. *Third kept part missing.* **Changed:** ``vic.momentum_t@1`` is named
   as the third kept part, next to ``vic.mass_total`` and ``vic.mass_dry``
   (section 4, "Kept parts"; the R2 and R9 rows).

**Answers to lane R's asks** (``R.rst:1602-1603``):

(a) **Confirmed:** ``vic.mass_clamped`` is ``AmountKind::flux_correction``.
    The clamps act on the transfers before they are posted
    (``vic_redistribute_impl.h:151-155``, ``implicit_hydro.cpp:527-528``),
    so the clamped amount is already inside ``boundary(1)``. Adding it again
    as a floor would count it twice. Revision 2's "floor amount" wording is
    withdrawn.
(b) **Confirmed:** the ``e+pe`` derived row (``R.hpp:34, 71-75``;
    ``R.rst:535-537``). Lane I supplies ``derived_total("e+pe", ...)`` from
    ``GravityWork::potential`` at step end, and its amounts with
    ``derived_amount``. Its stage amount uses ``stage_weight = w2_s``, and
    a change applied to ``u`` uses ``1.0``.
(c) **Confirmed:** gate G-R7 (``R.rst:1331-1334``). The per-column vic
    energy wall residual on #369's rest deck must be below 1e-13 relative,
    or energy stays ``vic.cell``. It is **specified, not run**.

**Lane C (Tianhao).**

- **Closed (rev 2.3).** C-N5: hypothesis, gate specified. Lane C's
  rest-velocity gate is ``max |v|/c <= 1e-12`` (``C.rst:1284-1287`` at
  ``bcac27c9``), with no ``du`` bound per reference mode. I4's gate cites
  it and stays a hypothesis (section 5).
- **Closed (rev 2.3).** I5: agreed, there is no reference row. The
  reference is built from the stage ``w`` before the solve
  (``hydro_forward.cpp:682``, ``_hydro_ref_x1`` at ``hydro.cpp:606-608``;
  solve at ``hydro_forward.cpp:1607``). **Cite note:** the PM's
  ``hydro.cpp:605-607`` is the function's signature, not the call before
  the solve.

**Lane A (Jiachen): does lane I migrate ``ConstGravity`` to the
``SourceTerm`` interface?** ``A.rst`` (``JiachenLiu-Atmos/snapy``
``v3-design/A`` ``4e0827b89be960e93968cca8f147301e7d501e77``) routes it to
lane I ("migration owner: K-1", section 3.6, line 492; K-1, lines
1293-1294). **Yes.** Lane I migrates ``ConstGravity`` to lane A's
``SourceTerm``. A owns the interface in ``forcing.hpp``, and I owns
``const_gravity.cpp`` (section 1):

- The declaration is phase ``pre_implicit``, rows IVX..IVZ and IPR, kind
  ``cell_source``, and ``split`` for the x1 density ``rho1`` that the pin
  passes to ``forward_split`` (``hydro_forward.cpp:1381``).
- The body of ``forward_split`` (``const_gravity.cpp:48-67``) becomes
  ``apply`` and writes A's per-source scratch, which the registry adds to
  ``du`` once (A.rst:728-735). The ``forward`` wrapper (``:43-47``) goes.
- Result: **bitwise when only ``grav1`` is non-zero (hypothesis)**, because
  the scratch receives one term per row and is added once. That covers
  every repository deck: ``git grep -E 'grav[23]:\s*[-0-9.]*[1-9]' --
  '*.yaml'`` finds none. With two or more non-zero components, the IPR row
  sums its terms in the scratch before adding them (pin: three ``+=`` at
  ``:52-53, 58, 63``), which is a **rounding change**.
- Line effect on section 9: ``const_gravity.cpp`` 50 -> 45 (-5, a target).
  Total 2,821 -> 2,028 (-793, -28.1%) at rev 2.1; 2,032 at rev 2.2 (see
  section 9).

**Lane A (Jiachen), earlier.** Answered in the lane I thread (I-1). m1 reads
``total(1)`` mass rows in ``post_implicit``, and the axial source reads
``vic.momentum_t`` under both matrices. **Closed (rev 2.3):** does
``vic.momentum_t.top`` enter the axial torque? **No.** Lane A's x1 source
reads the kept per-face ``kept(1, "vic.momentum_t")``; its top face enters
only as the top cell's ``P_hi``, as the pin's prefix sum does. Lane A never
reads the ``diagnostic`` amount ``vic.momentum_t.top`` (``A.rst:1411-1420``
at JiachenLiu-Atmos/snapy ``v3-design/A``
``c3ac77f3069e05cc785afe4d2941693c7ea1dc65``).

**Lane S (Jiheng, jihenghu/snapy ``v3-design/S`` rev 2 ``c505fb87``): wall and solid rows against #369.**

- **Closed (rev 2.3), accepted.** ``ColumnSegments`` is lane I's type and
  owns the surface rows and ``k0``/``k1``. S keeps the face set
  (``PrescribedFaces``, ``seam_register.hpp:69-86`` at ``c505fb87``). Both
  are built from the same solid mask and version (section 3). Jiheng's
  proposal as the PM carried it; S rev 2 defines none of ``ColumnSegments``,
  ``X1Wall``, ``k0``, ``k1``.
- **Closed (rev 2.3).** "floor == wall" is not the gate by itself. For I-1
  and I-2 the bitwise gate is pin against PR in the #348 harness, with
  "floor == wall" re-run and unchanged on each PR. I-3 is a rounding
  change, gated by a tolerance that lane I owns (section 10). This is
  Jiheng's answer as the PM carried it; that wording is not in S.rst at
  ``c505fb87``.

**Lane X (Xi): FP64 fallback, device status, graph segments.**

All six are **closed (rev 2.3)** by ``X.rst:1009-1030`` at ``89415a6c``
and applied in sections 6 and 7 and the skeleton:

1. A predicated second FP64 launch, always run. There are no CUDA
   conditional nodes.
2. ``kImplicit`` is X's row (``precision_policy.hpp:21``). The retry is
   that row forced to FP64, and the posts stay ``kFlux``.
3. No: ``dt`` stays a host double keyed in ``GraphKey``, and a change
   recaptures. Lane I's device ``dt`` is withdrawn.
4. Yes: the OR of ``col_status`` goes through R's ``retry_flags()`` into
   X's one step-end read as cause bit 5. Lane I makes no read of its own.
5. The solve needs no segment boundary. It sits in the hydro compute
   segment.
6. Yes in V3: FP32 stays restricted to Cartesian ideal-moist (pin
   ``hydro.cpp:502-507``).

**Cheng:** (c) of section 10. (a) and (b) were ruled on 2026-11-17.


11.1 Answers to Tianhao's review notes (lane I, revision 1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 6 14 80

   * - #
     - type
     - answer in revision 2
   * - 1
     - agree
     - Noted. The twelve sections and the R1-R10 table stay; the R table now uses lane R's header.
   * - 2
     - agree
     - Noted. The W pairing is unchanged; section 4 now writes W and K apart.
   * - 3
     - agree
     - Settled by Cheng (2026-11-17). The FOR CHENG markers on (a) and (b) are gone; section 10 keeps the seven tests to re-target with file:line.
   * - 4
     - agree
     - Settled by Cheng. Bitwise for face decks is still a **hypothesis**; its gate (the #348 harness) is specified in section 5.
   * - 5
     - conflict, accepted
     - I5 is rewritten (section 5). The operator is a first-order Roe linearisation of the full flux on cell states, with full gravity at any ``non-hydrostatic`` (``implicit_hydro.cpp:326-329``). The default reference is rebuilt per stage (``hydro.cpp:605-607``). No row is added because the operator never models the split. The finite-difference claim is withdrawn.
   * - 6
     - conflict, accepted
     - W and K are written apart (section 4). K acts on the density unknown as three bands (``implicit_hydro.cpp:409-420``) plus Woodbury wall points (``:436-472``), not as a five-point row in M. I1 is split into W and K tests.
   * - 7
     - conflict, accepted
     - The ``VicColumn`` skeleton gains the K bands and per-column Woodbury data (third points, ``k0``/``k1``), as #369 makes them per column (``_rs_ts``, ``k0`` at its head ``c382f0da``).
   * - 8
     - conflict, accepted
     - Per-column ``col_status[nc3, nc2]``, written without atomics, is the FP64 retry's predicate. The block status is its OR-reduction (section 7; skeleton).
   * - 9
     - conflict, accepted
     - Citations corrected. Revision 1 numbered some files from concatenated output: ``const_gravity.cpp:54-64`` is ``:28-38``; ``vic_gravity_work_impl.h:229-254`` is ``:23-48`` (branches ``:29-36``, ``:37-41``); ``implicit_dispatch.hpp`` flags are ``:32-35`` and stubs ``:16-24``. Restart is ``restart.cpp:26-123``. ``vic.mass_clamped`` uses the code's sign, moved - requested (``implicit_hydro.cpp:527-528``). The skeleton's section references are fixed.
   * - 10
     - request, done
     - Section 4 "Reads": the solve reads neither p* nor the well-balanced reference (``grep`` of ``src/implicit`` finds only the comment at ``implicit_hydro.cpp:326``). ``VicColumn`` has no such operand; changing that needs lanes C and I to agree.
   * - 11
     - request, done
     - ``rho_grav`` is lane R's (``hydro_forward.cpp:825-838, 961-983, 1539-1545``). Lane I reads it only in the cell work it subtracts when ``non-hydrostatic < 1`` (``:1500-1504``), so p* reaches gravity work only through ``rho_grav`` on the ``SNAP_X1_CENTROID_EXACT`` path.
   * - 12
     - request, done
     - Superseded in rev 2.3 by lane X's answer 3: ``dt`` is a host double keyed in X's ``GraphKey``, and a change recaptures (section 7). The skeleton follows.
   * - 13
     - request, done
     - Section 6 maps every lane I quantity to lane X's rows and proposes ``kImplicit`` for the solve (question to X).
   * - 14
     - request, done
     - Posts are :math:`M_f/(A_f\,\Delta t)` with the step ``dt``, before stage weights, per lane R's header (``R.hpp:4-5``); ``end_stage`` applies :math:`c_s\,\Delta t` (section 4).
   * - 15
     - request, done
     - ``ColumnSegments`` covers any mask (fluid runs per column). The single-segment fast path is taken when each column has one run reaching the top (no solid, or #369's floor). Other shapes keep the pin's per-cell K masking (section 3).


12. Skeleton index
------------------

``docs/v3/skeleton/I/`` holds declarations and comments only, 299 lines in
all (``wc -l``). It is not part of any build. It uses lane R's
``FluxRegister`` by forward declaration only.

.. list-table::
   :header-rows: 1

   * - file
     - declares
     - replaces (pin)
   * - ``vertical_implicit.hpp``
     - ``VicMatrix``, ``VicStatusBit``, ``VerticalImplicitOptionsImpl``, ``ColumnSegments``, ``VicIncrement``, ``VerticalImplicitImpl``
     - ``implicit_hydro.hpp``; the ``scheme`` bit test; ``_solve_failed`` (by per-column ``col_status``); ``mass_correction()`` (by register posts; ``correction()`` stays output-only)
   * - ``gravity_work.hpp``
     - ``X1Measure``, ``X1GridKey``, ``CentroidSlopeStencil``, ``GravityWorkRows``, ``GravityWork``
     - ``gravity_work.hpp``, ``gravity_work_radial.hpp``; ``_pe_work``, ``_rx_work``, ``_g_work_lo/hi``
   * - ``vic_kernels.hpp``
     - ``VicParams`` (device ``dt``), ``VicColumn`` (W and K rows, per-column Woodbury data and status), per-column kernel templates, ``CpuColumns``/``CudaColumns``, ``vic_stage``, 2 dispatch stubs; its header comment lists the kept files, ``lubksb.h`` and ``ludcmp.h`` included
     - ``implicit_dispatch.hpp``; ``vic_assemble_{partial,full}_impl.h``; ``vic_gravity_work_impl.h``; the stub bodies of ``implicit_dispatch.cpp``/``.cu``
