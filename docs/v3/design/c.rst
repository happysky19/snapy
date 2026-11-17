:orphan:

V3 lane C: reconstruction, Riemann solvers, well-balanced reference, conversion order
=====================================================================================

Revision 1, 2026-11-17. Owner: Tianhao Le (alternate: Xinyue). Design only:
no implementation change is proposed in this branch. Declarations are in
``docs/v3/skeleton/c/`` (not built).

Every ``path:line`` below is at chengcli/snapy
``9e5de2d4ce497d0b2d4da3295fc1fe969fe7e410`` (main, "FP32 step5 validation
(#368)") unless another commit is named. Line counts are ``wc -l`` at that
commit. Numbers marked *estimate* are design targets, not measurements.

1. Scope, pin and evidence
--------------------------

Lane C covers the face side of the hydro step: cell-average to primitive
conversion (orders 2 and 4), the key-4 wall fills, the well-balanced x1
reference and ``balance_column``, reconstruction, the Riemann solvers and the
face floors. It does not cover the implicit solve (lane I), angular momentum
(lane A), geometry and frames (lane S), or diagnostics (lane EF). Where those
lanes consume a lane-C output, the interface is stated here and listed as an
open question in section 12.

Read for this revision: the 50 baseline files below; ``hydro_forward.cpp``
lines 383-615, 616-987 and 1050-1153; ``hydro.cpp:605-872``
(``_hydro_ref_x1``, which the brief does not list but which the reference
interface cannot be designed without); ``V3_ROADMAP.md``; PR bodies of #334,
#335, #336, #339, #340, #341, #346, #347, #349, #354, #359, #360 and #362
(fetched read-only with ``gh pr view``).

Not available to this revision: Xinyue's inventory document at ``919936da``
was not in the workspace, so its count of 77 sites could not be checked. The
specific inventory claims quoted in the lane request are rechecked in
section 2. The shared brief's list of the twelve required sections was also
not in the workspace; the twelve sections here follow the lane request's
questions 1-8 and "decide and justify" items, and are mapped in section 12.

2. Baseline and inventory recheck at the pin
--------------------------------------------

Baseline, measured with ``wc -l`` at the pin (it matches the lane request's
5,841):

.. list-table::
   :header-rows: 1

   * - group
     - files
     - lines
   * - ``src/recon``
     - 23
     - 2,233
   * - ``src/riemann``
     - 17
     - 2,089
   * - ``hydro_ref_x1_impl.h``, ``hydro_reference.hpp``, ``wb_ref4.*``,
       ``balance_column.*``, ``split_reference_scalar.hpp``,
       ``hydro_dispatch.*``
     - 10
     - 1,519
   * - total
     - 50
     - 5,841

Recheck of the inventory claims (inventory taken at ``919936da`` = #339;
#347, #349, #352 and #354 have landed since):

.. list-table::
   :header-rows: 1

   * - claim at 919936da
     - at the pin
   * - WENO5 written at 5 library sites
     - Two formula sites remain: the shared CPU/CUDA point function
       ``src/recon/interp_point.h:71-120`` (uniform and per-face through the
       ``Nu`` flag, #347 commit 717ec3f, #349 commit 231dc22) and the MPS
       rewrite ``src/recon/recon_dispatch.cpp:117-158``. Coefficient tables
       are built twice: ``src/recon/weno5.cpp:12-25`` (uniform) and
       ``src/recon/x1_coeffs.cpp:59-120`` (per face). The test reference moved
       to ``tests/interp_simple.hpp`` (#349).
   * - face-local rotation written 6 times
     - Solvers share one helper, ``src/riemann/riemann_solver.cpp:12-47``
       (#349 commit f83c720). Three hand-written copies of the same switch
       remain in the covariance code, ``src/hydro/hydro_forward.cpp:93-97``,
       ``:212-216`` and ``:257-261``, and one diagnostic block in
       ``src/output/load_diag_output_data.cpp:175-187``.
   * - MPS HLLC wrong with species
     - Fixed by #354 (commit 464e4a8): ``src/riemann/hllc_dispatch.cpp:135-139``
       carries the dry fraction and species. A residual divergence remains:
       MPS is always float32, but the MPS rewrite uses the FP64 contact
       arithmetic (``hllc_dispatch.cpp:112``) while the CPU float kernel uses
       ``cl * ql`` (``src/riemann/hllc_impl.h:76-84``). MPS HLLC is a second
       formula.
   * - C++ and YAML Riemann defaults disagree
     - Fixed by #352 (commit f32912d): both are hllc,
       ``src/riemann/riemann_solver.hpp:33`` and
       ``src/riemann/riemann_solver.cpp:67``. A reconstruction default still
       disagrees: ``shock`` is ``true`` in ``ReconstructOptionsImpl``
       (``src/recon/reconstruct.hpp:49``) but ``false`` from YAML when a
       ``reconstruct`` section omits it (``src/recon/reconstruct.cpp:33``,
       ``src/scalar/scalar_options.cpp:37``).

New findings at the pin, relevant to the decisions below:

* ``plume-roe`` ignores its output buffer: ``PlumeRoeSolverImpl::forward``
  (``src/riemann/plume_roe.cpp:45-102``) returns a fresh Lax-Friedrichs flux
  and never writes ``flx``, and the Jacobian and characteristic polynomial it
  computes (``:81-92``) are unused.
* ``ppm`` throws on every call (``src/recon/ppm.cpp:14``).
* ``ReconstructOptions`` ``is_boundary_lower``, ``is_boundary_upper`` and
  ``limiter`` (``src/recon/reconstruct.hpp:47-50``) are read only inside the
  commented-out block ``src/recon/reconstruct.cpp:118-141``.
* ``HydroImpl::_revise_x1inner_ghost`` / ``_revise_x1outer_ghost``
  (``src/hydro/hydro.cpp:565-603``) are called only from commented-out code,
  ``src/hydro/hydro_forward.cpp:630-633``.
* The FP32 instantiation of the shared WENO point functions runs FP64
  arithmetic: the constants ``13. / 12.``, ``.25``, ``1e-6``, ``.3/.6/.1``
  and ``2.0 / 3.0`` are ``double`` (``src/recon/interp_point.h:61-62``,
  ``:99-104``, ``:109-115``). Measured by compiling ``interp_point.h`` with
  ``g++ -O2 -std=c++17`` (GCC 11.5.0, x86-64, the repository's Release flags
  have no ``-march``): ``snap::weno5_point<float, false>`` contains 6
  ``addsd``, 3 ``divsd``, 9 ``mulsd``, 9 ``cvtss2sd`` and 6 ``cvtsd2ss``.
  Against the same expression with constants typed ``T``, 363,162 of
  1,000,000 random faces (stencil values uniform in [0.5, 1.5]) differ.
  ``lmars_impl`` has the same pattern by reading
  (``src/riemann/lmars_impl.h:28-43``, ``auto rhobar = 0.5 * (...)`` is
  ``double``); it was not compiled. That these FP64 instructions cost real
  time on GPUs with a low FP64 rate is a hypothesis: no timing was run.
* MPS-only rewrites total 674 lines (function bodies, measured):
  ``recon_dispatch.cpp:83-158``, ``recon_dispatch_nu.cpp:90-100``,
  ``hllc_dispatch.cpp:50-164``, ``lmars_dispatch.cpp:44-102``,
  ``roe_dispatch.cpp:50-219``, ``shallow_roe_dispatch.cpp:33-81``,
  ``hydro_dispatch.cpp:33-54`` and ``:101-275``. The MPS reference
  (``hydro_ref_x1_mps``) uses ``torch::cumsum`` (``hydro_dispatch.cpp:116``)
  instead of the scan recurrence, and refuses stretched x1 (``:108-110``).

3. Where the duplication is today
---------------------------------

* **Seven interpolation classes** (``src/recon/interpolation.hpp:37-285``)
  wrap four point functions. The factory maps ``weno5`` to WENO5 for the
  density/species group and to cp5 for velocity/pressure by the last character
  of the module name (``src/recon/interpolation.cpp:21-36``).
* **Two dispatch paths** for uniform and per-face rows:
  ``recon_dispatch.{hpp,cpp,cu}`` (305 lines) and
  ``recon_dispatch_nu.{hpp,cpp,cu}`` (223 lines), plus two CUDA launch
  shapes and two tiled kernels selected by ``Nu`` in
  ``src/recon/interp_impl.cuh:83-188``.
* **Six Riemann classes** with five ``forward`` wrappers that each compute
  EOS face inputs, rotate, build an iterator and dispatch
  (``hllc.cpp:44-113``, ``lmars.cpp:30-76``, ``roe.cpp:16-67``,
  ``shallow_roe.cpp:26-57``); four CPU loops and four CUDA loops that differ
  only in the kernel called (``*_dispatch.cpp``, ``riemann_dispatch.cu:17-115``).
* **x1 weights built in five places**: per-face recon rows
  (``x1_coeffs.cpp:10-31``, ``primitive_row``), the wb_ref4 face density
  (``wb_ref4.cpp:26-39`` and ``:77-94``, ``lagrange_deriv``, the same
  primitive-derivative formula), conversion-order 4 ``L``
  (``hydro_forward.cpp:293-304``) and its copy in ``balance_column``
  (``balance_column.cpp:69-86``), the key-4 wall ghosts
  (``hydro_forward.cpp:312-339``), and the stretched six-face reference rows
  (``hydro_dispatch.cpp:277-312``). Each has its own staleness test
  (``hydro_forward.cpp:425-432``, ``hydro.cpp:695``, ``:793-794``,
  ``wb_ref4.hpp:30-33``).
* **Conversion order 4 twice**: the solver's stage
  (``hydro_forward.cpp:417-504``) and ``balance_column``'s pass
  (``balance_column.cpp:57-118``), which re-pads, re-weights and re-fills.
* **The reference in two shapes**: ``HydroReferenceX1Operator``
  (``hydro_reference.hpp:31-155``) evaluates; ``HydroImpl::_hydro_ref_x1``
  (``hydro.cpp:605-872``) adds anchor relay, the ghost-row seam exchange, the
  wb_ref4 faces and the per-side face density; ``balance_column`` uses only
  the first.
* **x2 and x3 face flux written twice**: ``hydro_forward.cpp:1088-1119`` and
  ``:1121-1152`` (identical apart from the direction, the seam tags and the
  buffers), and the x2/x3 reconstruction blocks ``:1010-1031``.
* **Face floors in five places** (section 10).

4. Target structure
-------------------

.. list-table::
   :header-rows: 1

   * - target file (lane C)
     - replaces
   * - ``recon/recon_point.h``
     - ``interp_point.h``, ``interp_impl.h``, the per-scheme classes
   * - ``recon/x1_rows.{hpp,cpp}``
     - ``x1_coeffs.*``, ``wb_ref4_stencils``, ``wall4_weights``,
       ``conv4_x1_weights``, ``hydro_ref_x1_stretched_rows``,
       ``balance_column``'s lap weights
   * - ``recon/recon_line.cuh``
     - ``interp_impl.cuh``, ``recon_launch.cuh``
   * - ``recon/recon_dispatch.{hpp,cpp,cu}``
     - ``recon_dispatch*.{hpp,cpp,cu}`` (both paths), all recon MPS code
   * - ``recon/reconstruct.{hpp,cpp}``
     - ``reconstruct.*``, ``interpolation.*``, ``cp3/cp5/weno3/weno5/plm/ppm.cpp``
   * - ``recon/conversion.{hpp,cpp}``
     - ``hydro_forward.cpp:291-368`` and ``:417-504``; ``balance_column``'s
       order-4 machinery
   * - ``recon/well_balanced_x1.{hpp,cpp}``
     - ``hydro_forward.cpp:668-820``
   * - ``recon/face_floor.{hpp,cpp}``
     - the five floor sites (section 10)
   * - ``riemann/riemann.{hpp,cpp}``
     - ``riemann_solver.*``, ``hllc.cpp``, ``lmars.cpp``, ``roe.cpp``,
       ``shallow_roe.cpp``, ``plume_roe.cpp``, ``riemann_dispatch.hpp``
   * - ``riemann/riemann_kernels.h``
     - ``hllc_impl.h``, ``lmars_impl.h``, ``roe_impl.h``, ``shallow_roe_impl.h``
   * - ``riemann/riemann_dispatch.{cpp,cu}``
     - ``*_dispatch.cpp`` (4), ``riemann_dispatch.cu``
   * - ``hydro/x1_reference.{hpp,cpp}``
     - ``hydro_reference.hpp``, ``hydro.cpp:605-872``, ``wb_ref4.{hpp,cpp}``
   * - ``hydro/x1_reference_dispatch.{hpp,cpp,cu}``
     - ``hydro_dispatch.{hpp,cpp,cu}``
   * - unchanged
     - ``hydro_ref_x1_impl.h``, ``split_reference_scalar.hpp``,
       ``balance_column.{hpp,cpp}`` (shrinks)

Declarations: ``docs/v3/skeleton/c/{recon_point.h, x1_rows.hpp,
reconstruct.hpp, x1_reference.hpp, riemann.hpp, sweep.hpp}``.

5. One kernel per scheme; one x1 path (questions 1 and 2)
---------------------------------------------------------

**How.** Each nonlinear or polynomial scheme (cp3, weno3, cp5, weno5) is one
``DISPATCH_MACRO`` point function in ``recon_point.h``, reached through one
template ``recon_point<Scheme, T>``. The CPU line loop and the CUDA line
kernel are written once over ``Scheme``. dc (a copy) and plm (torch ops,
``src/recon/plm.cpp:19-29``) stay tensor code: torch ops are already one
definition on every backend, and plm is the scheme the inventory found
bitwise between CPU and CUDA (not re-measured here), which a fused CUDA body
would lose. ppm is
removed.

**MPS.** MPS registers the CPU kernel through ``OnHost<cpu_fn>``
(``src/utils/on_host.hpp:61-70``, added by #354 for VIC, ``flip_zero`` and
``fix_vapor``). The four recon rewrites, the two stretched-x1 refusal stubs,
the four Riemann rewrites and the reference rewrite (674 lines, section 2)
are deleted. MPS then computes exactly the CPU float32 result, runs stretched
x1 (refused today, ``recon_dispatch_nu.cpp:90-100``,
``hydro_dispatch.cpp:108-110``) and stops being a source of formula drift
(the residual HLLC difference in section 2). Cost: a host copy of each
storage per call (``on_host.hpp:15-19``), which lowers MPS throughput.
``FOR CHENG``: MPS is a correctness target here, not a performance target.

**What remains.**

* ``recon_dispatch.{hpp,cpp,cu}``: one dispatch stub
  ``call_recon(iter, rows, scheme, dim, scale)``; the CPU loop
  (``recon_dispatch.cpp:16-40`` today) instantiated per scheme; one CUDA
  launcher (``recon_dispatch.cu:23-79`` today) with the one-block, split and
  tiled paths. ``recon_dispatch_nu.*`` is deleted.
* ``interp_impl.h`` is deleted (the line functions are one-line loops over
  the point function). ``interp_impl.cuh`` and ``recon_launch.cuh`` merge into
  ``recon_line.cuh``: one block kernel and one tiled kernel; the ``Weno3Op``,
  ``Weno5Op``, ``Weno5NuOp``, ``PolyOp`` wrappers and ``interp_nu_untiled``
  (``interp_impl.cuh:18-138``) become one ``Op<Scheme>``.
* The MPS rewrites: none.

**Uniform and non-uniform x1: one path.** A ``ReconRows`` table carries
``row_stride``: ``ncoeff`` for per-face rows, ``0`` for a uniform grid (one
row broadcast). The kernel always reads its row at ``coeff + face *
row_stride``; on CUDA a zero stride keeps the shared-memory load of the one
row (``interp_impl.cuh:100-109``). The per-face rows are needed anyway on
every radial grid (``src/coord/coordinate.cpp:546-562`` returns volume
coordinates for spherical-polar and gnomonic weno5/cp5 whatever the widths)
and on every stretched x1. There is no reason for two dispatch paths.

Bitwise consequence, by reading: the uniform WENO5 path uses the literal
linear weights ``.3, .6, .1`` (``interp_point.h:113-115``), the per-face path
reads ``d`` from the row (``:108-111``). Moving the uniform weights into the
table is bitwise in FP64 (the table holds the same doubles) but not in FP32
(``0.3f`` is not ``0.3``). This step therefore lands with the FP32
typed-constant change (PR C9, section 11), which re-baselines FP32 once.

Schemes without per-face rows (dc, plm, cp3, weno3) keep today's refusal on
a stretched x1 (``src/recon/interpolation.hpp:62-71``).

6. Conversion order, wall fills and balance_column (question 3)
---------------------------------------------------------------

Conversion is the first stage of reconstruction: it produces the primitive
cell values the reconstruction reads. It moves into ``recon/conversion``
as one ``Conversion`` object used by the solver and by ``balance_column``:

* order 2 is the identity after ``peos->forward`` (``hydro_forward.cpp:386``);
* order 4 is ``w = W(u - L u) + L W(u)`` with the per-cell admissibility
  fallback, limiter-mark and vapor-failure restore, trip counter and ghost
  rebuild (``hydro_forward.cpp:417-504``);
* the key-4 wall ghosts are ``Conversion::fill_walls`` (``wall4_fill``,
  ``hydro_forward.cpp:341-358``), used for the conversion averages
  (``:458-463``) and for the WB perturbations (``:724-726``, ``:755-758``).

**One definition of the weights.** Every x1 weight is built in
``recon/x1_rows`` from ``x1f`` in double on the host, once per grid version,
then moved to the device and dtype by one cache (``X1RowsCache``, key:
``x1f`` identity, ``_version()``, device, dtype). The reconstruction rows
(``x1_coeffs.cpp:10-31``) and the wb_ref4 face density
(``wb_ref4.cpp:26-39``, ``:77-94``) are the same formula, the value at a
point of the derivative of the primitive interpolant, and become one
``face_value_row``. ``balance_column`` stops re-deriving ``L``
(``balance_column.cpp:69-86``) and calls ``conv4_rows`` and
``Conversion::fill_walls`` on its padded column.

``balance_column`` keeps its contract (``balance_column.hpp:14-127``): it is
the initialization client of ``Conversion`` and of ``X1Reference``
(section 7) with no column link. The C++ entry point and its Python binding
are unchanged.

Bitwise consequence: key-2 decks never enter this code. At key 4 the face
density rows come from a different arithmetic order than ``lagrange_deriv``,
so their weights can differ in the last bit; key-4 decks are then expected
to agree to round-off, not bitwise (PR C6; not measured). ``balance_column`` at order 4 and the solver
then use bit-identical weights, which they do not today.

7. The reference interface (question 4)
---------------------------------------

One evaluator, ``X1Reference`` (``docs/v3/skeleton/c/x1_reference.hpp``):

* **Input**: ``ReferenceInput{base, delta}``. ``delta`` undefined selects the
  total path (the ``T`` kernel). Defined, it selects the split path (the
  ``SRS`` kernel, ``split_reference_scalar.hpp``): ``base`` is the FP64
  background (``pressure0``, ``density0`` of the anomaly store), ``delta``
  the perturbation. Every branch decision (anchor, floors, the six-face guard,
  wall continuation) reads the FP64 total and the arithmetic keeps the
  increment, as M3b requires (``V3_ROADMAP.md:459-464``). This is what
  ``evaluate_split`` does today (``hydro_reference.hpp:102-128``), kept.
* **Output**: ``ReferenceFaces`` with the totals (``psf_lo, psf_hi, pref,
  dref, dsf_lr``) and, on the split path, ``face0, face_delta, cell0,
  cell_delta, gauge`` (today ``HydroPressureSplit``, filled at
  ``hydro.cpp:667-674``).
* **Seams**: a ``X1ColumnLink`` interface (implemented by the layout, lane O)
  carries the anchor relay (``hydro.cpp:630-641``, ``:704-713``) and the
  ghost-row exchange (``:727-776``). ``nullptr`` means a single column:
  ``balance_column``, IC builders and ``nb1 = 1``. The evaluation order stays
  kernel, anchor relay, wb_ref4 flag, ghost-row exchange, wb_ref4 faces,
  per-side face density (``hydro.cpp:647-869``), so split columns still get
  one block's faces.
* **Initialization and runtime use the same object.** ``balance_column``
  builds an ``X1Reference`` with the solver's ``X1ReferenceConfig`` and no
  link; the runtime builds it with the block's link. The grid classification
  (uniform, legacy non-uniform, stretched) is made by the constructor as
  today (``hydro_reference.hpp:46-49``); the comment at
  ``balance_column.hpp:76-84`` about per-block classification stays a caller
  obligation.
* **MPS** runs the CPU kernel through ``OnHost`` (section 5); the split path
  stays refused on MPS (no FP64).

The reference kernel ``hydro_ref_x1_impl.h`` is not changed. Its
CPU/CUDA results can differ at round-off (``exp``, ``log``, ``pow`` in the
anchor and wall continuation, ``:74``, ``:89-94``), which is the existing
state.

8. One direction-generic sweep (question 5)
-------------------------------------------

``sweep(hydro, FaceDir, w, other)`` (``docs/v3/skeleton/c/sweep.hpp``)
replaces the x2 and x3 blocks (``hydro_forward.cpp:1088-1119``,
``:1121-1152``) and the x2/x3 reconstruction blocks (``:1010-1031``).
``FaceDir`` holds what differs: the dimension, the register slot, the seam
tag (``0x7730``/``0x7734``), the disable flag, the flux buffer and the split
background. The order inside a sweep is the order of today's code:
reconstruct, [x1: ``WellBalancedX1``], face floors, immersed solid
(``pib->forward``), covariance (x2/x3), Riemann, register.

The cubed-sphere face-state exchange (``:1013-1048``) stays between
reconstruction and solve; it begins x2 and x3 exchanges before either
completes, so ``sweep`` is split into ``reconstruct_faces(dir)`` and
``solve_faces(dir)`` with the exchange between them. x1 keeps its own
post-solve steps (sedimentation, seam flux average ``:861-946``, pressure
source ``:948-985``); they are not lane C's and stay in ``hydro_forward``.

Bitwise: this is a code move with the same calls in the same order, CPU and
CUDA bitwise in FP64 and FP32 (PR C8).

9. Riemann: output contract, frame and solver set (questions 6 and 7)
---------------------------------------------------------------------

**Output contract to the register** (``FaceFlux``, skeleton
``riemann.hpp``):

* ``flux``: the conserved flux, global frame (today's ``flx``).
* ``pressure``: the **total** face pressure p*. On the split path the kernel
  returns the perturbation and the sweep adds the background in one place, as
  today (``hydro_forward.cpp:568-570``); no consumer sees a perturbation.
  Undefined for shallow water (``:842-844``).
* ``mass_central``: rows IDN and ICY.. of ``1/2 (F(w_L) + F(w_R))``, written
  by the kernel from the face states it already holds. The dissipative mass
  flux for lane A is ``flux[mass rows] - mass_central``. Today
  ``conserve-axial-momentum: full`` gets it by two extra full solves per
  horizontal direction (``hydro_forward.cpp:997-1003``, ``:1108``,
  ``:1141``) and keeps all rows (``:1356-1361``); the in-kernel value removes
  four solves per stage and is expected to agree to round-off, not bitwise
  (PR C5; not measured).
* ``wave_speed``: ``max |S|`` at the face (HLLC ``max(-b_m, b_p)``, LMARS
  ``|u*| + c``, Roe ``max(|lambda_-|, |lambda_+|)``), optional.
* ``events``: per-face bits for the solver's own floors (HLLC p* clamped at
  0 or at ``-p0``, ``hllc_impl.h:96-97``; Roe LLF fallback,
  ``roe_impl.h:145-160``), optional, for lane EF.

Optional outputs are undefined unless requested and cost nothing then.

**One frame rotation.** The solver calls one ``to_face_frame_`` /
``to_global_frame_`` (``riemann_solver.cpp:12-47`` today). The helper moves to
lane S's coordinate module so the three covariance copies
(``hydro_forward.cpp:93-97``, ``:212-216``, ``:257-261``) call the same
function. Whether the rotation can be fused into the kernel as a per-face
3x3 matrix, instead of two in-place tensor passes per solve, is lane S's
call (section 12).

**One EOS face pass.** One function computes ``FaceThermo{e, gamma, c}``
from total states for both sides, with the aneos branch, replacing the three
copies in ``hllc.cpp:64-81``, ``lmars.cpp:36-52`` and ``roe.cpp:32-37``.
LMARS keeps its specific energy (``e / rho``) and no ``c``; Roe and HLLC
keep their order of calls, so results stay bitwise.

**Which solvers remain.**

.. list-table::
   :header-rows: 1

   * - solver
     - users at the pin (YAML parse of the 72 decks with a ``dynamics`` map)
     - decision
   * - hllc
     - 10 decks name it, 27 get it by default; only solver allowed with
       ``perturbation-flux`` (``hydro.cpp:207-210``)
     - keep; the single default
   * - lmars
     - 26 decks (straka, bryan, earth_crm, convection examples)
     - keep
   * - shallow-roe
     - 9 shallow-water example decks
     - keep
   * - roe
     - no deck; ``tests/test_roe_cubed_sphere_rest.py``,
       ``tests/test_mps_matches_cpu.py``, ``tests/test_riemann.cpp``;
       face-frame fix #340 (2026-11-09)
     - remove; ``FOR CHENG``
   * - upwind
     - no hydro deck; the scalar default (``scalar.hpp:29``,
       ``scalar_options.cpp:52``) and 2 test decks under ``scalar``
     - not a Riemann solver: becomes ``upwind_flux`` used by scalar
       transport; the YAML key keeps parsing
   * - plume-roe
     - no deck, no test, no Python binding; writes no output (section 2)
     - remove

**The perturbation HLLC entry for FP32** stays as the ``FaceBackground``
argument of the one ``forward``: the same kernel, ``shifted`` by ``p0``
(``hllc_impl.h:29-31``, ``:51-52``, ``:96-97``, ``:155-156``), as
``forward_perturbations`` does today (``riemann_solver.hpp:170-177``). LMARS
perturbation support stays deferred (``V3_ROADMAP.md:543``).

10. Face floors (question 8, with lane EF)
------------------------------------------

Where floors act today:

1. ``Reconstruct::forward``, non-shock path only: density and pressure
   floors with the EOS limiter (``reconstruct.cpp:149-159``); species
   ``>= 0`` on both paths (``:104-108``, ``:114``, ``:167``); every variable
   ``>= 0`` when the module has no hydro parent (``:98-102``).
2. The WB x1 restore: pressure falls back to the reference face pressure and
   density to the adjacent cell's density when the restored face is not
   positive (``hydro_forward.cpp:772-805``).
3. FP32 sweeps: pressure and density floors after the gauge is restored
   (``hydro_forward.cpp:602``, ``:605``, ``:611-612``).
4. Inside the solvers: HLLC contact pressure (``hllc_impl.h:96-97``), Roe's
   LLF fallback (``roe_impl.h:145-160``, ``:197-210``).
5. The immersed-solid face rewrite (``pib->forward``).

None reports anything. Design: ``FaceFloor::apply`` runs once per sweep after
the last face transform (WB restore, FP32 gauge) and before the immersed
solid and the solve. It applies the EOS floors under the same conditions as
today, so step 1 of this change is bitwise: the shock path still gets only
the species floor. It counts floored faces per row group into a persistent
device ``int64`` tensor (density, pressure, species), reduced with
``torch.sum`` (no ``.item()``, so it is graph-safe). The WB fallbacks stay
reference-specific (they are not floors: the fallback is a value of the
reference) but are counted in the same tensor. The solvers' own events come
back in ``FaceFlux::events``. Reading, resetting and reporting the counters
is lane EF's (section 12).

``FOR CHENG``: whether the shock path should get the density and pressure
floors too. It changes the 13 ``shock: true`` decks wherever a floor fires.

11. Decisions
-------------

**Kill list.**

* Remove now (no deck, no test of behaviour): ``ppm`` (throws),
  ``plume-roe`` (no output), the dead ``ReconstructOptions``
  (``is_boundary_*``, ``limiter``) and the commented block,
  ``_revise_x1*_ghost`` and their commented call, the MPS rewrites (replaced
  by ``OnHost``), ``recon_dispatch_nu.*``, ``hydro_pressure_scan_x1_tensor``
  (kept today only for a parity test, ``tests/test_pressure_scan_x1.cpp``).
* ``FOR CHENG``: ``roe`` (no deck, but #340 fixed it eight days ago, so
  someone may run it outside the tree).
* Keep without a deck: ``cp3`` and ``weno3`` (no deck; tests only). In point
  form they cost about 35 lines and are documented options
  (``docs/api/reconstruction.rst``). ``FOR CHENG`` if they should go too.
* Python: the per-solver module bindings ``UpwindSolver``, ``RoeSolver``,
  ``LmarsSolver``, ``ShallowRoeSolver`` (``python/csrc/pyriemann.cpp:26-41``)
  give way to one ``RiemannSolver``; no in-tree Python uses them.
  ``FOR CHENG`` (public API).

**The single default Riemann solver: hllc.** It already is the default in
``create()`` and in YAML (section 2). It is the only solver with the split
path required by ``anomaly`` and ``perturbation-flux`` (FP32), it returns a
total face pressure with a contact clamp, and 37 of the 72 hydro decks run
it. LMARS stays a named option for its 26 decks. The ``shock`` default of
``ReconstructOptions`` becomes ``false`` in ``create()`` to match every
deck that writes a ``reconstruct`` section; only the 26 decks with no
``reconstruct`` section (all dc) are affected, and only where a density or
pressure floor fires with the limiter on.

**CPU-versus-CUDA rule.**

* Same device, refactor PRs: bitwise against the base, FP64 and FP32, on CPU
  and on CUDA separately. This is the gate for C1-C4, C7 and C8.
* CPU against CUDA, same commit: agreement to round-off, bitwise only for
  dc and plm (dc is a copy; plm per the inventory, not re-measured here). nvcc contracts ``a * b + c`` into FMA by default
  (``--fmad=true``,
  https://docs.nvidia.com/cuda/cuda-compiler-driver-nvcc/index.html); the
  x86-64 Release build has no ``-march`` (``cmake/compilers.cmake:15-19``) and
  so no FMA. #349 measured CPU against CUDA dumps differing in all 20 cases by
  about 1e-15 relative after 20 rk3 steps (PR body). The tolerance is set per
  test before the change, from the base's own CPU-CUDA spread.
* MPS against CPU: bitwise at float32 once MPS runs the CPU kernel (C2), by
  construction; C2 confirms it by setting the tolerance of
  ``tests/test_mps_matches_cpu.py`` to zero for these arms (no MPS device was
  available to this revision). Until then, that test's tolerances.
* ``FOR CHENG``: a CI build with ``--fmad=false`` for the recon and Riemann
  ``.cu`` files would make those kernels CPU-CUDA bitwise for debugging; not
  proposed as default.

**PR sequence and their bitwise class.**

.. list-table::
   :header-rows: 1

   * - PR
     - content
     - class
   * - C1
     - kill list (now), dead options and code
     - bitwise CPU and CUDA, FP64/FP32
   * - C2
     - MPS through ``OnHost`` for recon, Riemann, reference
     - CPU/CUDA untouched (bitwise); MPS equals CPU at float32
   * - C3
     - one ``Interp``: ``Scheme`` + tables, one dispatch stub, one CUDA line
       kernel (``Nu`` kept as a compile-time branch on ``row_stride == 0``)
     - bitwise CPU and CUDA, FP64/FP32
   * - C4
     - one ``RiemannSolver``, one EOS face pass, one CPU loop and one CUDA
       loop
     - bitwise CPU and CUDA, FP64/FP32
   * - C5
     - ``FaceFlux``: in-kernel ``mass_central``, ``wave_speed``, ``events``;
       ``FaceFloor`` counters
     - bitwise except ``conserve-axial-momentum: full`` (round-off; gate:
       AAM closure and conservation budget tests)
   * - C6
     - ``x1_rows``: one definition of the weights; ``Conversion`` shared with
       ``balance_column``
     - key 2 bitwise; key 4 to round-off (gates: ``test_conversion_order``,
       ``test_balance_column_order4``, ``test_wb_ref4_order``)
   * - C7
     - ``X1Reference`` with ``X1ColumnLink``; ``WellBalancedX1``
     - bitwise CPU and CUDA, FP64/FP32 (code move)
   * - C8
     - ``sweep(FaceDir)``
     - bitwise CPU and CUDA, FP64/FP32 (code move)
   * - C9
     - FP32 typed constants in weno3/weno5/LMARS; uniform rows read ``d``
     - FP64 bitwise; FP32 re-baselined against FP64 with the predeclared
       ``test_fp32_*`` tolerances; CUDA FP32 timing reported
   * - C10
     - ``FOR CHENG`` items once ruled (roe, weno3/cp3, shock floors)
     - per item

Each PR runs the existing lane tests: ``test_weno``, ``test_plm``,
``test_weno5_cuda_line``, ``test_x1_coeffs``, ``test_x1_stretched_refusal``,
``test_riemann``, ``test_roe_cubed_sphere_rest``, ``test_hydro_ref_x1``,
``test_pressure_scan_x1``, ``test_split_reference``,
``test_balance_column``, ``test_wb_ref_wall``, ``test_conversion_order``,
``test_x1_seam_split``, ``test_perturbation_flux``,
``test_mps_matches_cpu`` (skips without MPS), and the
``fp32-foundations`` label (``V3_ROADMAP.md:529-535``).

12. Line budget, risks, FOR CHENG and open questions
----------------------------------------------------

**Line budget.** Baseline measured (section 2). Code that moves into lane C
files from ``hydro.cpp`` and ``hydro_forward.cpp`` is measured and added, so
moving lines out of the hydro files is not counted as a saving. Targets are
estimates from the existing bodies, not measurements.

.. list-table::
   :header-rows: 1

   * - group
     - baseline (measured)
     - moved in (measured)
     - target (estimate)
   * - recon (``src/recon``)
     - 2,233
     - 319 (``hydro_forward.cpp:291-368``, ``:417-504``, ``:668-820``)
     - 1,265: ``recon_point.h`` 130, ``x1_rows`` 300, ``recon_line.cuh``
       170, ``recon_dispatch`` 175, ``reconstruct`` 190, ``conversion``
       130, ``well_balanced_x1`` 120, ``face_floor`` 50
   * - riemann (``src/riemann``)
     - 2,089
     - 0
     - 905: ``riemann.{hpp,cpp}`` 260, ``riemann_kernels.h`` 520,
       ``riemann_dispatch.{cpp,cu}`` 125
   * - reference (the 10 hydro files)
     - 1,519
     - 268 (``hydro.cpp:605-872``)
     - 1,059: ``hydro_ref_x1_impl.h`` 280, ``split_reference_scalar.hpp``
       74, ``x1_reference`` 300, ``x1_reference_dispatch`` 195,
       ``balance_column`` 210
   * - total
     - 5,841
     - 587
     - 3,229

Against the 5,841-line baseline the target is 3,229 lines (-44.7%); against
baseline plus moved-in code, 6,428 to 3,229 (-49.8%). The lane target of at
least 20% is a ceiling of 4,672 lines. The direction-generic sweep is not in
these numbers: it replaces 87 lines (``hydro_forward.cpp:1010-1031``,
``:1088-1152``) with about 45 in ``hydro_forward.cpp``. The skeleton is 289
lines (``wc -l docs/v3/skeleton/c/*``). The largest single saving is the 674
lines of MPS rewrites (C2).

**Risks.**

* MPS throughput under ``OnHost`` (section 5).
* C9 changes FP32 results on every WENO face (36% of faces differ in the
  last bits in the probe of section 2); it must be judged against FP64, not
  against the old FP32.
* C5 changes ``conserve-axial-momentum: full`` at round-off; lane A must
  accept the in-kernel central flux as the definition.
* The key-4 weight rows of C6 change at the last bit; the key-4 goldens of
  ``test_conversion_order`` and ``test_x1_seam_split`` may need re-pinning
  with the reason recorded.
* ``FaceFloor`` must not move a floor across the immersed-solid rewrite or the
  WB fallback; C5 asserts bitwise default decks.

**FOR CHENG.**

1. Remove ``roe`` (section 9, 11).
2. Keep or remove ``cp3`` and ``weno3`` (no deck).
3. MPS as a correctness target through ``OnHost`` (section 5).
4. FP32 typed constants (C9), a one-time FP32 re-baseline.
5. ``shock`` default ``false`` in ``create()`` (section 11).
6. Density and pressure floors on the shock path (section 10).
7. One Python ``RiemannSolver`` in place of four per-solver bindings.
8. An optional ``--fmad=false`` CI build (section 11).

**Open interface questions.**

* Lane A: is ``mass_central`` (rows IDN and ICY..) enough, or does AAM need
  every row of the dissipative flux, as ``_aam_mass_flux`` keeps today
  (``hydro_forward.cpp:1356-1361``)? In which dtype does the register hold
  the face pressure in an FP32 run (FP64 background plus FP32 delta today)?
* Lane S: ownership of ``to_face_frame_`` / ``to_global_frame_``; in-kernel
  rotation or tensor passes; the cubed-sphere face-state exchange between
  ``reconstruct_faces`` and ``solve_faces``.
* Lane EF: counter layout, dtype and reset point for ``FaceFloor`` and
  ``FaceFlux::events`` under graph replay.
* Lane O (layout): ``X1ColumnLink`` (anchor relay, ghost-row exchange) and
  whether the seam flux average (``hydro_forward.cpp:882-946``) moves behind
  the same interface.
* Lane I: at the pin ``src/implicit`` reads no lane-C output (no use of the
  face pressure, the reference or the solver; ``grep`` of
  ``src/implicit``). Confirm that V3's implicit design keeps it that way, or
  name the ``FaceFlux`` / ``ReferenceFaces`` fields it will read.
* Brief: the twelve sections here are 1 scope, 2 baseline and recheck,
  3 duplication, 4 target, 5 questions 1-2, 6 question 3, 7 question 4,
  8 question 5, 9 questions 6-7, 10 question 8, 11 decisions, 12 budget,
  risks, flags and questions. If the shared brief prescribes other section
  titles, revision 2 will rename them; the content is the same.

How the numbers were produced (on the lane's build host, at the pin):

* ``wc -l`` on the listed files.
* Deck census: a Python script loading every ``*.yaml`` outside
  ``external/`` with ``yaml.safe_load_all`` and reading
  ``dynamics/riemann-solver/type``, ``dynamics/reconstruct/*`` and
  ``dynamics/conversion-order``; 72 decks have a ``dynamics`` map, none sets
  conversion order 4.
* FP32 probe: ``g++ -O2 -std=c++17`` of a driver including
  ``src/recon/interp_point.h`` (``DISPATCH_MACRO`` empty), 1,000,000 faces,
  ``std::mt19937`` seed 7; instruction counts from ``g++ -S`` of the same
  file.
* MPS ranges: start lines from ``grep -n``, end at the first closing ``}``
  in column 1.
