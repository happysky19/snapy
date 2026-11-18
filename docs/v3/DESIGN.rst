:orphan:

V3 design: merged budget, PR plan and gates (part 1)
====================================================

Draft part 1, 2026-11-17, Tianhao Le. Design text only: nothing here was
built, compiled or run. This part merges three things from the nine lane
designs: the section 9 line budgets (counted once under RULING V3-1), the
section 10 PR lists in one order with the provider repositories first, and
the gates by name, owner and kind. The full document follows after
``CONVERGED``.

Conventions. ``L.rst:N`` is line N of lane L's design at the snapshot head
in table 1. Bare repository paths with ``:N`` are at chengcli/snapy
``9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410`` (the pin). Numbers are copied
from the lane documents; a number derived here says how it was derived.
"Estimate" and "target" keep the lane's meaning: a design figure, not a
count of written code.


1. Snapshot
-----------

Every head below was read with ``git ls-remote`` and fetched; the full SHA
was then checked to be a commit. The repository and branch are the ones
GitHub returned for ``refs/heads/v3-design/<lane>``.

.. list-table:: Table 1. Lane heads used for this part
   :header-rows: 1
   :widths: 6 26 46 22

   * - lane
     - repository, branch
     - snapshot head
     - note
   * - R
     - happysky19/snapy ``v3-design/R``
     - ``a15af81660f75b53f3e905b7ee15aa935ada855c``
     - live head moved to ``c9ecc0ca`` (rev 2.5, section 11 text only)
   * - C
     - happysky19/snapy ``v3-design/C``
     - ``bcac27c97a9efc1de2cb2041e6b709f07eedcefe``
     - live head moved to ``5dc4d002`` (rev 6.3, change-list text only)
   * - I
     - zoeyzyhu/snapy ``v3-design/I``
     - ``fa3ad5e6ef4ab51f40b6a53889d9f3b7ec62cadb``
     - docs-only mirror, no common history with the pin
   * - EF
     - zoeyzyhu/snapy ``v3-design/EF``
     - ``f5c8e9a76f2b06045b545cc692bff7262f13ac0d``
     - docs-only mirror, no common history with the pin
   * - S
     - jihenghu/snapy ``v3-design/S``
     - ``4b96f4ea9a63fd6152e319a70930559cdfda0871``
     - rev 2.1
   * - A
     - JiachenLiu-Atmos/snapy ``v3-design/A``
     - ``a0b006d29cf7c9c8147ebdc387ecddc672623b79``
     -
   * - O
     - JiachenLiu-Atmos/snapy ``v3-design/O``
     - ``5d1c50b6be81840a4754235f16995b17536c30ea``
     -
   * - X
     - UCzhangxi/snapy ``v3-design/X``
     - ``36d4986fcf17da330f8678946401a7f39ee9db81``
     - rev 3.18; live head moved to ``e5a6abaa`` (rev 3.19, one commit)
   * - K
     - UCzhangxi/kintera ``v3-design/K``
     - ``8d962405f072e00bcadf7e072722ad5c5c18f4ec``
     -

The snapy heads except I and EF have the pin as merge base. The four live
moves above happened after the snapshot; this part cites the snapshot.


2. Line budget, each line counted once (RULING V3-1)
----------------------------------------------------

Section 2 corrected 2026-11-17 (part 1.1) with the PM's reconciliation
inputs, each checked below. Lanes O and S moved after the snapshot and
change the totals, so they are cited at their live heads: O
JiachenLiu-Atmos/snapy ``f5c8e9e1086ee1c56753e2b21af345ebb6cba28a``, S
jihenghu/snapy ``7ca6d21c7319a30c5d193e2e79347c3778029553`` (rev 2.2). The
other lanes' totals were re-read at their live heads and are unchanged: I
``2d8685c80ca6edda1c1e4e631dce035d8dff75f6`` (``I.rst:961-965``), EF
``5b3f18d28c2db7305fd3fef8b04f0319b8a326c1`` (``EF.rst:1366-1370``), A
``c405d49133326bb6db30650df57166d53f507067`` (``A.rst:1272-1275``), X
``7bed6980dbf572233c09d64e2d40bbf29eed0b7d`` (``X.rst:615``), R
``c9ecc0ca`` and C ``5dc4d002`` (text-only moves), K unmoved. Their cites
below stay at the snapshot of table 1. **Every figure in this section is
provisional** until ``CONVERGED`` and the open row of table 3.

