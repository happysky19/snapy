:orphan:

V3 lane C: reconstruction, Riemann solvers, well-balanced reference, conversion order
=====================================================================================

Revision 4, 2026-11-17. Owner: Tianhao Le (alternate: Xinyue). Design only:
no implementation change. Declarations are in ``docs/v3/skeleton/C/`` (not
built); the file-by-file line table is ``docs/v3/design/C_lines.csv``,
produced by ``docs/v3/design/C_lines.py``.

Every ``path:line`` is at chengcli/snapy
``9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410`` unless another commit is named.
"Measured" means produced by a command named in the text; "estimate" means a
design target.

Changes in revision 4 (from ``eb998ab1``), after Cheng's decision in the
home thread that every solver and scheme stays:

* **Nothing is removed.** All six Riemann solvers (roe, lmars, hllc,
  upwind, shallow-roe, plume-roe) and all six schemes (plm, ppm, weno3,
  weno5, cp3, cp5) stay, and dc stays as the default scheme. The kill lists
  are gone from sections 3.6, 9 and 10.
* **The budget is redone on structure alone**: one kernel definition per
  scheme and per solver across CPU, CUDA and MPS, one dispatch, one
  direction-generic sweep and one frame rotation. The estimate is 3,329
  lines against the 4,672-line ceiling (section 9).
* **The ``riemann`` increment and its ``central`` and ``dissipative``
  parts are defined for each of the six solvers** (section 3.6). Section 4
  states what lane A reads as ``riemann.central``. The names follow lane
  A's ``A.rst`` (JiachenLiu-Atmos/snapy ``v3-design/A`` ``2c9589c6``). They
  stay provisional until lane R's header exists.
* **"What changes" table** (section 3.8). The single default, the
  ``shock`` default, the shock-path floors, MPS through host copies, the
  FP32 typed constants, the Python binding and the ``--fmad=false`` CI build
  are ``FOR CHENG``.
* **The 587-line accounting with lane R is provisional** until lane R's
  owner confirms it in lane R's own table (section 9). Revision 3 called it
  confirmed; that was premature.

Revision 4.1 (on ``87333f5e``) reconciles the two round-2 reviews of
revision 3 (Xinyue's and Jiachen's). The changes:

* the PR #369 overlap and its "upward" reference mode (sections 3.5, 9 and
  11);
* the stage order: x1 seam average before positivity; diffusion placed
  (section 4);
* lane A's dissipative mass flux defined against the total registered
  x2/x3 flux (section 4);
* ``riemann.central`` as one summed mass row, its lifetime, and x2/x3 panel
  seams (section 4);
* the flux-dtype wording (sections 4 and 6);
* the AAM test arms (section 5);
* gravity work's x1 mass rows and FP64 inputs (section 4).

Earlier revisions:

* Revision 3 (``eb998ab1``) put sections 6 and 7 on lane X's contracts
  (UCzhangxi/snapy ``v3-design/X`` ``77c65d5a``).
* Revision 2 (``a660a7af``) answered Cheng's revision-1 review: the twelve
  sections, the register contract, the lane letters, the per-file budget,
  and upper-case names.
* Revision 1 is ``b7d1300f``.

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
* execution and graphs: lane X;
* the EOS and limiters, including the floor values ``FaceFloor`` applies:
  lane EF.

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
  lane's revision 1 was posted;
* lane X (UCzhangxi/snapy ``v3-design/X``
  ``77c65d5aac1f96ff6c34a45ef48faeb996c2128e``, fetched read-only; it
  descends from the pin): ``X.rst`` sections 3, 4, 6, 7, 8 and 11 and the
  skeletons ``precision_policy.hpp`` and ``stage_executor.hpp``;
* lane A (JiachenLiu-Atmos/snapy ``v3-design/A``
  ``2c9589c68c633796cfa5f749d003af7a2b57f38a``, fetched read-only):
  ``A.rst`` A-r2, sections 6.1 and 6.2, and question R-1/C-1, for what lane
  A reads as ``riemann.central``.

**Lane R material.** None is published. No ``v3-design/R`` branch exists on
any of the eleven chengcli/snapy forks or on chengcli (``git ls-remote``).
The only register-named ref is ``fix/224-register-tests``, which is
unrelated. Lane R's names and dtypes are therefore not used anywhere in
this document as settled.

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
* Upwind and plume-roe do not work as hydro solvers at the pin.

  * Upwind is ``RiemannSolverImpl::forward`` (``riemann_solver.cpp:79-88``).
    It refuses a face pressure, and the x1 solve passes one
    (``hydro_forward.cpp:842-845``). On x2/x3 it returns ``vel * ...``
    with the flux buffer read as ``vel``, and ``solve`` discards the return
    value (``:544-548``). Its working use is scalar transport, where ``vel``
    is the hydro mass flux (``scalar.cpp:150-163``).
  * Plume-roe refuses ``dim != 1`` (``plume_roe.cpp:52-55``), which in hydro
    is x3 (``DIM3 = 1``, ``hydro_forward.cpp:372``). It also refuses a face
    pressure, and it returns without writing ``flx`` (``:99-101``).

  No deck or test runs either in hydro (section 2.3).
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
     - one point function per scheme: cp3, weno3, cp5, weno5. dc, plm and
       ppm are tensor code.
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
   FluxRegister["riemann", dir, stage]  (+ p*, riemann.central) [R]
     |  later increments by their owners: sedimentation, covariance,
     |  positivity; seam reconciliation                        [R/S]
     v
   divergence and every flux-derived term read the register    [R]

3.3 Reconstruction (questions 1, 2)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**One definition per scheme**, for every scheme that stays:

* cp3 and cp5 are ``poly_point<3>`` and ``poly_point<5>``; weno3 and weno5
  are ``weno3_point`` and ``weno5_point``. All four are ``DISPATCH_MACRO``
  point functions reached through ``recon_point<Scheme,T>``. The CPU loop and
  the CUDA line kernel are written once over ``Scheme``.
* dc (a copy) and plm (torch ops, ``plm.cpp:19-29``) stay tensor code. Torch
  ops are already one definition on every backend, and plm is the scheme
  the inventory found bitwise between CPU and CUDA (not re-measured here).
* ppm stays a registered scheme with today's behaviour: the parser accepts
  it and ``forward`` throws "not implemented" (``ppm.cpp:14``). Implementing
  PPM is new numerics, outside this refactor.
* The group rule stays: ``weno5`` reconstructs velocity and pressure with
  cp5, and ``weno3`` with cp3 (``interpolation.cpp:21-36``). It becomes one
  explicit table in ``reconstruct.cpp``, keyed by scheme, in place of the
  name's last character.

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
* ``recon_dispatch_nu.*`` and ``interp_impl.h`` are deleted. They are
  code paths, not options.

**One x1 path.** ``ReconRows`` carries ``row_stride``: ``ncoeff`` for
per-face rows, and ``0`` (one broadcast row) for a uniform grid. Per-face rows
are already needed on every radial grid (``coordinate.cpp:546-562``) and on
every stretched x1.

