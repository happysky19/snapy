:orphan:

V3 design: the merged document
==============================

Full document, 2026-11-18, Tianhao Le, after ``CONVERGED`` (posted 22:40
EST 2026-11-17 in the kickoff thread). Design text and declarations only:
nothing here was built, compiled or run, and no implementation starts before
Cheng approves this document. It merges the nine lane designs at their
converged heads (table 1): the decisions, the frozen register header, the
lane contracts, the FP32 and CUDA-graph contracts, the line budget (counted
once under RULING V3-1), one PR order with the provider repositories first,
the gates by name, owner and kind, and the open FOR CHENG items.

Conventions. ``L.rst:N`` is line N of lane L's design
(``docs/v3/design/L.rst``) at the head in table 1; ``L:N`` without
``.rst`` is not used. Bare repository paths with ``:N`` are at chengcli/snapy
``9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410`` (the pin). Numbers are copied
from the lane documents; a number derived here says how it was derived.
"Estimate" and "target" keep the lane's meaning: a design figure, not a count
of written code.


1. Status and heads
-------------------

Every head below was read with ``git ls-remote`` on 2026-11-18 at 03:39 UTC
and fetched. Each is a descendant of the head that part 1 of this document
(``dac6ca5b``) cited for its lane. Part 1's citations were carried to these
heads by a line diff, each carried citation's end lines were checked to be
unchanged text, and the citations whose text changed, and every new one,
were read at these heads.

.. list-table:: Table 1. Converged heads
   :header-rows: 1
   :widths: 6 28 44 22

   * - lane
     - repository, branch
     - head
     - note
   * - R
     - happysky19/snapy ``v3-design/R``
     - ``9c711ba3ad52b6d33e58e93d3e415d503309538c``
     - rev 2.6; header frozen (section 3)
   * - C
     - happysky19/snapy ``v3-design/C``
     - ``5dc4d002428678d536150d7ebef5d10c4c2653a4``
     - rev 6.3
   * - I
     - zoeyzyhu/snapy ``v3-design/I``
     - ``2d8685c80ca6edda1c1e4e631dce035d8dff75f6``
     - rev 2.4; docs-only mirror, no common history with the pin. Rev 2.5
       (``1092aef9``) was not on the branch at 03:39 UTC
   * - EF
     - zoeyzyhu/snapy ``v3-design/EF``
     - ``5b3f18d28c2db7305fd3fef8b04f0319b8a326c1``
     - rev 3.8; docs-only mirror, no common history with the pin
   * - S
     - jihenghu/snapy ``v3-design/S``
     - ``bee1b27667601ea0b333c11595fe965d18de0f94``
     - rev 2.3
   * - A
     - JiachenLiu-Atmos/snapy ``v3-design/A``
     - ``c405d49133326bb6db30650df57166d53f507067``
     -
   * - O
     - JiachenLiu-Atmos/snapy ``v3-design/O``
     - ``36b61c401fd5f5d2a6917b9e05dcce3a00022815``
     - rev 5.3
   * - X
     - UCzhangxi/snapy ``v3-design/X``
     - ``07d4eedf2f7665c15e41705621ce3d834d62f0e9``
     -
   * - K
     - UCzhangxi/kintera ``v3-design/K``
     - ``8d962405f072e00bcadf7e072722ad5c5c18f4ec``
     - kintera repository

The snapy heads except I and EF have the pin as merge base.


2. Decisions
------------

Each item names the decision and the lane text that records it. Rulings
relayed in the threads and not yet written in a lane document say so.

* **RULING V3-1:** a deletion is counted by the lane that owns the file
  (``R.rst:130-131``). Section 6 counts each line once by it.
* **RULING V3-2:** from R's PR R-1 the monitor's census counts accepted
  steps only; before R-1 the existing meters stay as at the pin, with no
  interim hook (``R.rst:75-78``).
* **RULING V3-3:** C's ``solve_faces`` calls a ``before_solve`` hook after
  the floors and the solid step, before rotation and solve; R builds the
  #289 covariance there and posts it after the solve (``R.rst:81-85``;
  ``C.rst:1028-1035``). It closes R-C1.
* **RULING V3-4** (lane S thread, 23:10 EST 2026-11-17): synthesized
  corners are filled in the unpack of the last round of each field set:
  in row 0, round 1 for ``hydro_u`` and round 3 for ``scalar_s``, counting
  rounds from 0, as at the pin. S rev 2.3 says the row's last round
  (``S.rst:1565-1568`` at ``bee1b276``); S rev 2.4 carries the wording. No
  declaration changes.
* **Per-column FP64 retry accepted** (Cheng, 22:20 EST 2026-11-17). After a
  failed FP32 implicit solve only the failed columns are retried in FP64,
  through X's predicated second launch; the other columns keep their FP32
  solution. R's ``flag_retry`` cause ``implicit.column`` stays per column
  and no ``flux_register.hpp`` declaration changes (``R.rst:1410-1414``,
  ``:1439-1442``; ``X.rst:1487-1491``; ``precision_policy.hpp:21`` at X).
  Result change, from lane I's (c): bitwise when no column fails; failed
  columns bitwise to today's retry (hypothesis); the unfailed columns of a
  failing block keep FP32, beyond round-off (``I.rst:1215-1225``). Lane I's
  text at ``2d8685c8`` still marks (c) as open (``I.rst:1212-1213``); its
  rev 2.5 carries the ruling.
* **IMEX-ARK, a split implicit operator and a Newton option are not in
  V3** (Cheng, 20:35 EST): stages stay Shu-Osher with pyharp's weights and
  SSP positivity stays (``X.rst:872``, ``:913-915``).
* **The 159 ``src/mesh`` lines** (``meshblock.cpp:1623-1653``,
  ``:1226-1339`` less ``1336-1337``, ``cycle_diagnostics.hpp``) are X's
  deletion; O's ``restart.cpp`` and ``budget.cpp`` count new lines only
  (``X.rst:658-661``; ``O.rst:1528-1548``).
* **L-3, the face set of ``boundary(dim)``:** S's ``wall``, ``outflow`` and
  ``custom`` block faces with a fluid interior cell, plus every
  immersed-solid face with exactly one solid neighbour, all rows, outward
  from the fluid (``R.rst:637-672``). A's ``step_field {1, 2, 3}`` on
  immersed-solid decks follows it (``R.rst:762-770``).