2.1 The baseline: all of ``src/`` at the pin
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

2.2 Per lane
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
     - ``R.rst:1683-1709``; deletions D1-D7 1,303 (``R.rst:1617``)
   * - C
     - 50 lane C files (recon, riemann, reference)
     - 5,841
     - 3,329
     - ``C.rst:1598-1610``; the 587 lane R lines C replaces are not in
       C's 5,841 (``C.rst:1611-1615``, ``:1636-1639``)
   * - I
     - ``src/implicit``, ``gravity_work*.hpp``, ``const_gravity.cpp``,
       plus ``src/math`` (166)
     - 2,821
     - 2,032
     - ``I.rst:844-847``, ``:935-939``
   * - EF
     - eos, scalar, sedimentation, ``src/turbulence``,
       ``flux_positivity.*``
     - 4,971
     - 3,896
     - ``EF.rst:1126-1132``, ``:1364-1368``; ANEOS kept, F6 decided
       (``EF.rst:1414-1416``)
   * - S
     - coord, layout, bc
     - 8,472
     - 7,460
     - live ``S.rst:1822-1825``, ``:1828-1833``, ``:1853-1854``: rev 2.1's
       7,445 plus rev 2.2's +15 (pack/unpack split, estimate); no ceiling
   * - A
     - ``src/forcing`` less ``const_gravity.cpp``
     - 2,870
     - 2,088
     - ``A.rst:1210-1213``; needs O's options schema first, else 2,399
       (``A.rst:1245-1247``)
   * - O
     - ``src/output``, ``src/input``, ``src/utils``, ``src/diagnostics``
     - 9,830
     - 4,473
     - live ``O.rst:2394-2395``, ``:2397-2414``, ``:2429-2433``: 9,830 -
       5,357 (settled cut, 54.5 %). O drops the 166 ``src/math`` lines from
       both columns so they count once, in I (``O.rst:2401``, "Closed").
       The draft's 4,453 used rev 3's cut 5,377; rev 4's is 5,357 (+20)
   * - X
     - ``src/mesh``, ``src/interface``
     - 4,274
     - 2,551
     - ``X.rst:587-611``; needs O5, else a cut of 827 (``X.rst:751-755``;
       ``O.rst:1456-1459``)
   * - top level
     - ``src/snap.h``, ``src/add_arg.h``
     - 105
     - 105
     - in no lane; counted unchanged (2.1)
   * - **snapy**
     -
     - **42,677**
     - **28,691**
     - sum of the rows above, provisional (2.4)
   * - K
     - kintera touched files
     - 2,678
     - 2,585
     - ``K.rst:679-696``; kintera thermo total 4,801 -> 4,787
       (``K.rst:675-677``) is a wider scope, not added. K counts no snapy
       line (``K.rst:766-774``). Not in ``src/`` of snapy

Provider lines in X's table: pyharp and pydisort are listed apart and not in
X's 4,274 (``X.rst:589-592``; pydisort D1 -51 and D2 -17 at
``X.rst:740-745``). They are outside snapy's ``src/`` and the target.

