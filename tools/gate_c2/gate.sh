#!/bin/bash
# V3 wave 1, lane C step C2: CPU comparison gate and OnHost probe.
#
#   tools/gate_c2/gate.sh <work_dir> [<sha_a> <sha_b>]
#
# sha_a defaults to C1 (54aa6ccb), sha_b to C2 (674bfdbc). The script fetches
# both from happysky19/snapy, builds each on CPU, and checks:
#   1. ctest: serial C++ entries, same verdict per test on A and B
#   2. decks: 5 example decks, 20 steps, every restart file byte-identical,
#      every netCDF variable byte-equal, every cycle line identical, and the
#      same exit code on A and B
#   3. probe: each kernel C2 registers for MPS, run through OnHost on CUDA
#      tensors, equals the same CPU kernel on CPU tensors (B only; needs a
#      CUDA GPU visible to torch, else skipped)
# Environment: VENV = a Python venv with torch 2.10, kintera >= 2.6.9, pyharp,
# pydisort, netCDF4 and PyYAML (default: the dungeon3 venv below).
# Exit status: 0 when every check passes.
set -u
here=$(cd "$(dirname "$0")" && pwd)
W=$(mkdir -p "$1" && cd "$1" && pwd)
A=${2:-54aa6ccb0d5892ae3799d35fcec74fe4ec1d18cf}
B=${3:-674bfdbcac0981c082617b03ae7b196872b76e5b}
VENV=${VENV:-/data02/tianhaol/fridica-snapy/worker1/pr367-review-20261116/.venv367}
REPO=${REPO:-https://github.com/happysky19/snapy.git}
JOBS=${JOBS:-12}
SP=$(ls -d "$VENV"/lib*/python3*/site-packages | while read d; do
  [ -d "$d/torch" ] && echo "$d" && break; done)
export PATH=$VENV/bin:$PATH
export LD_LIBRARY_PATH=$SP/torch/lib:$SP/pyharp/lib:$SP/kintera/lib:${LD_LIBRARY_PATH:-}
export CPATH=$SP/pyharp/include:${CPATH:-} LIBRARY_PATH=$SP/pyharp/lib:${LIBRARY_PATH:-}
PY=$VENV/bin/python
L=$W/logs; mkdir -p "$L"
fail=0
say() { echo "$*" | tee -a "$L/summary.txt"; }

say "gate_c2 $(date -u +%FT%TZ) host=$(hostname -s)"
say "A=$A B=$B venv=$VENV"
say "torch=$($PY -c 'import torch;print(torch.__version__)') kintera=$($PY -c 'import kintera;print(kintera.__version__)') cxx=$(c++ --version | head -1)"

# ---- fetch and build -------------------------------------------------------
[ -d "$W/src/.git" ] || git clone -q "$REPO" "$W/src"
git -C "$W/src" fetch -q origin "$A" "$B"
for T in A B; do
  sha=${!T}
  [ -d "$W/tree-$T" ] || git -C "$W/src" worktree add -q --detach "$W/tree-$T" "$sha"
  git -C "$W/tree-$T" checkout -q --detach "$sha"
  say "$T tree $(git -C "$W/tree-$T" rev-parse HEAD)"
  (cd "$W/tree-$T" &&
   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DNETCDF=ON -DBUILD_TESTS=ON \
     -DFULL_TESTS=OFF -DCUDA=OFF -DPython3_EXECUTABLE="$PY" \
     -DCMAKE_PREFIX_PATH="$SP/torch/share/cmake" -DSNAPY_TEST_PYTHONPATH="$SP" \
     > "$L/configure-$T.log" 2>&1 &&
   cmake --build build --parallel "$JOBS" > "$L/build-$T.log" 2>&1)
  rc=$?
  say "$T build rc=$rc warnings=$(grep -c 'warning:' "$L/build-$T.log")"
  [ $rc -eq 0 ] || exit 2
done

# ---- 1. ctest --------------------------------------------------------------
for T in A B; do
  (cd "$W/tree-$T/build" && CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 \
     ctest -j 1 -R '^test_' -E '_python$|cuda|gpu' --timeout 900 \
     --output-on-failure > "$L/ctest-$T.log" 2>&1)
  say "$T ctest rc=$? $(grep -E 'tests passed' "$L/ctest-$T.log")"
done
status() { grep -oE 'Test +#[0-9]+: \S+ \.+ *\**\S+' "$1" | awk '{print $3, $NF}' | sort; }
if diff <(status "$L/ctest-A.log") <(status "$L/ctest-B.log") > "$L/ctest-diff.txt" &&
   grep -q '100% tests passed' "$L/ctest-B.log"; then
  say "PASS ctest: $(status "$L/ctest-B.log" | wc -l) tests, same verdict per test, all pass"
else
  say "FAIL ctest: see logs/ctest-diff.txt"; fail=1
fi

# ---- 2. decks --------------------------------------------------------------
$PY "$here/make_decks.py" "$W/tree-A/examples" "$W/decks" | tee -a "$L/summary.txt"
for T in A B; do
  CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=4 bash "$here/run_decks.sh" \
    "$W/tree-$T" "$W/decks" "$W/runs/$T" "$SP" | tee -a "$L/summary.txt"
done
if $PY "$here/compare_runs.py" "$W/runs/A" "$W/runs/B" > "$L/compare.txt" 2>&1; then
  say "PASS decks: $(tail -1 "$L/compare.txt")"
else
  say "FAIL decks: $(tail -1 "$L/compare.txt")"; fail=1
fi

# ---- 3. OnHost probe (B) ---------------------------------------------------
if $PY -c 'import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)'; then
  bash "$here/build_probe.sh" "$W/tree-B" "$W/probe" "$here/onhost_probe.cpp" \
    > "$L/probe-build.log" 2>&1
  if "$W/probe/onhost_probe" > "$L/probe.txt" 2>&1; then
    say "PASS probe: $(tail -1 "$L/probe.txt")"
  else
    say "FAIL probe: $(tail -1 "$L/probe.txt")"; fail=1
  fi
else
  say "SKIP probe: no CUDA device visible to torch"
fi

say "gate_c2 result: $([ $fail -eq 0 ] && echo PASS || echo FAIL)"
exit $fail
