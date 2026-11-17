:orphan:

V3 lane C: reconstruction, Riemann solvers, well-balanced reference, conversion order
=====================================================================================

Revision 2, 2026-11-17. Owner: Tianhao Le (alternate: Xinyue). Design only:
no implementation change. Declarations are in ``docs/v3/skeleton/C/`` (not
built); the file-by-file line table is ``docs/v3/design/C_lines.csv``,
produced by ``docs/v3/design/C_lines.py``.

Every ``path:line`` is at chengcli/snapy
``9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410`` unless another commit is named.
"Measured" means produced by a command named in the text; "estimate" means a
design target.

Changes from revision 1 (``b7d1300f``), by Cheng's numbered review:
(1) the twelve sections are the brief's, in its order; (2) section 4 states
the register contract: the named increment ``riemann``, its frame and area
weighting, its FP32 dtype, no lane C flux storage, and the memory of
``mass_central``; (3) diagnostics is lane O and layout is lane S; (4) the line
budget is per file, and the lines moved in from lane R files are split as in
section 9; (5) paths and branch are upper case. In addition, revision 2
decides the solver and scheme kill lists from the pinned decks (section 3.6).
Revision 1 had already fixed hllc as the default and removed ``ppm`` and
``plume-roe``, but it left ``roe``, ``weno3`` and ``cp3`` marked
``FOR CHENG``. No deck uses any of them, so revision 2 removes them.

1. Scope and pins
-----------------

**Scope.** The face side of the hydro step:

* cell-average to primitive conversion (orders 2 and 4) and the key-4 wall
  fills;
* the well-balanced x1 reference and ``balance_column``;
* reconstruction;
* the Riemann solvers;
* the face floors;
* the direction-generic face sweep.

Lane C owns the 50 baseline files (5,841 lines, section 9) and the four
lane R ranges that move into them (section 9).

**Not in scope**, with the lane that owns each:

* the flux register and the monitor: lane R;
* layout and seam communication: lane S;
* angular momentum: lane A;
* the implicit solve: lane I;
* output and diagnostics: lane O;
* execution and graphs: lane X.

**Pins.** snapy ``9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410`` (chengcli main
when this revision was written; checked with ``git ls-remote``). No kintera,
pyharp or commux source is read or changed (section 8).

**Sources read.**

* the baseline files;
* ``hydro_forward.cpp:383-1153``;
* ``hydro.cpp:551-872``;
* ``coordinate.cpp:546-562`` and ``:706-760``;
* ``V3_ROADMAP.md``;
* the PR bodies of #334, #335, #336, #339, #340, #341, #346, #347, #349,
  #354, #359, #360 and #362, fetched read-only;
* lane O revision 1 (JiachenLiu-Atmos/snapy ``v3-design/O``
  ``7dac5f4a``), for its assumptions about lane R. It was read after this
  lane's revision 1 was posted.

**Not available.** Xinyue's 77-site inventory at ``919936da`` is not in the
shared workspace. It is also not on a ``v3-design``, ``inventory`` or
``recon`` branch of any of the ten chengcli/snapy forks (``git ls-remote``),
and the chengcli/snapy issue bodies and comments searched contain no
inventory. Its count is therefore unchecked. Its claims as quoted in the lane
request are rechecked in section 2.4. Lane R's register design was not
published either, so section 4 states what lane C posts and lists the
assumptions about the register as questions (section 11).

2. Concepts and current sites
-----------------------------

2.1 Pipeline today
~~~~~~~~~~~~~~~~~~

Per RK stage, ``HydroImpl::forward`` (``hydro_forward.cpp:370``):

1. ``peos->forward`` gives ``W(u)`` (``:386``); with conversion order 4,
   ``w = W(u - L u) + L W(u)`` with per-cell fallback, a trip counter and a
   ghost rebuild (``:417-504``).
2. **x1 sweep** (``:617-987``). With gravity, it uses the well-balanced
   split (``:668-812``). The reference is ``_hydro_ref_x1``
   (``hydro.cpp:605-872``). The sweep subtracts the reference, fills
   parity ghosts, reconstructs the perturbations, restores the reference at
   the faces with fallbacks, and mirrors the wall faces. Without gravity it
   is a plain reconstruction (``:813-820``). Both end with the immersed
   solid, the Riemann solve into ``_flux1`` with the face pressure into
   ``_face_pressure1``, sedimentation, and the seam average (``:822-946``).
3. **x2/x3 sweeps.** Reconstruction (``:1010-1031``), the cubed-sphere
   face-state exchange (``:1033-1048``), covariance and the Riemann solve
   into ``_flux2``/``_flux3`` (``:1088-1152``).
4. The divergence ``coord->forward(w, _flux1, _flux2, _flux3,
   _face_pressure1)`` (``:1264-1285``). Fluxes are per unit face area: the
   divergence multiplies by ``face_area<d>`` and divides by the cell volume
   (``coordinate.cpp:706-735``).

2.2 Current sites of each concept
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - concept
     - sites at the pin
   * - reconstruction point formulas
     - ``recon/interp_point.h:26-120`` (CPU and CUDA, uniform and per-face
       through ``Nu``); MPS rewrites ``recon/recon_dispatch.cpp:83-158``;
       plm in torch ops ``recon/plm.cpp:10-32``
   * - scheme classes and factory
     - ``recon/interpolation.hpp:37-285`` (7 classes);
       ``recon/interpolation.cpp:6-40``. The name's last character maps
       ``weno5`` to weno5 or cp5 (``:21-36``).
   * - dispatch paths
     - ``recon_dispatch.{hpp,cpp,cu}`` (305 lines);
       ``recon_dispatch_nu.{hpp,cpp,cu}`` (223 lines);
       ``recon_launch.cuh``, ``interp_impl.cuh:83-188``
   * - x1 weights, built in five places
     - ``recon/x1_coeffs.cpp:10-31``; ``hydro/wb_ref4.cpp:26-39``,
       ``:77-94``; ``hydro_forward.cpp:293-304``;
       ``balance_column.cpp:69-86``; ``hydro_forward.cpp:312-339``;
       ``hydro_dispatch.cpp:277-312``
   * - conversion order 4, twice
     - ``hydro_forward.cpp:417-504``; ``balance_column.cpp:57-118``
   * - reference, two shapes
     - ``hydro_reference.hpp:31-155``; ``hydro.cpp:605-872``
   * - Riemann classes and wrappers
     - ``riemann/riemann_solver.hpp:54-242`` (6 classes); ``hllc.cpp:44-113``,
       ``lmars.cpp:30-76``, ``roe.cpp:16-67``, ``shallow_roe.cpp:26-57``,
       ``plume_roe.cpp:45-102``; CPU loops in 4 ``*_dispatch.cpp``; CUDA
       ``riemann_dispatch.cu:17-115``
   * - face-frame rotation
     - ``riemann_solver.cpp:12-47`` (shared by the solvers); hand copies
       ``hydro_forward.cpp:93-97``, ``:212-216``, ``:257-261``;
       ``output/load_diag_output_data.cpp:175-187``
   * - x2 and x3 sweeps, twice
     - ``hydro_forward.cpp:1088-1119`` and ``:1121-1152``; ``:1010-1031``
   * - face floors, five places
     - ``reconstruct.cpp:98-108``, ``:149-159``;
       ``hydro_forward.cpp:772-805``; ``:602``, ``:605``, ``:611-612``;
       ``hllc_impl.h:96-97``, ``roe_impl.h:145-160``, ``:197-210``;
       ``pib->forward`` (``:822-823``, ``:1089-1090``)
   * - face-flux storage outside a register
     - ``_flux1/_flux2/_flux3`` (``hydro.cpp:248-271``),
       ``_face_pressure1`` FP64 (``:252-253``), ``cen2/cen3`` and
       ``_aam_mass_flux`` (``hydro_forward.cpp:996``, ``:1356-1361``),
       ``bflux1`` (``:847-848``)