2.3 Cross-lane ranges and who counts them
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table:: Table 3. Shared ranges
   :header-rows: 1
   :widths: 30 12 58

   * - range
     - counted by
     - evidence
   * - 587 ``hydro_forward.cpp``/``hydro.cpp`` lines C replaces
     - R (deletion); C (new code)
     - ``C.rst:1611-1615``, ``:1636-1639``; inside R's 1,303
       (``R.rst:1617``)
   * - 108 ``hydro_forward.cpp`` positivity lines
     - R
     - ``EF.rst:1130-1131``
   * - 149 hydro lines (R's D7, D5 ``:882-946``, D1 ``hydro.cpp:727-776``)
     - R
     - ``R.rst:1677-1681``; S counts none (``S.rst:125-126``)
   * - 153 gnomonic AAM lines leaving coord
     - S
     - ``S.rst:1580-1590``; A counts ``src/forcing`` only (``A.rst:1213``)
   * - 127 coord options-parsing lines
     - S
     - S deletes and counts them, O books none (``S.rst:1591-1594``)
   * - outside-lane deletions of I's rulings (a), (b)
     - R 136, X 124, A 18
     - ``I.rst:941-946``
   * - mesh fixer lines
     - X
     - ``X.rst:686``, ``:1295``; R books none (``R.rst`` section 9)
   * - ``signal_handler.*`` (213) moved into ``src/mesh``
     - O (kept, not cut)
     - ``O.rst:1451-1453``; outside X's 4,274 (``X.rst:769-774``)
   * - K's joint snapy rows (``ideal_moist.cpp``, ``meshblock.cpp``,
       ``moist_mixture.cpp``)
     - EF, X
     - ``K.rst:766-774``
   * - ``src/math/{lubksb,ludcmp}.h`` (166)
     - I
     - **closed** by O at ``f5c8e9e1``: O's roll-up drops them from both
       its baseline and its "after" (live ``O.rst:2397-2414``); I keeps
       them in 2,821 and 2,032 (``I.rst:844-846``, ``:925-934``)
   * - ``meshblock.cpp:1623-1653`` (31), ``:1226-1339`` less ``1336-1337``
       (112), ``cycle_diagnostics.hpp`` (16): 159 lines
     - **open, provisional**
     - Both lanes call them moved, counted in neither lane's cut (live
       ``X.rst:970-985``; live ``O.rst:1475-1484``, ``:2898-2900``). X
       lists ``meshblock.cpp`` (1,919 -> 1,919) and
       ``cycle_diagnostics.hpp`` (16 -> 16) as joint rows not counted
       (live ``X.rst:608``, ``:770-771``), and O absorbs the lines into its
       estimated ``restart.cpp`` (260) and ``budget.cpp`` (200) (live
       ``O.rst:1481-1483``). Neither says which "after" column holds them.
       The PM has asked Xi and Jiachen; no owner is chosen here (2.4)

2.4 Merged total, provisional
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Baseline **42,677**, after **28,691**: cut 13,986 (-32.8 %), 5,450 under
  the round target 34,141.
* The PM's arithmetic is reproduced: 42,738 - 166 + 105 = 42,677, and the
  draft's 28,551 + 105 (top level) + 20 (O, 4,473 not 4,453) + 15 (S rev
  2.2) = 28,691.
* **Open, the 159 ``src/mesh`` lines** (last row of table 3). If X's
  "after" and O's estimates both hold them, the after is 28,532; if one of
  them does, 28,691; if neither does, 28,850. The after therefore lies in
  **28,532 to 28,850**, under the target in every case (5,291 to 5,609
  lines under). The owner is for Xi and Jiachen to state.
* S rev 2.2 (``7ca6d21c``) has an open design conflict in the lane S thread
  (S rev 2.3, Jiheng); its +15 is S's estimate and may move with it.
* The draft's 28,676 and 34,141 question is answered: 34,141 is the round
  target (2.1), and the PM's inputs reconcile the after to 28,691.
* Kintera, outside snapy's ``src/``: 2,678 -> 2,585.


3. PR plan, one order
---------------------