Moving weno5's ``.3/.6/.1`` (``interp_point.h:113-115``) into the table is
bitwise in FP64 but not in FP32 (``0.3f != 0.3``), so it lands with C9.
Until then C3 keeps ``Nu`` as a compile-time branch on ``row_stride == 0``.
dc, plm, ppm, cp3 and weno3 keep today's stretched-x1 refusal
(``interpolation.hpp:62-71``).

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

**PR #369 overlap.** #369 is open at ``c382f0da``, "Terrain (per-column
immersed solid) on the x1-wall path", based on ``cbf86830``, the pin's
parent. It adds ``dynamics/wb-wall-reference`` (``auto``, ``upward``,
``main``; #369 ``hydro_options.cpp:54-68``). With ``upward``:

* every grid takes the six-face rows path;
* each cell's row starts at its own lower face (#369
  ``hydro_reference.hpp``, ``hydro_dispatch.hpp``);
* each solid depth gets its own x1 frame (``HydroImpl::X1Depth``, #369
  ``hydro.hpp``).

It rewrites most of lane C's moved ranges in ``hydro_forward.cpp``
(``git diff --stat 9e5de2d4...pr/369``: +438/-166 in that file). It also
uses ``hydro_ref_x1_mps`` as a CPU-callable parity port (#369
``tests/test_hydro_ref_x1.cpp:583``,
``mps_port_matches_the_kernel_on_the_upward_rows``).

Lane C stays on the pin. If #369 merges first:

* ``X1ReferenceConfig`` gains the reference mode and the depth index, and
  ``six_face_rows`` gains ``upward``;
* the budget's moved-in ranges are re-measured on the new base;
* C2 must either keep the tensor port (+175 lines, section 9) or turn
  #369's parity test into a comparison of ``OnHost`` against the kernel.
  That choice is the PR author's and Cheng's (question to #369, section
  11).

3.6 Riemann (questions 6, 7): six solvers, one module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All six solvers stay. One ``RiemannSolverImpl`` with ``RiemannKind`` replaces
the six classes (``riemann_solver.hpp:54-242``).

* **One kernel definition per solver** for CPU, CUDA and MPS:

  * hllc, lmars, roe and shallow-roe are ``DISPATCH_MACRO`` face functions
    in ``riemann_kernels.h``. One CPU loop and one CUDA loop switch on the
    kind once per call. MPS runs the CPU loop through ``OnHost``, which is
    ``FOR CHENG`` (section 3.8).
  * upwind and plume-roe are torch-op formulas, which already run as one
    definition on every backend.
* **One EOS face pass**, ``FaceThermo``, replaces ``hllc.cpp:64-81``,
  ``lmars.cpp:36-52`` and ``roe.cpp:32-37``. The per-kind order of the EOS
  calls is kept, so the results stay bitwise. Roe's ideal-moist tables
  (``roe.cpp:20-30``) go into ``RiemannParams``.
* **One rotation**, owned by coord (lane S), replaces
  ``riemann_solver.cpp:12-47`` and the three covariance copies.
* **One dispatch stub**, ``riemann_fn``, replaces ``call_hllc``,
  ``call_lmars``, ``call_roe`` and ``call_shallow_roe``.

**What each solver provides.** The ``riemann`` increment is defined in
section 4. Its parts are:

* ``central`` = the conserved rows of ``1/2 (F(w_L) + F(w_R))``, where ``F``
  is the solver's own physical flux of one state. For every solver here,
  ``F(w, w)`` is that physical flux, so this is today's ``1/2 (F(w_L, w_L) +
  F(w_R, w_R))`` (``hydro_forward.cpp:997-1003``) up to round-off;
* ``dissipative`` = ``riemann - central``. It is derived, never stored.