2.3 Usage census (measured)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Decks are the YAML files of the tree, loaded with ``yaml.safe_load_all``
(outside ``external/`` and ``build/``). 72 have a ``dynamics`` map. Of those
72:

* no deck sets ``precision`` (all FP64);
* none sets ``conversion-order: 4``;
* none sets ``perturbation-flux`` or ``anomaly: true``;
* none sets ``conserve-axial-momentum: full``;
* every ``riemann-solver`` block names its type.

Code-built options in ``examples/``, ``tests/``, ``python/snapy`` and
``docs`` were found by ``grep`` for each name.

.. list-table::
   :header-rows: 1

   * - option
     - decks (examples among them)
     - code-built users
   * - riemann hllc
     - 10 named (6 examples) + 27 by default (0 examples)
     - tests
   * - riemann lmars
     - 26 (10 examples)
     - 12+ tests (e.g. ``test_conversion_order.py:62``)
   * - riemann shallow-roe
     - 9 (9 examples)
     - ``test_axial_momentum_flux_form.py:216``
   * - riemann roe
     - 0
     - ``test_roe_cubed_sphere_rest.py:16``,
       ``test_mps_matches_cpu.py:196``, ``test_riemann.cpp:242``, ``:297``
   * - riemann plume-roe
     - 0
     - none
   * - riemann upwind (hydro)
     - 0
     - ``test_conversion_order.py:72`` is a ``scalar`` block
   * - scalar upwind
     - 10 (3 examples; 8 by default)
     - scalar default ``scalar.hpp:29``, ``scalar_options.cpp:52``
   * - recon weno5
     - 39 (25 examples)
     - many
   * - recon dc (default)
     - 26 by default + 1 named (0 examples)
     - ``test_x1_seam_split.cpp:131-132``
   * - recon plm
     - 6 (0 examples)
     - ``test_plm.cpp``
   * - recon cp5
     - 1 (0 examples)
     - also weno5's velocity/pressure partner and the face-density rows
       (``hydro.cpp:792-815``)
   * - recon weno3, cp3
     - 0
     - ``test_weno.cpp:216-240``, ``test_weno5_cuda_line.cpp:27-31``,
       ``test_mps_matches_cpu.py:162``, ``:200``,
       ``test_stretched_x1_ref.cpp:143-146``, refusal lists
       ``test_x1_coeffs.cpp:285``, ``test_x1_stretched_refusal.cpp:29``
   * - recon ppm
     - 0
     - refusal lists only (``ppm.cpp:14`` throws)
   * - ``reconstruct`` ``shock: true``
     - 13 (12 with the EOS limiter on; 6 examples)
     - —
   * - no ``reconstruct`` section (``shock`` = C++ default ``true``)
     - 26 (7 with the limiter on, all tests)
     - —

Out-of-tree decks were not checked. The production Jupiter deck named in
``V3_ROADMAP.md:375-380`` runs WENO5 and HLLC by that text; the deck itself
was not read.

2.4 Inventory claims rechecked at the pin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The inventory was taken at ``919936da`` = #339. #347, #349, #352 and #354
landed after it.

* **"WENO5 at 5 library sites."** Two formula sites remain:
  ``interp_point.h:71-120`` (CPU and CUDA) and the MPS rewrite
  ``recon_dispatch.cpp:117-158``. Two table sites: ``weno5.cpp:12-25`` and
  ``x1_coeffs.cpp:59-120``. The test copy moved to
  ``tests/interp_simple.hpp`` (#349).
* **"Rotation written 6 times."** One solver helper,
  ``riemann_solver.cpp:12-47`` (#349, commit f83c720). Three covariance
  copies and one diagnostic block remain (section 2.2).
* **"MPS HLLC wrong with species."** Fixed by #354 (commit 464e4a8,
  ``hllc_dispatch.cpp:135-139``). One divergence remains: MPS is float32
  but uses the FP64 contact arithmetic (``hllc_dispatch.cpp:112``), while
  the CPU float kernel uses ``cl * ql`` (``hllc_impl.h:76-84``).
* **"C++ and YAML Riemann defaults disagree."** Fixed by #352 (commit
  f32912d): both are hllc (``riemann_solver.hpp:33``,
  ``riemann_solver.cpp:67``). The reconstruction ``shock`` default still
  disagrees: ``true`` in C++ (``reconstruct.hpp:49``), ``false`` from YAML
  (``reconstruct.cpp:33``, ``scalar_options.cpp:37``).

2.5 Findings beyond the inventory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``plume-roe`` never writes ``flx``. It returns a fresh tensor
  (``plume_roe.cpp:99-101``), and its Jacobian and polynomial are unused
  (``:81-92``).
* Dead options and code:


  * ``ReconstructOptions::is_boundary_lower/upper`` and ``limiter``
    (``reconstruct.hpp:47-50``) are read only in the commented block
    ``reconstruct.cpp:118-141``;
  * ``_revise_x1*_ghost`` (``hydro.cpp:565-603``) is called only from
    commented code, ``hydro_forward.cpp:630-633``.