Order rules taken from the lanes' merge-order text: providers first
(``X.rst:570-571``; ``K.rst:654-670``); R's own order (``R.rst:1551-1558``);
C (``C.rst:1575-1585``); I (``I.rst:832-838``); EF (``EF.rst:1524-1527``);
S (``S.rst:1560-1564``, phases ``:1867-1893``); A (``A.rst:1148-1158``,
phases ``:1256-1272``); O (``O.rst:1385-1394``); K (``K.rst:654-667``).
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
     - ``X.rst:806``; first in ``K.rst:656``
   * - 0
     - P2 pydisort flag tables
     - pydisort
     - none
     - bitwise; same printed text
     - ``X.rst:807``
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
     - ``I.rst:834``
   * - 1
     - O1, O2, O2b, O3, O4
     - snapy
     - none (``O.rst:1388``)
     - bitwise (O2b: for runs without ``SNAP_FP32_STORAGE``)
     - ``O.rst:2529-2567``
   * - 1
     - C1, C2
     - snapy
     - none
     - C1 bitwise; C2 MPS changes (FOR CHENG)
     - ``C.rst:1577``, ``:1786-1797``
   * - 1
     - EF-1, EF-2, EF-5, EF-11; EF-10 any time
     - snapy
     - none
     - bitwise (EF-1: MPS path changes)
     - ``EF.rst:1524-1526``, ``:1449-1481``, ``:1505-1515``
   * - 1
     - X1 ``PrecisionPolicy``, then X2, X3
     - snapy
     - providers (``X.rst:570``)
     - X1 bitwise; X2 bitwise (hypothesis); X3 eager bitwise
     - ``X.rst:809-811``
   * - 1
     - S merge steps (1)-(3), phase 1 transport
     - snapy
     - none
     - bitwise (phase 1); T1 round-off
     - ``S.rst:1560-1562``, ``:1867-1872``
   * - 1
     - R-1 register, no reader
     - snapy
     - none
     - gates G-R1, G-R3
     - ``R.rst:1553``, ``:1723-1724``
   * - 1
     - I-1, I-2, I-3 (need no register)
     - snapy
     - #369
     - I-1, I-2 bitwise (hypothesis); I-3 rounding (target 1e-11)
     - ``I.rst:836-837``, ``:962-979``
   * - 2
     - A phase 1
     - snapy
     - O4 (``A.rst:1150-1151``, ``:1245``)
     - G1 bitwise
     - ``A.rst:1259-1261``
   * - 2
     - C3, C4; C4's rotation call after S moves the helper
     - snapy
     - C1, C2; S (``C.rst:1583``)
     - bitwise
     - ``C.rst:1578``, ``:1798-1805``
   * - 2
     - C6; C7
     - snapy
     - C7 after X1 (``C.rst:1579``)
     - C6 key 2 bitwise, key 4 round-off; C7 bitwise
     - ``C.rst:1813-1820``
   * - 2
     - R-2, R-3 with C5, C8 and EF-3 -> EF-4 -> EF-6 -> EF-12 -> EF-7
     - snapy
     - R-1 (``C.rst:1581``; ``EF.rst:1524-1525``)
     - C5 bitwise except AAM ``exact``; EF-3 bitwise without
       sedimentation; EF-4 bitwise (hypothesis); EF-6, EF-7 rounding
     - ``R.rst:1554``, ``:1725-1727``; ``C.rst:1806-1812``,
       ``:1821-1823``; ``EF.rst:1463-1493``
   * - 2
     - R-4 with S step (4) and phase 3: seam ``replace``, row 16r,
       ``boundary.prescribed``
     - snapy
     - R-1
     - round-off (hypothesis, G-R10); else FOR CHENG
     - ``R.rst:1555``, ``:1728-1729``; ``S.rst:1562-1564``,
       ``:1881-1893``
   * - 2
     - R-5 with I-4, I-5, I-6, I-7 (and R's and X's I-7 parts)
     - snapy
     - R-1; I-6 waits on Cheng's ruling (c)
     - I-4, I-5 rounding (hypothesis)
     - ``R.rst:1556``, ``:1730``; ``I.rst:980-991``
   * - 2
     - X4 global phase; X5; X6; X7
     - snapy
     - X1-X3
     - X4, X5 bitwise (hypothesis); X6 bitwise plus 5 % wall time
     - ``X.rst:812-815``
   * - 3
     - A phase 2; R-6
     - snapy
     - R, I-4 (``I.rst:838``), X4, S rotation data, #370 in the reference
     - G2-G7 (tolerance)
     - ``A.rst:1152-1154``, ``:1262-1270``; ``R.rst:1557``, ``:1731-1732``
   * - 3
     - EF-8, raising the kintera floor
     - snapy
     - the kintera release (K1-K4)
     - bitwise FP64
     - ``EF.rst:1525``, ``:1494-1504``; ``K.rst:649-650``
   * - 3
     - S-K1, S-K2, S-K3, then S-K4
     - snapy
     - EF-2 and EF-8; S-K4 also X4
     - S-K1, S-K3 bitwise; S-K2 hypothesis (K-G5); S-K4 with X's gate
     - ``K.rst:650-652``, ``:660-666``, ``:786-789``
   * - 3
     - O5, then X8 (F1, F2; sv after O4; F3 any time)
     - snapy
     - O5 before X8 (``O.rst:2581-2587``)
     - bitwise files; X8 no numerics
     - ``O.rst:2568-2587``; ``X.rst:816``
   * - 3
     - O6a, then O6b; O7
     - snapy
     - G-2 passes before O6b
     - bitwise data, exact metadata
     - ``O.rst:2588-2602``
   * - 4
     - O8 consumers; R-7
     - snapy
     - R's register and monitor; X's post-accept phase
       (``O.rst:1389-1392``)
     - new file; cycle line bitwise if order kept
     - ``O.rst:2603-2610``; ``R.rst:1558``, ``:1733``
   * - 4
     - A phase 3 (diffusion ``post_split``) with S's M6
     - snapy
     - A phase 2; S-3
     - G8, G9 (tolerance)
     - ``A.rst:1271``; ``S.rst:1891-1893``
   * - 4
     - S phase 2 (rotation, corners); S step (5) deletions
     - snapy
     - S phase 1
     - round-off (T1); periodic corners beyond round-off (FOR CHENG)
     - ``S.rst:1874-1879``, ``:1564``
   * - 5
     - A phase 4 (FP32, perturbation flux)
     - snapy
     - A phase 3
     - G10
     - ``A.rst:1272``
   * - 5
     - C9 last; C10 only if Cheng accepts
     - snapy
     - all lane C PRs
     - FP64 bitwise; FP32 re-baselined
     - ``C.rst:1585``, ``:1824-1829``
   * - 6
     - K5 (``nfail_`` private)
     - kintera
     - snapy no longer uses ``nfail_``
     - bitwise
     - ``K.rst:667``, ``:790``

