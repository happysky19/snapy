# V3 closing Audit 2 (Tianhao): code removable with no result change

Findings only. This document changes no source file. The scratch tree
described in section 3 was used to measure and test the removals; it is
local to dungeon3 and is not published.

## 1. Pins

| what | value |
|---|---|
| audited commit | `UCzhangxi/snapy` `v3/wave3` = `d3178f207b60663ff966b7c7ef20025821ef52fa` (tree `874a4125d67a92c8f899097e15233e9a53df1f4c`) |
| its base | `v3/base3` = `deeabfee597cd83f68f4586d245b01f6091eaa6e` (merge of #372; tree `cfd9b32f6f53968588363c99ea2b03da24e92f91`, the same tree as the merge-base `9ecee6f523ee9d0db2363411a2023c0b547d9f41`) |
| line-count method | `docs/v3/DESIGN.rst` section 6.1, `happysky19/snapy` `v3-design/DESIGN` = `449636b3e1963b5fc7d44407cb7d6db437e8b016`, lines 317-326 |
| scope searched | every file under `src/` (C++, CUDA, `src/options/*.yaml`, `src/CMakeLists.txt`); `python/`, `tests/` and `examples/` were searched as consumers; `tests/` for duplicate tests |
| host | dungeon3, CPU build (GCC, Release), PyTorch 2.10.0+cu128, kintera 2.6.11 wheel installed into the audit folder (the shared environments carry 2.6.10, below the pin's `>= 2.6.11`) |

Verification of the pin and its base (run 2026-11-22):

```
$ git ls-remote https://github.com/UCzhangxi/snapy.git refs/heads/v3/wave3 refs/heads/v3/base3; date -u +%FT%TZ
deeabfee597cd83f68f4586d245b01f6091eaa6e	refs/heads/v3/base3
d3178f207b60663ff966b7c7ef20025821ef52fa	refs/heads/v3/wave3
2026-11-22T17:06:03Z
$ git log -1 --format="%H%nparents %P%ntree %T%n%an %ad%n%s" d3178f207b60663ff966b7c7ef20025821ef52fa
d3178f207b60663ff966b7c7ef20025821ef52fa
parents 5656951128ccc8c662faf3a0acab8082a42c4bef
tree 874a4125d67a92c8f899097e15233e9a53df1f4c
Tianhao Le Sat Nov 21 22:56:19 2026 -0500
recon, riemann, hydro: lane C under its 4,672-line ceiling (V3 C.trim)
$ git log -1 --format="%H%nparents %P%ntree %T%n%s" deeabfee597cd83f68f4586d245b01f6091eaa6e
deeabfee597cd83f68f4586d245b01f6091eaa6e
parents 6007eaa9f1f3a66fdfd929616ca219ee3f560bd2 9ecee6f523ee9d0db2363411a2023c0b547d9f41
tree cfd9b32f6f53968588363c99ea2b03da24e92f91
V3 wave 2: flux register, EOS and floors, reconstruction, cubed-sphere faces, MeshBlock split, implicit face work (29 commits) (#372)
$ git merge-base d3178f207b60663ff966b7c7ef20025821ef52fa deeabfee597cd83f68f4586d245b01f6091eaa6e
9ecee6f523ee9d0db2363411a2023c0b547d9f41
$ git rev-parse 9ecee6f523ee9d0db2363411a2023c0b547d9f41^{tree}  # = the base tree above
cfd9b32f6f53968588363c99ea2b03da24e92f91
$ git rev-list --count deeabfee597cd83f68f4586d245b01f6091eaa6e..d3178f207b60663ff966b7c7ef20025821ef52fa
29
$ git diff --shortstat deeabfee597cd83f68f4586d245b01f6091eaa6e d3178f207b60663ff966b7c7ef20025821ef52fa -- src
 116 files changed, 4182 insertions(+), 5890 deletions(-)
```

## 2. Method

**Net lines.** DESIGN 6.1 counts every `.cpp`, `.hpp`, `.h`, `.cu` and
`.cuh` file under `src/` with `wc -l` (blank and comment lines included):

```
git ls-tree -r --name-only <rev> -- src \
  | grep -E '\.(cpp|hpp|h|cu|cuh)$' \
  | while read f; do git cat-file -p <rev>:$f | wc -l; done \
  | awk '{s+=$1} END{print s}'
```

It prints 36,859 at the base `deeabfee` and **35,136** at the pin `d3178f20`.
Every finding was applied as its own commit on a local scratch branch from
the pin, and its net lines are `count(commit) - count(parent)` by the
command above. Lines outside the 6.1 file set (`src/options/*.yaml`,
`.cpp_`, `tests/`, `python/`) are listed separately and are not in the
net figure.

**Search.**

1. A token index of the tree, comments stripped (string contents kept,
   because option keys are read through strings), over `src/`, `python/`,
   `tests/` and `examples/`; every identifier that occurs in `src/` with at
   most two occurrences and none outside `src/` was inspected by hand.
2. Every name declared as a function or method in `src/`, with its total use
   count; counts of 1 or 2 (declaration, or declaration plus definition)
   were inspected.
3. Every row of `src/options/*.yaml` and every hand-written `ADD_ARG` field:
   readers outside the generated code, and deck keys in every tracked
   `.yaml`.
4. One-statement functions (`return g(...)` or `g(...);`) with at most four
   name occurrences: one-caller wrappers.
5. Comment lines that end in `;` or are commented-out code blocks.
6. A CPU build of the pin with `-Wunused -Wunused-but-set-variable
   -Wunused-const-variable=1 -Wunused-macros` added to the C.trim gate's
   CMake flags. These warnings do not change the generated code.
7. Duplicate tests: every `TEST`/`TEST_F`/`TEST_P` body in `tests/*.cpp`
   (660 cases), comments stripped and whitespace collapsed, grouped by
   equal body; and every `add_test` in `tests/CMakeLists.txt` that runs an
   existing test binary again.

**Proof of removability.** For each finding: the grep at the pin (section
4), then the scratch tree with all findings applied had to (a) compile and
link with no new warning, (b) give the same verdict per test as the pin in
the C.trim gate's serial ctest selection, and (c) write byte-identical files
for five short example decks (section 5).

## 3. Summary

The scratch branch `audit2-scratch-local` (head
`94f6fa99db354c147385c31df12a3b487b84399b`, 16 commits on the pin, local
to dungeon3 only) applies all sixteen findings: 40 files, 5 insertions, 258
deletions. The 6.1 count goes from 35,136 to 34,916: **-220 lines**.

| # | kind | site at the pin | removal | expected result | net (6.1) | other lines |
|---|---|---|---|---|---|---|
| F1 | unreached files | `src/mesh/mesh_functions.hpp:1-16`, `src/mesh/mesh_functions.cpp:1-30`, `src/coord/coordinate.hpp:16` | both files and the include | bitwise identical | -47 | |
| F2 | unreached method | `src/layout/cubed_sphere_layout.cpp:866-890`, `cubed_sphere_layout.hpp:65-69`, `src/layout/layout.hpp:225` | `CubedSphereLayoutImpl::_interpolate_to_local` (no caller), then `LayoutImpl::is_root` (its only caller) | bitwise identical | -31 | |
| F3 | unreached methods | `src/mesh/signal_handler.hpp:52-59`, `signal_handler.cpp:133-144` | `SignalHandler::SetWallTimeAlarm`, `CancelWallTimeAlarm` | bitwise identical; an external SIGALRM is still handled | -20 | |
| F4 | unreached method | `src/mesh/meshblock.hpp:305-308` (and the mention at `:291`), `src/mesh/meshblock_redo.cpp:32-36` | `MeshBlockImpl::saturation_failures` | bitwise identical | -9 | |
| F5 | unreached function | `src/layout/cubed_sphere_layout.cpp:381-391`, `:490-491` | `cs_clamp_inside`, called only from a commented-out line | bitwise identical | -13 | |
| F6 | unread field | `src/hydro/hydro.hpp:313-320` | `HydroImpl::_cell_vol` and its struct `CellVolume` | bitwise identical | -8 | |
| F7 | unread accessors | `src/hydro/flux_register.hpp:102`, `:146`; `src/layout/process_group.hpp:36`; `src/diagnostics/budget.hpp:73`; `src/output/budget_series.hpp:44`; `src/scalar/scalar.hpp:116-119` | `RegisterMonitor::retry_names`, `FluxRegister::weight1`, `ProcessGroupContext::is_ucx`, `BudgetConsumer::started`, `BudgetOutput::consumer`, `ScalarImpl::get_buffer` | bitwise identical | -9 | |
| F8 | unused alias, enumerators | `src/coord/coordinate.hpp:25`; `src/snap.h:65-68` | `IndexRange`; `kTPMassLR = 5`, `kDPMassLR = 6` | bitwise identical | -5 | |
| F9 | unused enumerators | `src/mesh/precision_policy.hpp:20-21`, `:23-26` | `Quantity::kGauge`, `kReduction`, `kThermo`, `kRegister`, `kSource`, `kDiagnostic` | bitwise identical (see note) | -6 | |
| F10 | commented-out code | 12 ranges in `src/eos/*` (listed by the F10 grep), `src/scalar/scalar_options.cpp:43-45`, `src/layout/cubed_sphere_layout.cpp:537` | the commented `get_buffer`/`pretty_print` stubs, the `pull_neighbors` loop, the commented `from_yaml` calls and `printf` | bitwise identical (comments only) | -41 | |
| F11 | unread locals | `src/coord/gnomonic_equiangle.cpp:373,378,384,393,398,404,428,433,439,457,462,468` | `auto T11 = 1.` (unused, GCC `-Wunused-variable`) and the two commented lines that used it, in four functions | bitwise identical | -12 | |
| F12 | one-caller wrappers | `src/implicit/implicit_hydro.hpp:135` (caller `src/mesh/meshblock_advance.cpp:142`); `src/hydro/flux_register.cpp:66-69`, `flux_register.hpp:104` (caller `flux_register.cpp:80`) | `ImplicitHydroImpl::reset_solve_failure` (calls `reset_status()`), `RegisterMonitor::minimum_index` (calls `index_of(_minimum, ...)`); the caller calls the callee | bitwise identical | -6 | |
| F13 | unread options | `src/options/output.yaml:21`, `:40` | `outputs[]/cartesian_vector`, `outputs[]/data_format` | bitwise identical output for every tracked deck; see note | 0 | yaml -2, `python/snapy/output.pyi` -17 (regenerated), `tests/test_options_table.cpp` +2/-4 |
| F14 | unreached file | `src/coord/cylindrical.cpp_:1-7` | the file | bitwise identical (never compiled) | 0 | -7 (`.cpp_` is outside 6.1) |
| F15 | duplicate test | `tests/CMakeLists.txt:103-107` | `test_hydro_ref_x1_stretched_cuda` | the case still runs inside `test_hydro_ref_x1` | 0 | -5 |
| F16 | unread locals and function (GCC warnings) | `src/bc/bc_func.cpp:54`; `src/bc/rectify_solid.cpp:114`; `src/eos/equation_of_state.cpp:340`; `src/hydro/hydro_forward.cpp:331-334`; `src/implicit/implicit_hydro.cpp:23-27`; `src/riemann/riemann_kernels.h:346` | `nc`, `nc1`, `nghost`, the lambda `fill4`, `static acc_type`, `du0` | bitwise identical | -13 | |
| | | | | | **-220** | |

Per-commit counts (the 6.1 command at each scratch commit and its parent):

```
$ bash netlines.sh
pin d3178f207b60663ff966b7c7ef20025821ef52fa 35136
63552e63 F1 net -47  other:
b5bf2aff F2 net -31  other:
57a6163f F3 net -20  other:
6277ce60 F4 net -9  other:
eec0aff3 F5 net -13  other:
6e9138cf F6 net -8  other:
bce4b744 F7 net -9  other:
876bc069 F8 net -5  other:
945fec6a F9 net -6  other:
61d8e999 F10 net -41  other:
b7431d5d F11 net -12  other:
5f1a686b F12 net -6  other:
71446000 F13 net +0  other: python/snapy/output.pyi:+0/-17 src/options/output.yaml:+0/-2 tests/test_options_table.cpp:+2/-4
842ed29b F14 net +0  other: src/coord/cylindrical.cpp_:+0/-7
0f003a7f F15 net +0  other: tests/CMakeLists.txt:+0/-5
94f6fa99 F16 net -13  other:
all 94f6fa99db354c147385c31df12a3b487b84399b 34916 net -220
```

## 4. Findings and their evidence

Each grep ran in a clean checkout of the pin, with `external/`, `docs/`
and Markdown files excluded. Exit 1 means no match. The complete
transcript is in appendix A.

**F1. `src/mesh/mesh_functions.{hpp,cpp}`.** The files declare
`compute_logical_position` and `MeshGenerator`. Neither name occurs outside
the two files. `coordinate.hpp:16` includes the header and uses nothing from
it. `src/CMakeLists.txt` globs `mesh/*.cpp`, so deleting the files needs no
build edit. No other header reaches `<functional>` through this one: the
scratch tree builds.

**F2. `CubedSphereLayoutImpl::_interpolate_to_local`.** Declared at
`cubed_sphere_layout.hpp:66`, defined at `cubed_sphere_layout.cpp:867`; no
call anywhere. Its body clones a tensor, prints under `verbose` and ends at
`//\TODO calculate neighbor coordinates and perform interpolation`.
`LayoutImpl::is_root` (`layout.hpp:225`) has this function as its only
caller, so it goes too.

**F3. `SignalHandler::SetWallTimeAlarm` / `CancelWallTimeAlarm`.** Only the
declarations and definitions match. snapy never calls `alarm()` otherwise;
the SIGALRM handler and its flag stay (`meshblock_output.cpp:68`,
`signal_handler.cpp:37,44`), so a SIGALRM sent by a scheduler is handled as
before. `<unistd.h>` was kept: the audit did not check whether anything else
in the file needs it.

**F4. `MeshBlockImpl::saturation_failures`.** The definition, the
declaration and a comment mention (`meshblock.hpp:291`, reworded in the
scratch tree to "Drains kintera's saturation-failure count", net 0) are the
only matches. The step-start drain the comment at `:306` describes does
not go through this method.

**F5. `cs_clamp_inside`.** A `static inline` function whose one reference
is a commented-out call (`cubed_sphere_layout.cpp:491`).

**F6. `HydroImpl::_cell_vol`.** The member and its struct are the only
matches: nothing reads or writes them. Its comment says the tracer
positivity limiter builds it on first use; no such code exists at the pin.

**F7. Six accessors with no caller.** `retry_names()`, `weight1()`,
`is_ucx()`, `started()`, `consumer()` and the live `ScalarImpl::get_buffer`
each match only their own line. The fields behind them (`_retry`, `_w1`,
`backend`, `_started`, `_consumer`) are still read elsewhere. `weight2()`
is used (`implicit_hydro.cpp:633`) and stays.

**F8. `IndexRange`, `kTPMassLR`, `kDPMassLR`.** Single matches.
`python/csrc/snapy.cpp:42-43` exports only `kPrimitive` and `kConserved`.

**F9. Six `Quantity` enumerators.** Each name occurs only on its own line.
The only other code that touches them is the loop over `kCount` in
`tests/test_precision_policy.cpp:22-23`, which checks that every row is
either narrow or wide; with the rows gone it checks seven rows instead of
thirteen and still passes. Every removed row holds the default wide dtype.
*Note:* these rows are lane X's dtype contract table (X.rst section 6).
Removing them changes no result, but lane X decides whether the table may
list quantities no code names.

**F10. Commented-out code.** The grep lists every range. It removes
comments and blank lines only, so the compiled code is the same.

**F11. `T11` in `prim2local2_`, `prim2local3_`, `flux2global2_`,
`flux2global3_`.** GCC reports each `auto T11 = 1.` unused (section 5). The
only other `T11` lines are the commented `w[IVX] = T11 * uu1;` and
`flux[IVX] = T11 * txx;`, together with the commented `uu1`/`txx` lines.

**F12. One-caller wrappers.** `reset_solve_failure()` is
`{ reset_status(); }`. Its one caller (`meshblock_advance.cpp:142`) can
call `reset_status()`, which is public (`implicit_hydro.hpp:129`; the
tests call it). `minimum_index(name)` is `return index_of(_minimum, name,
"minimum");` with one caller in the same class (`flux_register.cpp:80`).
Its siblings `counter_index` and `retry_index` have more callers and stay.

**F13. `outputs[]/cartesian_vector`, `outputs[]/data_format`.** No reader
in `src/`. The generated code only stores and binds them
(`build/snap_options/output_{members,read,pybind}.inc`). No tracked deck
sets them (exit 1 for the dashed keys; the underscore keys match only the
yaml, the generated stub and the table test). *Note:* run output is
bitwise identical. Two behaviours change: (a) the option report printed
with `verbose` loses two lines; (b) a deck that sets either key would now
be refused, because the generated reader calls `check_keys`
(`src/input/check_keys.cpp:26-29`, `TORCH_CHECK` on an unknown key).
Before, such a deck was accepted and the value ignored. In the scratch
commit, `tools/gen_options.py --write-pyi` regenerated the stub and
`--check-pyi` passed.

**F14. `src/coord/cylindrical.cpp_`.** No glob or list matches the `.cpp_`
suffix (`src/CMakeLists.txt:35-55`), and its seven lines are not valid C++
(the missing `;` on line 4). It is outside the 6.1 count.

**F15. `test_hydro_ref_x1_stretched_cuda`.** `setup_test(test_hydro_ref_x1)`
registers the whole binary with no filter
(`cmake/macros/macro_setup_test.cmake:33`) and no environment. The extra
entry runs one of its cases,
`HydroRefX1Dispatch.cuda_matches_cpu_on_the_stretched_rows`, again with no
environment. The case runs twice on a CUDA host and is skipped twice on a
CPU host. Removing the entry drops its own `TIMEOUT 120` and `hydro;gpu`
labels. The only label selections in the tree are the
`ctest ... -L fp32-*` commands in `V3_PROGRESS.md` and `docs/`
(foundations, dynamics, pressure-scan, acceptance, restart, science; all
listed in appendix A). None selects `hydro` or `gpu`.
`test_hydro_ref_x1` keeps its own `fp32-foundations` label
(`tests/CMakeLists.txt:883`), so those selections still run the case. The other re-run entries are not duplicates:
each sets an environment that changes the path
(`SNAP_X1_CENTROID_EXACT=1`, `SNAP_BUDGET_CUDA=1`, `GTEST_FILTER` per seam
arm). No two gtest bodies are equal.

**F16. GCC unused warnings in `src/`.** All six initialisers have no side
effects. `var.size(dim)` is already called on the line before
(`bc_func.cpp:53`). `pcoord->options->nghost()` is an `ADD_ARG` getter.
`du0` is plain arithmetic. `fill4` is a lambda that is never called.
`acc_type` is a `static` function that is never called. One qualification:
for a solid tensor with fewer than three dimensions, `solid_in.size(2)`
(`rectify_solid.cpp:114`) throws. Without that line, the same
dimension-out-of-range error comes from `var.size(dim)` in
`solid_inner(solid, DIM1 = 2, ...)` (`bc_func.cpp:69`), a few lines later.
Nothing in between writes (an `nghost` read, option setup and two registry
lookups), so only the error's source line changes.

## 5. Validation of the scratch tree

Builds: `build.sh` (appendix C) = the C.trim gate's CMake line (`-DCMAKE_BUILD_TYPE=Release
-DNETCDF=ON -DBUILD_TESTS=ON -DFULL_TESTS=OFF -DCUDA=OFF`) with the warning
flags of section 2.

```
$ bash build.sh A; bash build.sh B
build A d3178f207b60663ff966b7c7ef20025821ef52fa rc=0 2026-11-22T16:59:11Z
build B 94f6fa99db354c147385c31df12a3b487b84399b rc=0 2026-11-22T17:03:43Z
```

The pin's unused-entity warnings (`_deps/` excluded); every `src/` line is
covered by F11 or F16:

```
$ grep warning: build-A.log | grep -v _deps | sort | uniq -c
      1 examples/run_hydro.cpp:104:7: warning: unused variable ‘nvapor’ [-Wunused-variable]
      1 examples/run_hydro.cpp:105:7: warning: unused variable ‘ncloud’ [-Wunused-variable]
      1 src/bc/bc_func.cpp:54:7: warning: unused variable ‘nc’ [-Wunused-variable]
      1 src/bc/rectify_solid.cpp:114:7: warning: unused variable ‘nc1’ [-Wunused-variable]
      1 src/coord/gnomonic_equiangle.cpp:378:8: warning: unused variable ‘T11’ [-Wunused-variable]
      1 src/coord/gnomonic_equiangle.cpp:398:8: warning: unused variable ‘T11’ [-Wunused-variable]
      1 src/coord/gnomonic_equiangle.cpp:433:8: warning: unused variable ‘T11’ [-Wunused-variable]
      1 src/coord/gnomonic_equiangle.cpp:462:8: warning: unused variable ‘T11’ [-Wunused-variable]
      1 src/eos/equation_of_state.cpp:340:10: warning: unused variable ‘nghost’ [-Wunused-variable]
      1 src/hydro/hydro_forward.cpp:331:8: warning: variable ‘fill4’ set but not used [-Wunused-but-set-variable]
      1 src/implicit/implicit_hydro.cpp:24:26: warning: ‘c10::ScalarType snap::acc_type(const at::Tensor&)’ defined but not used [-Wunused-function]
      2 src/riemann/riemann_kernels.h:346:5: warning: unused variable ‘du0’ [-Wunused-variable]
      1 tests/test_coordinate.cpp:312:7: warning: unused variable ‘nghost’ [-Wunused-variable]
      1 tests/test_coordinate.cpp:333:7: warning: unused variable ‘nghost’ [-Wunused-variable]
      1 tests/test_coordinate.cpp:502:7: warning: unused variable ‘nghost’ [-Wunused-variable]
```

The scratch tree's (no `src/` warning left; the `tests/` and `examples/`
ones are outside this audit's scope):

```
$ grep warning: build-B.log | grep -v _deps | sort | uniq -c
      1 examples/run_hydro.cpp:104:7: warning: unused variable ‘nvapor’ [-Wunused-variable]
      1 examples/run_hydro.cpp:105:7: warning: unused variable ‘ncloud’ [-Wunused-variable]
      1 tests/test_coordinate.cpp:312:7: warning: unused variable ‘nghost’ [-Wunused-variable]
      1 tests/test_coordinate.cpp:333:7: warning: unused variable ‘nghost’ [-Wunused-variable]
      1 tests/test_coordinate.cpp:502:7: warning: unused variable ‘nghost’ [-Wunused-variable]
```

Serial ctest, the C.trim gate's selection
(`ctest -j 1 -R '^test_' -E '_python$|cuda|gpu' --timeout 900`), CPU only:

```
$ bash ctest.sh A 29941; bash ctest.sh B 29951
ctest A d3178f207b60663ff966b7c7ef20025821ef52fa rc=0 100% tests passed, 0 tests failed out of 122 2026-11-22T17:04:42Z
ctest B 94f6fa99db354c147385c31df12a3b487b84399b rc=0 100% tests passed, 0 tests failed out of 122 2026-11-22T17:08:09Z
$ grep -E "tests passed|Total Test time" ctest-A.log ctest-B.log
ctest-A.log:100% tests passed, 0 tests failed out of 122
ctest-A.log:Total Test time (real) = 294.07 sec
ctest-B.log:100% tests passed, 0 tests failed out of 122
ctest-B.log:Total Test time (real) = 201.14 sec
$ bash verdicts.sh
diff exit 0
    122 Passed
```

Five short example decks, run with each tree's own example binaries on CPU
(`OMP_NUM_THREADS=4`). The copies change only `nlim` and the output `dt`
(`decks.py`, appendix C: shock 40 steps, straka_single 100, jupiter_evap_precip_1d
30, shallow_xy_single 40, shallow_splash_mesh6 20; the last is the
cubed-sphere deck with six blocks in one process). Every output file
(netCDF and restart) was compared with `cmp`:

```
$ bash rundecks.sh A; bash rundecks.sh B
work/rundecks.sh: line 11: 45951 Aborted                 timeout 1800 $T/build/bin/$exe.release $deck.yaml > run.log 2>&1
shock rc=134 files=4
straka_single rc=0 files=6
jupiter_evap_precip_1d rc=0 files=31
shallow_xy_single rc=0 files=4
shallow_splash_mesh6 rc=0 files=21
work/rundecks.sh: line 11: 46161 Aborted                 timeout 1800 $T/build/bin/$exe.release $deck.yaml > run.log 2>&1
shock rc=134 files=4
straka_single rc=0 files=6
jupiter_evap_precip_1d rc=0 files=31
shallow_xy_single rc=0 files=4
shallow_splash_mesh6 rc=0 files=21
$ bash cmpdecks.sh
only in B: 0
files 66 byte-identical 66
jupiter_evap_precip_1d log(filtered) A=5ae378f95d69 B=5ae378f95d69 same
shallow_splash_mesh6 log(filtered) A=ec4009ff6d70 B=ec4009ff6d70 same
shallow_xy_single log(filtered) A=e60973835134 B=e60973835134 same
shock log(filtered) A=8c4d6bea66d6 B=a9659fa7abcb DIFFER
straka_single log(filtered) A=8f5aa6831f74 B=8f5aa6831f74 same
$ diff <(grep -v "^frame" runs-A/shock/run.log) <(grep -v "^frame" runs-B/shock/run.log)
3c3
< Exception raised from radiating at $W/A/src/bc/bc_func.cpp:132 (most recent call first):
---
> Exception raised from radiating at $W/B/src/bc/bc_func.cpp:131 (most recent call first):
```

The shock example aborts on both trees at the same step, after the same
four files, with `outflow: nonfinite hydro input`
(`src/bc/bc_func.cpp:132` at the pin). It is a property of the pin and this
short copy, not of the removals, and was not investigated. Its logs differ
only in that source line: `bc_func.cpp:132` on A, `:131` on B, because F16
deletes line 54 above it.

## 6. Candidates examined and not proposed

| candidate | why not |
|---|---|
| `ANEOSThermoImpl::_cal_TUL/_cal_PTL/_cal_PUL`, `eos_header`, `eos_data` (`src/eos/aneos/aneos_thermo.hpp:14-15,39-46`) | no use in the tree, but the class is built for a strong out-of-tree implementation that replaces the `__attribute__((weak))` stubs in `aneos_thermo_dummy.cpp`. Removing members changes the class layout that implementation compiles against |
| buffer `conversion_trips` (`src/hydro/hydro.cpp:276`) | no C++ reader by name, but a registered buffer is in the module's buffers and state; not shown result-neutral |
| `OutputType::PrimStatMean/PrimStatStd/ScalarStatMean/ScalarStatStd` (one caller each) | they wrap anonymous-namespace helpers in `output_type.cpp`. Inlining them means moving the helpers, which saves no lines |
| `ImplicitHydroImpl::count_fp64_columns`, `reset_dry_clamp_step`, `AxialMomentum::disarm`, `LayoutImpl::use_process_group` (one caller each) | they touch private state; inlining needs a friend or a public field |
| `CylindricalImpl` and the `"cylindrical"` branch (`coordinate.cpp:757`) | reachable from a deck (`coord/type`) |
| `ADD_ARG` fields (93 in `src/`) | every one has at least five uses outside its declaration |
| headers never included | none: every `src/` header is included somewhere |
| `#if 0`, `if (false)`, `if (0)` | none in `src/` |
| `tests/test_coordinate.cpp:312,333,502`, `examples/run_hydro.cpp:104-105` unused locals | outside `src/` (GCC reports them) |

## 7. Limits

- CPU only. The `.cu` files were not compiled. Every name removed from a
  header shared with CUDA code (`riemann_kernels.h:346`, `snap.h`,
  `precision_policy.hpp`) has no other match in `.cu`/`.cuh` files by the
  greps above, but no CUDA build or CUDA ctest was run.
- `python/csrc` (the pybind module that `setup.py` builds) was not
  compiled. The greps include `python/` and find no reference to any
  removed name. F13's bindings are generated from the yaml, and
  `--check-pyi` passes.
- Not run: the ctest entries the selection excludes (`*_python`, and every
  name with `cuda` or `gpu`), and the #348/#349/nb-pz gates. The selection
  does include the two-rank gloo entries and the Python-script entries
  without the `_python` suffix.
- The five decks are short copies, not the production gates. They cover
  ideal-gas (2-D Cartesian), ideal-moist with kintera and the implicit
  solver (1-D), shallow water (Cartesian) and the cubed sphere (six blocks
  in one process).
- kintera 2.6.11 came from PyPI (`kintera-2.6.11-cp311-cp311-manylinux_2_27_x86_64.whl`)
  and was installed with `--no-deps --target` into the audit folder,
  because the shared environments hold 2.6.10.
- The search is a token search plus GCC's warnings. Code reached only
  through a virtual call or a string-keyed registry could be missed, which
  errs toward keeping code. A name used only in `tests/` counts as used.

## Appendix A. Grep transcript at the pin (`evidence.sh`, appendix C)

```
$ git rev-parse HEAD; git status --porcelain | wc -l
d3178f207b60663ff966b7c7ef20025821ef52fa
0
## F1
$ git grep -n -w compute_logical_position -- . ':!external' ':!docs' ':!*.md'
src/mesh/mesh_functions.cpp:11:torch::Tensor compute_logical_position(torch::Tensor index, int64_t nrange,
src/mesh/mesh_functions.hpp:12:torch::Tensor compute_logical_position(torch::Tensor index, int64_t nrange,
(exit 0)
$ git grep -n -w MeshGenerator -- . ':!external' ':!docs' ':!*.md'
src/mesh/mesh_functions.hpp:15:using MeshGenerator = std::function<torch::Tensor(torch::Tensor, float, float)>;
(exit 0)
$ git grep -n -w mesh_functions -- . ':!external' ':!docs' ':!*.md'
src/coord/coordinate.hpp:16:#include <snap/mesh/mesh_functions.hpp>
src/mesh/mesh_functions.cpp:5:#include "mesh_functions.hpp"
(exit 0)
## F2
$ git grep -n -w _interpolate_to_local -- . ':!external' ':!docs' ':!*.md'
src/layout/cubed_sphere_layout.cpp:867:void CubedSphereLayoutImpl::_interpolate_to_local(
src/layout/cubed_sphere_layout.hpp:66:  void _interpolate_to_local(MeshBlockImpl const* pmb,
(exit 0)
$ git grep -n -w is_root -- . ':!external' ':!docs' ':!*.md'
src/layout/cubed_sphere_layout.cpp:882:  if (options->verbose() && is_root()) {
src/layout/layout.hpp:225:  bool is_root() const { return options->rank() == options->root_rank(); }
(exit 0)
## F3
$ git grep -n -w SetWallTimeAlarm -- . ':!external' ':!docs' ':!*.md'
src/mesh/signal_handler.cpp:135:void SignalHandler::SetWallTimeAlarm(int t) {
src/mesh/signal_handler.hpp:56:  void SetWallTimeAlarm(int t);
(exit 0)
$ git grep -n -w CancelWallTimeAlarm -- . ':!external' ':!docs' ':!*.md'
src/mesh/signal_handler.cpp:141:void SignalHandler::CancelWallTimeAlarm() {
src/mesh/signal_handler.hpp:59:  void CancelWallTimeAlarm();
(exit 0)
## F4
$ git grep -n -w saturation_failures -- . ':!external' ':!docs' ':!*.md'
src/mesh/meshblock.hpp:291:  //! Drains the saturation-failure count like saturation_failures()
src/mesh/meshblock.hpp:307:  int64_t saturation_failures();
src/mesh/meshblock_redo.cpp:32:int64_t MeshBlockImpl::saturation_failures() {
(exit 0)
## F5
$ git grep -n -w cs_clamp_inside -- . ':!external' ':!docs' ':!*.md'
src/layout/cubed_sphere_layout.cpp:381:static inline void cs_clamp_inside(int pxy, int* nx, int* ny) {
src/layout/cubed_sphere_layout.cpp:491:  // cs_clamp_inside(pxy, out_rx, out_ry);
(exit 0)
## F6
$ git grep -n -w _cell_vol -- . ':!external' ':!docs' ':!*.md'
src/hydro/hydro.hpp:320:  CellVolume _cell_vol;
(exit 0)
$ git grep -n -w CellVolume -- . ':!external' ':!docs' ':!*.md'
src/hydro/hydro.hpp:316:  struct CellVolume {
src/hydro/hydro.hpp:320:  CellVolume _cell_vol;
(exit 0)
## F7
$ git grep -n -w retry_names -- . ':!external' ':!docs' ':!*.md'
src/hydro/flux_register.hpp:102:  std::vector<std::string> const& retry_names() const { return _retry; }
(exit 0)
$ git grep -n -w weight1 -- . ':!external' ':!docs' ':!*.md'
src/hydro/flux_register.hpp:146:  double weight1() const { return _w1; }
(exit 0)
$ git grep -n -w is_ucx -- . ':!external' ':!docs' ':!*.md'
src/layout/process_group.hpp:36:  bool is_ucx() const { return backend == "ucx"; }
(exit 0)
$ git grep -n -F 'started()' -- . ':!external' ':!docs' ':!*.md'
src/diagnostics/budget.hpp:73:  bool started() const { return _started; }
(exit 0)
$ git grep -n -F 'consumer()' -- . ':!external' ':!docs' ':!*.md'
src/output/budget_series.hpp:44:  BudgetConsumer const& consumer() const { return _consumer; }
(exit 0)
$ git grep -n -F 'get_buffer(' -- . ':!external' ':!docs' ':!*.md'
src/eos/aneos.hpp:43:  /*torch::Tensor get_buffer(std::string var) const override {
src/eos/equation_of_state.cpp:222:/*torch::Tensor EquationOfStateImpl::get_buffer(std::string) const {
src/eos/equation_of_state.cpp:223:  TORCH_CHECK(false, "[EquationOfState] get_buffer() is not implemented.",
src/eos/equation_of_state.hpp:154:  // virtual torch::Tensor get_buffer(std::string) const;
src/eos/ideal_gas.hpp:28:  /*torch::Tensor get_buffer(std::string var) const override {
src/eos/ideal_moist.hpp:50:  /*torch::Tensor get_buffer(std::string var) const override {
src/eos/moist_mixture.hpp:29:  /*torch::Tensor get_buffer(std::string var) const override {
src/eos/shallow_water.hpp:24:  /*torch::Tensor get_buffer(std::string var) const override {
src/scalar/scalar.hpp:116:  torch::Tensor get_buffer(std::string var) const {
(exit 0)
## F8
$ git grep -n -w IndexRange -- . ':!external' ':!docs' ':!*.md'
src/coord/coordinate.hpp:25:using IndexRange = std::vector<torch::indexing::TensorIndex>;
(exit 0)
$ git grep -n -w kTPMassLR -- . ':!external' ':!docs' ':!*.md'
src/snap.h:67:  kTPMassLR = 5,  //!< Temperature, pressure, mass with left-right states
(exit 0)
$ git grep -n -w kDPMassLR -- . ':!external' ':!docs' ':!*.md'
src/snap.h:68:  kDPMassLR = 6,  //!< Density, pressure, mass with left-right states
(exit 0)
## F9
$ git grep -n -w kGauge -- . ':!external' ':!docs' ':!*.md'
src/mesh/precision_policy.hpp:20:  kGauge,        // gauges, total face pressure
(exit 0)
$ git grep -n -w kReduction -- . ':!external' ':!docs' ':!*.md'
src/mesh/precision_policy.hpp:21:  kReduction,    // dt, budget and closure sums
(exit 0)
$ git grep -n -w kThermo -- . ':!external' ':!docs' ':!*.md'
src/mesh/precision_policy.hpp:23:  kThermo,       // kintera totals, saturation
(exit 0)
$ git grep -n -w kRegister -- . ':!external' ':!docs' ':!*.md'
src/mesh/precision_policy.hpp:24:  kRegister,     // flux register step accumulator
(exit 0)
$ git grep -n -w kSource -- . ':!external' ':!docs' ':!*.md'
src/mesh/precision_policy.hpp:25:  kSource,       // stage-local source accumulator
(exit 0)
$ git grep -n -w kDiagnostic -- . ':!external' ':!docs' ':!*.md'
src/mesh/precision_policy.hpp:26:  kDiagnostic,   // diagnostic sums
(exit 0)
$ git grep -n -E 'Quantity::k(Gauge|Reduction|Thermo|Register|Source|Diagnostic)|static_cast<Quantity>' -- src python tests examples
tests/test_precision_policy.cpp:23:    auto q = static_cast<Quantity>(i);
(exit 0)
## F10
$ git grep -n -E '/\*torch::Tensor [A-Za-z:]*get_buffer|// virtual torch::Tensor get_buffer|// void pretty_print|pull_neighbors|// op->(thermo|kinetics)\(\)|// printf' -- src
src/eos/aneos.hpp:43:  /*torch::Tensor get_buffer(std::string var) const override {
src/eos/equation_of_state.cpp:222:/*torch::Tensor EquationOfStateImpl::get_buffer(std::string) const {
src/eos/equation_of_state.cpp:305:  //   cons.index(interior)[i] = pull_neighbors3(cons.index(interior)[i]);
src/eos/equation_of_state.cpp:308:  //    pull_neighbors4(cons.index(interior).narrow(0, ICY, nvapor));
src/eos/equation_of_state.hpp:154:  // virtual torch::Tensor get_buffer(std::string) const;
src/eos/ideal_gas.hpp:19:  // void pretty_print(std::ostream& os) const override;
src/eos/ideal_gas.hpp:28:  /*torch::Tensor get_buffer(std::string var) const override {
src/eos/ideal_moist.hpp:27:  // void pretty_print(std::ostream& os) const override;
src/eos/ideal_moist.hpp:50:  /*torch::Tensor get_buffer(std::string var) const override {
src/eos/moist_mixture.hpp:22:  // void pretty_print(std::ostream& os) const override;
src/eos/moist_mixture.hpp:29:  /*torch::Tensor get_buffer(std::string var) const override {
src/eos/shallow_water.hpp:19:  // void pretty_print(std::ostream& os) const override;
src/eos/shallow_water.hpp:24:  /*torch::Tensor get_buffer(std::string var) const override {
src/layout/cubed_sphere_layout.cpp:537:    // printf("lx = %d, ly = %d, dx = %d, dy = %d\n", lx, ly, dx, dy);
src/scalar/scalar_options.cpp:43:  // op->thermo() = kintera::ThermoOptionsImpl::from_yaml(filename);
src/scalar/scalar_options.cpp:44:  // op->kinetics() = kintera::KineticsOptionsImpl::from_yaml(filename);
(exit 0)
## F11
$ git grep -n -w T11 -- src
src/coord/gnomonic_equiangle.cpp:378:  auto T11 = 1.;
src/coord/gnomonic_equiangle.cpp:384:  // w[IVX] = T11 * uu1;
src/coord/gnomonic_equiangle.cpp:398:  auto T11 = 1.;
src/coord/gnomonic_equiangle.cpp:404:  // w[IVX] = T11 * uu1;
src/coord/gnomonic_equiangle.cpp:433:  auto T11 = 1.0;
src/coord/gnomonic_equiangle.cpp:439:  // flux[IVX] = T11 * txx;
src/coord/gnomonic_equiangle.cpp:462:  auto T11 = 1.0;
src/coord/gnomonic_equiangle.cpp:468:  // flux[IVX] = T11 * txx;
(exit 0)
## F12
$ git grep -n -w reset_solve_failure -- . ':!external' ':!docs' ':!*.md'
src/implicit/implicit_hydro.hpp:135:  void reset_solve_failure() { reset_status(); }
src/mesh/meshblock_advance.cpp:142:      phydro->picorr->reset_solve_failure();
(exit 0)
$ git grep -n -w minimum_index -- . ':!external' ':!docs' ':!*.md'
src/hydro/flux_register.cpp:66:int RegisterMonitor::minimum_index(std::string const& name) const {
src/hydro/flux_register.cpp:80:  auto slot = minima[minimum_index(name)];
src/hydro/flux_register.hpp:104:  int minimum_index(std::string const& name) const;
(exit 0)
## F13
$ git grep -n -e cartesian_vector -- . ':!external' ':!docs'
python/snapy/output.pyi:71:    def cartesian_vector(self) -> bool:
python/snapy/output.pyi:73:        `outputs[]/cartesian_vector`."""
python/snapy/output.pyi:77:    def cartesian_vector(self, value: bool) -> "OutputOptions": ...
src/options/output.yaml:21:  - {name: cartesian_vector, key: cartesian_vector, type: bool, default: false, doc: "Write vectors in Cartesian components."}
tests/test_options_table.cpp:69:  EXPECT_FALSE(o.cartesian_vector());
tests/test_options_table.cpp:104:            "* include_ghost_zones = 0\n* cartesian_vector = 0\n"
(exit 0)
$ git grep -n -e data_format -- . ':!external' ':!docs'
python/snapy/output.pyi:125:    def data_format(self) -> str:
python/snapy/output.pyi:126:        """Data format string. Deck key `outputs[]/data_format`."""
python/snapy/output.pyi:130:    def data_format(self, value: str) -> "OutputOptions": ...
src/options/output.yaml:40:  - {name: data_format, key: data_format, type: string, read: if_present, doc: "Data format string."}
tests/test_options_table.cpp:74:  EXPECT_EQ(o.data_format(), "");
tests/test_options_table.cpp:106:            "* x3_slice = []\n* file_type = \n* data_format = \n"
(exit 0)
$ git grep -n -e cartesian-vector -- . ':!external' ':!docs'
(exit 1)
$ git grep -n -e data-format -- . ':!external' ':!docs'
(exit 1)
## F14
$ git grep -n -e 'cpp_' -e 'cylindrical.cpp' -- CMakeLists.txt src/CMakeLists.txt cmake setup.py
cmake/yamlpp.cmake:13:include_directories(${yaml-cpp_SOURCE_DIR}/include)
setup.py:11:from torch.utils import cpp_extension
setup.py:115:ext_module = cpp_extension.CppExtension(
setup.py:128:    cmdclass={"build_ext": cpp_extension.BuildExtension},
(exit 0)
$ git grep -n -w -e vec_from_cartesian -- . ':!external'
src/coord/cylindrical.cpp_:2:torch::TensorList CylindricalImpl::vec_from_cartesian(float vec[3]) {
(exit 0)
$ sed -n '1,7p' src/coord/cylindrical.cpp_

torch::TensorList CylindricalImpl::vec_from_cartesian(float vec[3]) {
  auto theta = x2v.unsqueeze(0).unsqueeze(2);
  auto omega1 = cos(theta) * vec[0] + sin(theta) * vec[1]
  auto omega2 = -sin(theta) * vec[0] + cos(theta) * vec[1];
  auto omega3 = vec[2];
}
## F15
$ grep -n -E 'test_hydro_ref_x1[ .)]|cuda_matches_cpu_on_the_stretched_rows' tests/CMakeLists.txt cmake/macros/macro_setup_test.cmake
tests/CMakeLists.txt:102:setup_test(test_hydro_ref_x1)
tests/CMakeLists.txt:104:         COMMAND test_hydro_ref_x1.${buildl}
tests/CMakeLists.txt:105:                 --gtest_filter=HydroRefX1Dispatch.cuda_matches_cpu_on_the_stretched_rows)
tests/CMakeLists.txt:883:    test_hydro_ref_x1 test_hydro_ref_x1_rf_wall test_gravity_work_cache_to
$ grep -n 'add_test' cmake/macros/macro_setup_test.cmake
33:  add_test(NAME ${namel}.${buildl} COMMAND ${namel}.${buildl})
$ grep -n 'TEST(' tests/test_hydro_ref_x1.cpp
193:TEST(HydroRefX1Dispatch, cpu_matches_tensor_reference) {
216:TEST(HydroRefX1Dispatch, wall_clamp_keeps_the_interior_free_of_the_ghosts) {
235:TEST(HydroRefX1Dispatch, without_the_clamp_the_ghosts_do_reach_the_interior) {
249:TEST(HydroRefX1Dispatch, cuda_matches_cpu) {
331:TEST(HydroRefX1Dispatch, cuda_matches_cpu_on_the_stretched_rows) {
409:TEST(HydroRefX1Dispatch, a_thin_block_keeps_the_interior_free_of_the_ghosts) {
470:TEST(HydroRefX1Dispatch,
508:TEST(HydroRefX1Dispatch, without_the_clamp_a_thin_blocks_ghosts_do_reach_it) {
524:TEST(HydroRefX1Dispatch,
558:TEST(HydroRefX1Dispatch, shared_operator_invalidates_geometry_cache) {
$ git grep -n -E 'ctest.*(-L|--label-regex)' -- . ':!external'
V3_PROGRESS.md:355:- `ctest --test-dir build --output-on-failure -L fp32-foundations`:
V3_PROGRESS.md:408:- `ctest --test-dir build --output-on-failure -L fp32-foundations`:
V3_PROGRESS.md:487:- `ctest --test-dir build --output-on-failure -L fp32-foundations`:
V3_PROGRESS.md:516:- `ctest --test-dir build --output-on-failure -L fp32-foundations`:
V3_PROGRESS.md:559:- `ctest --test-dir build --output-on-failure -L fp32-pressure-scan`:
V3_PROGRESS.md:569:- `ctest --test-dir build --output-on-failure -L fp32-foundations`:
V3_PROGRESS.md:625:- `ctest --test-dir build --output-on-failure -L fp32-dynamics`:
V3_PROGRESS.md:627:- Final `ctest --test-dir build --output-on-failure -L fp32-foundations`:
V3_PROGRESS.md:663:- `ctest --test-dir build --output-on-failure -L fp32-foundations`: **31/31 passed**,
V3_PROGRESS.md:731:- `ctest --test-dir build --output-on-failure -L fp32-foundations`:
V3_PROGRESS.md:745:- `ctest --test-dir build --output-on-failure -L fp32-acceptance`:
V3_PROGRESS.md:765:  above. `ctest --test-dir build --output-on-failure -L fp32-foundations`:
V3_PROGRESS.md:770:- `ctest --test-dir build --output-on-failure -L fp32-acceptance`:
V3_PROGRESS.md:818:- `ctest --test-dir build --output-on-failure -L fp32-foundations`:
V3_PROGRESS.md:820:- `ctest --test-dir build --output-on-failure -L fp32-acceptance`:
V3_PROGRESS.md:862:- `ctest --test-dir build --output-on-failure -L fp32-science`: **1/1 passed**,
V3_PROGRESS.md:863:  8.11 s. `ctest --test-dir build --output-on-failure -L fp32-foundations`:
V3_PROGRESS.md:943:  `ctest --test-dir build --output-on-failure -L 'fp32-(foundations|science|acceptance)'`:
V3_PROGRESS.md:993:- `ctest --test-dir build --output-on-failure -L 'fp32-(foundations|science|acceptance)'`:
V3_ROADMAP.md:358:CUDA_VISIBLE_DEVICES=0 ctest --test-dir build --output-on-failure -L fp32-foundations
docs/derivations/fp32-compute-policy.md:62:`ctest --test-dir build --output-on-failure -L fp32-foundations` includes dtype
docs/derivations/fp32-compute-policy.md:65:`ctest --test-dir build --output-on-failure -L fp32-acceptance` runs 1000-step
docs/derivations/fp32-perturbation-dynamics.md:97:`ctest --test-dir build --output-on-failure -L fp32-dynamics` covers paired
docs/derivations/fp32-restart.md:45:Validation: `ctest --test-dir build --output-on-failure -L fp32-restart` covers
docs/notes/fp32-m6-validation.md:36:ctest --test-dir build --output-on-failure -L fp32-science
docs/notes/fp32-m6-validation.md:37:ctest --test-dir build --output-on-failure -L fp32-foundations
docs/notes/fp32-m6-validation.md:296:ctest --test-dir build --output-on-failure -L 'fp32-(foundations|science|acceptance)'
docs/notes/fp32-straka-speed-plan.md:96:ctest --test-dir build --output-on-failure -L 'fp32-(foundations|science|acceptance)'
(exit 0)
## F16 (see the build-log warnings)
$ git grep -n -w acc_type -- . ':!external' ':!docs' ':!*.md'
src/implicit/implicit_hydro.cpp:24:static torch::ScalarType acc_type(torch::Tensor const& t) {
(exit 0)
$ git grep -n -w fill4 -- . ':!external' ':!docs' ':!*.md'
src/hydro/hydro_forward.cpp:331:  auto fill4 = [&](torch::Tensor a, int c, bool pos, torch::Tensor ref) {
src/recon/well_balanced_x1.cpp:26:  auto fill4 = [&](torch::Tensor a, int c, bool pos, torch::Tensor r) {
src/recon/well_balanced_x1.cpp:57:    fill4(wx1[c], c == IDN ? 2 : 3, true, c == IDN ? dref : pref);
src/recon/well_balanced_x1.cpp:89:    fill4(wx1[IVX], 1, false, {});
(exit 0)
```

## Appendix B. The scratch patch

`git diff -U1 d3178f20 94f6fa99`, without three whole-file deletions
(`src/mesh/mesh_functions.cpp` 30 lines, `src/mesh/mesh_functions.hpp` 16,
`src/coord/cylindrical.cpp_` 7) and the regenerated
`python/snapy/output.pyi` (-17):

```diff
diff --git a/src/bc/bc_func.cpp b/src/bc/bc_func.cpp
index bb5c58f4..49d88836 100644
--- a/src/bc/bc_func.cpp
+++ b/src/bc/bc_func.cpp
@@ -53,3 +53,2 @@ BC_FUNCTION(extrapolation_inner, var, dim, op) {
   if (var.size(dim) == 1) return;
-  int nc = var.size(dim);
   int nghost = op.nghost();
diff --git a/src/bc/rectify_solid.cpp b/src/bc/rectify_solid.cpp
index f00d8933..0f8a8633 100644
--- a/src/bc/rectify_solid.cpp
+++ b/src/bc/rectify_solid.cpp
@@ -113,3 +113,2 @@ torch::Tensor InternalBoundaryImpl::rectify_solid(
   int nc2 = solid_in.size(1);
-  int nc1 = solid_in.size(2);

diff --git a/src/coord/coordinate.hpp b/src/coord/coordinate.hpp
index bcf5bb7c..9b3db044 100644
--- a/src/coord/coordinate.hpp
+++ b/src/coord/coordinate.hpp
@@ -15,3 +15,2 @@
 // snap
-#include <snap/mesh/mesh_functions.hpp>
 #include <snap/utils/tensor_cast_cache.hpp>
@@ -24,3 +23,2 @@ struct LayoutOptionsImpl;
 using LayoutOptions = std::shared_ptr<LayoutOptionsImpl>;
-using IndexRange = std::vector<torch::indexing::TensorIndex>;

diff --git a/src/coord/gnomonic_equiangle.cpp b/src/coord/gnomonic_equiangle.cpp
index ea001522..3466c603 100644
--- a/src/coord/gnomonic_equiangle.cpp
+++ b/src/coord/gnomonic_equiangle.cpp
@@ -372,3 +372,2 @@ void GnomonicEquiangleImpl::prim2local2_(torch::Tensor const& w) const {
   // Extract global projected 4-velocities
-  // auto uu1 = w[IVX].clone();
   auto uu2 = w[IVY];
@@ -377,3 +376,2 @@ void GnomonicEquiangleImpl::prim2local2_(torch::Tensor const& w) const {
   // Calculate transformation matrix
-  auto T11 = 1.;
   auto T22 = 1.0 / gi22.sqrt();
@@ -383,3 +381,2 @@ void GnomonicEquiangleImpl::prim2local2_(torch::Tensor const& w) const {
   // Transform projected velocities
-  // w[IVX] = T11 * uu1;
   w[IVZ] = T32 * uu2 + T33 * uu3;
@@ -392,3 +389,2 @@ void GnomonicEquiangleImpl::prim2local3_(torch::Tensor const& w) const {
   // Extract global projected 4-velocities
-  // auto uu1 = w[IVX].clone();
   auto uu2 = w[IVY];
@@ -397,3 +393,2 @@ void GnomonicEquiangleImpl::prim2local3_(torch::Tensor const& w) const {
   // Calculate transformation matrix
-  auto T11 = 1.;
   auto T22 = g22.sqrt();
@@ -403,3 +398,2 @@ void GnomonicEquiangleImpl::prim2local3_(torch::Tensor const& w) const {
   // Transform projected velocities
-  // w[IVX] = T11 * uu1;
   w[IVY] = T22 * uu2 + T23 * uu3;
@@ -427,3 +421,2 @@ void GnomonicEquiangleImpl::flux2global2_(torch::Tensor const& flux) const {
   // Extract local conserved quantities and fluxes
-  // auto txx = flux[IVX].clone();
   auto txy = flux[IVY];
@@ -432,3 +425,2 @@ void GnomonicEquiangleImpl::flux2global2_(torch::Tensor const& flux) const {
   // Calculate transformation matrix
-  auto T11 = 1.0;
   auto T22 = gi22.sqrt();
@@ -438,3 +430,2 @@ void GnomonicEquiangleImpl::flux2global2_(torch::Tensor const& flux) const {
   // Set fluxes
-  // flux[IVX] = T11 * txx;
   flux[IVZ] = T32 * txy + T33 * txz;
@@ -456,3 +447,2 @@ void GnomonicEquiangleImpl::flux2global3_(torch::Tensor const& flux) const {
   // Extract local conserved quantities and fluxes
-  // auto txx = flux[IVX];
   auto txy = flux[IVY];
@@ -461,3 +451,2 @@ void GnomonicEquiangleImpl::flux2global3_(torch::Tensor const& flux) const {
   // Calculate transformation matrix
-  auto T11 = 1.0;
   auto T22 = 1.0 / g22.sqrt();
@@ -467,3 +456,2 @@ void GnomonicEquiangleImpl::flux2global3_(torch::Tensor const& flux) const {
   // Set fluxes
-  // flux[IVX] = T11 * txx;
   flux[IVY] = T22 * txy + T23 * txz;
diff --git a/src/diagnostics/budget.hpp b/src/diagnostics/budget.hpp
index 7effb369..c50bbca5 100644
--- a/src/diagnostics/budget.hpp
+++ b/src/diagnostics/budget.hpp
@@ -72,3 +72,2 @@ class BudgetConsumer : public Consumer {
   void resume(BudgetCarry const& carry, torch::Device device);
-  bool started() const { return _started; }

diff --git a/src/eos/aneos.hpp b/src/eos/aneos.hpp
index 0d9f0de7..d7adae85 100644
--- a/src/eos/aneos.hpp
+++ b/src/eos/aneos.hpp
@@ -42,6 +42,2 @@ class ANEOSImpl : public EquationOfStateImpl,

-  /*torch::Tensor get_buffer(std::string var) const override {
-    return named_buffers()[var];
-  }*/
-
  private:
diff --git a/src/eos/equation_of_state.cpp b/src/eos/equation_of_state.cpp
index ff49a8de..9d2791d5 100644
--- a/src/eos/equation_of_state.cpp
+++ b/src/eos/equation_of_state.cpp
@@ -221,7 +221,2 @@ torch::Tensor EquationOfStateImpl::compute(

-/*torch::Tensor EquationOfStateImpl::get_buffer(std::string) const {
-  TORCH_CHECK(false, "[EquationOfState] get_buffer() is not implemented.",
-              "Please use this method in a derived class.");
-}*/
-
 bool EquationOfStateImpl::convert_(std::string const& ab,
@@ -303,8 +298,2 @@ void EquationOfStateImpl::apply_conserved_limiter_(torch::Tensor const& cons,

-  // for (int i = ICY; i < ICY + nvapor; ++i)
-  //   cons.index(interior)[i] = pull_neighbors3(cons.index(interior)[i]);
-  //  batched
-  // cons.index(interior).narrow(0, ICY, nvapor) =
-  //    pull_neighbors4(cons.index(interior).narrow(0, ICY, nvapor));
-
   int ny = 0;
@@ -339,3 +328,2 @@ void EquationOfStateImpl::apply_conserved_limiter_(torch::Tensor const& cons,
   if (options->thermo() && ny > 0) {
-    auto nghost = pcoord->options->nghost();
     auto species = [&] { return cons.index(interior).narrow(0, ICY, ny); };
diff --git a/src/eos/equation_of_state.hpp b/src/eos/equation_of_state.hpp
index 34cd83c2..796d80dd 100644
--- a/src/eos/equation_of_state.hpp
+++ b/src/eos/equation_of_state.hpp
@@ -153,4 +153,2 @@ class EquationOfStateImpl {

-  // virtual torch::Tensor get_buffer(std::string) const;
-
   torch::Tensor forward(torch::Tensor cons,
diff --git a/src/eos/ideal_gas.hpp b/src/eos/ideal_gas.hpp
index 597e9bd4..4c3ffebd 100644
--- a/src/eos/ideal_gas.hpp
+++ b/src/eos/ideal_gas.hpp
@@ -18,3 +18,2 @@ class IdealGasImpl final : public torch::nn::Cloneable<IdealGasImpl>,
   void reset() override;
-  // void pretty_print(std::ostream& os) const override;
   using EquationOfStateImpl::forward;
@@ -27,6 +26,2 @@ class IdealGasImpl final : public torch::nn::Cloneable<IdealGasImpl>,

-  /*torch::Tensor get_buffer(std::string var) const override {
-    return named_buffers()[var];
-  }*/
-
   //! \brief Implementation of ideal gas equation of state.
diff --git a/src/eos/ideal_moist.hpp b/src/eos/ideal_moist.hpp
index 8c6fb16f..f0db1de0 100644
--- a/src/eos/ideal_moist.hpp
+++ b/src/eos/ideal_moist.hpp
@@ -26,3 +26,2 @@ class IdealMoistImpl final : public torch::nn::Cloneable<IdealMoistImpl>,
   void reset() override;
-  // void pretty_print(std::ostream& os) const override;
   using EquationOfStateImpl::forward;
@@ -49,6 +48,2 @@ class IdealMoistImpl final : public torch::nn::Cloneable<IdealMoistImpl>,

-  /*torch::Tensor get_buffer(std::string var) const override {
-    return named_buffers()[var];
-  }*/
-
   //! \brief Implementation of ideal gas equation of state.
diff --git a/src/eos/moist_mixture.hpp b/src/eos/moist_mixture.hpp
index ddc13f92..036d7267 100644
--- a/src/eos/moist_mixture.hpp
+++ b/src/eos/moist_mixture.hpp
@@ -21,3 +21,2 @@ class MoistMixtureImpl final : public torch::nn::Cloneable<MoistMixtureImpl>,
   void reset() override;
-  // void pretty_print(std::ostream& os) const override;
   using EquationOfStateImpl::forward;
@@ -28,6 +27,2 @@ class MoistMixtureImpl final : public torch::nn::Cloneable<MoistMixtureImpl>,

-  /*torch::Tensor get_buffer(std::string var) const override {
-    return named_buffers()[var];
-  }*/
-
   //! \brief Implementation of moist mixture equation of state.
diff --git a/src/eos/shallow_water.hpp b/src/eos/shallow_water.hpp
index d203a165..6a382102 100644
--- a/src/eos/shallow_water.hpp
+++ b/src/eos/shallow_water.hpp
@@ -18,3 +18,2 @@ class ShallowWaterImpl final : public torch::nn::Cloneable<ShallowWaterImpl>,
   void reset() override;
-  // void pretty_print(std::ostream& os) const override;
   using EquationOfStateImpl::forward;
@@ -23,6 +22,2 @@ class ShallowWaterImpl final : public torch::nn::Cloneable<ShallowWaterImpl>,

-  /*torch::Tensor get_buffer(std::string var) const override {
-    return named_buffers()[var];
-  }*/
-
   //! \brief Implementation of shallow water equation of state.
diff --git a/src/hydro/flux_register.cpp b/src/hydro/flux_register.cpp
index fecd0e02..057a4ea2 100644
--- a/src/hydro/flux_register.cpp
+++ b/src/hydro/flux_register.cpp
@@ -65,6 +65,2 @@ int RegisterMonitor::counter_index(std::string const& name) const {

-int RegisterMonitor::minimum_index(std::string const& name) const {
-  return index_of(_minimum, name, "minimum");
-}
-
 int RegisterMonitor::retry_index(std::string const& name) const {
@@ -79,3 +75,3 @@ void RegisterMonitor::record_min(std::string const& name,
                                  torch::Tensor const& v) {
-  auto slot = minima[minimum_index(name)];
+  auto slot = minima[index_of(_minimum, name, "minimum")];
   slot.copy_(torch::minimum(slot, v.min().to(minima.scalar_type())));
diff --git a/src/hydro/flux_register.hpp b/src/hydro/flux_register.hpp
index 901c7440..c17e172e 100644
--- a/src/hydro/flux_register.hpp
+++ b/src/hydro/flux_register.hpp
@@ -101,5 +101,3 @@ class RegisterMonitor {
   std::vector<std::string> const& minimum_names() const { return _minimum; }
-  std::vector<std::string> const& retry_names() const { return _retry; }
   int counter_index(std::string const& name) const;
-  int minimum_index(std::string const& name) const;
   int retry_index(std::string const& name) const;
@@ -145,3 +143,2 @@ class FluxRegister {
   void begin_stage(int stage, harp::IntegratorWeight const& w);
-  double weight1() const { return _w1; }
   double weight2() const { return _w2; }
diff --git a/src/hydro/hydro.hpp b/src/hydro/hydro.hpp
index dfa894cb..65fd124f 100644
--- a/src/hydro/hydro.hpp
+++ b/src/hydro/hydro.hpp
@@ -312,10 +312,2 @@ class HydroImpl : public torch::nn::Cloneable<HydroImpl> {
   mutable FaceMoment2 _s2;
-  //! cell_volume() for this block's grid, built on first use by the tracer
-  //! positivity limiter. Holds the three face tensors, so a key tensor
-  //! cannot be freed and its address reused
-  struct CellVolume {
-    torch::Tensor f1, f2, f3, val;
-    int64_t v1 = -1, v2 = -1, v3 = -1;
-  };
-  CellVolume _cell_vol;

diff --git a/src/hydro/hydro_forward.cpp b/src/hydro/hydro_forward.cpp
index 73e1b1e5..ef5149b8 100644
--- a/src/hydro/hydro_forward.cpp
+++ b/src/hydro/hydro_forward.cpp
@@ -330,6 +330,2 @@ torch::Tensor HydroImpl::forward(double dt, torch::Tensor u,
   }
-  auto fill4 = [&](torch::Tensor a, int c, bool pos, torch::Tensor ref) {
-    if (wall4[0] || wall4[1])  // key 2 and wall-less blocks never enter
-      conv4_->fill_walls(a, c, pos, ref, {}, _conv4_trips);
-  };
   bool split_flux = options->perturbation_flux();
diff --git a/src/implicit/implicit_hydro.cpp b/src/implicit/implicit_hydro.cpp
index bddf4d0b..d03f739e 100644
--- a/src/implicit/implicit_hydro.cpp
+++ b/src/implicit/implicit_hydro.cpp
@@ -22,7 +22,2 @@
 namespace snap {
-// screen sums in FP64, except on MPS, which has no FP64
-static torch::ScalarType acc_type(torch::Tensor const& t) {
-  return t.is_mps() ? torch::kFloat32 : torch::kFloat64;
-}
-
 ImplicitOptions ImplicitOptionsImpl::from_yaml(const std::string& filename,
diff --git a/src/implicit/implicit_hydro.hpp b/src/implicit/implicit_hydro.hpp
index 0ef28f41..1d1ea650 100644
--- a/src/implicit/implicit_hydro.hpp
+++ b/src/implicit/implicit_hydro.hpp
@@ -134,3 +134,2 @@ class ImplicitHydroImpl : public torch::nn::Cloneable<ImplicitHydroImpl> {
   bool solve_failed() const { return status().item<bool>(); }
-  void reset_solve_failure() { reset_status(); }

diff --git a/src/layout/cubed_sphere_layout.cpp b/src/layout/cubed_sphere_layout.cpp
index 29dfc240..20e8a783 100644
--- a/src/layout/cubed_sphere_layout.cpp
+++ b/src/layout/cubed_sphere_layout.cpp
@@ -380,13 +380,2 @@ static inline int get_side(std::tuple<int, int, int> const& offset) {

-static inline void cs_clamp_inside(int pxy, int* nx, int* ny) {
-  if (*nx < 0)
-    *nx = 0;
-  else if (*nx >= pxy)
-    *nx = pxy - 1;
-  if (*ny < 0)
-    *ny = 0;
-  else if (*ny >= pxy)
-    *ny = pxy - 1;
-}
-
 static inline void cs_edge_map_into_neighbor(int pxy, int leaving_side,
@@ -489,4 +478,2 @@ void CubedSphereLayoutImpl::_step_one(int face, int rx, int ry, int dx, int dy,
   cs_edge_map_into_neighbor(pxy(), side, pos, &emap, out_rx, out_ry);
-
-  // cs_clamp_inside(pxy, out_rx, out_ry);
 }
@@ -536,3 +523,2 @@ int CubedSphereLayoutImpl::neighbor_rank(
     // do (dx,0) and then (0,dy)
-    // printf("lx = %d, ly = %d, dx = %d, dy = %d\n", lx, ly, dx, dy);
     int f1, x1, y1;
@@ -866,27 +852,2 @@ std::tuple<int, int, int> CubedSphereLayoutImpl::_peer_exchange_offset(

-void CubedSphereLayoutImpl::_interpolate_to_local(
-    MeshBlockImpl const* pmb, std::tuple<int, int, int> offset,
-    torch::Tensor var) const {
-  // my coordinates
-  auto pcoord = pmb->pcoord;
-  auto mesh = torch::meshgrid({pcoord->x3v, pcoord->x2v, pcoord->x1v},
-                              /*indexing=*/"ij");
-
-  auto sub = pmb->part(offset, PartOptions().exterior(true));
-
-  auto x2v = mesh[1].unsqueeze(0).index(sub).squeeze(0);
-  auto x3v = mesh[0].unsqueeze(0).index(sub).squeeze(0);
-
-  auto var_neighbor = var.clone();
-
-  if (options->verbose() && is_root()) {
-    std::cout << "offset = (" << std::get<0>(offset) << ", "
-              << std::get<1>(offset) << ", " << std::get<2>(offset) << ")\n";
-    std::cout << "var from neighbor = \n"
-              << var_neighbor[IDN].squeeze().transpose(0, 1).flip(0) << "\n";
-  }
-
-  //\TODO calculate neighbor coordinates and perform interpolation
-}
-
 }  // namespace snap
diff --git a/src/layout/cubed_sphere_layout.hpp b/src/layout/cubed_sphere_layout.hpp
index d4e17d82..98efd65f 100644
--- a/src/layout/cubed_sphere_layout.hpp
+++ b/src/layout/cubed_sphere_layout.hpp
@@ -64,7 +64,2 @@ class CubedSphereLayoutImpl : public LayoutImpl {

-  //! \brief Interpolate transmitted variable to local ghost zones
-  void _interpolate_to_local(MeshBlockImpl const* pmb,
-                             std::tuple<int, int, int> offset,
-                             torch::Tensor var) const;
-
   torch::Tensor const& _velocity_transform(SyncOptions const& opts,
diff --git a/src/layout/layout.hpp b/src/layout/layout.hpp
index f47085c3..e9c93325 100644
--- a/src/layout/layout.hpp
+++ b/src/layout/layout.hpp
@@ -224,3 +224,2 @@ class LayoutImpl {

-  bool is_root() const { return options->rank() == options->root_rank(); }
   bool use_process_group() const {
diff --git a/src/layout/process_group.hpp b/src/layout/process_group.hpp
index 7876bc34..0e28bbe5 100644
--- a/src/layout/process_group.hpp
+++ b/src/layout/process_group.hpp
@@ -35,3 +35,2 @@ class ProcessGroupContext {

-  bool is_ucx() const { return backend == "ucx"; }
   bool owns_process_group() const { return owns_process_group_; }
diff --git a/src/mesh/meshblock.hpp b/src/mesh/meshblock.hpp
index 13b4eab6..af295329 100644
--- a/src/mesh/meshblock.hpp
+++ b/src/mesh/meshblock.hpp
@@ -290,3 +290,3 @@ class MeshBlockImpl : public torch::nn::Cloneable<MeshBlockImpl> {
   //! into the retry causes by read_redo_flags; built without a host read.
-  //! Drains the saturation-failure count like saturation_failures()
+  //! Drains kintera's saturation-failure count
   torch::Tensor local_redo_flag_tensor(Variables const& vars);
@@ -304,6 +304,2 @@ class MeshBlockImpl : public torch::nn::Cloneable<MeshBlockImpl> {

-  //! drains kintera's count of cells whose saturation adjustment failed since
-  //! the last call (also called at step start); 0 without a ThermoY
-  int64_t saturation_failures();
-
   //! roll back (causes != 0: 1 floor, 2 clamp, 4 limiter, 8 nan,
diff --git a/src/mesh/meshblock_advance.cpp b/src/mesh/meshblock_advance.cpp
index dae33b37..671158c4 100644
--- a/src/mesh/meshblock_advance.cpp
+++ b/src/mesh/meshblock_advance.cpp
@@ -141,3 +141,3 @@ void MeshBlockImpl::advance_local(Variables &vars, double dt, int stage) {
       phydro->picorr->reset_dry_clamp_step();
-      phydro->picorr->reset_solve_failure();
+      phydro->picorr->reset_status();
     }
diff --git a/src/mesh/meshblock_redo.cpp b/src/mesh/meshblock_redo.cpp
index 2260db1d..27c90317 100644
--- a/src/mesh/meshblock_redo.cpp
+++ b/src/mesh/meshblock_redo.cpp
@@ -31,7 +31,2 @@ namespace snap {

-int64_t MeshBlockImpl::saturation_failures() {
-  auto pthermo = thermo();
-  return pthermo ? pthermo->take_saturation_adjustment_failures() : 0;
-}
-
 int MeshBlockImpl::apply_redo(Variables &vars, int causes) {
diff --git a/src/mesh/precision_policy.hpp b/src/mesh/precision_policy.hpp
index 576949b3..930c5a98 100644
--- a/src/mesh/precision_policy.hpp
+++ b/src/mesh/precision_policy.hpp
@@ -19,9 +19,3 @@ enum class Quantity {
   kPrimitive,    // hydro_w totals
-  kGauge,        // gauges, total face pressure
-  kReduction,    // dt, budget and closure sums
   kImplicit,     // vertical implicit solve
-  kThermo,       // kintera totals, saturation
-  kRegister,     // flux register step accumulator
-  kSource,       // stage-local source accumulator
-  kDiagnostic,   // diagnostic sums
   kCount
diff --git a/src/mesh/signal_handler.cpp b/src/mesh/signal_handler.cpp
index 81987091..1cb9ec79 100644
--- a/src/mesh/signal_handler.cpp
+++ b/src/mesh/signal_handler.cpp
@@ -133,14 +133,2 @@ void SignalHandler::SetSignalFlag(int s) {

-//! \brief Set the wall time limit alarm
-void SignalHandler::SetWallTimeAlarm(int t) {
-  alarm(t);
-  return;
-}
-
-//! \brief Cancel the wall time limit alarm
-void SignalHandler::CancelWallTimeAlarm() {
-  alarm(0);
-  return;
-}
-
 }  // namespace snap
diff --git a/src/mesh/signal_handler.hpp b/src/mesh/signal_handler.hpp
index 447ba962..930ab6ca 100644
--- a/src/mesh/signal_handler.hpp
+++ b/src/mesh/signal_handler.hpp
@@ -52,10 +52,2 @@ class SignalHandler {

-  //! \brief Set wall-time alarm
-  //!
-  //! \param[in] t Time in seconds for alarm
-  void SetWallTimeAlarm(int t);
-
-  //! \brief Cancel the wall-time alarm
-  void CancelWallTimeAlarm();
-
  private:
diff --git a/src/options/output.yaml b/src/options/output.yaml
index aa8710eb..9db3484d 100644
--- a/src/options/output.yaml
+++ b/src/options/output.yaml
@@ -20,3 +20,2 @@ options:
   - {name: include_ghost_zones, key: include_ghost_zones, type: bool, default: false, doc: "Write the ghost zones too."}
-  - {name: cartesian_vector, key: cartesian_vector, type: bool, default: false, doc: "Write vectors in Cartesian components."}
   - name: double_precision
@@ -39,3 +38,2 @@ options:
     doc: "Writer: netcdf, pnetcdf, restart or budget (the budget time series)."
-  - {name: data_format, key: data_format, type: string, read: if_present, doc: "Data format string."}
   - {name: variables, key: variables, type: "list[string]", read: if_present, doc: "Variables to write."}
diff --git a/src/output/budget_series.hpp b/src/output/budget_series.hpp
index 34320b0a..607f0f28 100644
--- a/src/output/budget_series.hpp
+++ b/src/output/budget_series.hpp
@@ -43,3 +43,2 @@ class BudgetOutput : public OutputType {

-  BudgetConsumer const& consumer() const { return _consumer; }
   //! the domain record of the last interval (every process holds it)
diff --git a/src/riemann/riemann_kernels.h b/src/riemann/riemann_kernels.h
index 40882069..264af02c 100644
--- a/src/riemann/riemann_kernels.h
+++ b/src/riemann/riemann_kernels.h
@@ -345,3 +345,2 @@ void DISPATCH_MACRO roe_impl(T* flx, T const* wl, T const* wr, T el, T er,

-  T du0 = WR(IDN) - WL(IDN);
   T du1 = WR(IDN) * WR(ivx) - WL(IDN) * WL(ivx);
diff --git a/src/scalar/scalar.hpp b/src/scalar/scalar.hpp
index 7476bffd..0259c939 100644
--- a/src/scalar/scalar.hpp
+++ b/src/scalar/scalar.hpp
@@ -115,6 +115,2 @@ class ScalarImpl : public torch::nn::Cloneable<ScalarImpl> {

-  torch::Tensor get_buffer(std::string var) const {
-    return named_buffers()[var];
-  }
-
   //! Advance the conserved variables by one time step.
diff --git a/src/scalar/scalar_options.cpp b/src/scalar/scalar_options.cpp
index feb9192f..f94069df 100644
--- a/src/scalar/scalar_options.cpp
+++ b/src/scalar/scalar_options.cpp
@@ -42,5 +42,2 @@ ScalarOptions ScalarOptionsImpl::from_yaml(std::string const& filename,

-  // op->thermo() = kintera::ThermoOptionsImpl::from_yaml(filename);
-  // op->kinetics() = kintera::KineticsOptionsImpl::from_yaml(filename);
-
   if (node["riemann-solver"]) {
diff --git a/src/snap.h b/src/snap.h
index 384c0ba3..81354856 100644
--- a/src/snap.h
+++ b/src/snap.h
@@ -64,6 +64,2 @@ enum {
   kScalar = 2,     //!< Scalar variables
-
-  // temperature, pressure, mass fraction with LR states
-  kTPMassLR = 5,  //!< Temperature, pressure, mass with left-right states
-  kDPMassLR = 6,  //!< Density, pressure, mass with left-right states
 };
diff --git a/tests/CMakeLists.txt b/tests/CMakeLists.txt
index 144d1add..31a3240e 100644
--- a/tests/CMakeLists.txt
+++ b/tests/CMakeLists.txt
@@ -102,7 +102,2 @@ setup_test(test_balance_column)
 setup_test(test_hydro_ref_x1)
-add_test(NAME test_hydro_ref_x1_stretched_cuda.${buildl}
-         COMMAND test_hydro_ref_x1.${buildl}
-                 --gtest_filter=HydroRefX1Dispatch.cuda_matches_cpu_on_the_stretched_rows)
-set_tests_properties(test_hydro_ref_x1_stretched_cuda.${buildl}
-                     PROPERTIES TIMEOUT 120 LABELS "hydro;gpu")
 setup_test(test_uranus_cycle1_abort)
diff --git a/tests/test_options_table.cpp b/tests/test_options_table.cpp
index 3401fee0..0f616f7a 100644
--- a/tests/test_options_table.cpp
+++ b/tests/test_options_table.cpp
@@ -68,3 +68,2 @@ TEST(options_table, pin_defaults) {
   EXPECT_FALSE(o.include_ghost_zones());
-  EXPECT_FALSE(o.cartesian_vector());
   EXPECT_TRUE(o.x1_slice().empty());
@@ -73,3 +72,2 @@ TEST(options_table, pin_defaults) {
   EXPECT_EQ(o.file_type(), "");
-  EXPECT_EQ(o.data_format(), "");
   EXPECT_TRUE(o.variables().empty());
@@ -103,5 +101,5 @@ TEST(options_table, pin_report) {
             "* output_sumx2 = 0\n* output_sumx3 = 0\n"
-            "* include_ghost_zones = 0\n* cartesian_vector = 0\n"
+            "* include_ghost_zones = 0\n"
             "* double_precision = 0\n* x1_slice = []\n* x2_slice = []\n"
-            "* x3_slice = []\n* file_type = \n* data_format = \n"
+            "* x3_slice = []\n* file_type = \n"
             "* variables = []\n* combine = 1\n* verbose = 0\n");
```

## Appendix C. The scripts

They ran on dungeon3. `$W` stands for the audit's work folder there.
`$VENV367` (PyTorch 2.10.0+cu128) and `$VENV_EF34` (pyharp 2.7.17, pydisort
1.7.1) are the read-only environments of the earlier C.trim gate. `kt/` is
the kintera 2.6.11 target directory.

### build.sh

```bash
#!/bin/bash
# build.sh <tree>: CPU Release build, the C.trim gate's flags plus g++'s
# unused-entity warnings (they change no generated code).
set -u
T=$(cd "$1" && pwd)
VENV=$VENV367
SP=$(ls -d "$VENV"/lib*/python3*/site-packages | while read d; do [ -d "$d/torch" ] && echo "$d" && break; done)
H17=$VENV_EF34; HSP=$H17/lib64/python3.11/site-packages
KT=$W/kt
export PYTHONPATH=$KT PATH=$H17/bin:$VENV/bin:$PATH LD_LIBRARY_PATH=$KT/kintera/lib:$SP/torch/lib:$HSP/pyharp/lib:$HSP/pydisort/lib
export CPATH=$HSP/pyharp/include LIBRARY_PATH=$HSP/pyharp/lib
PY=$H17/bin/python
cd "$T" && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DNETCDF=ON -DBUILD_TESTS=ON \
  -DFULL_TESTS=OFF -DCUDA=OFF -DPython3_EXECUTABLE="$PY" \
  -DCMAKE_CXX_FLAGS="-Wunused -Wunused-but-set-variable -Wunused-const-variable=1 -Wunused-macros" \
  -DCMAKE_PREFIX_PATH="$SP/torch/share/cmake" -DSNAPY_TEST_PYTHONPATH="$KT:$HSP:$SP" > "$T/../configure-$(basename $T).log" 2>&1 &&
cmake --build build --parallel 12 > "$T/../build-$(basename $T).log" 2>&1
rc=$?; echo "build $(basename $T) $(git -C $T rev-parse HEAD) rc=$rc $(date -u +%FT%TZ)"
```

### ctest.sh

```bash
#!/bin/bash
# ctest.sh <tree> <port>: the C.trim gate's serial C++ ctest selection
T=$(cd "$1" && pwd)
VENV=$VENV367
SP=$(ls -d "$VENV"/lib*/python3*/site-packages | while read d; do [ -d "$d/torch" ] && echo "$d" && break; done)
H17=$VENV_EF34; HSP=$H17/lib64/python3.11/site-packages
KT=$W/kt
export PYTHONPATH=$KT PATH=$H17/bin:$VENV/bin:$PATH LD_LIBRARY_PATH=$KT/kintera/lib:$SP/torch/lib:$HSP/pyharp/lib:$HSP/pydisort/lib
export CUDA_VISIBLE_DEVICES= PET_MASTER_PORT=$2 OMP_NUM_THREADS=4
cd "$T/build" && ctest -j 1 -R '^test_' -E '_python$|cuda|gpu' --timeout 900 --output-on-failure > "$T/../ctest-$(basename $T).log" 2>&1
echo "ctest $(basename $T) $(git -C $T rev-parse HEAD) rc=$? $(grep -E 'tests passed' "$T/../ctest-$(basename $T).log") $(date -u +%FT%TZ)"
```

### netlines.sh

```bash
#!/bin/bash
# netlines.sh: DESIGN 6.1's count (every .cpp/.hpp/.h/.cu/.cuh under src/,
# wc -l) at the pin and at each scratch commit; net = count(c) - count(c^).
count() { git ls-tree -r --name-only $1 -- src | grep -E '\.(cpp|hpp|h|cu|cuh)$' \
  | while read f; do git cat-file -p $1:$f | wc -l; done | awk '{s+=$1} END{print s}'; }
P=d3178f207b60663ff966b7c7ef20025821ef52fa
echo "pin $P $(count $P)"
for c in $(git rev-list --reverse $P..audit2-scratch-local); do
  a=$(count $c^); b=$(count $c)
  other=$(git diff --numstat $c^ $c | awk '$3 !~ /^src\/.*\.(cpp|hpp|h|cu|cuh)$/ {printf "%s:+%s/-%s ", $3, $1, $2}')
  printf "%s %s net %+d  other: %s\n" "$(git log -1 --format=%h $c)" "$(git log -1 --format=%s $c | cut -d' ' -f1)" $((b-a)) "$other"
done
T=$(git rev-parse audit2-scratch-local); echo "all $T $(count $T) net $(( $(count $T) - $(count $P) ))"
```

### evidence.sh

```bash
#!/bin/bash
# evidence.sh: the grep evidence of every finding, run in a clean checkout of
# the pin. g NAME: every whole-word use outside external/ and docs/.
cd "$(dirname "$0")/../A"
echo "\$ git rev-parse HEAD; git status --porcelain | wc -l"
git rev-parse HEAD; git status --porcelain | wc -l
g() { echo "\$ git grep -n -w $1 -- . ':!external' ':!docs' ':!*.md'"; git grep -n -w "$1" -- . ':!external' ':!docs' ':!*.md'; echo "(exit $?)"; }
echo "## F1"; g compute_logical_position; g MeshGenerator; g mesh_functions
echo "## F2"; g _interpolate_to_local; g is_root
echo "## F3"; g SetWallTimeAlarm; g CancelWallTimeAlarm
echo "## F4"; g saturation_failures
echo "## F5"; g cs_clamp_inside
echo "## F6"; g _cell_vol; g CellVolume
echo "## F7"; g retry_names; g weight1; g is_ucx
for m in 'started()' 'consumer()' 'get_buffer('; do echo "\$ git grep -n -F '$m' -- . ':!external' ':!docs' ':!*.md'"; git grep -n -F "$m" -- . ':!external' ':!docs' ':!*.md'; echo "(exit $?)"; done
echo "## F8"; g IndexRange; g kTPMassLR; g kDPMassLR
echo "## F9"; for q in kGauge kReduction kThermo kRegister kSource kDiagnostic; do g $q; done
echo "\$ git grep -n -E 'Quantity::k(Gauge|Reduction|Thermo|Register|Source|Diagnostic)|static_cast<Quantity>' -- src python tests examples"
git grep -n -E 'Quantity::k(Gauge|Reduction|Thermo|Register|Source|Diagnostic)|static_cast<Quantity>' -- src python tests examples; echo "(exit $?)"
echo "## F10"
P='/\*torch::Tensor [A-Za-z:]*get_buffer|// virtual torch::Tensor get_buffer|// void pretty_print|pull_neighbors|// op->(thermo|kinetics)\(\)|// printf'
echo "\$ git grep -n -E '$P' -- src"; git grep -n -E "$P" -- src; echo "(exit $?)"
echo "## F11"; echo "\$ git grep -n -w T11 -- src"; git grep -n -w T11 -- src; echo "(exit $?)"
echo "## F12"; g reset_solve_failure; g minimum_index
echo "## F13"; for o in cartesian_vector data_format cartesian-vector data-format; do echo "\$ git grep -n -e $o -- . ':!external' ':!docs'"; git grep -n -e $o -- . ':!external' ':!docs'; echo "(exit $?)"; done
echo "## F14"; echo "\$ git grep -n -e 'cpp_' -e 'cylindrical.cpp' -- CMakeLists.txt src/CMakeLists.txt cmake setup.py"; git grep -n -e 'cpp_' -e 'cylindrical.cpp' -- CMakeLists.txt src/CMakeLists.txt cmake setup.py; echo "(exit $?)"
echo "\$ git grep -n -w -e vec_from_cartesian -- . ':!external'"; git grep -n -w -e vec_from_cartesian -- . ':!external'; echo "(exit $?)"
echo "\$ sed -n '1,7p' src/coord/cylindrical.cpp_"; sed -n '1,7p' src/coord/cylindrical.cpp_
echo "## F15"; echo "\$ grep -n -E 'test_hydro_ref_x1[ .)]|cuda_matches_cpu_on_the_stretched_rows' tests/CMakeLists.txt cmake/macros/macro_setup_test.cmake"
grep -n -E 'test_hydro_ref_x1[ .)]|cuda_matches_cpu_on_the_stretched_rows' tests/CMakeLists.txt cmake/macros/macro_setup_test.cmake
echo "\$ grep -n 'add_test' cmake/macros/macro_setup_test.cmake"; grep -n 'add_test' cmake/macros/macro_setup_test.cmake
echo "\$ grep -n 'TEST(' tests/test_hydro_ref_x1.cpp"; grep -n 'TEST(' tests/test_hydro_ref_x1.cpp
echo "\$ git grep -n -E 'ctest.*(-L|--label-regex)' -- . ':!external'"; git grep -n -E 'ctest.*(-L|--label-regex)' -- . ':!external'; echo "(exit $?)"
echo "## F16 (see the build-log warnings)"; g acc_type; g fill4
```

### decks.py

```python
# Short copies of five example decks: nlim N, every output's dt set to D,
# pnetcdf written as netcdf. decks.py <examples dir> <out dir>
import sys, yaml, os
src, out = sys.argv[1:3]; os.makedirs(out, exist_ok=True)
plan = {"shock.yaml": (40, 0.005), "straka_single.yaml": (100, 5.0),
        "jupiter_evap_precip_1d.yaml": (30, 1.0), "shallow_xy_single.yaml": (40, 0.1),
        "shallow_splash_mesh6.yaml": (20, 100.0)}
for f, (n, d) in plan.items():
    y = yaml.safe_load(open(os.path.join(src, f)))
    y["integration"]["nlim"] = n
    for o in y.get("outputs", []):
        if o.get("type") == "pnetcdf": o["type"] = "netcdf"
        if d is not None: o["dt"] = d
    yaml.safe_dump(y, open(os.path.join(out, f), "w"), sort_keys=False)
    print(f, n, d, [ (o.get("type"), o.get("dt")) for o in y.get("outputs", [])])
```

### rundecks.sh

```bash
#!/bin/bash
# rundecks.sh <tree>: the five short decks with <tree>'s example binaries,
# each in its own directory under runs-<tree>/ (CPU, 4 threads)
T=$(cd "$1" && pwd); W=$(cd "$(dirname "$0")" && pwd)
VENV=$VENV367
SP=$(ls -d "$VENV"/lib*/python3*/site-packages | while read d; do [ -d "$d/torch" ] && echo "$d" && break; done)
H17=$VENV_EF34; HSP=$H17/lib64/python3.11/site-packages
KT=$W/../kt
export LD_LIBRARY_PATH=$KT/kintera/lib:$SP/torch/lib:$HSP/pyharp/lib:$HSP/pydisort/lib CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=4
R=$W/../runs-$(basename $T); rm -rf $R; mkdir -p $R
for d in shock:shock straka:straka_single jupiter_evap_precip_1d:jupiter_evap_precip_1d shallow_xy:shallow_xy_single shallow_splash:shallow_splash_mesh6; do
  exe=${d%%:*}; deck=${d#*:}; mkdir -p $R/$deck; cd $R/$deck
  cp $W/decks/$deck.yaml .; ln -s $KT/kintera/data/* .  # kintera looks in '.'
  timeout 1800 $T/build/bin/$exe.release $deck.yaml > run.log 2>&1
  echo "$deck rc=$? files=$(find . -type f ! -name '*.yaml' ! -name run.log | wc -l)"
done
```

### cmpdecks.sh

```bash
#!/bin/bash
# cmpdecks.sh: every output file of runs-A against runs-B with cmp; the
# run logs compared with the timing columns removed
cd "$(dirname "$0")/.."
n=0; same=0
for f in $(cd runs-A && find . -type f ! -name '*.yaml' ! -name run.log ! -name '*.dat' | sort); do
  n=$((n+1)); if cmp -s runs-A/$f runs-B/$f; then same=$((same+1)); else echo "DIFFER $f"; fi
done
echo "only in B: $(cd runs-B && find . -type f ! -name '*.yaml' ! -name run.log ! -name '*.dat' | sort | comm -13 <(cd ../runs-A && find . -type f ! -name '*.yaml' ! -name run.log ! -name '*.dat' | sort) - | wc -l)"
echo "files $n byte-identical $same"
for d in runs-A/*/; do d=$(basename $d)
  a=$(grep -v -E '^frame|time|Time|sec|wall|[0-9]+\.[0-9]+ ?s\b' runs-A/$d/run.log | sed 's#/A/#/T/#g' | md5sum | cut -c1-12)
  b=$(grep -v -E '^frame|time|Time|sec|wall|[0-9]+\.[0-9]+ ?s\b' runs-B/$d/run.log | sed 's#/B/#/T/#g' | md5sum | cut -c1-12)
  echo "$d log(filtered) A=$a B=$b $([ $a = $b ] && echo same || echo DIFFER)"
done
```

### verdicts.sh

```bash
#!/bin/bash
# verdicts.sh: each ctest entry's name and verdict, A against B
cd "$(dirname "$0")/.."
status() { grep -E '^ *[0-9]+/[0-9]+ Test +#[0-9]+: ' "$1" | sed -E 's/^ *[0-9]+\/[0-9]+ Test +#[0-9]+: ([^ ]+) \.+ *([A-Za-z*]+( [A-Za-z]+)?).*/\1 \2/' | sort; }
diff <(status ctest-A.log) <(status ctest-B.log); echo "diff exit $?"
status ctest-B.log | cut -d' ' -f2 | sort | uniq -c
```

### idx_lib.py

```python
import os, re, subprocess, collections
csrc = re.compile(r'\.(cpp|hpp|h|cu|cuh)$')
def strip_c(s, keep_str=True):
    out=[];i=0;n=len(s)
    while i<n:
        if s.startswith('//',i):
            j=s.find('\n',i); i=n if j<0 else j
        elif s.startswith('/*',i):
            j=s.find('*/',i+2); i=n if j<0 else j+2
        elif s[i]=='"':
            j=i+1
            while j<n and s[j]!='"': j+= 2 if s[j]=='\\' else 1
            out.append(s[i:j+1] if keep_str else '""'); i=j+1
        elif s[i]=="'" and i+2<n and (s[i+1]!='\\' and s[i+2]=="'" or s[i+1]=='\\'):
            j=s.find("'",i+2); out.append(s[i:j+1]); i=j+1
        else:
            out.append(s[i]); i+=1
    return ''.join(out)
def strip_py(s):
    s=re.sub(r'(?s)# BEGIN generated.*?# END generated[^\n]*','',s)
    return re.sub(r'#[^\n]*','',s)
def load(root):
    files = subprocess.check_output(['git','-C',root,'ls-files'], text=True).split()
    toks=collections.defaultdict(collections.Counter); texts={}
    for f in files:
        if f.split('/')[0] in ('external','docs','.github','patches','.cache') or f.startswith('src/options/'): continue
        p=os.path.join(root,f)
        if not os.path.isfile(p): continue
        if csrc.search(f): s=strip_c(open(p,errors='replace').read())
        elif f.endswith(('.py','.pyi')): s=strip_py(open(p,errors='replace').read())
        else: continue
        texts[f]=s
        for t in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', s): toks[t][f]+=1
    return toks, texts
```

### idx.py (search 1)

```python
# Token-count index: for each identifier that occurs in src/, count its
# occurrences in src/, and in the rest of the consumers (python/, tests/,
# examples/, external/ excluded). Comments and string literals are stripped
# for C/C++ so a name mentioned only in prose is not a use.
import os, re, sys, collections, subprocess
root = sys.argv[1]
files = subprocess.check_output(['git','-C',root,'ls-files'], text=True).split()
csrc = re.compile(r'\.(cpp|hpp|h|cu|cuh|cpp_)$')
def strip_c(s):
    out=[];i=0;n=len(s)
    while i<n:
        c=s[i]
        if s.startswith('//',i):
            j=s.find('\n',i); i=n if j<0 else j
        elif s.startswith('/*',i):
            j=s.find('*/',i+2); i=n if j<0 else j+2
        elif c=='"' :
            # keep string contents: option keys are read via strings
            j=i+1
            while j<n and s[j]!='"':
                j+= 2 if s[j]=='\\' else 1
            out.append(s[i:j+1]); i=j+1
        else:
            out.append(c); i+=1
    return ''.join(out)
tok=re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
cnt={ 'src':collections.Counter(), 'other':collections.Counter() }
where=collections.defaultdict(set)
for f in files:
    top=f.split('/')[0]
    if top in ('external','docs','.github','patches','.cache'): continue
    p=os.path.join(root,f)
    if not os.path.isfile(p): continue
    try: s=open(p,errors='replace').read()
    except: continue
    if csrc.search(f): s=strip_c(s)
    elif not re.search(r'\.(py|pyi|yaml|yml|txt|cmake|in)$',f) and 'CMakeLists' not in f: continue
    k='src' if top=='src' else 'other'
    for t in tok.findall(s):
        cnt[k][t]+=1; where[t].add(f)
for t,c in cnt['src'].items():
    print(f"{c}\t{cnt['other'][t]}\t{len(where[t])}\t{t}\t{' '.join(sorted(where[t])[:4])}")
```

### defs.py (search 2)

```python
# Every function or method name defined or declared in src/ C/C++ (a name
# followed by '(' at a declaration position), with its total token count in
# the repo (src + python + tests + examples, comments stripped).
import re, sys, collections
sys.path.insert(0,'work'); from idx_lib import load
toks, texts = load(sys.argv[1])
decl = re.compile(r'(?m)^[ \t]*(?:(?:static|inline|virtual|constexpr|explicit|friend|DISPATCH_MACRO|template\s*<[^>]*>|__host__|__device__|__global__)\s+)*[\w:<>,\*&\s]*?[\s\*&:](~?\w+)\s*\([^;{)]*(?:\)[^;{]*)?[;{]')
seen = collections.defaultdict(set)
for f, s in texts.items():
    if not f.startswith('src/'): continue
    for m in decl.finditer(s):
        n = m.group(1)
        if n in ('if','for','while','switch','return','sizeof','decltype','catch','operator'): continue
        seen[n].add(f)
for n, fs in sorted(seen.items()):
    tot = sum(toks[n].values()); src = sum(c for f,c in toks[n].items() if f.startswith('src/'))
    print(f"{tot}\t{src}\t{n}\t{' '.join(f'{f}:{c}' for f,c in sorted(toks[n].items()))}")
```

### opts.py (search 3)

```python
# For each src/options/*.yaml row: occurrences of the row name as a C++/Python
# token outside src/options and the generated .pyi blocks, and occurrences of
# its deck key in any tracked .yaml outside src/options.
import re, sys, subprocess, yaml, os
sys.path.insert(0, 'work'); from idx_lib import load
root = sys.argv[1]
toks, texts = load(root)
files = subprocess.check_output(['git','-C',root,'ls-files'], text=True).split()
decks = [f for f in files if f.endswith(('.yaml','.yml')) and not f.startswith(('src/options','.github','docs','external'))]
deck_txt = {f: open(os.path.join(root,f)).read() for f in decks}
for p in sorted(os.listdir(f'{root}/src/options')):
    for d in yaml.safe_load_all(open(f'{root}/src/options/{p}')):
        if not d: continue
        for r in d['options']:
            n = r['name']; key = r.get('key') or ''
            uses = {f:c for f,c in toks.get(n, {}).items()}
            k = key.split('/')[-1] if key else ''
            nd = sum(1 for f,t in deck_txt.items() if k and re.search(r'(^|\s)'+re.escape(k)+r'\s*:', t, re.M))
            print(f"{p}\t{n}\t{key}\t{sum(uses.values())}\t{nd}\t{' '.join(f'{f}:{c}' for f,c in sorted(uses.items()))}")
```

### addarg.py (search 3)

```python
# ADD_ARG(T, name) fields in src/: every use of `name` as a token outside its
# ADD_ARG line, over src + python + tests + examples (comments stripped).
import re, sys, collections
sys.path.insert(0,'work'); from idx_lib import load
toks, texts = load(sys.argv[1])
for f, s in sorted(texts.items()):
    if not f.startswith('src/'): continue
    for m in re.finditer(r'ADD_ARG\(\s*([^,]+?)\s*,\s*(\w+)\s*\)', s):
        n = m.group(2); c = toks[n].copy(); c[f] -= 1
        tot = sum(c.values())
        if tot <= 99:
            print(f"{tot}\t{f}:{s[:m.start()].count(chr(10))+1}\t{n}\t{' '.join(f'{k}:{v}' for k,v in sorted(c.items()) if v)}")
```

### wrappers.py (search 4)

```python
# One-statement functions in src/ (body is a single `return g(...)` or a
# single call `g(...);`) with exactly one use of their name outside the
# definition/declaration, over src + python + tests + examples.
import re, sys, collections
sys.path.insert(0,'work'); from idx_lib import load
toks, texts = load(sys.argv[1])
defn = re.compile(r'(?:[\w:<>,\*&]+\s+)+?(?:\w+::)?(~?\w+)\s*\(([^;{}()]*(?:\([^()]*\)[^;{}()]*)*)\)\s*(?:const)?\s*(?:noexcept)?\s*(?:override)?\s*\{\s*((?:return\s+)?[\w:\->\.]+(?:<[^;{}]*>)?\s*\([^;{}]*\)\s*;)\s*\}')
for f, s in texts.items():
    if not f.startswith('src/'): continue
    for m in defn.finditer(s):
        n = m.group(1)
        if n in ('if','for','while','switch'): continue
        tot = sum(toks[n].values())
        line = s[:m.start()].count('\n') + 1
        if tot <= 4:
            body = re.sub(r"\s+", " ", m.group(3))[:90]
            print(f"{tot}\t{f}:{line}\t{n}\t{body}")
```

### duptests.py (search 7)

```python
# Duplicate gtest bodies: every TEST/TEST_F/TEST_P in tests/*.cpp, body
# normalised (comments stripped, whitespace collapsed); groups of equal bodies.
import re, sys, glob, collections, os
sys.path.insert(0,'work'); from idx_lib import strip_c
root=sys.argv[1]; groups=collections.defaultdict(list); n=0
for f in sorted(glob.glob(f'{root}/tests/**/*.cpp', recursive=True)):
    s=strip_c(open(f).read())
    for m in re.finditer(r'\bTEST(?:_F|_P)?\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*\{', s):
        i=m.end(); d=1
        while d and i<len(s):
            d += {'{':1,'}':-1}.get(s[i],0); i+=1
        body=re.sub(r'\s+',' ',s[m.end():i-1]).strip()
        n+=1; groups[body].append(f"{os.path.relpath(f,root)}:{s[:m.start()].count(chr(10))+1} {m.group(1)}.{m.group(2)}")
print('gtest cases', n)
for b,v in groups.items():
    if len(v)>1: print(len(v), len(b), v)
```

### del.sh (applies a finding in the scratch tree)

```bash
# del.sh FILE A-B [C-D ...]: delete the inclusive line ranges (bottom-up)
f=$1; shift
for r in $(printf '%s\n' "$@" | sort -t- -k1,1nr); do sed -i "${r%-*},${r#*-}d" "$f"; done
```