For hydro, ``central`` is stored as **one summed mass row**: IDN (dry) plus
the sum of the ICY.. species rows. It is stored only when a consumer asks for
it (lane A's ``conserve-axial-momentum`` modes). The only consumer at the
pin sums those rows itself (``gnomonic_equiangle.cpp:690-694``, the
``mass`` lambda of ``axial_coriolis_rate``), so per-species rows carry
nothing it uses. For the other rows only the total is posted.

.. list-table::
   :header-rows: 1

   * - solver
     - equations; where it works at the pin
     - ``riemann`` (posted)
     - ``central`` (summed hydro mass row, stored on request)
     - ``p*``
   * - hllc
     - Euler + species; hydro, every direction
     - ``hllc_impl.h:151-162``
     - dry ``1/2 (rho_L u_L rd_L + rho_R u_R rd_R)``; species ``1/2
       (rho_L q_L u_L + rho_R q_R u_R)``; ``u`` is the face-normal velocity
       in the face frame, ``rd = 1 - sum q``
     - contact pressure, clamped (``:96-98``)
   * - lmars
     - Euler + species; hydro
     - ``lmars_impl.h:47-77`` (upwinded by ``ubar``)
     - same formula as hllc
     - ``pbar`` (``:38-40``)
   * - roe
     - Euler + species, ideal-moist aware; hydro (tests)
     - ``roe_impl.h:103-210``
     - same formula; it is the ``0.5 (fl + fr)`` the kernel already forms
       before subtracting dissipation (``:103-112``)
     - acoustic estimate (``:119-122``)
   * - shallow-roe
     - shallow water (h, hu, hv), ny = 0; hydro shallow-water decks
     - ``shallow_roe_impl.h:60-71``
     - ``1/2 (h_L u_L + h_R u_R)``, the kernel's own central row
       (``:60``)
     - none
   * - upwind
     - transport of a quantity ``q`` by a given face mass flux ``m``;
       scalar transport (``scalar.cpp:150-163``); not functional in hydro
       (section 2.5)
     - ``m q_upwind`` (``riemann_solver.cpp:86-87``)
     - ``m 1/2 (q_L + q_R)`` for each transported row; ``dissipative`` =
       ``1/2 abs(m) (q_L - q_R)``. Posted by whoever transports ``q``; no
       hydro mass rows
     - none
   * - plume-roe
     - plume equations (R, W, B, V), ``dim == 1`` only; not functional in
       hydro (section 2.5)
     - Lax-Friedrichs, ``plume_roe.cpp:14-39``
     - all four rows ``1/2 (F(w_L) + F(w_R))`` (``:38``); dissipative
       ``-1/2 alpha (w_R - w_L)``; no hydro mass rows
     - none

So hllc, lmars, roe and shallow-roe give lane A its mass rows. Upwind and
plume-roe have no hydro mass rows. With them, ``riemann.central`` is
undefined for lane A, and an option that needs it refuses at ``reset()``
with a message naming the solver.

**Retained, with proposed contract fixes** (``FOR CHENG``, section 3.8):

* plume-roe writes its flux into its slot, as every solver must. Its unused
  Roe averages, Jacobian and characteristic polynomial
  (``plume_roe.cpp:57-92``) are dead code and go; the option stays.
* Upwind and plume-roe under ``dynamics`` are refused at ``reset()`` for a
  direction they cannot solve, in place of today's runtime failure or
  discarded result. Upwind stays the scalar default (``scalar.hpp:29``).

**Single default (proposal; ``FOR CHENG``).** hllc, unchanged:

* it is the default already in ``create()`` and YAML, relied on by 27
  decks and named by 10;
* it is the only solver allowed with ``perturbation-flux``
  (``hydro.cpp:207-210``), which FP32 needs (``hydro.cpp:80-81``);
* it is the roadmap's first FP32 case (``V3_ROADMAP.md:375-376``).

**FP32 perturbation entry**: the ``FaceBackground`` argument, hllc only. It
is the same kernel shifted by ``p0`` (``hllc_impl.h:29-31``, ``:51-52``,
``:96-97``, ``:155-156``). The mass rows carry no pressure, so ``central``
is unaffected by the gauge; face densities are totals on both paths
(``hydro_forward.cpp:586-588``, ``:790-805``). LMARS and Roe perturbation
support stays deferred (``V3_ROADMAP.md:543``).

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

3.8 What changes
~~~~~~~~~~~~~~~~

Every option of the pin stays (Cheng's decision). This table lists what
the design proposes to change in behaviour or interface. "Decks" is the
in-tree census of section 2.3.

.. list-table::
   :header-rows: 1

   * - change
     - decks whose results change
     - status
   * - single Riemann default: hllc (unchanged)
     - none
     - FOR CHENG
   * - one ``shock`` default, ``false`` in ``create()`` as in YAML
     - 7 test decks with the limiter on, where a density or pressure floor
       fires
     - FOR CHENG
   * - density and pressure floors on the shock path
     - 12 decks (6 examples), where a floor fires
     - FOR CHENG
   * - MPS through host copies (``OnHost``)
     - every MPS run: MPS results become the CPU float32 result; MPS
       throughput drops
     - FOR CHENG
   * - FP32 typed constants in weno3/weno5/LMARS (C9)
     - none in-tree (no deck sets ``precision: float32``); FP32 tests are
       re-baselined against FP64
     - FOR CHENG
   * - Python: one ``RiemannSolver`` binding in place of ``UpwindSolver``,
       ``RoeSolver``, ``LmarsSolver``, ``ShallowRoeSolver``
       (``pyriemann.cpp:26-41``)
     - none (no in-tree Python uses them)
     - FOR CHENG
   * - a ``--fmad=false`` CI build of the recon/Riemann ``.cu`` files, for
       bitwise CPU/CUDA debugging (not the default)
     - none
     - FOR CHENG
   * - plume-roe writes its slot; upwind/plume-roe refused at ``reset()``
       for a hydro direction they cannot solve
     - none (none works in hydro at the pin, section 2.5)
     - FOR CHENG (new in revision 4)
   * - in-kernel ``riemann.central`` in place of two extra solves per
       x2/x3 direction (C5)
     - none (no deck runs ``conserve-axial-momentum: full``); round-off
       change expected
     - proposal; lane A gate H1 (1e-14 relative)
   * - key-4 weight rows from ``x1_rows`` (C6)
     - none (no deck runs key 4); round-off change expected
     - proposal

4. Flux-register contract
-------------------------

Register owner: lane R. Lane C stores no face flux. ``_flux1/2/3``,
``_face_pressure1``, ``cen2/3``, ``_aam_mass_flux`` and ``bflux1`` become
register slots or views of them. The executor side of the register
(allocation by ``StateStore`` at ``reset()``, ``begin_stage`` with the
integrator weights, reset at stage 0 and on rollback, the monitor read with
the retry flags) is lane X's, ``X.rst`` section 4. Lane C takes it as stated
there.

**Provisional until lane R answers** (questions R1-R4, section 11). Lane R
has no published design yet, so these lane C items are proposals, not
agreed interfaces:

* the increment name ``riemann``;
* the part names ``riemann.central`` and ``riemann.dissipative``. They are
  lane A's names (``A.rst`` A-r2), and lane A has asked lane R whether a
  named part is supported (A's R-1);
* whether ``central`` is kept as a field or reported only as an integral;
* the register API that ``solve_faces`` writes into;
* the FP32 accumulation dtype.

No lane R header or numbered review notes were available to this revision.
No R name or dtype is taken as settled here.

They may change with lane R's revision. Lane C's own computation (what
the solve produces, its frame, area weighting and compute dtype) does not
depend on those answers.

**What lane C posts.** One increment per direction ``d`` and stage,
provisionally named ``riemann`` (req. 2), written in place into the
register's slot by ``solve_faces``:

* **quantity**: conservative flux density per unit face area, all ``nvar``
  rows. The register's divergence applies ``face_area<d>`` and the cell
  volume, as ``coordinate.cpp:706-735`` does today (req. 1);
* **frame**: global coordinate components, after coord's
  ``to_global_frame_`` (req. 1, 5). Rotation is one function owned by coord;
  lane C calls it and does not own it;
* **location**: face index ``i`` along ``d`` is the face between cells
  ``i-1`` and ``i`` (today's convention);
* **dtype**: ``policy.compute(Quantity::kFlux)`` (X section 6, "fluxes,
  du"): FP32 in an FP32 run, FP64 otherwise (req. 8). The step accumulator
  is X's ``Quantity::kRegister``, FP64 as a hypothesis in X and open to lane
  R (question R2). Lane C posts in ``kFlux`` whatever R chooses.

**Companion fields, posted with the increment.** They are not flux
increments.

* ``p*`` (x1 only): the total face pressure, ``Quantity::kGauge``, FP64 in
  every precision (X section 6, "gauges, total face pressure"). In FP32 runs
  it is the ``kFlux`` perturbation plus the FP64 background, added once in
  ``solve_faces`` (today ``hydro_forward.cpp:568-570``,
  ``hydro.cpp:252-253``). It is read by the pressure source and gravity work.

**Parts of the increment (provisional names, lane A's).** Section 3.6
defines them per solver.

* ``riemann.central``: **one row**, the summed mass flux (IDN dry plus all
  ICY.. species) of ``1/2 (F(w_L) + F(w_R))``. It is formed in the kernel
  from the face states the solver used: A-r2's ``1/2 Σ_s (ρ_s u_n)_L +
  (ρ_s u_n)_R``, summed over ``s``. The one row is enough because the
  consumer sums the rows (``gnomonic_equiangle.cpp:690-694``).

  * Densities are totals on both the total and the perturbation path
    (section 3.6), so lane A's R-1 sub-question is answered from lane C's
    side: totals.
  * The mass rows are not touched by the frame rotation (``flux2global*_``
    rewrites only the momentum rows, ``gnomonic_equiangle.cpp:428-455``), so
    the row is the same in the face and global frames.
  * Defined for hllc, lmars, roe and shallow-roe. Upwind and plume-roe have
    no hydro mass rows (section 3.6), and a mode that needs ``central``
    refuses them at ``reset()``.
  * Stored only on request, on the directions asked for: x2 and x3 today
    (``hydro_forward.cpp:1356-1361``).
  * **Lifetime.** ``solve_faces`` writes it in steps 4.A/4.B of the stage
    (``hydro_forward.cpp:1050-1152``). It stays valid through the stage end:
    the forcing phase reads it (today ``:1356`` and the Coriolis call in the
    loop at ``:1378``), and so does lane A's post-implicit phase (``A.rst``
    R-1; today's post-implicit forcings, ``:1624-1669``). The register's reset
    at stage 0 and on rollback (X section 4) is its only reset. Today's
    ``_aam_mass_flux`` is cleared after the first Coriolis call (``:1391``);
    that early clear goes.
  * **x2/x3 panel seams.** At the pin a panel-seam face is single-valued
    because both sides solve the same exchanged face states (``:1005-1048``).
    ``src/hydro`` has no panel-seam flux average. ``central`` is formed from
    those same states, and its row is frame-free, so it is as single-valued
    as the ``riemann`` mass rows, to the same round-off. If lane S/R add a
    panel-seam reconciliation for ``riemann``, it applies to ``central``
    with the same rule (question S4).
* ``riemann.dissipative`` = the summed ``riemann`` mass row minus
  ``riemann.central``: the Riemann part only. It is derived, never stored.
* **Lane A's dissipative mass flux** ``F_d`` is not ``riemann.dissipative``.
  It is the **total registered** x2/x3 summed mass flux minus
  ``riemann.central``. The total is every mass-carrying increment of the
  stage on that face: ``riemann``, the #289 covariance (``:1099-1110``,
  ``:1134-1143``) and the positivity scaling (4.C, ``:1154-1252``). That is
  today's definition: ``_aam_mass_flux = _flux2 - cen2`` is formed after
  4.C (``:1356-1361``), and the closure reads the total ``phydro->flux2()``
  (``coriolis.cpp:200``). Lane A forms ``F - F_c`` itself in FP64
  (``A.rst`` 6.1).

**dtype of the parts.** ``riemann.central`` is in the flux dtype, X's
``Quantity::kFlux``, the same as the increment: FP64 in an FP64 run, FP32 in
an FP32 run (``A.rst`` 6.1: "flux dtype (FP32)"). A consumer that needs
FP64 casts it on read (X's ``kReduction`` row). Lane C posts no FP64 copy.
At the pin the AAM full mode refuses FP32 (``hydro_forward.cpp:993-995``).
Lane A plans to lift that after its gate G10 (``A.rst`` 6.2), so lane C
does not assume FP64.

**Memory of riemann.central (req. 9).** Size: ``nc3 x nc2 x nc1 x b``
bytes per stored direction (one row), with ``b`` = 8 (FP64) or 4 (FP32).
It is fixed storage allocated at ``reset()`` only when requested.

* For ``examples/jupiter_gcm.yaml`` dimensions (48 x 48 x 100, nghost 3,
  so 309,096 cells with ghosts) in FP64, that is 2.47 MB per direction and
  4.9 MB per block for x2 and x3.
* Today the same option holds ``cen`` and ``_flux - cen``: 2 x nvar rows
  (nvar = 14 there), or 69.2 MB per direction (by reading
  ``hydro_forward.cpp:997-1003``, ``:1356-1361``; not profiled). Lane A's
  count (``A.rst``, table at line 694) is "2 (5+ny)" rows today; one
  summed row is below its "2 (1+ny)".
* It also removes four Riemann solves per stage.

**Gravity work's x1 mass rows (lane I/R reads).** Gravity work reads two
summed x1 mass rows:

* the **total registered** x1 mass flux, after sedimentation and
  positivity (``hydro_forward.cpp:1412-1425``);
* in cell form, the **Riemann part alone** (today ``bflux1``, ``:846-848``).
  It is seam-averaged with the flux (``:902-917``) and subtracted from the
  total (``:1430-1433``).

Both come from the register: the second is the summed mass row of the
reconciled ``riemann`` increment, so no separate lane C row is needed. Both
are in ``kFlux``. Gravity work's sums are FP64 (X's ``kReduction`` row), so
the reader casts on read. Lane C posts no FP64 copy (question I-C1).

**What lane C reads from the register:** nothing. Reconstruction and the
reference read the state.

**What lane C corrects:** nothing. It does not modify another lane's
increment.

**Ordering constraints**, the stage order at the pin (inside X's posting
segment, X section 4: post before pack):

1. x1: ``riemann`` (``hydro_forward.cpp:845``), then sedimentation as its own
   increment (``:861-866``).
2. x1 seam average (``:882-946``). This is the reconciliation of a shared
   face (req. 5): in X's terms, the register's exchange phase. It applies to
   the x1 ``riemann`` with ``p*``, gravity work's Riemann row and the split
   background, and it is lane R/S's. It runs **before positivity**, so
   positivity sees single-valued seam faces (comment at ``:1158-1159``).
3. x2/x3: ``riemann`` with ``riemann.central`` (``:1088-1152``), then the
   #289 covariance as its own increment (``:1099-1110``, ``:1134-1143``).
4. Positivity (4.C, ``:1154-1252``). Its theta exchange is at ``:1227``. It
   scales the species rows of all three directions; it must be posted as
   ``(theta - 1) F``, which is lane R's rule.
5. Divergence (``:1254``), then the forcing phase (``:1306-1552``). That
   phase includes Coriolis, which reads ``riemann.central``, and diffusion.
   Diffusion (lane A, ``A.rst`` phase 3) is its own increment after
   positivity. It carries no mass flux, so ``riemann.central`` and ``F_d``
   are unchanged by it.
6. Gravity work (``:1412-1535``), then the implicit solve (``:1554``) and
   the post-implicit forcings (``:1624-1669``).

So the increments must be reportable separately (req. 2): gravity work
reads ``riemann`` alone, and lane A reads the total minus ``central``.

**Floors (req. 7):** counts, as described in section 3.7. The solver's
p* clamp is reported in ``FaceFlux::events``. Both go into lane R's monitor,
which X reads with the retry flags.

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
   * - ``riemann.central`` equals today's central mass rows (two extra
       solves, ``hydro_forward.cpp:997-1003``)
     - tolerance: 1e-14 relative, FP64 (lane A's H1)
     - lane A's G2 on the #363 deck. AAM arms of
       ``tests/test_axial_momentum_flux_form.py`` (ctest at
       ``tests/CMakeLists.txt:333``):

       * (f)-(h) and (l) run lmars (``test_axial_momentum_flux_form.yaml:30``);
       * (i)-(k) run shallow-roe (``test_axial_momentum_flux_form.py:216``).

       No arm runs hllc or roe. C5 adds one arm each, at the (f) and (k)
       settings.
   * - every solver and scheme of the pin still parses and runs as before
       (ppm still throws)
     - bitwise per C1-C4, C7, C8
     - existing tests per option: ``test_riemann`` (lmars, roe),
       ``test_weno`` (weno3, cp3, weno5, cp5), ``test_plm``,
       ``test_x1_stretched_refusal``, scalar upwind tests
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

**The contract is lane X's** (``X.rst`` section 6; ``PrecisionPolicy``
and ``Quantity`` in ``docs/v3/skeleton/X/precision_policy.hpp``). Lane C
defines no second dtype table. Every lane C quantity maps onto one X row,
and lane C code calls ``policy.compute(q)`` / ``policy.cast(q, x)`` in
place of ``fp32()``.

.. list-table::
   :header-rows: 1

   * - lane C quantity
     - X row
     - FP32 run
     - FP64 run
     - pin evidence
   * - conversion input and output (``u - L u``, ``W``, ``w``)
     - ``kPrimitive``
     - FP64
     - FP64
     - ``hydro_forward.cpp:410-412``, ``:512-519``
   * - reference evaluation (``SRS`` pairs, scan, ``psf``, ``pref``,
       ``dref``, ``dsf_lr``)
     - ``kReference``
     - FP64
     - FP64
     - ``hydro_reference.hpp:102-128``
   * - x1 weight tables (``x1_rows``)
     - ``kReference`` master, cast per use
     - FP64 master; consumer's compute dtype on the device
     - FP64
     - X: "reference and geometry masters, FP64, cached casts"
   * - gauges, split background, ``p*``
     - ``kGauge``
     - FP64
     - FP64
     - ``hydro.cpp:671-674``; ``hydro_forward.cpp:568-570``
   * - WB perturbations ``w'``
     - formed in ``kPrimitive``, cast to ``kFlux`` for reconstruction
     - FP64, then FP32
     - FP64
     - ``hydro_forward.cpp:700-705``, ``:762``
   * - face states (reconstruction output, Riemann input), ``FaceThermo``
     - ``kFlux`` (proposed; X has no face-state row, question X1)
     - FP32
     - FP64
     - ``hydro_forward.cpp:565``, ``:586-588``
   * - ``riemann`` increment
     - ``kFlux``
     - FP32
     - FP64
     - ``hydro.cpp:248``
   * - ``riemann.central`` (provisional; one summed row)
     - ``kFlux`` (flux dtype); FP64 readers cast on read
     - FP32 (refused at the pin, ``hydro_forward.cpp:993-995``; lane A
       plans to lift it)
     - FP64
     - ``A.rst`` 6.1
   * - register step accumulator
     - ``kRegister``
     - FP64 (X's hypothesis; open to R)
     - FP64
     - X section 6
   * - floor counters, solver events
     - not a float quantity
     - ``int64`` / ``uint8``
     - same
     - section 3.7

**Floors** act on the dtype of the value they floor. On the split path the
x2/x3 pressure floor acts on the FP64 total after the gauge is restored
(``hydro_forward.cpp:600-605``, ``:608-613``), which is ``kGauge``.
Elsewhere they act on ``kFlux`` face states.

**Where revision 2 and X disagreed, and the resolution:**

1. *Mechanism.* Revision 2 described FP32 behaviour through today's
   ``fp32()`` conditions. X replaces all 30 ``fp32()`` calls in ``src``
   (counted at the pin: ``git grep -c 'fp32()'``) with ``PrecisionPolicy``.
   Ten of them are in the ranges that move into lane C files:

   * ``hydro_forward.cpp:693``, ``:704``, ``:762``, ``:774``, ``:781``,
     ``:784``, ``:814``;
   * ``hydro.cpp:638``, ``:671``, ``:709``.

   Lane C's PR C7 converts those ten to policy calls, after X's PR X1
   (section 8). The baseline lane C files contain none. HLLC's
   ``is_same_v<T, float>`` branches (``hllc_impl.h:76``, ``:102``) are
   template dispatch on the kernel type, not precision policy, and stay.
2. *Dtype-change rebinding.* HLLC rebinds its FP64 buffers to the state
   dtype on first use (``hllc.cpp:51-54``). That is X's "allocation on dtype
   change" class (X section 7), and it goes the same way: ``FaceThermo``
   buffers are created in ``policy.compute(kFlux)`` at ``reset()``.
3. *Face states* have no X row. Lane C proposes ``kFlux`` (question X1)
   and does not add a ``Quantity``.
4. *Floors.* Revision 2 said "FP64 floors on FP64 totals" for all floors.
   That is true only on the split path. The table above is the precise
   statement.

No other lane C dtype differs from X's table. The FP64 islands (conversion,
reference, gauges, ``p*``) are X's ``kPrimitive``, ``kReference`` and
``kGauge`` rows. FP32 arithmetic in the point functions is C9 (section
2.5), which makes the ``kFlux`` compute dtype hold inside the kernels as
well.

**MPS** follows X's MPS rule (no FP64). Lane C's MPS path is the CPU
kernel at float32 (``OnHost``). The split path stays refused on MPS,
because anomaly storage refuses MPS (#354, commit 7ca41432).

7. CUDA-graph contract
----------------------

**The contract is lane X's** (``X.rst`` section 7; ``StageExecutor``,
``Segment``, ``Op`` and ``GraphKey`` in
``docs/v3/skeleton/X/stage_executor.hpp``):

* eager is the reference;
* an ``Op`` is capturable when it does no host read and allocates nothing
  outside the graph pool;
* communication is a ``kPack`` / ``kHost`` / ``kUnpack`` boundary;
* graphs are keyed by ``GraphKey``.

Lane C adds no executor. Its code runs inside lane R's ``hydro.forward``
compute op. This section states lane C's part of X's per-owner rulings and
the boundaries lane C adds inside that op.

**Host reads: lane C's ruling on X's per-directory counts.** X counts
``.item<`` lines at the pin: recon 2, hydro 11, riemann 0.

* ``recon``, 2: ``x1_coeffs.cpp:131``, ``:135``. They run at the build of
  ``X1RowsCache``, outside every segment.
* ``hydro``, 5 of the 11 are lane C's: ``hydro_reference.hpp:47-48``, at
  the cache build in the ``X1Reference`` constructor; and
  ``balance_column.cpp:55``, ``:142``, ``:149``, at initialization only,
  never in a step.
* 4 of the 11 (``hydro.cpp:889``, ``:892``, ``:899``, ``:903``) are inside
  the commented block ``hydro.cpp:883-907``, so they are not live (note to
  X, question X4).
* 2 (``hydro.cpp:470``, ``:530``) are lane R's.

The per-stage path of lane C has no host read. ``grep`` of ``.item``/
``.cpu()`` in ``hydro_forward.cpp:383-1153`` and ``hydro.cpp:605-872``
finds none. Gate: X's replay under
``torch.cuda.set_sync_debug_mode('error')`` (X section 5).

**Allocations.** Revision 2 required every per-call temporary to become
fixed workspace. That is stricter than X, whose capturable ``Op`` may
allocate from the graph pool. Resolved by adopting X's rule:

* temporaries that live inside one segment stay graph-pool allocations;
  that covers most of the 45 allocating lines in
  ``hydro_forward.cpp:383-1153`` and the 9 in ``hydro.cpp:605-872``;
* fixed storage, allocated at ``reset()`` and part of
  ``StateStore::generation`` when its address can change, is required only
  for a tensor that crosses a segment boundary:

  * the x2/x3 ``FaceStates`` across the cubed-sphere exchange;
  * ``ReferenceFaces`` and the anchor across the relay and ghost-row
    exchange;
  * the primitive ``w`` across the conversion-order 4 ghost exchange
    (``hydro_w`` is lane R's buffer);
  * the register slots (lane R/X);
* the HLLC dtype rebinding is removed (section 6, item 2).

**Data-dependent host branches.** None on tensor values. Branches depend on
options, shapes, dtype and ``defined()``, which are fixed per ``GraphKey``.

**Cache rebuilds.** ``X1RowsCache`` and the ``X1Reference`` constructor
rebuild at ``reset()``, ``to()`` and restart, which are X's generation
events, or when ``x1f`` is rewritten. An ``x1f`` rewrite during a run must
bump X's ``config_generation`` (question X2). With a fixed grid nothing
rebuilds inside a step.

**Graph key.** Lane C ops read no ``dt``; gravity is a constant of the
configuration. They depend on the precision generation (dtype) and the
configuration generation (``x1f``, options), both already in ``GraphKey``.

**Boundaries lane C adds inside R's compute op.** X's segment list names
only ``hydro_forward.cpp:1017``, ``:1029`` and ``scalar.cpp:120-146``. It
does not list B1, B2, B3 or B5, so X's list understates
the boundaries. Lane C declares them here, and asks X to add them
(question X3):

.. list-table::
   :header-rows: 1

   * - boundary (pin)
     - when
     - X segment kind
     - G
   * - B1: conversion-order 4 ghost exchange and boundary functions
       (``hydro_forward.cpp:489-503``)
     - ``conversion-order: 4`` (no in-tree deck)
     - pack / host / unpack
     - G1 (key 4), G4
   * - B2: reference anchor relay (``hydro.cpp:636``, ``:712``), a serial
       chain down the x1 block column
     - x1 split (``pz > 1``)
     - host
     - G4
   * - B3: reference ghost-row exchange (``hydro.cpp:727-776``)
     - x1 split
     - pack / host / unpack
     - G4
   * - B4: cubed-sphere face-state exchange (``hydro_forward.cpp:1017-1048``)
     - cubed sphere
     - pack / host / unpack (in X's list; lane S)
     - G6
   * - B5: ``SNAP_X1_CENTROID_EXACT`` ghost rows (``:666``, ``:953``) and
       covariance seam rows (``:1059-1065``)
     - that switch, or covariance with an x1 split
     - pack / host / unpack
     - G4
   * - B6: x1 seam flux average (``:882-946``)
     - x1 split across processes
     - the register's exchange phase (X section 4; lane R/S)
     - G4

Each stays an eager boundary until lane S provides a capture-safe exchange,
as X section 7 does for every exchange. The single-block Cartesian key-2
path (G1) crosses none of them.

**G-milestone mapping** (X's milestones):

* **G1**: single-block dry and moist explicit. No lane C boundary at key 2;
  needs C2-C4 and the removal of the HLLC rebinding.
* **G2**: moist. The conversion's limiter-mark and vapor-failure restore
  must stay device-side; it already copies tensors,
  ``hydro_forward.cpp:470-480``.
* **G4**: multi-block. B1, B2, B3, B5 and B6.
* **G5**: FP32 cubed sphere. The split reference is Cartesian-only
  (``hydro.cpp:196-203``); lane C's part is extending ``ReferenceInput`` to
  panel seams.
* **G6**: B4 and the rotation.

8. Cross-repository interface changes and merge order
-----------------------------------------------------

**None.** Lane C changes no kintera, pyharp or commux interface. The EOS
calls (``W->I``, ``W->A``, ``WA->L``, ``W->L``) are snapy's
``EquationOfState`` and stay as they are.

**Merge order inside snapy:**

1. C1 and C2 first; they are independent.
2. Then C3 and C4.
3. C6; C7 after lane X's PR X1 (``PrecisionPolicy``), because C7 converts
   the ten moved ``fp32()`` sites (section 6).
4. C5 and C8 after lane R's register API, which they post into
   (provisional until R answers).
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
     - 1,069 (11 files kept)
   * - lane R ranges moved in (``hydro_forward.cpp:291-368``, ``:417-504``,
       ``:668-820``; ``hydro.cpp:605-872``)
     - 587
     - 0 (code now in new lane C files)
   * - 19 new lane C files
     - 0
     - 2,260
   * - **lane C**
     - **6,428**
     - **3,329**

Every solver and scheme of the pin is in these numbers (Cheng's decision).
The reduction comes only from structure:

* one kernel definition per scheme and per solver for CPU, CUDA and MPS.
  This deletes the 674 MPS-only lines (section 2.5) and the duplicate CPU and
  CUDA loops;
* one dispatch per family (``recon_dispatch``, ``riemann_fn``). This
  deletes ``recon_dispatch_nu.*`` and the four per-solver CPU dispatch files;
* one direction-generic sweep. It sits in lane R's file and is not counted
  here;
* one frame rotation, moved to coord: ``riemann_solver.cpp:12-47``, counted
  by lane S;
* one weight builder (``x1_rows``) and one reference evaluator
  (``X1Reference``).

By group, now to after: recon 2,233 to 1,275; riemann 2,089 to 980; the 10
reference files plus their new files 1,519 to 1,074. The moved-in lines'
new home is inside those "after" numbers.

**Against the ceiling.** The lane ceiling is 4,672 (20% below 5,841). The
estimate is 3,329: 1,343 lines under the ceiling, -43.0% against the 5,841
baseline, -48.2% against baseline plus moved-in lines (6,428). Two variants
were checked against it:

* if MPS keeps on-device torch formulas instead of host copies (``FOR
  CHENG``, section 3.8), one tensor-scalar instantiation of the same point
  functions adds about 90 lines (estimate): 3,419;
* if the rotation stays in lane C (lane S declines it), add 36: 3,365;
* if PR #369 merges and its CPU parity test keeps the tensor MPS reference
  (section 3.5), add 175: 3,504.

All three stay under 4,672. If #369 merges first, its rewrite of the moved
ranges changes their measured lengths. ``C_lines.py`` then needs the new
base and ranges, and the numbers here are re-measured.

**Split with lane R: provisional until lane R's owner confirms it.** The
proposal is that the 587 moved lines count once:

* in lane R's table as deletions from ``hydro.cpp`` and
  ``hydro_forward.cpp``, with "after" 0 for those ranges;
* in lane C's table only in the "after" of the new files (as here).

A message in the home thread accepted this split and said lane R's deleted
ranges would be compared with ``C_lines.csv`` once lane R's table exists.
No lane R table or design is published (section 1), so the R side is not
verified and stays provisional (question R6). The call sites left in lane
R's files are lane R's lines.

File by file:

.. csv-table::
   :header: "file", "now (measured)", "after (estimate)", "fate"
   :widths: 34, 10, 10, 46

   "src/recon/cp3.cpp", 53, 0, "merged: table -> x1_rows.cpp, calls -> reconstruct.cpp"
   "src/recon/cp5.cpp", 60, 0, "merged: table -> x1_rows.cpp, calls -> reconstruct.cpp"
   "src/recon/interp_impl.cuh", 193, 0, "merged -> recon_line.cuh (Op wrappers, interp_nu_untiled deleted)"
   "src/recon/interp_impl.h", 49, 0, "deleted: line loops are the CPU loop in recon_dispatch.cpp"
   "src/recon/interp_point.h", 124, 0, "renamed -> recon_point.h (all point functions kept)"
   "src/recon/interpolation.cpp", 42, 0, "deleted: factory -> Scheme parse in reconstruct.cpp"
   "src/recon/interpolation.hpp", 288, 0, "deleted: 7 Interp classes -> Scheme + ReconRows"
   "src/recon/plm.cpp", 33, 0, "merged -> reconstruct.cpp (torch ops kept)"
   "src/recon/ppm.cpp", 18, 0, "merged -> reconstruct.cpp (ppm kept; not implemented at the pin, as today)"
   "src/recon/recon_dispatch.cpp", 179, 70, "MPS rewrites :83-158 deleted (OnHost); one stub"
   "src/recon/recon_dispatch.cu", 106, 70, "one launcher for uniform and per-face rows"
   "src/recon/recon_dispatch.hpp", 20, 15, "one dispatch stub"
   "src/recon/recon_dispatch_nu.cpp", 115, 0, "deleted: second path"
   "src/recon/recon_dispatch_nu.cu", 91, 0, "deleted: second path"
   "src/recon/recon_dispatch_nu.hpp", 17, 0, "deleted: second path"
   "src/recon/recon_launch.cuh", 98, 0, "merged -> recon_line.cuh"
   "src/recon/reconstruct.cpp", 181, 165, "dead block :118-141 and floors removed; plm, ppm stub, Scheme parse and group table added"
   "src/recon/reconstruct.hpp", 103, 60, "dead options is_boundary_*, limiter removed"
   "src/recon/weno3.cpp", 58, 0, "merged: table -> x1_rows.cpp, calls -> reconstruct.cpp"
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
   "src/riemann/plume_roe.cpp", 104, 45, "kept as tensor code; writes its slot; unused Roe averages, Jacobian and polynomial (:57-92) dropped"
   "src/riemann/riemann_dispatch.cu", 125, 65, "one CUDA loop switching on kind (hllc, lmars, roe, shallow-roe)"
   "src/riemann/riemann_dispatch.hpp", 25, 0, "merged -> riemann.hpp"
   "src/riemann/riemann_solver.cpp", 113, 0, "-> riemann.cpp (incl. upwind); rotation :12-47 -> coord (lane S)"
   "src/riemann/riemann_solver.hpp", 245, 0, "-> riemann.hpp; 6 classes -> 1"
   "src/riemann/roe.cpp", 69, 0, "merged -> riemann.cpp (ideal-moist params in RiemannParams)"
   "src/riemann/roe_dispatch.cpp", 229, 0, "CPU loop -> riemann_dispatch.cpp; MPS :50-219 deleted"
   "src/riemann/roe_impl.h", 218, 0, "moved -> riemann_kernels.h"
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
   "src/recon/recon_point.h", 0, 125, "new lane C file"
   "src/recon/recon_line.cuh", 0, 165, "new lane C file"
   "src/recon/x1_rows.hpp", 0, 45, "new lane C file"
   "src/recon/x1_rows.cpp", 0, 260, "new lane C file"
   "src/recon/conversion.hpp", 0, 30, "new lane C file"
   "src/recon/conversion.cpp", 0, 100, "new lane C file"
   "src/recon/well_balanced_x1.hpp", 0, 20, "new lane C file"
   "src/recon/well_balanced_x1.cpp", 0, 100, "new lane C file"
   "src/recon/face_floor.hpp", 0, 25, "new lane C file"
   "src/recon/face_floor.cpp", 0, 25, "new lane C file"
   "src/riemann/riemann.hpp", 0, 110, "new lane C file"
   "src/riemann/riemann.cpp", 0, 175, "new lane C file"
   "src/riemann/riemann_kernels.h", 0, 525, "new lane C file"
   "src/riemann/riemann_dispatch.cpp", 0, 60, "new lane C file"
   "src/hydro/x1_reference.hpp", 0, 70, "new lane C file"
   "src/hydro/x1_reference.cpp", 0, 230, "new lane C file"
   "src/hydro/x1_reference_dispatch.hpp", 0, 35, "new lane C file"
   "src/hydro/x1_reference_dispatch.cpp", 0, 65, "new lane C file"
   "src/hydro/x1_reference_dispatch.cu", 0, 95, "new lane C file"
   "TOTAL baseline files", 5841, 1069, ""
   "TOTAL moved in from lane R", 587, 0, ""
   "TOTAL new files", 0, 2260, ""
   "TOTAL lane C", 6428, 3329, "-43.0% vs baseline; -48.2% vs baseline+moved"

10. Migration
-------------

.. list-table::
   :header-rows: 1

   * - PR
     - content
     - class and why
   * - C1
     - dead code only: the commented blocks (``reconstruct.cpp:118-141``,
       ``hydro_forward.cpp:630-633``), ``_revise_x1*_ghost``
       (``hydro.cpp:565-603``), the unread ``ReconstructOptions`` fields
       ``is_boundary_lower``, ``is_boundary_upper`` and ``limiter``, and
       plume-roe's unused Roe averages and Jacobian (``plume_roe.cpp:57-92``)
     - bitwise: nothing removed is executed or read
   * - C2
     - MPS through ``OnHost`` for recon, Riemann (hllc, lmars, roe,
       shallow-roe), reference
     - CPU/CUDA bitwise (untouched); MPS changes to the CPU float32 result
       (FOR CHENG)
   * - C3
     - ``Scheme`` + tables for all six schemes (and dc), one dispatch stub,
       one CUDA line kernel
     - bitwise: same point functions, same order; ppm still throws
   * - C4
     - one ``RiemannSolver`` for all six kinds, one EOS pass, one CPU and
       one CUDA loop; upwind and plume-roe keep their torch formulas
     - bitwise: per-kind EOS order kept
   * - C5
     - post into the register (after lane R's API); ``FaceFloor``;
       in-kernel ``riemann.central``; plume-roe writes its slot;
       upwind/plume-roe refused at ``reset()`` where they cannot solve
       (FOR CHENG)
     - bitwise except AAM full (round-off, expected; no deck; lane A gate
       H1)
   * - C6
     - ``x1_rows``, ``Conversion`` shared with ``balance_column``
     - key 2 bitwise; key 4 to round-off (expected; weights rebuilt in
       another arithmetic order; no deck)
   * - C7
     - ``X1Reference`` + ``X1ColumnLink``; ``WellBalancedX1``; the ten moved
       ``fp32()`` sites become ``PrecisionPolicy`` calls
     - bitwise: code move; the policy returns the same dtypes
   * - C8
     - ``reconstruct_faces`` / ``solve_faces``
     - bitwise: code move
   * - C9
     - FP32 typed constants; uniform rows read ``d``
     - FP64 bitwise; FP32 re-baselined against FP64 (no deck runs FP32)
   * - C10
     - the ``shock`` default and shock-path floors, if Cheng accepts them
     - deck results change where floors fire

**Options removed: none.** Every ``riemann-solver`` type, every
``reconstruct`` type and every YAML key of the pin stays. The removals are
code paths and unread fields:

* the MPS rewrites (replaced by ``OnHost``, FOR CHENG) and
  ``hydro_pressure_scan_x1_tensor``;
* ``recon_dispatch_nu.*`` (one dispatch with per-face rows);
* the unread ``ReconstructOptions`` fields and the commented code (C1);
* the Python per-solver modules, only if Cheng accepts one
  ``RiemannSolver`` binding (FOR CHENG).

11. Open questions to other lanes
---------------------------------

**Lane R (Linfeng).** R1-R4 are open. The lane C items they govern are
provisional (section 4):

* R1: the register API ``solve_faces`` writes into: slot views per
  (increment, direction, stage)? Is the name ``riemann`` acceptable?
* R2: the accumulation dtype in FP32 runs? X (``Quantity::kRegister``) and
  lane O both assume FP64.
* R3: the declared increment order, the ``(theta - 1) F`` rule for
  positivity, and named parts: can ``riemann`` carry ``riemann.central``
  (one stored summed mass row) and ``riemann.dissipative`` (derived)? This is also
  lane A's R-1. Field or integral?
* R4: will the monitor hold the ``FaceFloor`` counters and
  ``FaceFlux::events``, and who resets them on a redo? X section 4 resets
  registers at stage 0 and on rollback.
* R5: who owns the x1 seam reconciliation?
* R6: the 587-line split of section 9. It was accepted in the home thread
  but is provisional until lane R's own table shows the same ranges as
  deletions.
* R7: lane R's header and numbered review notes on lane C were not
  available to this revision. Lane C will align names and dtypes to them
  only once they are published.

**PR #369 (Xi, open at ``c382f0da``):** if it merges before C2/C7:

* is the upward reference mode carried into ``X1ReferenceConfig``?
* does its CPU parity test keep ``hydro_ref_x1_mps``, or compare
  ``OnHost`` against the kernel instead? This is a question for the PR's
  author and Cheng (section 3.5).

**Lane S (Jiheng):**

* S1: ``X1ColumnLink`` (anchor relay, ghost rows) and a capture-safe form.
* S2: ``to_face_frame_`` and ``to_global_frame_`` in coord; in-kernel 3x3 or
  tensor passes.
* S3: the cubed-sphere face-state exchange between ``reconstruct_faces`` and
  ``solve_faces``.
* S4: at the pin, x2/x3 panel-seam faces are single-valued only through
  the exchanged face states (section 4). Will S add a panel-seam flux
  reconciliation? If so, it covers ``riemann.central`` too.

**Lane A (from ``A.rst`` at ``2c9589c6``):**

* Lane C provides ``riemann.central`` as one summed mass row (dry plus
  species), x2/x3, formed from the solver's face states, in ``kFlux``, valid
  through the stage end (section 4). ``F_d`` is the total registered flux
  minus it. A1: confirm that one summed row is enough; the pin's consumer
  sums the rows (``gnomonic_equiangle.cpp:690-694``).
* Under perturbation-flux the face densities are totals (section 3.6).
* Lane A's C-1 asks who posts the implicit x1 mass transfer and the
  tangential momentum correction (``hydro_forward.cpp:1645-1646``,
  ``:1668-1669``). Not lane C: lane C posts only ``riemann`` and its parts.
  These are lane I's (implicit) and the register's (R).
* A2: upwind and plume-roe give no ``riemann.central`` for hydro mass
  rows. Is a ``reset()`` refusal of AAM modes with those solvers right?

**Lane O (Jiachen):** the display of the floor counts and solver events.

**Lane I (Xinyue):**

* ``src/implicit`` reads no lane C output at the pin (no ``grep`` match for
  the face pressure, the reference or the solver). Does V3 keep it that way?
* I-C1: gravity work reads the total and the Riemann-only summed x1 mass
  rows from the register, in ``kFlux``, and casts them to FP64 on read
  (section 4). Is cast-on-read enough, or does lane I want a stored FP64
  row?

**Lane X (Xi):**

* X1: face states (reconstruction output, Riemann input) have no
  ``Quantity`` row. Is ``kFlux`` right, or should X add a row?
* X2: does an ``x1f`` rewrite during a run bump ``config_generation``
  (section 7, cache rebuilds)?
* X3: add lane C's boundaries B1, B2, B3 and B5 (section 7) to X's segment
  list, which names only ``hydro_forward.cpp:1017``, ``:1029`` and
  ``scalar.cpp:120-146``.
* X4: 4 of X's 11 ``hydro`` ``.item<`` lines (``hydro.cpp:889-903``) are
  inside a comment block (``:883-907``); X's count of live sites is 7.
* X5: are the eager boundaries acceptable for G4/G6 until lane S makes them
  capture-safe?

**Cheng:** the ``FOR CHENG`` rows of section 3.8.

12. Skeleton index
------------------

``docs/v3/skeleton/C/``: declarations and comments only, 293 lines
(``wc -l``). It is outside ``src/``, so no CMake glob, Doxygen input or
clang-format hook reads it.

.. list-table::
   :header-rows: 1

   * - file
     - lines
     - declares
   * - ``recon_point.h``
     - 34
     - ``Scheme`` (dc, plm, ppm, cp3, weno3, cp5, weno5), ``SchemeTraits``,
       ``poly_point``, ``weno3_point``, ``weno5_point``, ``recon_point``
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
     - 54
     - ``ReferenceInput``, ``ReferenceFaces``, ``X1ColumnLink``,
       ``X1ReferenceConfig``, ``X1Reference``
   * - ``riemann.hpp``
     - 70
     - ``RiemannKind`` (all six), ``RiemannSolverOptionsImpl``, ``FaceFlux``
       (with the ``central`` part),
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
* the ``riemann.central`` sizes, from the deck's ``cells`` and ``species``.