Open in the plan: no lane gives a dependency for P2 or for S's phase 2;
both are placed where they block nothing. I-6 waits on Cheng's ruling (c)
(``I.rst`` 10(c)). C2, C10, S phase 2's corner correction and the
FOR CHENG items of each lane stay with Cheng.


4. Gates by name, owner and kind
--------------------------------

Kind is one of: **bitwise** (exact equality, or an exact pass/fail
identity), **tolerance** (a stated bound), **hypothesis** (the lane marks
the claim unverified, or the bound is a target to be set by a first
measurement). Where a lane states two kinds for one gate, both are given.
Every gate here is specified, not run.

4.1 Named gates
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
     - ``R.rst:1441-1444``
   * - G-R2
     - R
     - shared faces single-valued after ``reconcile``
     - bitwise x1; hypothesis x2/x3 (round-off)
     - ``R.rst:1445-1450``
   * - G-R3
     - R
     - step recursion equals ``sum c_s dt T_s``
     - tolerance 1e-15
     - ``R.rst:1451-1454``
   * - G-R4
     - R
     - budget closes
     - tolerance 1e-12 per row
     - ``R.rst:1455-1458``
   * - G-R5
     - R
     - rollback zeroes register and monitor
     - bitwise
     - ``R.rst:1459-1462``
   * - G-R6
     - R
     - capturable, fixed addresses
     - bitwise (capture succeeds)
     - ``R.rst:1463-1466``
   * - G-R7
     - R
     - vic energy wall residual
     - tolerance < 1e-13, else ``vic.cell``
     - ``R.rst:1467-1470``
   * - G-R8
     - R
     - ``riemann.central`` equals ``cen2``/``cen3``
     - tolerance 1e-14
     - ``R.rst:1471-1474``
   * - G-R9
     - R
     - ``boundary.prescribed`` amount
     - hypothesis (round-off, else declared change)
     - ``R.rst:1475-1479``
   * - G-R10
     - R
     - same-process x1 seam difference
     - hypothesis (measured, for K6)
     - ``R.rst:1480-1483``; ``S.rst:1885-1887``
   * - G-R11
     - R
     - ``A_f total(1)`` equals ``Phi``
     - tolerance 1 ulp
     - ``R.rst:1484-1487``
   * - G-R12
     - R
     - carry momentum frame
     - bitwise
     - ``R.rst:1488-1492``
   * - G-R13
     - R
     - transposed panel edges after ``owner_copy``
     - bitwise non-momentum; tolerance 1e-14 momentum
     - ``R.rst:1493-1497``
   * - G-R14
     - R
     - amounts recursion
     - tolerance 1e-15
     - ``R.rst:1498-1502``
   * - G-S13
     - S
     - panel-edge map on 2T:3T, with a negative control
     - bitwise non-momentum; hypothesis 1e-14 momentum
     - ``S.rst:1412-1425``
   * - G-S-K7
     - S
     - post-limit single-valuedness (gate harness only)
     - bitwise x1 and panel non-momentum; tolerance momentum; failing
       today is a hypothesis
     - ``S.rst:1426-1449``
   * - G-EF-1
     - EF
     - register posts equal the pin after step 4.C
     - bitwise species and no-sedimentation decks; tolerance otherwise
     - ``EF.rst:845-852``
   * - G-EF-2
     - EF
     - ``EfStatus`` gives the same redo causes
     - bitwise
     - ``EF.rst:853-857``
   * - G-EF-3
     - EF
     - graph replay equals eager (limiter, vapor, sedimentation)
     - bitwise
     - ``EF.rst:858-863``
   * - G-EF-4
     - EF
     - shared ``PositivityLimiter`` equals today's scalar path
     - bitwise (EF-4 marks it hypothesis, ``EF.rst:1474``)
     - ``EF.rst:864-867``
   * - G-EF-9
     - EF
     - base ``species_energy`` and single sedimentation kernel
     - hypothesis (tolerance 1e-12 to be set from measurement)
     - ``EF.rst:868-875``
   * - EF I1-I11
     - EF
     - existing invariants: species mass, positivity, carry, ratio, vapor
       repair, borrow, floors, sedimentation, scalars, EOS round trips,
       theta
     - I2, I7, I11 bitwise (exact); I5 tolerance (mass) and exact
       (counts); the rest tolerance
     - ``EF.rst:789-844``
   * - G1
     - A
     - existing tests against the reference
     - bitwise
     - ``A.rst:927-928``
   * - G2
     - A
     - kept ``riemann.central`` vs today's central
     - tolerance 1e-13
     - ``A.rst:929-931``
   * - G3, G3b
     - A
     - ``exact`` AAM drift; block-count invariance (G3b plan only)
     - tolerance 1e-12
     - ``A.rst:932-935``
   * - G4
     - A
     - ``off`` and ``transport`` against the reference
     - bitwise (rule)
     - ``A.rst:936-937``
   * - G5
     - A
     - seam single-valuedness of ``A F · K_f``, after G-S-K7
     - tolerance 1e-14
     - ``A.rst:938-939``; ``S.rst:1441-1449``
   * - G6, G7, G7s
     - A
     - closure; sponge/drag torque; AAM with sedimentation
     - tolerance (1e-12; 1e-15 of L; C n eps)
     - ``A.rst:940-944``
   * - G8, G9, G9b
     - A
     - diffusion suite; viscous torque; register vs Cartesian route
       (G9b plan only)
     - tolerance (own; 1e-12; 1e-12)
     - ``A.rst:945-950``
   * - G10
     - A
     - FP32 + perturbation-flux AAM drift vs FP64
     - tolerance (drift <= 1e-12)
     - ``A.rst:951-952``
   * - G-1
     - O
     - 25 example decks, every written file vs base
     - bitwise
     - ``O.rst:1021-1025``
   * - G-2
     - O
     - combiner parity
     - bitwise data, exact metadata
     - ``O.rst:1026-1031``
   * - G-3
     - O
     - generated option structs and parses
     - bitwise (exact)
     - ``O.rst:1032-1037``
   * - G-4
     - O
     - restart round trip, budget carry
     - bitwise, plus a RED test
     - ``O.rst:1038-1045``
   * - G-5
     - O
     - budget residual, closed box and all fixers
     - tolerance (proposed 1e-12 x total, estimate; set by G0)
     - ``O.rst:1046-1050``, ``:1004-1006``
   * - G-6
     - O
     - ported ``test_rectify``
     - bitwise (exact)
     - ``O.rst:1051-1054``
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