* **C9 accepted** (Cheng, 21:05 EST): ``exact`` with an upwind or plume-roe
  Riemann solver is refused at ``reset()`` (``A.rst:264-265``,
  ``:1388-1392``).
* **Lane A:** ``conserve-axial-momentum-closure`` removed, ``exact``
  includes the closure (``A.rst:1372-1373``); the radial-conduction
  positivity failure keeps the pin's abort (``A.rst:1393-1395``).
* **Lane EF:** F6, ``src/turbulence`` deleted; F1, ANEOS stays; F2
  withdrawn (``EF.rst:1603-1608``).
* **Lane O:** pnetcdf stays; the hdf5/fits stubs and the FP32 storage
  emulation are removed (``O.rst:755-756``). ``mppnccombine.cpp`` is
  replaced by ``combine_parts``, a small snapy-specific combiner of about
  200 lines (estimate). In-model combining stays and ``combine`` keeps its
  default ``true``, so users see one merged file per output frame as today.
  Gate G-2, parity against ``mppnccombine`` on the same parts, passes
  before the deletion: O6a adds the combiner and the test, O6b deletes
  ``mppnccombine.cpp`` (``O.rst:2711-2727``, ``:2681-2691``).
* **Lane I:** ``gravity-work: cell`` is refused and the global
  gravity-work fixer is removed (``I.rst:1031-1032``, ``:1070-1071``).
* **Lane C:** every Riemann solver and reconstruction of the pin stays
  (``C.rst:1621``).
* **Lane S:** no line ceiling (``S.rst:1643-1644``).
* **Lanes X and K:** the chemistry executor slot and L-2 (a user output
  callback taking ``FluxRegister const&``) are accepted
  (``X.rst:1481-1482``; ``K.rst:1197-1198``).


3. The frozen register header
-----------------------------

``docs/v3/skeleton/R/flux_register.hpp`` is frozen at
``4c59162ae37080d0ab307b2823742b44f46da7c3``. At R's head in table 1 it has
the same 117 lines, and with comments removed its text is identical to
``4c59162a`` (checked by diff); only comments changed since. No client
re-cites it. It declares (line numbers at R's head):

* ``RegisterPhase`` (``:14-23``): ``sweep``, ``reconcile``, ``limit``,
  ``divergence``, ``pre_implicit``, ``implicit``, ``post_implicit``,
  ``after_combine``; ``SeamRule`` (``:24``); ``AmountKind`` (``:25-31``):
  ``flux_correction``, ``cell_source``, ``floor``, ``fixer``,
  ``diagnostic``;
* ``RegisterRequest`` (``:32-39``): ``row_names``, ``derived``, ``keep``,
  ``counters``, ``retry``, ``step_field``;
* ``FluxRegister`` (``:41-88``): ``reset``, ``set_prescribed``,
  ``begin_step``, ``begin_stage``, ``weights``, ``enter``; the posts
  ``slot``, ``part_slot``, ``post_slot``, ``add``, ``scale``, ``replace``,
  ``apply_prescribed``, ``keep``; the amounts ``cell_amount``,
  ``derived_amount``, ``derived_total``, ``count``, ``record_min``,
  ``flag_retry``; ``post_split``; the reads ``total``, ``kept``,
  ``step_field``; ``end_stage``, ``rollback``, ``monitor``;
* ``RegisterMonitor`` (``:90-103``): ``rollback``, ``row_names``,
  ``amount_names``, ``kind``, ``amounts``, ``boundary``, ``domain_total``,
  ``counter_names``, ``counters``, ``minima``, ``retry_flags``;
* ``Fixer`` (``:105-116``): ``name``, ``rows``, ``partial_sums``,
  ``apply(u, global_sums, dt, stage_weight, reg)``.

``docs/v3/skeleton/R/hydro_stage.hpp`` (rev 4.3, 82 lines) is R's stage
driver; no client calls it. ``HydroStage::after_combine`` is removed: X's
``StageExecutor::after_combine(stage, dt)`` is the one runner of the
``after_combine`` phase.


4. Lane contracts
-----------------

Each lane's contract is its sections 3 (target design) and 4 (register
contract) and its skeleton (declarations only, in no build).

.. list-table:: Table 7. Lanes, owners and skeletons
   :header-rows: 1
   :widths: 5 20 25 26 24

   * - lane
     - scope
     - owner
     - skeleton (``docs/v3/skeleton/<lane>/``, lines)
     - sections 3, 4
   * - R
     - flux register, monitor, hydro stage
     - Tianhao Le (``R.rst:20``)
     - ``flux_register.hpp`` 117, ``hydro_stage.hpp`` 82
     - ``R.rst:402-1444``
   * - C
     - reconstruction, Riemann solvers, well-balanced reference, conversion
       order
     - Tianhao Le (``C.rst:7``)
     - ``recon_point.h`` 34, ``reconstruct.hpp`` 61, ``riemann.hpp`` 70,
       ``sweep.hpp`` 30, ``x1_reference.hpp`` 54, ``x1_rows.hpp`` 48
     - ``C.rst:504-1263``
   * - I
     - vertical implicit solver, gravity work
     - Xinyue Wang (``I.rst:5``)
     - ``gravity_work.hpp`` 86, ``vertical_implicit.hpp`` 121,
       ``vic_kernels.hpp`` 92
     - ``I.rst:208-629``
   * - EF
     - EOS, floors, positivity, tracers, sedimentation
     - Zoey Hu (``EF.rst:5``)
     - ``ef_register_use.hpp`` 37, ``ef_status.hpp`` 51,
       ``eos_floors.hpp`` 36, ``eos_interface.hpp`` 26,
       ``positivity_limiter.hpp`` 68, ``sedimentation_kernel.hpp`` 38,
       ``species_repair.hpp`` 43
     - ``EF.rst:332-776``
   * - S
     - seams, coord, layout, exchange, boundaries
     - Jiheng Hu (``S.rst:5``)
     - ``coord_rotation.hpp`` 80, ``exchange.hpp`` 121,
       ``seam_register.hpp`` 93
     - ``S.rst:205-1368``
   * - A
     - rotation, axial angular momentum, sources, diffusion
     - Jiachen Liu (``A.rst:6``)
     - ``axial_momentum.hpp`` 87, ``coriolis_diffusion.hpp`` 92,
       ``rotation_geometry.hpp`` 12, ``source_term.hpp`` 90
     - ``A.rst:393-865``
   * - O
     - output, input, utilities, diagnostics, options schema
     - Jiachen (``O.rst:7``)
     - ``budget_series.cdl`` 23, ``diagnostics.hpp`` 61,
       ``gen_options.pyi`` 15, ``options_table.yaml`` 45,
       ``restart.hpp`` 57, ``writer_core.hpp`` 98
     - ``O.rst:423-1058``
   * - X
     - execution: precision, CUDA graphs, mesh, integrator
     - Xi Zhang (``X.rst:4``)
     - ``meshblock_parts.hpp`` 63, ``precision_policy.hpp`` 58,
       ``pyharp_integrator.hpp`` 23, ``stage_executor.hpp`` 103,
       ``state_store.hpp`` 50
     - ``X.rst:63-263``
   * - K
     - kintera thermodynamics and chemistry contracts
     - Xi Zhang (``K.rst:4``)
     - ``chemistry_source.hpp`` 42, ``tables.hpp`` 72, ``thermo_v3.hpp``
       78
     - ``K.rst:111-541``