* The FP32 WENO point functions compute in FP64. Their constants are
  ``double`` (``interp_point.h:61-62``, ``:99-104``, ``:109-115``). In a
  compile probe, ``weno5_point<float>`` holds 6 ``addsd``, 3 ``divsd``,
  9 ``mulsd``, 9 ``cvtss2sd`` and 6 ``cvtsd2ss`` (``g++ -O2`` 11.5.0,
  x86-64). Typing the constants as ``T`` changes 363,162 of 1,000,000 FP32
  faces. LMARS has the same pattern by reading (``lmars_impl.h:28-43``).
  Whether this costs GPU time is a hypothesis; nothing was timed.
* The MPS-only rewrites total 674 lines (measured):


  * ``recon_dispatch.cpp:83-158`` and ``recon_dispatch_nu.cpp:90-100``;
  * ``hllc_dispatch.cpp:50-164``, ``lmars_dispatch.cpp:44-102``,
    ``roe_dispatch.cpp:50-219``, ``shallow_roe_dispatch.cpp:33-81``;
  * ``hydro_dispatch.cpp:33-54`` and ``:101-275``.

  The MPS reference uses ``cumsum`` in place of the scan recurrence
  (``hydro_dispatch.cpp:116``) and refuses stretched x1 (``:108-110``).

3. Target design
----------------

3.1 Types and ownership
~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - type (skeleton file)
     - role
   * - ``Scheme``, ``recon_point<Scheme,T>`` (``recon_point.h``)
     - one point function per scheme: cp5, weno5. dc and plm stay torch ops.
   * - ``ReconRows``, ``face_value_row``, ``conv4_rows``, ``wall4_rows``,
       ``face_density_rows``, ``six_face_rows``, ``X1RowsCache``
       (``x1_rows.hpp``)
     - every x1 weight, built once per grid version on the host in double,
       cached per device and dtype
   * - ``Conversion``, ``WellBalancedX1``, ``FaceFloor``,
       ``ReconstructImpl``, ``FaceStates`` (``reconstruct.hpp``)
     - the reconstruction stages, in order
   * - ``X1Reference``, ``ReferenceInput``, ``ReferenceFaces``,
       ``X1ColumnLink`` (``x1_reference.hpp``)
     - one reference evaluator for initialization and runtime; seams
       through a link that lane S implements
   * - ``RiemannSolverImpl``, ``RiemannKind``, ``FaceFlux``,
       ``FaceThermo``, ``FaceBackground`` (``riemann.hpp``)
     - one solver module; the ``riemann`` increment (section 4)
   * - ``FaceDir``, ``reconstruct_faces``, ``solve_faces``
       (``sweep.hpp``)
     - one sweep for x1, x2 and x3

3.2 Data flow
~~~~~~~~~~~~~

::

   u (cell averages)
     |  Conversion (order 2 | 4, key-4 wall ghosts, trips)   [C]
     v
   w (primitives) ---- X1Reference(base[, delta], link) ---> ReferenceFaces
     |                    anchor relay, ghost rows: link      [C; link: S]
     v
   reconstruct_faces(dir)                                     [C]
     |  dir x1 + gravity: WellBalancedX1(w, ReferenceFaces)
     |  dir x2/x3: ReconstructImpl(w), FP32 gauge
     v
   FaceStates  --- cubed-sphere face-state exchange (x2, x3) [S]
     |
   solve_faces(dir)                                           [C]
     |  FaceFloor (counts -> monitor [R])
     |  immersed solid (pib)
     |  RiemannSolver: FaceThermo, rotate (coord [S]), kernel, rotate back
     v
   FluxRegister["riemann", dir, stage]  (+ p*, mass_central)  [R]
     |  later increments by their owners: sedimentation, covariance,
     |  positivity; seam reconciliation                        [R/S]
     v
   divergence and every flux-derived term read the register    [R]

3.3 Reconstruction (questions 1, 2)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**One definition per scheme.** cp5 and weno5 are ``DISPATCH_MACRO`` point
functions, reached through ``recon_point<Scheme,T>``. The CPU loop and the
CUDA line kernel are written once over ``Scheme``. dc (a copy) and plm (torch
ops) stay tensor code. Torch ops are already one definition on every
backend, and plm is the scheme the inventory found bitwise between CPU and
CUDA (not re-measured here).