4.2 Gates named by identity (no id in the lane)
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
     - ``C.rst:1273-1275``
   * - C
     - CPU against CUDA
     - tolerance (bitwise for dc/plm)
     - ``C.rst:1276-1279``
   * - C
     - MPS equals CPU at float32 after C2
     - bitwise
     - ``C.rst:1280-1283``
   * - C
     - rest balance, ``max |v|/c <= 1e-12``
     - tolerance
     - ``C.rst:1284-1287``
   * - C
     - ``balance_column`` fixed point; no mass through a reflecting wall;
       x1 seam faces single-valued; floor counts
     - bitwise (identity)
     - ``C.rst:1288-1296``, ``:1325-1327``
   * - C
     - key-4 order >= 4.9
     - tolerance
     - ``C.rst:1297-1299``
   * - C
     - ``riemann.central`` equals today's central rows (A's G2)
     - tolerance 1e-14
     - ``C.rst:1300-1311``
   * - C
     - every solver and scheme parses and runs as before; split equals
       total in FP64; conservation; FP32 after C9
     - bitwise; tolerance (existing tests); tolerance (predeclared)
     - ``C.rst:1312-1330``
   * - I
     - I1 rows = apply (W and K unit tests, RED if one side changes)
     - tolerance (round-off)
     - ``I.rst:628-631``, ``:676``
   * - I
     - I2 booked = G[register M]; I3 mass telescoping
     - unstated in the invariant line
     - ``I.rst:632-636``, ``:677``
   * - I
     - I4 linear in the explicit increment, on C's rest gate
     - hypothesis
     - ``I.rst:637-647``, ``:678-679``
   * - I
     - I5 no reference row (operator argument, no run)
     - none (design argument)
     - ``I.rst:648-662``
   * - I
     - #348 harness (bitwise gate of I-1, I-2); I-3 energy row
     - bitwise (hypothesis); hypothesis (target 1e-11)
     - ``I.rst:666``, ``:669-671``, ``:962-979``
   * - I
     - sync-counter test; per-column status test
     - bitwise (pass/fail)
     - ``I.rst:680-682``
   * - S
     - same-process x1 seams; seam single-valuedness; transport-only rows
       (nb and pz pairs)
     - bitwise (momentum to the section 4 tolerance)
     - ``S.rst:1400-1407``, ``:1450-1453``, ``:1869-1870``
   * - S
     - periodic corners (ghost-image test); rotation involution
       (structural); solid faces (= G-R9)
     - bitwise (structural); G-R9's kind
     - ``S.rst:1396-1399``, ``:1408-1411``, ``:1454-1456``


5. Remaining work for the full document
---------------------------------------

Due Wednesday 08:00 EST, after ``CONVERGED``:

* re-read every head in table 1 at the converged SHAs and update every
  cite;
* settle with X and O the open row of table 3 (the 159 ``src/mesh``
  lines) and replace the provisional figures of section 2;
* add the per-lane contract summaries, the frozen register header
  (``flux_register.hpp``, frozen at ``4c59162a``), the FP32 and CUDA-graph
  contracts, and the FOR CHENG list in one place;
* check the PR plan against each lane's final section 8 and 10, and mark
  the PRs that carry each gate.