Lane I's owner line names Xinyue Wang; in the threads Zoey Hu holds lane I
as backup owner.


5. FP32 and CUDA-graph contracts
--------------------------------

Lane X owns the precision policy and the executor; every lane states its own
rows and sites in its sections 6 and 7.

* **Precision.** One ``PrecisionPolicy`` row per quantity
  (``precision_policy.hpp:12-23`` at X): state, fluxes and ``du`` in FP32
  storage on an FP32 run; reference and geometry masters, ``hydro_w``
  totals, gauges and kintera totals in FP64; time, ``dt`` and stage weights
  as host doubles; the register step accumulator and budget sums in FP64,
  FP32 on MPS, which has no FP64 (``X.rst:285-307``). The implicit solve,
  ``kImplicit``, is FP32 on Cartesian ideal-moist only, with the FP64 retry
  of failed columns (section 2). ``PrecisionPolicy`` replaces the 29
  ``fp32()`` callers in ``src`` (``X.rst:309-313``). R's rows:
  ``R.rst:1521-1546``.
* **CUDA graphs.** The executor runs eager by default; ``cuda-graph`` is
  opt-in, falls back to eager on CPU and MPS, and strict mode rejects a
  case with any eager segment (``stage_executor.hpp:57-59``;
  ``X.rst:851-870``). ``dt`` stays a host double keyed in ``GraphKey``, so
  a change recaptures (``stage_executor.hpp:52``). Host reads,
  allocations and data-dependent branches in a step are listed with their
  fate and milestone (``X.rst:318-342``).
* **Per lane**, sections 6 and 7: R ``R.rst:1521-1560``; C
  ``C.rst:1336-1571``; I ``I.rst:694-825``; EF ``EF.rst:879-1057``; S
  ``S.rst:1482-1613``; A ``A.rst:1053-1181``; O ``O.rst:1194-1293``; X
  ``X.rst:282-545``; K ``K.rst:561-625``.


6. Line budget, each line counted once (RULING V3-1)
----------------------------------------------------

Every figure here is at the heads of table 1. The baseline is measured at
the pin; the "after" figures are the lanes' own estimates and targets, not
counts of written code.

6.1 The baseline: all of ``src/`` at the pin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The round's baseline is every ``.cpp``, ``.hpp``, ``.h``, ``.cu`` and
``.cuh`` file under ``src/`` at the pin, counted with ``wc -l``::

  git ls-tree -r --name-only 9e5de2d4 -- src \
    | grep -E '\.(cpp|hpp|h|cu|cuh)$' \
    | while read f; do git cat-file -p 9e5de2d4:$f | wc -l; done \
    | awk '{s+=$1} END{print s}'