**MPS** registers the CPU kernel through ``OnHost`` (``on_host.hpp:61-70``,
#354). The 674 MPS-only lines are deleted. MPS then gives the CPU float32
result, and MPS runs stretched x1. The cost is a host copy of each storage
per call (``on_host.hpp:15-19``).

**What remains:**

* one dispatch stub, ``recon_dispatch.{hpp,cpp,cu}``, with the CPU loop
  (``recon_dispatch.cpp:16-40`` today) and one CUDA launcher (``.cu:23-79``
  today), which keeps the one-block, split and tiled paths;
* ``recon_line.cuh`` in place of ``interp_impl.cuh`` and
  ``recon_launch.cuh``. The four ``Op`` wrappers and ``interp_nu_untiled``
  become one ``Op<Scheme>``;
* ``recon_dispatch_nu.*`` and ``interp_impl.h`` are deleted.

**One x1 path.** ``ReconRows`` carries ``row_stride``: ``ncoeff`` for
per-face rows, and ``0`` (one broadcast row) for a uniform grid. Per-face rows
are already needed on every radial grid (``coordinate.cpp:546-562``) and on
every stretched x1.

Moving weno5's ``.3/.6/.1`` (``interp_point.h:113-115``) into the table is
bitwise in FP64 but not in FP32 (``0.3f != 0.3``), so it lands with C9.
Until then C3 keeps ``Nu`` as a compile-time branch on ``row_stride == 0``.
dc and plm keep the stretched-x1 refusal (``interpolation.hpp:62-71``).

3.4 Conversion, wall fills, balance_column (question 3)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Conversion`` is the first reconstruction stage. It is used by the solver
and by ``balance_column``:

* order 2 is the identity after ``peos->forward``;
* order 4 is ``hydro_forward.cpp:417-504`` moved as is;
* ``fill_walls`` is ``wall4_fill`` (``:341-358``).

Every x1 weight comes from ``x1_rows``, with one cache key: ``x1f``
identity, ``_version``, device, dtype. That key replaces four staleness
tests: ``hydro_forward.cpp:425-432``, ``hydro.cpp:695``, ``:793-794`` and
``wb_ref4.hpp:30-33``.

The recon rows (``x1_coeffs.cpp:10-31``) and the wb_ref4 face density
(``wb_ref4.cpp:26-39``, ``:77-94``) are one formula, ``face_value_row``.
``balance_column`` stops re-deriving ``L`` (``balance_column.cpp:69-86``)
and keeps its contract (``balance_column.hpp:14-127``) and its Python
binding.

3.5 Reference (question 4)
~~~~~~~~~~~~~~~~~~~~~~~~~~

``X1Reference::evaluate(ReferenceInput{base, delta}, grav, link)``.

* An undefined ``delta`` selects the total ``T`` kernel. A defined
  ``delta`` selects the ``SRS`` pair kernel. Its branches read the FP64
  total and its arithmetic keeps the increment, as M3b requires
  (``V3_ROADMAP.md:459-464``; today ``hydro_reference.hpp:102-128``).
* The output, ``ReferenceFaces``, holds the totals and the split fields
  (``hydro.cpp:667-674``).
* ``link`` carries the anchor relay (``hydro.cpp:630-641``, ``:704-713``)
  and the ghost-row exchange (``:727-776``). It is implemented by lane S.
* ``nullptr`` means one column: ``balance_column``, the IC builders and
  ``nb1 = 1``.
* The order is unchanged (``hydro.cpp:647-869``). The kernel
  ``hydro_ref_x1_impl.h`` is not changed.

3.6 Riemann (questions 6, 7), default and kill lists
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One ``RiemannSolverImpl`` with ``RiemannKind`` in place of six classes.

* **One EOS face pass**, ``FaceThermo``, replaces ``hllc.cpp:64-81``,
  ``lmars.cpp:36-52`` and ``roe.cpp:32-37``. The per-kind order of the EOS
  calls is kept, so the results stay bitwise.
* **One rotation**, owned by coord (lane S), replaces
  ``riemann_solver.cpp:12-47`` and the three covariance copies.
* **Output contract**: section 4.

**Single default: hllc. Decided, not FOR CHENG.**

* It is the default already in ``create()`` and YAML. 27 decks rely on the
  default and 10 name it.
* It is the only solver allowed with ``perturbation-flux``
  (``hydro.cpp:207-210``), so FP32 runs need it (``hydro.cpp:80-81``).
* It is the solver of the roadmap's first FP32 case
  (``V3_ROADMAP.md:375-376``).
* It returns a contact pressure with a positivity clamp
  (``hllc_impl.h:93-98``).

A different default would change 27 decks.

**Solver kill list. Decided, no deck uses these** (section 2.3):

* **roe**: ``roe.cpp``, ``roe_dispatch.cpp``, ``roe_impl.h`` (516 lines)
  and the roe cases of ``test_riemann.cpp:242-343``,
  ``test_mps_matches_cpu.py:196`` and ``test_roe_cubed_sphere_rest.py``.
  #340 fixed roe on the cubed sphere on 2026-11-09. That is evidence of
  recent use outside the deck set, not of a deck, so it is noted here and
  does not block the decision.
* **plume-roe**: ``plume_roe.cpp`` (104 lines). It has no user and writes no
  output.
* **upwind as a hydro solver** goes. ``upwind_flux`` stays as the scalar
  transport flux (10 scalar decks), and its YAML key keeps parsing under
  ``scalar``.
* **Python** per-solver bindings (``pyriemann.cpp:26-41``) are replaced by
  one ``RiemannSolver``. No in-tree Python uses them.
* **Kept**: hllc, lmars (26 decks), shallow-roe (9 decks).

**Scheme kill list. Decided, no deck uses these:**

* **ppm**: it throws.
* **weno3** and **cp3**, with ``weno3_point``. Their tests are adapted in C1.
* The dead ``ReconstructOptions`` fields.
* **Kept**: dc (27 decks), plm (6), cp5 (1, plus weno5's partner), weno5
  (39).

A deck that names a removed type gets an error that names the remaining
types.

**FP32 perturbation entry**: the ``FaceBackground`` argument. It is the same
kernel shifted by ``p0`` (``hllc_impl.h:29-31``, ``:51-52``, ``:96-97``,
``:155-156``). LMARS perturbation support stays deferred
(``V3_ROADMAP.md:543``).

3.7 Sweep (question 5) and floors (question 8)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``reconstruct_faces(dir)`` and ``solve_faces(dir)`` replace
``hydro_forward.cpp:1010-1031`` and ``:1088-1152``. The sweep is split in
two because the cubed-sphere exchange (``:1033-1048``) begins x2 and x3
before either completes.

``FaceFloor::apply`` runs once per sweep, after the last face transform and
before the immersed solid and the solve:

* it applies the EOS floors under today's conditions, so it is bitwise: the
  shock path keeps only the species floor;
* it counts floored faces (rho, p, species) into a device ``int64``
  counter, which lane R's monitor holds and lane O displays;
* the WB fallbacks (``hydro_forward.cpp:786-787``, ``:804-805``) are
  counted in the same counter.

Face-state floors are not flux increments: the flux they cause has no
separate value without a second solve. So they register counts, not flux
(section 4).

3.8 FOR CHENG (each changes deck results)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **One ``shock`` default.** Make it ``false`` in ``create()``, matching
   YAML. 7 test decks change wherever a density or pressure floor fires
   (section 2.3).
2. **Density and pressure floors on the shock path.** 12 decks change,
   including 6 examples.
3. **MPS through ``OnHost``.** Every MPS run moves from the MPS formulas to
   the CPU kernel's float32 result (within ``test_mps_matches_cpu.py``
   tolerances today), and MPS throughput drops.

Decided without Cheng, because no deck is affected:

* the kill lists;
* hllc as the default (unchanged);
* the FP32 typed constants (C9), since no deck runs FP32;
* the in-kernel ``mass_central`` (C5), since no deck runs
  ``conserve-axial-momentum: full``;
* the key-4 weight rows (C6), since no deck runs key 4;
* the Python binding change;
* no ``--fmad=false`` build.

4. Flux-register contract
-------------------------

Register owner: lane R. Lane C stores no face flux. ``_flux1/2/3``,
``_face_pressure1``, ``cen2/3``, ``_aam_mass_flux`` and ``bflux1`` become
register slots or views of them.

**What lane C posts.** One increment per direction ``d`` and stage, named
``riemann`` (req. 2), written in place into the register's slot by
``solve_faces``:

* **quantity**: conservative flux density per unit face area, all ``nvar``
  rows. The register's divergence applies ``face_area<d>`` and the cell
  volume, as ``coordinate.cpp:706-735`` does today (req. 1);
* **frame**: global coordinate components, after coord's
  ``to_global_frame_`` (req. 1, 5). Rotation is one function owned by coord;
  lane C calls it and does not own it;
* **location**: face index ``i`` along ``d`` is the face between cells
  ``i-1`` and ``i`` (today's convention);
* **dtype**: the compute dtype. That is FP32 under FP32: lr is cast at
  ``hydro_forward.cpp:565`` and the slots are FP32 at ``hydro.cpp:248``.
  FP64 otherwise (req. 8). The accumulation dtype is lane R's (question R2).

**Companion fields, posted with the increment.** They are not flux
increments.

* ``p*`` (x1 only): the total face pressure, FP64 in every precision. In
  FP32 runs it is the FP32 perturbation plus the FP64 background, added
  once in ``solve_faces`` (today ``hydro_forward.cpp:568-570``,
  ``hydro.cpp:252-253``). It is read by the pressure source and gravity work.
* ``mass_central`` (x2, x3): only with ``conserve-axial-momentum: full``,
  which refuses FP32 (``hydro_forward.cpp:993-995``), so it is FP64. It
  holds rows IDN and ICY.. of ``1/2 (F(w_L) + F(w_R))`` in the global frame.
  The dissipative mass flux for lane A is ``riemann[mass rows] -
  mass_central``.

**Memory of mass_central (req. 9).** Size: ``(1+ny) x nc3 x nc2 x nc1 x 8``
bytes per direction, in fixed storage allocated only when the option is on.

* For ``examples/jupiter_gcm.yaml`` dimensions (48 x 48 x 100, nghost 3,
  10 species, so ny = 9 and nvar = 14), that is 24.7 MB per direction and
  49.5 MB per block.
* Today the same option holds ``cen`` and ``_flux - cen``: 2 x nvar rows,
  or 69.2 MB per direction (by reading ``hydro_forward.cpp:997-1003``,
  ``:1356-1361``; not profiled).
* It also removes four Riemann solves per stage.

**What lane C reads from the register:** nothing. Reconstruction and the
reference read the state.

**What lane C corrects:** nothing. It does not modify another lane's
increment.

**Ordering constraints:**

* ``riemann`` is posted first in each direction;
* sedimentation (x1), covariance (x2/x3) and positivity post after it, as
  their own increments. Positivity's multiplicative scaling must be posted
  as ``(theta - 1) F``, which is lane R's rule;
* gravity work in cell form reads ``riemann`` alone (today ``bflux1``,
  ``:847-848``). This is why the increments must be reportable separately
  (req. 2);
* the x1 seam average (``:882-946``) is the reconciliation of a shared
  face (req. 5). It applies to ``riemann``, ``p*`` and the split background,
  after all of a stage's x1 increments, and it is lane R/S's.

**Floors (req. 7):** counts, as described in section 3.7. The solver's
p* clamp is reported in ``FaceFlux::events``.

**Restart (req. 10):** nothing of lane C is written. ``X1RowsCache`` and the
reference are rebuilt.

5. Invariants and gates
-----------------------

.. list-table::
   :header-rows: 1

   * - invariant
     - kind
     - gate
   * - one definition: no second weno5/cp5 formula, no MPS formula, one
       weight builder, one rotation
     - identity (code)
     - review; ``grep`` of ``13. / 12.`` gives one ``src`` site
   * - refactor PRs C1-C4, C7, C8 change no result
     - bitwise, CPU and CUDA separately, FP64 and FP32
     - dump set as in #349: 20 cases x CPU/CUDA x FP64/FP32
   * - CPU against CUDA
     - tolerance, set per test from the base's spread; bitwise for dc/plm
     - existing ``*_cuda`` tests; #349 measured about 1e-15 relative
       after 20 rk3 steps
   * - MPS equals CPU at float32 after C2
     - bitwise by construction
     - ``test_mps_matches_cpu.py`` arms at tolerance 0; no MPS device was
       available here
   * - rest balance (well-balanced)
     - tolerance: max ``abs(v)/c`` <= 1e-12 (as #341)
     - ``test_balance_column``, ``test_wb_ref_wall``,
       ``test_hydro_ref_x1_rf_wall``
   * - ``balance_column`` fixed point is the solver's
     - identity (same objects)
     - ``test_balance_column_order4``: second call takes 0 passes
   * - no mass through a reflecting x1 wall
     - identity (mirror face)
     - ``test_conversion_order`` wall arm
   * - x1 seam faces single-valued
     - identity after reconciliation
     - ``test_x1_seam_split``, ``test_x1_seam_split_mp``
   * - key-4 order
     - tolerance: order >= 4.9 (as #347)
     - ``test_conversion_order``, ``test_wb_ref4_order``
   * - split path equals the total path in FP64
     - tolerance of the existing tests
     - ``test_perturbation_flux``, ``test_perturbation_flux_split``,
       ``test_split_reference``, ``test_pressure_scan_x1``
   * - conservation
     - tolerance of ``test_conservation_budget``
     - unchanged rows
   * - floor counts equal the faces changed
     - identity
     - new test in C5
   * - FP32 after C9
     - tolerance against FP64, predeclared
     - ``fp32-foundations`` label (``V3_ROADMAP.md:529-535``)

6. FP32 contract
----------------

.. list-table::
   :header-rows: 1

   * - stage
     - FP32 run today (pin)
     - after
   * - conversion (orders 2/4) and admissibility
     - FP64; perturbation ``delta`` updated in FP64
       (``hydro_forward.cpp:512-519``)
     - unchanged
   * - reference
     - FP64 ``SRS`` pairs (``hydro_reference.hpp:102-128``); gauge FP64
       (``hydro.cpp:671-674``)
     - unchanged
   * - x1 WB perturbations
     - formed in FP64, cast to FP32 for reconstruction (``:762``), restored
       with FP64 references (``:772-787``)
     - unchanged
   * - x2/x3 faces
     - gauge subtracted in FP64, reconstructed in FP32 (``:585-588``),
       pressure restored and floored in FP64 (``:600-605``, ``:608-613``)
     - unchanged
   * - point functions
     - FP32 storage, FP64 arithmetic in the weno5/weno3 constants and in
       LMARS (section 2.5)
     - typed ``T`` (C9); weno3 removed
   * - Riemann
     - FP32 HLLC (``:565``; ``hllc_impl.h:60-63`` asserts FP32 work)
     - unchanged
   * - posted ``riemann`` increment
     - FP32 slot (``hydro.cpp:248``)
     - FP32 increment; accumulation dtype is lane R's
   * - ``p*``
     - FP64 (FP32 delta plus FP64 background, ``:568-570``)
     - unchanged, FP64
   * - ``mass_central``
     - not available in FP32 (``:993-995``)
     - unchanged
   * - floors and counters
     - FP64 floors on FP64 totals; no counters
     - same floors; ``int64`` counters

7. CUDA-graph contract
----------------------

**Host reads.** None in the per-stage path of lane C code. Found with
``grep`` of ``.item``/``.cpu()`` in the baseline files and in
``hydro_forward.cpp:383-1153`` and ``hydro.cpp:605-872``. Every host read is
at setup or on a cache rebuild, which must be outside capture:

* ``x1_coeffs.cpp:130-135``;
* ``hydro_reference.hpp:45-48``;
* ``wb_ref4.cpp:52``;
* ``hydro_dispatch.cpp:280``;
* ``balance_column.cpp:55``, ``:142``, ``:149``, at initialization only.

After the change, every one of them sits in ``X1RowsCache`` or the
``X1Reference`` constructor.

**Allocations per call** (measured lines). These become fixed workspace
owned by the module, sized at construction:

* 45 allocating lines in ``hydro_forward.cpp:383-1153``;
* 9 in ``hydro.cpp:605-872``;
* ``reconstruct.cpp:88``;
* ``hllc.cpp:58-59``, ``:89``.

The workspace is:

* ``FaceStates`` for each direction;
* ``ReferenceFaces``;
* ``FaceThermo``;
* register slots, which lane R owns.

**Data-dependent host branches.** None on tensor values. The branches
depend on options, shapes, dtype and ``defined()``. One branch must happen
before capture: HLLC rebinds its buffers on the first call with a new dtype
(``hllc.cpp:51-54``), so warm-up must run first. Branches inside kernels are
device-side.

**Segment boundaries.** Host-controlled communication inside a lane C
stage:

1. conversion-order 4 ghost exchange and boundary functions
   (``hydro_forward.cpp:489-503``);
2. reference anchor relay, a serial dependency down the x1 block column
   (``hydro.cpp:636``, ``:712``);
3. reference ghost-row exchange (``hydro.cpp:727-776``);
4. cubed-sphere face-state exchange (``hydro_forward.cpp:1033-1048``);
5. ``SNAP_X1_CENTROID_EXACT`` ghost rows (``:666``, ``:953``) and the
   covariance seam rows (``:1059-1065``);
6. the x1 seam flux average (``:882-946``), owned by lane R/S.

Each is an eager boundary until lane S gives a capture-safe exchange.

**G-milestone mapping:**

* **G1**: single-block dry. No boundary applies; needs the fixed workspace
  and the C2-C4 refactors.
* **G2**: moist. Needs the conversion's limiter-mark and vapor-failure
  restore to stay device-side; it already copies tensors,
  ``hydro_forward.cpp:470-480``.
* **G4**: multi-block Cartesian. Boundaries 1, 2, 3 and 6.
* **G5**: FP32 cubed sphere. The split reference is Cartesian-only today
  (``hydro.cpp:196-203``); lane C's part is extending ``ReferenceInput`` to
  panel seams.
* **G6**: boundary 4 and the rotation.

8. Cross-repository interface changes and merge order
-----------------------------------------------------

**None.** Lane C changes no kintera, pyharp or commux interface. The EOS
calls (``W->I``, ``W->A``, ``WA->L``, ``W->L``) are snapy's
``EquationOfState`` and stay as they are.

**Merge order inside snapy:**

1. C1 and C2 first; they are independent.
2. Then C3 and C4.
3. C6 and C7.
4. C5 and C8 after lane R's register API, which they post into.
5. C4's rotation call after lane S moves the helper to coord. Until then
   C4 calls ``riemann_solver.cpp``'s helper unchanged.
6. C9 last, as a predeclared FP32 re-baseline.

9. Line budget
--------------

Measured "now" is ``git show 9e5de2d4:<file> | wc -l``, and for a lane R
range, its length. "After" is an estimate. The table is
``docs/v3/design/C_lines.csv``, produced by
``python3 docs/v3/design/C_lines.py`` from the snapy clone.

.. list-table::
   :header-rows: 1

   * - total
     - now (measured)
     - after (estimate)
   * - the 50 lane C baseline files
     - 5,841
     - 999 (10 files kept)
   * - lane R ranges moved in (``hydro_forward.cpp:291-368``, ``:417-504``,
       ``:668-820``; ``hydro.cpp:605-872``)
     - 587
     - 0 (code now in new lane C files)
   * - 19 new lane C files
     - 0
     - 1,965
   * - **lane C**
     - **6,428**
     - **2,964**

* Against the 5,841-line baseline: -49.3%.
* Against baseline plus moved-in lines: -53.9%.
* The lane ceiling (20%) is 4,672.
* The largest deletions are the MPS rewrites (674 lines, C2) and roe (516
  lines, C1).

**Split with lane R (proposed to Linfeng, question R6).** The 587 moved
lines count once:

* in lane R's table as deletions from ``hydro.cpp`` and
  ``hydro_forward.cpp``, with "after" 0 for those ranges;
* in lane C's table only in the "after" of the new files.

The call sites left in lane R's files are lane R's lines. The sweep
(``hydro_forward.cpp:1010-1031``, ``:1088-1152``, 87 lines) stays in lane
R's file, at about 45 lines after; lane C counts none of it. The rotation
helper (``riemann_solver.cpp:12-47``) moves to coord, so lane S counts it.

File by file:

.. csv-table::
   :header: "file", "now (measured)", "after (estimate)", "fate"
   :widths: 34, 10, 10, 46

   "src/recon/cp3.cpp", 53, 0, "removed: cp3 killed (no deck)"
   "src/recon/cp5.cpp", 60, 0, "merged: table -> x1_rows.cpp, calls -> reconstruct.cpp"
   "src/recon/interp_impl.cuh", 193, 0, "merged -> recon_line.cuh (Op wrappers, interp_nu_untiled deleted)"
   "src/recon/interp_impl.h", 49, 0, "deleted: line loops are the CPU loop in recon_dispatch.cpp"
   "src/recon/interp_point.h", 124, 0, "renamed -> recon_point.h (weno3_point deleted)"
   "src/recon/interpolation.cpp", 42, 0, "deleted: factory -> Scheme parse in reconstruct.cpp"
   "src/recon/interpolation.hpp", 288, 0, "deleted: 7 Interp classes -> Scheme + ReconRows"
   "src/recon/plm.cpp", 33, 0, "merged -> reconstruct.cpp (torch ops kept)"
   "src/recon/ppm.cpp", 18, 0, "removed: ppm killed (throws)"
   "src/recon/recon_dispatch.cpp", 179, 70, "MPS rewrites :83-158 deleted (OnHost); one stub"
   "src/recon/recon_dispatch.cu", 106, 70, "one launcher for uniform and per-face rows"
   "src/recon/recon_dispatch.hpp", 20, 15, "one dispatch stub"
   "src/recon/recon_dispatch_nu.cpp", 115, 0, "deleted: second path"
   "src/recon/recon_dispatch_nu.cu", 91, 0, "deleted: second path"
   "src/recon/recon_dispatch_nu.hpp", 17, 0, "deleted: second path"
   "src/recon/recon_launch.cuh", 98, 0, "merged -> recon_line.cuh"
   "src/recon/reconstruct.cpp", 181, 150, "dead block :118-141 and floors removed; plm, Scheme parse added"
   "src/recon/reconstruct.hpp", 103, 60, "dead options is_boundary_*, limiter removed"
   "src/recon/weno3.cpp", 58, 0, "removed: weno3 killed (no deck)"
   "src/recon/weno5.cpp", 70, 0, "merged: table -> x1_rows.cpp"
   "src/recon/x1_coeffs.cpp", 239, 0, "merged -> x1_rows.cpp"
   "src/recon/x1_coeffs.hpp", 86, 0, "merged -> x1_rows.hpp"
   "src/recon/x1_coeffs_device.h", 10, 0, "merged -> recon_point.h traits"
   "src/riemann/hllc.cpp", 115, 0, "merged -> riemann.cpp (one forward)"
   "src/riemann/hllc_dispatch.cpp", 174, 0, "CPU loop -> riemann_dispatch.cpp; MPS :50-164 deleted"
   "src/riemann/hllc_impl.h", 170, 0, "moved -> riemann_kernels.h"
   "src/riemann/lmars.cpp", 78, 0, "merged -> riemann.cpp"
   "src/riemann/lmars_dispatch.cpp", 112, 0, "CPU loop -> riemann_dispatch.cpp; MPS :44-102 deleted"
   "src/riemann/lmars_impl.h", 85, 0, "moved -> riemann_kernels.h"
   "src/riemann/plume_roe.cpp", 104, 0, "removed: plume-roe killed (no deck, no output)"
   "src/riemann/riemann_dispatch.cu", 125, 55, "one CUDA loop switching on kind"
   "src/riemann/riemann_dispatch.hpp", 25, 0, "merged -> riemann.hpp"
   "src/riemann/riemann_solver.cpp", 113, 0, "-> riemann.cpp; rotation -> coord (lane S)"
   "src/riemann/riemann_solver.hpp", 245, 0, "-> riemann.hpp; 6 classes -> 1"
   "src/riemann/roe.cpp", 69, 0, "removed: roe killed (no deck)"
   "src/riemann/roe_dispatch.cpp", 229, 0, "removed: roe killed"
   "src/riemann/roe_impl.h", 218, 0, "removed: roe killed"
   "src/riemann/shallow_roe.cpp", 58, 0, "merged -> riemann.cpp"
   "src/riemann/shallow_roe_dispatch.cpp", 91, 0, "CPU loop -> riemann_dispatch.cpp; MPS :33-81 deleted"
   "src/riemann/shallow_roe_impl.h", 78, 0, "moved -> riemann_kernels.h"
   "src/hydro/hydro_ref_x1_impl.h", 296, 290, "kept; stretched rows read from x1_rows table"
   "src/hydro/hydro_reference.hpp", 157, 0, "-> x1_reference.hpp"
   "src/hydro/wb_ref4.cpp", 132, 0, "rows -> x1_rows.cpp; flag/faces -> x1_reference.cpp"
   "src/hydro/wb_ref4.hpp", 53, 0, "-> x1_rows.hpp, x1_reference.hpp"
   "src/hydro/balance_column.cpp", 160, 105, "order-4 pass uses Conversion and X1Reference"
   "src/hydro/balance_column.hpp", 134, 110, "contract kept"
   "src/hydro/split_reference_scalar.hpp", 74, 74, "unchanged"
   "src/hydro/hydro_dispatch.cpp", 327, 0, "-> x1_reference_dispatch.cpp; MPS :33-54, :101-275 deleted; rows :277-312 -> x1_rows"
   "src/hydro/hydro_dispatch.cu", 118, 0, "-> x1_reference_dispatch.cu"
   "src/hydro/hydro_dispatch.hpp", 68, 0, "-> x1_reference_dispatch.hpp; wall4/conv4 decls -> recon"
   "src/hydro/hydro_forward.cpp:291-368", 78, 0, "lane R range, moved in: conv4 weights, wall4 weights/fill, admissibility -> x1_rows, conversion"
   "src/hydro/hydro_forward.cpp:417-504", 88, 0, "lane R range, moved in: conversion-order 4 stage -> conversion.cpp"
   "src/hydro/hydro_forward.cpp:668-820", 153, 0, "lane R range, moved in: well-balanced x1 block -> well_balanced_x1.cpp"
   "src/hydro/hydro.cpp:605-872", 268, 0, "lane R range, moved in: _hydro_ref_x1 -> x1_reference.cpp"
   "src/recon/recon_point.h", 0, 95, "new lane C file"
   "src/recon/recon_line.cuh", 0, 165, "new lane C file"
   "src/recon/x1_rows.hpp", 0, 45, "new lane C file"
   "src/recon/x1_rows.cpp", 0, 250, "new lane C file"
   "src/recon/conversion.hpp", 0, 30, "new lane C file"
   "src/recon/conversion.cpp", 0, 100, "new lane C file"
   "src/recon/well_balanced_x1.hpp", 0, 20, "new lane C file"
   "src/recon/well_balanced_x1.cpp", 0, 100, "new lane C file"
   "src/recon/face_floor.hpp", 0, 25, "new lane C file"
   "src/recon/face_floor.cpp", 0, 25, "new lane C file"
   "src/riemann/riemann.hpp", 0, 100, "new lane C file"
   "src/riemann/riemann.cpp", 0, 140, "new lane C file"
   "src/riemann/riemann_kernels.h", 0, 320, "new lane C file"
   "src/riemann/riemann_dispatch.cpp", 0, 55, "new lane C file"
   "src/hydro/x1_reference.hpp", 0, 70, "new lane C file"
   "src/hydro/x1_reference.cpp", 0, 230, "new lane C file"
   "src/hydro/x1_reference_dispatch.hpp", 0, 35, "new lane C file"
   "src/hydro/x1_reference_dispatch.cpp", 0, 65, "new lane C file"
   "src/hydro/x1_reference_dispatch.cu", 0, 95, "new lane C file"
   "TOTAL baseline files", 5841, 999, ""
   "TOTAL moved in from lane R", 587, 0, ""
   "TOTAL new files", 0, 1965, ""
   "TOTAL lane C", 6428, 2964, "-49.3% vs baseline; -53.9% vs baseline+moved"

10. Migration
-------------

.. list-table::
   :header-rows: 1

   * - PR
     - content
     - class and why
   * - C1
     - kill lists (section 3.6), dead options and code, tests adapted
     - bitwise for every deck: removed paths are unreachable from decks
   * - C2
     - MPS through ``OnHost`` for recon, Riemann, reference
     - CPU/CUDA bitwise (untouched); MPS changes to the CPU float32 result
       (FOR CHENG 3)
   * - C3
     - ``Scheme`` + tables, one dispatch stub, one CUDA line kernel
     - bitwise: same point functions, same order
   * - C4
     - one ``RiemannSolver``, one EOS pass, one CPU and one CUDA loop
     - bitwise: per-kind EOS order kept
   * - C5
     - post into the register; ``FaceFloor``; in-kernel ``mass_central``
     - bitwise except AAM full (round-off, expected; no deck)
   * - C6
     - ``x1_rows``, ``Conversion`` shared with ``balance_column``
     - key 2 bitwise; key 4 to round-off (expected; weights rebuilt in
       another arithmetic order; no deck)
   * - C7
     - ``X1Reference`` + ``X1ColumnLink``; ``WellBalancedX1``
     - bitwise: code move
   * - C8
     - ``reconstruct_faces`` / ``solve_faces``
     - bitwise: code move
   * - C9
     - FP32 typed constants; uniform rows read ``d``
     - FP64 bitwise; FP32 re-baselined against FP64 (no deck runs FP32)
   * - C10
     - FOR CHENG items 1 and 2 once ruled
     - deck results change where floors fire

**Options and paths removed:**

* ``riemann-solver: {type: roe | plume-roe | upwind}`` under ``dynamics``;
* ``reconstruct`` ``type: ppm | weno3 | cp3``;
* the ``ReconstructOptions`` fields ``is_boundary_lower``,
  ``is_boundary_upper`` and ``limiter``;
* the Python ``UpwindSolver``, ``RoeSolver``, ``LmarsSolver`` and
  ``ShallowRoeSolver``;
* ``hydro_pressure_scan_x1_tensor`` and the MPS reference;
* ``recon_dispatch_nu`` and the stretched-x1 refusal on MPS.

11. Open questions to other lanes
---------------------------------

**Lane R (Linfeng):**

* R1: the register API ``solve_faces`` writes into: slot views per
  (increment, direction, stage)?
* R2: the accumulation dtype in FP32 runs (lane O assumes FP64)?
* R3: the declared increment order and the ``(theta - 1) F`` rule for
  positivity?
* R4: will the monitor hold the ``FaceFloor`` counters and
  ``FaceFlux::events``, and who resets them on a redo?
* R5: who owns the x1 seam reconciliation?
* R6: the line split of section 9.

**Lane S (Jiheng):**

* S1: ``X1ColumnLink`` (anchor relay, ghost rows) and a capture-safe form.
* S2: ``to_face_frame_`` and ``to_global_frame_`` in coord; in-kernel 3x3 or
  tensor passes.
* S3: the cubed-sphere face-state exchange between ``reconstruct_faces`` and
  ``solve_faces``.

**Lane A:** is ``mass_central`` (IDN and ICY.. rows, FP64, x2/x3) enough,
or must AAM keep every row, as ``_aam_mass_flux`` does today
(``hydro_forward.cpp:1356-1361``)?

**Lane O (Jiachen):** the display of the floor counts and solver events.

**Lane I (Xinyue):** ``src/implicit`` reads no lane C output at the pin (no
``grep`` match for the face pressure, the reference or the solver). Does V3
keep it that way?

**Lane X:** are the eager boundaries in section 7 acceptable for G4/G6,
until lane S makes them capture-safe?

**Cheng:** section 3.8 items 1-3.

12. Skeleton index
------------------

``docs/v3/skeleton/C/``: declarations and comments only, 287 lines
(``wc -l``). It is outside ``src/``, so no CMake glob, Doxygen input or
clang-format hook reads it.

.. list-table::
   :header-rows: 1

   * - file
     - lines
     - declares
   * - ``recon_point.h``
     - 31
     - ``Scheme``, ``SchemeTraits``, ``poly_point``, ``weno5_point``,
       ``recon_point``
   * - ``x1_rows.hpp``
     - 48
     - ``face_value_row``, ``ReconRows``, ``recon_rows``, ``conv4_rows``,
       ``wall4_rows``, ``FaceDensityRows``, ``six_face_rows``,
       ``X1RowsCache``
   * - ``reconstruct.hpp``
     - 60
     - ``ReconstructOptionsImpl``, ``FaceStates``, ``Conversion``,
       ``WellBalancedX1``, ``FaceFloor``, ``ReconstructImpl``
   * - ``x1_reference.hpp``
     - 53
     - ``ReferenceInput``, ``ReferenceFaces``, ``X1ColumnLink``,
       ``X1ReferenceConfig``, ``X1Reference``
   * - ``riemann.hpp``
     - 68
     - ``RiemannKind``, ``RiemannSolverOptionsImpl``, ``FaceFlux``,
       ``kRiemannIncrement``, ``FaceThermo``, ``FaceBackground``,
       ``RiemannSolverImpl``, ``riemann_face``, ``riemann_fn``
   * - ``sweep.hpp``
     - 27
     - ``FaceDir``, ``reconstruct_faces``, ``solve_faces``

Measurements in this revision (on the lane's build host, at the pin):

* ``wc -l`` and ``docs/v3/design/C_lines.py``;
* the deck census in section 2.3 (``yaml.safe_load_all`` over the tree's
  YAML; ``grep`` for code-built options);
* the FP32 probe (``g++ -O2 -std=c++17``, ``interp_point.h`` with an empty
  ``DISPATCH_MACRO``, 1,000,000 faces, ``mt19937`` seed 7; ``g++ -S``
  instruction counts);
* ``grep`` for host reads, allocations and communication;
* the ``mass_central`` sizes, from the deck's ``cells`` and ``species``.
