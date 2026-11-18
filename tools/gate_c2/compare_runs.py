"""Compare two run folders of run_decks.sh: compare_runs.py <runs_a> <runs_b>

Rules (all bitwise, no tolerance):
  * exit code: the same for each deck on A and B;
  * restart files (*.restart, the FP64 state each cycle): the same set of
    files, each byte-identical;
  * netCDF files (*.nc): the same set; every variable has the same dtype,
    shape and bytes;
  * run.log: the "cycle=" diagnostic lines identical.
Exit status 0 when every rule holds and at least one file was compared.
"""
import glob
import os
import sys

import netCDF4
import numpy as np

a_dir, b_dir = sys.argv[1], sys.argv[2]
bad = 0
nres = nres_eq = nvar = nvar_eq = 0
for deck in sorted(os.listdir(a_dir)):
    a, b = os.path.join(a_dir, deck), os.path.join(b_dir, deck)
    rc = [open(os.path.join(x, "rc.txt")).read().strip() for x in (a, b)]
    if rc[0] != rc[1]:
        print(f"DIFF {deck}: exit code {rc[0]} vs {rc[1]}")
        bad += 1
    names = {
        ext: (sorted(os.path.basename(p) for p in glob.glob(f"{a}/*{ext}")),
              sorted(os.path.basename(p) for p in glob.glob(f"{b}/*{ext}")))
        for ext in (".restart", ".nc")
    }
    for ext, (na, nb) in names.items():
        if na != nb:
            print(f"DIFF {deck}: {ext} file sets differ")
            bad += 1
    for f in names[".restart"][0]:
        nres += 1
        with open(os.path.join(a, f), "rb") as x, open(os.path.join(b, f), "rb") as y:
            if x.read() == y.read():
                nres_eq += 1
            else:
                print(f"DIFF {deck}/{f}")
                bad += 1
    for f in names[".nc"][0]:
        x, y = netCDF4.Dataset(os.path.join(a, f)), netCDF4.Dataset(os.path.join(b, f))
        if set(x.variables) != set(y.variables):
            print(f"DIFF {deck}/{f}: variable sets differ")
            bad += 1
        for v in x.variables:
            nvar += 1
            p, q = np.asarray(x[v][:]), np.asarray(y[v][:])
            if p.dtype == q.dtype and p.shape == q.shape and p.tobytes() == q.tobytes():
                nvar_eq += 1
            else:
                print(f"DIFF {deck}/{f}:{v}")
                bad += 1
    cyc = [[l for l in open(os.path.join(x, "run.log")) if l.startswith("cycle=")]
           for x in (a, b)]
    if cyc[0] != cyc[1]:
        print(f"DIFF {deck}: cycle lines")
        bad += 1
    print(f"{deck}: exit {rc[0]}/{rc[1]}, {len(names['.restart'][0])} restart, "
          f"{len(names['.nc'][0])} netcdf, {len(cyc[0])} cycle lines")
print(f"restart {nres_eq}/{nres} byte-identical, netCDF variables "
      f"{nvar_eq}/{nvar} byte-equal, {bad} differences")
sys.exit(0 if bad == 0 and nres > 0 and nvar > 0 else 1)