It prints **42,677**. Per directory: bc 1,155, coord 4,001, diagnostics
1,585, eos 2,716, forcing 2,938, hydro 5,608, implicit 2,337, input 2,041,
interface 1,008, layout 3,316, math 166, mesh 3,266, output 4,487, recon
2,233, riemann 2,089, scalar 458, sedimentation 1,049, turbulence 402,
utils 1,717, and two top-level files, ``src/snap.h`` 80 and
``src/add_arg.h`` 25 (105). The lane baselines partition this set exactly
(derived here from the per-file counts): R the six hydro files in table 2;
C recon + riemann + 1,519 lines of hydro reference files; I implicit +
``gravity_work*.hpp`` (250) + ``const_gravity.cpp`` (68) + math; EF eos +
scalar + sedimentation + turbulence + ``flux_positivity.*`` (346); S bc +
coord + layout; A forcing less ``const_gravity.cpp`` (2,938 - 68); O
output + input + utils + diagnostics; X mesh + interface. ``src/math``
(166) was in both O's and I's, and the 105 top-level lines are in no lane.
So 42,738 (the draft's sum) - 166 + 105 = 42,677.

The round target is **34,141**: 80 % of 42,677 (34,141.6), truncated
(Cheng's 20 % reduction on the whole of ``src/``). It is not a sum of lane
ceilings.

6.2 Per lane
~~~~~~~~~~~~

.. list-table:: Table 2. Section 9 totals, ``src/math`` counted once
   :header-rows: 1
   :widths: 6 30 10 10 44

   * - lane
     - scope
     - now
     - after
     - source and condition
   * - R
     - ``hydro_forward.cpp``, ``hydro.cpp``, ``hydro.hpp``,
       ``hydro_options.cpp``, ``register_forcing_modules.cpp``,
       ``x1_mass_covariance.hpp``
     - 3,493
     - 2,757
     - ``R.rst:1699-1725``; deletions D1-D7 1,303 (``R.rst:1633``)
   * - C
     - 50 lane C files (recon, riemann, reference)
     - 5,841
     - 3,329
     - ``C.rst:1602-1614``; the 587 lane R lines C replaces are not in
       C's 5,841 (``C.rst:1615-1619``, ``:1640-1643``)
   * - I
     - ``src/implicit``, ``gravity_work*.hpp``, ``const_gravity.cpp``,
       plus ``src/math`` (166)
     - 2,821
     - 2,032
     - ``I.rst:870-873``, ``:961-965``
   * - EF
     - eos, scalar, sedimentation, ``src/turbulence``,
       ``flux_positivity.*``
     - 4,971
     - 3,896
     - ``EF.rst:1128-1134``, ``:1366-1370``; ANEOS kept, F6 decided
       (``EF.rst:1416-1418``)
   * - S
     - coord, layout, bc
     - 8,472
     - 7,470
     - ``S.rst:1878-1890``: rev 2.1's 7,445, rev 2.2's +15 (pack/unpack
       split) and rev 2.3's +10 (``gather_x1`` and anchor-relay split), both
       estimates; no ceiling
   * - A
     - ``src/forcing`` less ``const_gravity.cpp``
     - 2,870
     - 2,088
     - ``A.rst:1272-1275``; needs O's options schema first, else 2,399
       (``A.rst:1307-1309``)
   * - O
     - ``src/output``, ``src/input``, ``src/utils``, ``src/diagnostics``
     - 9,830
     - 4,473
     - ``O.rst:1751``, ``:2453-2454``, ``:2456-2473``: 9,830 - 5,357
       (settled cut, 54.5 %). O drops the 166 ``src/math`` lines from both
       columns so they count once, in I (``O.rst:2460``, "Closed"). The
       draft's 4,453 used rev 3's cut 5,377; rev 4's is 5,357 (+20). O's
       ``restart.cpp`` (260) and ``budget.cpp`` (200) are new lines only
       (``O.rst:1540-1546``)
   * - X
     - ``src/mesh``, ``src/interface``
     - 4,274
     - 2,392
     - ``X.rst:591-616``: cut 1,882 (44.0 %), with the 159 ``src/mesh``
       lines of table 3 as X's deletion (o3, o4; ``X.rst:658-661``). Needs
       O5, else a cut of 986, and 827 without o3-o4 (``X.rst:760-762``;
       ``O.rst:1520-1523``)
   * - top level
     - ``src/snap.h``, ``src/add_arg.h``
     - 105
     - 105
     - in no lane; counted unchanged (6.1)
   * - **snapy**
     -
     - **42,677**
     - **28,542**
     - sum of the rows above (6.4)
   * - K
     - kintera touched files
     - 2,678
     - 2,585
     - ``K.rst:679-696``; kintera thermo total 4,801 -> 4,787
       (``K.rst:675-677``) is a wider scope, not added. K counts no snapy
       line (``K.rst:766-774``). Not in ``src/`` of snapy

Provider lines in X's table: pyharp and pydisort are listed apart and not in
X's 4,274 (``X.rst:593-597``; pydisort D1 -51 and D2 -17 at
``X.rst:749-754``). They are outside snapy's ``src/`` and the target.

6.3 Cross-lane ranges and who counts them
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table:: Table 3. Shared ranges
   :header-rows: 1
   :widths: 30 12 58

   * - range
     - counted by
     - evidence
   * - 587 ``hydro_forward.cpp``/``hydro.cpp`` lines C replaces
     - R (deletion); C (new code)
     - ``C.rst:1615-1619``, ``:1640-1643``; inside R's 1,303
       (``R.rst:1633``)
   * - 108 ``hydro_forward.cpp`` positivity lines
     - R
     - ``EF.rst:1132-1133``
   * - 149 hydro lines (R's D7, D5 ``:884-948``, D1 ``hydro.cpp:727-776``)
     - R
     - ``R.rst:1693-1697``; S counts none (``S.rst:129-130``)
   * - 153 gnomonic AAM lines leaving coord
     - S
     - ``S.rst:1653-1663``; A counts ``src/forcing`` only (``A.rst:1275``)
   * - 127 coord options-parsing lines
     - S
     - S deletes and counts them, O books none (``S.rst:1664-1667``)
   * - outside-lane deletions of I's rulings (a), (b)
     - R 136, X 124, A 18
     - ``I.rst:967-972``
   * - mesh fixer lines
     - X
     - ``X.rst:695``, ``:1314``; R books none (``R.rst`` section 9)
   * - ``signal_handler.*`` (213) moved into ``src/mesh``
     - O (kept, not cut)
     - ``O.rst:1515-1517``; outside X's 4,274 (``X.rst:778-783``)
   * - K's joint snapy rows (``ideal_moist.cpp``, ``meshblock.cpp``,
       ``moist_mixture.cpp``)
     - EF, X
     - ``K.rst:766-774``
   * - ``src/math/{lubksb,ludcmp}.h`` (166)
     - I
     - O's roll-up drops them from both its baseline and its "after"
       (``O.rst:2456-2473``); I keeps
       them in 2,821 and 2,032 (``I.rst:870-872``, ``:951-960``)
   * - ``meshblock.cpp:1623-1653`` (31), ``:1226-1339`` less ``1336-1337``
       (112), ``cycle_diagnostics.hpp`` (16): 159 lines
     - X (deletion); O (new lines only)
     - N = 159, counted at the pin. Under V3-1 X, the files' owner,
       counts the deletion (o3 -143, o4 -16; ``X.rst:593-594``,
       ``:658-661``), and O's ``restart.cpp`` (260) and ``budget.cpp``
       (200) are new lines only (``O.rst:91-106``, ``:1528-1548``)

6.4 Merged total
~~~~~~~~~~~~~~~~

* Baseline **42,677**, after **28,542**: cut 14,135 (-33.1 %), 5,599
  lines under the round target 34,141 (6.1).
* The after is the sum of table 2's rows as each lane states it: R 2,757,
  C 3,329, I 2,032, EF 3,896, S 7,470, A 2,088, O 4,473, X 2,392 and the
  105 top-level lines.
* History: part 1 summed 42,738 -> 28,717 with ``src/math`` twice and the
  top-level files missing; the PM's inputs gave 42,677 and 28,691; S rev
  2.3 (+10) and the 159 lines as X's deletion (-159) give 28,542.
* S's +25 since rev 2.1, O's design target (5,787, ``O.rst:1757``)
  and X's conditions on O5 are estimates or conditions, not counts.
* Kintera, outside snapy's ``src/``: 2,678 -> 2,585 (``K.rst:679-696``).


7. PR plan, one order
---------------------

Order rules taken from the lanes' merge-order text: providers first
(``X.rst:574-575``; ``K.rst:654-670``); R's own order (``R.rst:1567-1574``);
C (``C.rst:1579-1589``); I (``I.rst:858-864``); EF (``EF.rst:1526-1529``);
S (``S.rst:1633-1637``, phases ``:1949-1975``); A (``A.rst:1210-1220``,
phases ``:1318-1334``); O (``O.rst:1449-1458``); K (``K.rst:654-667``).
"Against main" is the lane's own words, shortened. A step can start when
every step it depends on has merged; steps in one wave are independent of
each other unless the dependency column says so.

.. list-table:: Table 4. Merged PR plan
   :header-rows: 1
   :widths: 5 12 9 30 22 22

   * - wave
     - PR
     - repo
     - depends on
     - against main
     - source
   * - 0
     - P1 pyharp ``out=``
     - pyharp
     - none
     - bitwise
     - ``X.rst:815``; first in ``K.rst:656``
   * - 0
     - P2 pydisort flag tables
     - pydisort
     - none
     - bitwise; same printed text
     - ``X.rst:816``
   * - 0
     - K1-K4, one kintera release
     - kintera
     - P1 (``K.rst:656-659``); paired-revision gate K-G9
     - bitwise (K3: hypothesis near ``ftol``)
     - ``K.rst:782-785``, ``:644-646``
   * - 1
     - #369 (open upstream PR)
     - snapy
     - none; V3 rebases on it
     - n/a
     - ``I.rst:860``
   * - 1
     - O1, O2, O2b, O3, O4
     - snapy
     - none (``O.rst:1452``)
     - bitwise (O2b: for runs without ``SNAP_FP32_STORAGE``)
     - ``O.rst:2622-2660``
   * - 1
     - C1, C2
     - snapy
     - none
     - C1 bitwise; C2 MPS changes (FOR CHENG)
     - ``C.rst:1581``, ``:1790-1801``
   * - 1
     - EF-1, EF-2, EF-5, EF-11; EF-10 any time
     - snapy
     - none
     - bitwise (EF-1: MPS path changes)
     - ``EF.rst:1526-1528``, ``:1451-1483``, ``:1507-1517``
   * - 1
     - X1 ``PrecisionPolicy``, then X2, X3
     - snapy
     - providers (``X.rst:574``)
     - X1 bitwise; X2 bitwise (hypothesis); X3 eager bitwise
     - ``X.rst:818-820``
   * - 1
     - S merge steps (1)-(3), phase 1 transport
     - snapy
     - none
     - bitwise (phase 1); T1 round-off
     - ``S.rst:1633-1635``, ``:1949-1954``
   * - 1
     - R-1 register, no reader
     - snapy
     - none
     - gates G-R1, G-R3
     - ``R.rst:1569``, ``:1739-1740``
   * - 1
     - I-1, I-2, I-3 (need no register)
     - snapy
     - #369
     - I-1, I-2 bitwise (hypothesis); I-3 rounding (target 1e-11)
     - ``I.rst:862-863``, ``:988-1005``
   * - 2
     - A phase 1
     - snapy
     - O4 (``A.rst:1212-1213``, ``:1307``)
     - G1 bitwise
     - ``A.rst:1321-1323``
   * - 2
     - C3, C4; C4's rotation call after S moves the helper
     - snapy
     - C1, C2; S (``C.rst:1587``)
     - bitwise
     - ``C.rst:1582``, ``:1802-1809``
   * - 2
     - C6; C7
     - snapy
     - C7 after X1 (``C.rst:1583``)
     - C6 key 2 bitwise, key 4 round-off; C7 bitwise
     - ``C.rst:1817-1824``
   * - 2
     - R-2, R-3 with C5, C8 and EF-3 -> EF-4 -> EF-6 -> EF-12 -> EF-7
     - snapy
     - R-1 (``C.rst:1585``; ``EF.rst:1526-1527``)
     - C5 bitwise except AAM ``exact``; EF-3 bitwise without
       sedimentation; EF-4 bitwise (hypothesis); EF-6, EF-7 rounding
     - ``R.rst:1570``, ``:1741-1743``; ``C.rst:1810-1816``,
       ``:1825-1827``; ``EF.rst:1465-1495``
   * - 2
     - R-4 with S step (4) and phase 3: seam ``replace``, row 16r,
       ``boundary.prescribed``
     - snapy
     - R-1
     - round-off (hypothesis, G-R10); else FOR CHENG
     - ``R.rst:1571``, ``:1744-1745``; ``S.rst:1635-1637``,
       ``:1963-1975``
   * - 2
     - R-5 with I-4, I-5, I-6, I-7 (and R's and X's I-7 parts)
     - snapy
     - R-1; I-6 with X's predicated second launch (section 2)
     - I-4, I-5 rounding (hypothesis); I-6 per-column FP64 retry
       (accepted, 1.1): bitwise when no column fails, beyond round-off
       for the unfailed columns of a failing block
     - ``R.rst:1572``, ``:1746``; ``I.rst:1006-1017``
   * - 2
     - X4 global phase; X5; X6; X7
     - snapy
     - X1-X3
     - X4, X5 bitwise (hypothesis); X6 bitwise plus 5 % wall time
     - ``X.rst:821-824``
   * - 3
     - A phase 2; R-6
     - snapy
     - R, I-4 (``I.rst:864``), X4, S rotation data, #370 in the reference
     - G2-G7 (tolerance)
     - ``A.rst:1214-1216``, ``:1324-1332``; ``R.rst:1573``, ``:1747-1748``
   * - 3
     - EF-8, raising the kintera floor
     - snapy
     - the kintera release (K1-K4)
     - bitwise FP64
     - ``EF.rst:1527``, ``:1496-1506``; ``K.rst:649-650``
   * - 3
     - S-K1, S-K2, S-K3, then S-K4
     - snapy
     - EF-2 and EF-8; S-K4 also X4
     - S-K1, S-K3 bitwise; S-K2 hypothesis (K-G5); S-K4 with X's gate
     - ``K.rst:650-652``, ``:660-666``, ``:786-789``
   * - 3
     - O5, then X8 (F1, F2; sv after O4; F3 any time)
     - snapy
     - O5 before X8 (``O.rst:2674-2680``)
     - bitwise files; X8 no numerics
     - ``O.rst:2661-2680``; ``X.rst:825``
   * - 3
     - O6a, then O6b; O7
     - snapy
     - G-2 passes before O6b
     - bitwise data, exact metadata
     - ``O.rst:2681-2697``
   * - 4
     - O8 consumers; R-7
     - snapy
     - R's register and monitor; X's post-accept phase
       (``O.rst:1453-1456``)
     - new file; cycle line bitwise if order kept
     - ``O.rst:2698-2707``; ``R.rst:1574``, ``:1749``
   * - 4
     - A phase 3 (diffusion ``post_split``) with S's M6
     - snapy
     - A phase 2; S-3
     - G8, G9 (tolerance)
     - ``A.rst:1333``; ``S.rst:1973-1975``
   * - 4
     - S phase 2 (rotation, corners); S step (5) deletions
     - snapy
     - S phase 1
     - round-off (T1); periodic corners beyond round-off (FOR CHENG)
     - ``S.rst:1956-1961``, ``:1637``
   * - 5
     - A phase 4 (FP32, perturbation flux)
     - snapy
     - A phase 3
     - G10
     - ``A.rst:1334``
   * - 5
     - C9 last; C10 only if Cheng accepts
     - snapy
     - all lane C PRs
     - FP64 bitwise; FP32 re-baselined
     - ``C.rst:1589``, ``:1828-1833``
   * - 6
     - K5 (``nfail_`` private)
     - kintera
     - snapy no longer uses ``nfail_``
     - bitwise
     - ``K.rst:667``, ``:790``

Open in the plan: no lane gives a dependency for P2 or for S's phase 2;
both are placed where they block nothing. I-6 is no longer blocked: the
per-column retry is accepted (section 2). C2, C10, S phase 2's corner correction
and the FOR CHENG items of each lane stay with Cheng.


8. Gates by name, owner and kind
--------------------------------

Kind is one of: **bitwise** (exact equality, or an exact pass/fail
identity), **tolerance** (a stated bound), **hypothesis** (the lane marks
the claim unverified, or the bound is a target to be set by a first
measurement). Where a lane states two kinds for one gate, both are given.
Every gate here is specified, not run.

8.1 Named gates
~~~~~~~~~~~~~~~

.. list-table:: Table 5. Named gates
   :header-rows: 1
   :widths: 9 6 45 20 20

   * - gate
     - owner
     - identity (short)
     - kind
     - source
   * - G-R1
     - R
     - posts reproduce the pin's ``_flux1/2/3``
     - bitwise (EF settling part excepted)
     - ``R.rst:1457-1460``
   * - G-R2
     - R
     - shared faces single-valued after ``reconcile``
     - bitwise x1; hypothesis x2/x3 (round-off)
     - ``R.rst:1461-1466``
   * - G-R3
     - R
     - step recursion equals ``sum c_s dt T_s``
     - tolerance 1e-15
     - ``R.rst:1467-1470``
   * - G-R4
     - R
     - budget closes
     - tolerance 1e-12 per row
     - ``R.rst:1471-1474``
   * - G-R5
     - R
     - rollback zeroes register and monitor
     - bitwise
     - ``R.rst:1475-1478``
   * - G-R6
     - R
     - capturable, fixed addresses
     - bitwise (capture succeeds)
     - ``R.rst:1479-1482``
   * - G-R7
     - R
     - vic energy wall residual
     - tolerance < 1e-13, else ``vic.cell``
     - ``R.rst:1483-1486``
   * - G-R8
     - R
     - ``riemann.central`` equals ``cen2``/``cen3``
     - tolerance 1e-14
     - ``R.rst:1487-1490``
   * - G-R9
     - R
     - ``boundary.prescribed`` amount
     - hypothesis (round-off, else declared change)
     - ``R.rst:1491-1495``
   * - G-R10
     - R
     - same-process x1 seam difference
     - hypothesis (measured, for K6)
     - ``R.rst:1496-1499``; ``S.rst:1967-1969``
   * - G-R11
     - R
     - ``A_f total(1)`` equals ``Phi``
     - tolerance 1 ulp
     - ``R.rst:1500-1503``
   * - G-R12
     - R
     - carry momentum frame
     - bitwise
     - ``R.rst:1504-1508``
   * - G-R13
     - R
     - transposed panel edges after ``owner_copy``
     - bitwise non-momentum; tolerance 1e-14 momentum
     - ``R.rst:1509-1513``
   * - G-R14
     - R
     - amounts recursion
     - tolerance 1e-15
     - ``R.rst:1514-1518``
   * - G-S13
     - S
     - panel-edge map on 2T:3T, with a negative control
     - bitwise non-momentum; hypothesis 1e-14 momentum
     - ``S.rst:1435-1448``
   * - G-S-K7
     - S
     - post-limit single-valuedness (gate harness only)
     - bitwise x1 and panel non-momentum; tolerance momentum; failing
       today is a hypothesis
     - ``S.rst:1449-1472``
   * - G-EF-1
     - EF
     - register posts equal the pin after step 4.C
     - bitwise species and no-sedimentation decks; tolerance otherwise
     - ``EF.rst:847-854``
   * - G-EF-2
     - EF
     - ``EfStatus`` gives the same redo causes
     - bitwise
     - ``EF.rst:855-859``
   * - G-EF-3
     - EF
     - graph replay equals eager (limiter, vapor, sedimentation)
     - bitwise
     - ``EF.rst:860-865``
   * - G-EF-4
     - EF
     - shared ``PositivityLimiter`` equals today's scalar path
     - bitwise (EF-4 marks it hypothesis, ``EF.rst:1476``)
     - ``EF.rst:866-869``
   * - G-EF-9
     - EF
     - base ``species_energy`` and single sedimentation kernel
     - hypothesis (tolerance 1e-12 to be set from measurement)
     - ``EF.rst:870-877``
   * - EF I1-I11
     - EF
     - existing invariants: species mass, positivity, carry, ratio, vapor
       repair, borrow, floors, sedimentation, scalars, EOS round trips,
       theta
     - I2, I7, I11 bitwise (exact); I5 tolerance (mass) and exact
       (counts); the rest tolerance
     - ``EF.rst:791-846``
   * - G1
     - A
     - existing tests against the reference
     - bitwise
     - ``A.rst:976-977``
   * - G2
     - A
     - kept ``riemann.central`` vs today's central
     - tolerance 1e-13
     - ``A.rst:978-980``
   * - G3, G3b
     - A
     - ``exact`` AAM drift; block-count invariance (G3b plan only)
     - tolerance 1e-12
     - ``A.rst:981-984``
   * - G4
     - A
     - ``off`` and ``transport`` against the reference
     - bitwise (rule)
     - ``A.rst:985-986``
   * - G5
     - A
     - seam single-valuedness of ``A F · K_f``, after G-S-K7
     - tolerance 1e-14
     - ``A.rst:987-988``; ``S.rst:1464-1472``
   * - G6, G7, G7s
     - A
     - closure; sponge/drag torque; AAM with sedimentation
     - tolerance (1e-12; 1e-15 of L; C n eps)
     - ``A.rst:989-993``
   * - G8, G9, G9b
     - A
     - diffusion suite; viscous torque; register vs Cartesian route
       (G9b plan only)
     - tolerance (own; 1e-12; 1e-12)
     - ``A.rst:994-999``
   * - G10
     - A
     - FP32 + perturbation-flux AAM drift vs FP64
     - tolerance (drift <= 1e-12)
     - ``A.rst:1000-1001``
   * - G-1
     - O
     - 25 example decks, every written file vs base
     - bitwise
     - ``O.rst:1083-1087``
   * - G-2
     - O
     - combiner parity
     - bitwise data, exact metadata
     - ``O.rst:1088-1093``
   * - G-3
     - O
     - generated option structs and parses
     - bitwise (exact)
     - ``O.rst:1094-1099``
   * - G-4
     - O
     - restart round trip, budget carry
     - bitwise, plus a RED test
     - ``O.rst:1100-1107``
   * - G-5
     - O
     - budget residual, closed box and all fixers
     - tolerance (proposed 1e-12 x total, estimate; set by G0)
     - ``O.rst:1108-1112``, ``:1066-1068``
   * - G-6
     - O
     - ported ``test_rectify``
     - bitwise (exact)
     - ``O.rst:1113-1116``
   * - K-G1
     - K
     - exact plan equals the pin's ``VU->T``, ``PV->T``
     - bitwise (FP64 inputs)
     - ``K.rst:550``
   * - K-G2
     - K
     - ``fixed`` equals ``eager_exit``
     - bitwise
     - ``K.rst:551``
   * - K-G3
     - K
     - no host sync in a captured kintera op
     - bitwise (pass/fail)
     - ``K.rst:552``
   * - K-G4
     - K
     - failure counts survive replay
     - bitwise (exact)
     - ``K.rst:553``
   * - K-G5
     - K
     - retry repeats the first attempt
     - hypothesis (bitwise)
     - ``K.rst:554``
   * - K-G6
     - K
     - tables equal the pin's per-call values
     - bitwise
     - ``K.rst:555``
   * - K-G7
     - K
     - saturation conserves mass and energy
     - tolerance (round-off, FP64 sum)
     - ``K.rst:556``
   * - K-G8
     - K
     - chemistry conserves elements
     - tolerance (solver)
     - ``K.rst:557``
   * - K-G9
     - K
     - paired revisions build
     - bitwise (exact)
     - ``K.rst:558``
   * - K-G10
     - K
     - ``prepare()`` idempotent
     - bitwise (same addresses)
     - ``K.rst:559``

8.2 Gates named by identity (no id in the lane)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table:: Table 6. Unnumbered gates
   :header-rows: 1
   :widths: 6 50 22 22

   * - owner
     - identity and test
     - kind
     - source
   * - X
     - eager result after X1, X2, X5 equals the pin (N-step golden)
     - bitwise
     - ``X.rst:270``
   * - X
     - ``out=`` RK combine equals the allocating form
     - bitwise (x86 NaN payloads excepted)
     - ``X.rst:271``
   * - X
     - state addresses fixed; no host sync inside a segment
     - bitwise (exact)
     - ``X.rst:272-273``
   * - X
     - graph replay equals eager (Straka)
     - hypothesis (bitwise), else the test's tolerance
     - ``X.rst:274``
   * - X
     - flags survive replay; rollback restores the step; dtype per quantity
     - bitwise (exact)
     - ``X.rst:275``, ``:277-278``
   * - X
     - global corrections unchanged on 1 and 4 blocks
     - hypothesis (bitwise if partial order kept)
     - ``X.rst:279``
   * - X
     - chemistry slot before ``Mesh::forward``'s final exchange
     - hypothesis (bitwise); the no-source baseline strictly bitwise;
       fallback tolerance measured first
     - ``X.rst:280``
   * - C
     - refactor PRs C1-C4, C7, C8 change no result (#349 dump set)
     - bitwise
     - ``C.rst:1277-1279``
   * - C
     - CPU against CUDA
     - tolerance (bitwise for dc/plm)
     - ``C.rst:1280-1283``
   * - C
     - MPS equals CPU at float32 after C2
     - bitwise
     - ``C.rst:1284-1287``
   * - C
     - rest balance, ``max |v|/c <= 1e-12``
     - tolerance
     - ``C.rst:1288-1291``
   * - C
     - ``balance_column`` fixed point; no mass through a reflecting wall;
       x1 seam faces single-valued; floor counts
     - bitwise (identity)
     - ``C.rst:1292-1300``, ``:1329-1331``
   * - C
     - key-4 order >= 4.9
     - tolerance
     - ``C.rst:1301-1303``
   * - C
     - ``riemann.central`` equals today's central rows (A's G2)
     - tolerance 1e-14
     - ``C.rst:1304-1315``
   * - C
     - every solver and scheme parses and runs as before; split equals
       total in FP64; conservation; FP32 after C9
     - bitwise; tolerance (existing tests); tolerance (predeclared)
     - ``C.rst:1316-1334``
   * - I
     - I1 rows = apply (W and K unit tests, RED if one side changes)
     - tolerance (round-off)
     - ``I.rst:637-640``, ``:685``
   * - I
     - I2 booked = G[register M]; I3 mass telescoping
     - unstated in the invariant line
     - ``I.rst:641-645``, ``:686``
   * - I
     - I4 linear in the explicit increment, on C's rest gate
     - hypothesis
     - ``I.rst:646-656``, ``:687-688``
   * - I
     - I5 no reference row (operator argument, no run)
     - none (design argument)
     - ``I.rst:657-671``
   * - I
     - #348 harness (bitwise gate of I-1, I-2); I-3 energy row
     - bitwise (hypothesis); hypothesis (target 1e-11)
     - ``I.rst:675``, ``:678-680``, ``:988-1005``
   * - I
     - sync-counter test; per-column status test
     - bitwise (pass/fail)
     - ``I.rst:689-691``
   * - S
     - same-process x1 seams; seam single-valuedness; transport-only rows
       (nb and pz pairs)
     - bitwise (momentum to the section 4 tolerance)
     - ``S.rst:1423-1430``, ``:1473-1476``, ``:1951-1952``
   * - S
     - periodic corners (ghost-image test); rotation involution
       (structural); solid faces (= G-R9)
     - bitwise (structural); G-R9's kind
     - ``S.rst:1419-1422``, ``:1431-1434``, ``:1477-1479``

8.3 Which PR carries each gate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Only where the lane names it; a gate with no PR named is run with the PRs
of its lane's section 10.

* **R:** R-1 G-R1, G-R3; R-2 G-R8; R-4 G-R2, G-R9, G-R10; R-6 G-R11; R-7
  G-R4 (``R.rst:1739-1749``).
* **C:** C1-C4, C7, C8 the #349 dump set; C5 the floor-count test; C9 the
  ``fp32-foundations`` label (``C.rst:1277-1279``, ``:1329-1334``).
* **I:** I-1 and I-2 the #348 harness, pin against PR; I-3 the energy-row
  tolerance target (``I.rst:988-1005``).
* **EF:** EF-2 G-EF-2; EF-4 G-EF-4; EF-6 and EF-7 G-EF-9
  (``EF.rst:1459-1463``, ``:1473-1476``, ``:1484-1495``).
* **S:** phase 1 the nb = 1, 2 and pz = 1, 2 bitwise runs
  (``S.rst:1949-1953``); phase 3 G-R10 and the solid-face leak
  (``S.rst:1963-1973``).
* **A:** G1 phase 1; G2-G7s phase 2; G8, G9, G9b phase 3; G10 phase 4
  (``A.rst:974-1001``).
* **O:** G-1 O1-O3, O5, O7; G-2 O6a, before O6b; G-3 O4; G-4 O7; G-5 O8;
  G-6 O2 (``O.rst:1083-1116``).
* **X:** X2 and X5 the N-step golden; X4 the chemistry-slot gate's
  no-source baseline, its source run with S-K4; X6 the wall-time gate
  (``X.rst:819-823``).
* **K:** K3 K-G1, K-G2; S-K2 K-G5; the release K-G9 (``K.rst:784``,
  ``:787``, ``:644-646``).


9. FOR CHENG, in one place
--------------------------

Open items only, each with the lane's text; decided items are in section 2.
Lanes R and X carry none (X's last two are accepted, ``X.rst:1481-1482``).
Lane I's (c) is decided (section 2).

.. list-table:: Table 8. Open FOR CHENG items
   :header-rows: 1
   :widths: 5 55 40

   * - lane
     - item
     - source
   * - C
     - single Riemann default ``hllc``; one ``shock`` default; density and
       pressure floors on the shock path; MPS through ``OnHost``; FP32
       typed constants (C9 of lane C); one Python ``RiemannSolver``
       binding; a ``--fmad=false`` CI build; upwind and plume-roe refused
       where they cannot solve a hydro direction
     - ``C.rst:837-867``; defaults ``C.rst:885``
   * - EF
     - F3 sedimentation results; F4 MPS support level; F5 one moist EOS
       (undecided); the D8 sedimentation target
     - ``EF.rst:1610``, ``:1637``, ``:1659-1660``, ``:1716-1718``
   * - S
     - the periodic-corner correction (beyond round-off on periodic x2
       and x3); enabling the same-process x1 mean if G-R10 shows more than
       round-off; the solid-face mirror leak if it is not round-off; the
       M3 anchor scan beyond round-off
     - ``S.rst:1956-1961``, ``:1044-1048``, ``:1963-1973``,
       ``:1979-1983``
   * - A
     - refusing ``full`` with a message naming ``exact``; Coriolis
       ``type: 123``; the AAM key on grids with no axis; a non-z rotation
       axis
     - ``A.rst:166-172``, ``:1365-1387``
   * - O
     - super-resolution (removed in this design with ``utils/refine.*``);
       the ``SNAP_ANOMALY`` override
     - ``O.rst:743-744``, ``:758-761``
   * - K
     - K-F1, restoring the active set on a retry; K-F2, a cheaper graph
       form of the T-dependent inversion
     - ``K.rst:798-807``


10. Open items and the approval condition
-----------------------------------------

* **Cheng's approval of this document** is the condition for any
  implementation, build or runtime gate. No gate in section 8 has run.
* **Lane I rev 2.5** (``1092aef9``) was not on ``zoeyzyhu/snapy
  v3-design/I`` at 03:39 UTC; ``2d8685c8`` still marks the per-column retry
  as open (section 2).
* **R:** Xinyue's five notes, whose text R never had (``R.rst:1804``).
* **EF on S:** EF's notes 3-5 on S are not verified against S
  (``EF.rst:2058-2061``).
* **S, RULING V3-4** (section 2): corners are filled in the unpack of the
  last round of each field set. S rev 2.3 (``bee1b276``,
  ``S.rst:1565-1568``) still says the row's last round; S rev 2.4 carries
  the wording, with no declaration change.
* **The FOR CHENG items** of section 9.
* **Estimates:** every "after" figure of section 6 and the 34,141 target
  margin rest on design estimates (section 6.4).
