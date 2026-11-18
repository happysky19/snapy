# gate_c2: CPU comparison gate and OnHost probe for V3 C2

C2 (lane C, `docs/v3/design/C.rst` section 10) moves MPS to the CPU kernels
through `OnHost` and must leave CPU and CUDA results bitwise unchanged. This
gate compares two heads on CPU and checks the OnHost path on a non-host device.
It is outside the wave PR and does not replace the #349 dump set.

Defaults: A = C1 `54aa6ccb0d5892ae3799d35fcec74fe4ec1d18cf`,
B = C2 `674bfdbcac0981c082617b03ae7b196872b76e5b`, both on happysky19/snapy.

## Run

```
VENV=/path/to/venv tools/gate_c2/gate.sh <work_dir> [<sha_a> <sha_b>]
```

`VENV` needs torch 2.10, kintera >= 2.6.9, pyharp, pydisort, netCDF4 and
PyYAML. Optional: `REPO` (clone URL, default happysky19/snapy), `JOBS`
(build parallelism, default 12). The script clones `REPO` into
`<work_dir>/src`, fetches both shas, and writes everything below
`<work_dir>`. `<work_dir>/logs/summary.txt` holds the result lines; the exit
status is 0 only if every check passes.

## Build (each head, same flags)

```
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DNETCDF=ON -DBUILD_TESTS=ON \
  -DFULL_TESTS=OFF -DCUDA=OFF -DPython3_EXECUTABLE=$VENV/bin/python \
  -DCMAKE_PREFIX_PATH=<site-packages>/torch/share/cmake \
  -DSNAPY_TEST_PYTHONPATH=<site-packages>
cmake --build build --parallel $JOBS
```

with `CPATH` and `LIBRARY_PATH` pointing at pyharp's `include` and `lib`.

## Checks and comparison rules

1. **ctest.** `CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 ctest -j 1 -R '^test_'
   -E '_python$|cuda|gpu'` on both builds. Pass: every test passes on B and
   each test has the same verdict on A and B. Serial on purpose: with `-j` the
   torchrun tests race for port 29500.
2. **Decks.** `make_decks.py` writes five decks from A's `examples/`:

   | deck | executable | covers |
   |---|---|---|
   | `straka_single.yaml` | `straka` | dry, lmars, weno5, gravity, reflecting x1 walls |
   | `shock.yaml` | `shock` | hllc, weno5 shock path, outflow |
   | `bryan.yaml` | `bryan` | moist, lmars |
   | `shallow_xy_single.yaml` | `shallow_xy` | shallow-roe |
   | `jupiter_evap_precip_1d.yaml` | `jupiter_evap_precip_1d` (`-i`) | moist 1-D, hllc |

   Changed keys only: `integration.nlim = 20`, `integration.ncycle_out = 1`,
   every netCDF output `dt = 1e-9` (a file each cycle), and the restart output
   replaced by one with `dt = 1e-9` (the FP64 state each cycle). Each deck runs
   on CPU (`CUDA_VISIBLE_DEVICES=`, `OMP_NUM_THREADS=4`) in its own folder,
   with kintera's `data/*` and `build/tests/*.dat` copied beside it.
   `compare_runs.py` passes when, for every deck, A and B have the same exit
   code, the same restart and netCDF files, every restart file is
   byte-identical, every netCDF variable has the same dtype, shape and bytes,
   and the `cycle=` lines of the log are identical. No tolerance.

   `shock.yaml` aborts on main 730b3500 as well, during cycle 4, with
   `outflow: nonfinite hydro input`; the rule compares what it wrote before
   the abort and its exit code (134 on both).
3. **OnHost probe (B only).** `build_probe.sh` compiles `onhost_probe.cpp`
   with B's own test flags against B's `libsnap`. For every kernel C2
   registers for MPS (`call_poly_cpu<3,5>`, `call_weno3_cpu`,
   `call_weno5_cpu` with and without scale, `call_hllc_cpu`,
   `call_lmars_cpu`, `call_roe_cpu`, `call_shallow_roe_cpu`,
   `hydro_pressure_scan_x1_cpu`, `hydro_ref_x1_cpu`), in FP32 and FP64, it
   runs `OnHost<kernel>::run` on CUDA tensors and the kernel itself on CPU
   tensors. The iterators are built as on MPS (only dim 0 squashed). Pass:
   every case `torch::equal`, and no compared output is all zero. CUDA stands
   in for MPS as a device that is not the host. Skipped when torch sees no
   CUDA device.

Not covered: an MPS run (`tests/test_mps_matches_cpu.py`), a CUDA build of
snapy, and the #349 dump set.
