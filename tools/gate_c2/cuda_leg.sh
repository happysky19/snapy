#!/bin/bash
# CUDA leg of the C2 gate, with the shared #349 dump set.
#
#   tools/gate_c2/cuda_leg.sh <work_dir> <sha_a> <sha_b>
#
# Builds A and B with CUDA=ON and identical flags, installs each as a Python
# package overlay (pip --target), and runs the #349 dump set
# (gitlinffff/snapy_linfel v3/wave1-dumpset349, tools/dumpset349) on cuda and
# on cpu, float64: A twice (the device is deterministic), then A against B
# with its compare.py, which passes only when all 20 cases ran and every
# dump is byte-identical. Then serial ctest on both CUDA builds, GPU visible:
# every test keeps its verdict and B passes all that A passes.
# Environment: VENV (torch 2.10 cu12x, kintera >= 2.6.9 with its CUDA
# library, pyharp, pydisort, PyYAML), REPO (happysky19/snapy), JOBS (12),
# CUDA_HOME (/usr/local/cuda-12.9), CUDA_ARCH (120), DUMPSET_REPO
# (gitlinffff/snapy_linfel), DUMPSET_SHA (b5976290...).
set -u
W=$(mkdir -p "$1" && cd "$1" && pwd)
A=$2
B=$3
VENV=${VENV:-/data02/tianhaol/fridica-snapy/worker1/pr367-review-20261116/.venv367}
REPO=${REPO:-https://github.com/happysky19/snapy.git}
JOBS=${JOBS:-12}
CUDA_HOME=${CUDA_HOME:-/usr/local/cuda-12.9}
CUDA_ARCH=${CUDA_ARCH:-120}
DUMPSET_REPO=${DUMPSET_REPO:-https://github.com/gitlinffff/snapy_linfel.git}
DUMPSET_SHA=${DUMPSET_SHA:-b59762901489958603a3d8e22ae9d873185e65d8}
SP=$(ls -d "$VENV"/lib*/python3*/site-packages | while read d; do
  [ -d "$d/torch" ] && echo "$d" && break; done)
export PATH=$CUDA_HOME/bin:$VENV/bin:$PATH CUDACXX=$CUDA_HOME/bin/nvcc
export LD_LIBRARY_PATH=$SP/torch/lib:$SP/pyharp/lib:$SP/kintera/lib:${LD_LIBRARY_PATH:-}
export CPATH=$SP/pyharp/include:${CPATH:-} LIBRARY_PATH=$SP/pyharp/lib:${LIBRARY_PATH:-}
PY=$VENV/bin/python
L=$W/logs; mkdir -p "$L"
fail=0
say() { echo "$*" | tee -a "$L/summary.txt"; }

say "cuda_leg $(date -u +%FT%TZ) A=$A B=$B dumpset=$DUMPSET_SHA"
say "torch=$($PY -c 'import torch;print(torch.__version__, torch.cuda.get_device_name(0))') nvcc=$($CUDA_HOME/bin/nvcc --version | tail -1) arch=$CUDA_ARCH"

[ -d "$W/src/.git" ] || git clone -q "$REPO" "$W/src"
git -C "$W/src" fetch -q origin "$A" "$B"
[ -d "$W/dumpset/.git" ] || git clone -q "$DUMPSET_REPO" "$W/dumpset"
git -C "$W/dumpset" fetch -q origin "$DUMPSET_SHA"
git -C "$W/dumpset" checkout -q --detach "$DUMPSET_SHA"
DS=$W/dumpset/tools/dumpset349

for T in A B; do
  sha=${!T}
  [ -d "$W/tree-$T" ] || git -C "$W/src" worktree add -q --detach "$W/tree-$T" "$sha"
  git -C "$W/tree-$T" checkout -q --detach "$sha"
  (cd "$W/tree-$T" &&
   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DNETCDF=ON -DBUILD_TESTS=ON \
     -DFULL_TESTS=OFF -DCUDA=ON -DCMAKE_CUDA_COMPILER=$CUDA_HOME/bin/nvcc \
     -DCMAKE_CUDA_ARCHITECTURES=$CUDA_ARCH \
     -DKINTERA_CUDA_LIBRARY=$SP/kintera/lib/libkintera_cuda_release.so \
     -DPython3_EXECUTABLE="$PY" -DCMAKE_PREFIX_PATH="$SP/torch/share/cmake" \
     -DSNAPY_TEST_PYTHONPATH="$SP" > "$L/configure-$T.log" 2>&1 &&
   cmake --build build --parallel "$JOBS" > "$L/build-$T.log" 2>&1 &&
   rm -rf "$W/pkg-$T" &&
   WORKSPACE="$W/tree-$T" MAX_JOBS=$JOBS $PY -m pip install --no-deps \
     --no-build-isolation --target "$W/pkg-$T" . > "$L/pip-$T.log" 2>&1)
  rc=$?
  say "$T $(git -C "$W/tree-$T" rev-parse HEAD) cuda build+package rc=$rc warnings=$(grep -c 'warning:' "$L/build-$T.log")"
  [ $rc -eq 0 ] || exit 2
done

# the dump set, run from outside the source trees so import snapy is the overlay
mkdir -p "$W/run"
for dev in cuda cpu; do
  for run in A A2 B; do
    T=${run%2}
    vis=""; [ $dev = cpu ] && vis="CUDA_VISIBLE_DEVICES="
    (cd "$W/run" && env $vis PYTHONPATH="$W/pkg-$T:$SP" $PY "$DS/dumpset349.py" \
       --device $dev --dtype float64 --out "$W/runs/${run}_$dev" \
       > "$L/dumpset-${run}_$dev.log" 2>&1)
    say "dumpset $run $dev rc=$?"
  done
  $PY "$DS/compare.py" "$W/runs/A_$dev" "$W/runs/A2_$dev" > "$L/compare-AA2-$dev.txt" 2>&1
  r1=$?
  $PY "$DS/compare.py" "$W/runs/A_$dev" "$W/runs/B_$dev" > "$L/compare-AB-$dev.txt" 2>&1
  r2=$?
  say "#349 $dev: A vs A2 rc=$r1 ($(tail -1 "$L/compare-AA2-$dev.txt")); A vs B rc=$r2 ($(tail -1 "$L/compare-AB-$dev.txt"))"
  [ $r1 -eq 0 ] && [ $r2 -eq 0 ] || fail=1
done

# serial ctest on the CUDA builds, GPU visible (CUDA cases run)
status() { grep -oE 'Test +#[0-9]+: \S+ \.+ *\**\S+' "$1" | awk '{print $3, $NF}' | sort; }
for T in A B; do
  (cd "$W/tree-$T/build" && OMP_NUM_THREADS=1 ctest -j 1 -R '^test_' -E '_python$' \
     --timeout 900 --output-on-failure > "$L/ctest-$T.log" 2>&1)
  say "$T cuda-build ctest rc=$? $(grep -E 'tests passed' "$L/ctest-$T.log")"
done
if diff <(status "$L/ctest-A.log") <(status "$L/ctest-B.log") > "$L/ctest-diff.txt"; then
  say "PASS ctest (cuda build): same verdict per test, $(status "$L/ctest-B.log" | wc -l) tests"
else
  say "FAIL ctest (cuda build): see logs/ctest-diff.txt"; fail=1
fi
say "cuda_leg result: $([ $fail -eq 0 ] && echo PASS || echo FAIL)"
exit $fail
