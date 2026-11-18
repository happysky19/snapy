"""Compare two run folders of run_decks.sh:

  compare_runs.py <runs_a> <runs_b> [--diagnostic <deck> ...]

Rules for every counted deck (all bitwise, no tolerance):
  * exit code: 0 on A and on B (a deck that fails to run is a gate failure,
    even when both heads fail the same way);
  * restart files (*.restart, the FP64 state each cycle): the same set of
    files, each byte-identical;
  * netCDF files (*.nc): the same set; every variable has the same dtype,
    shape and bytes;
  * run.log: the "cycle=" diagnostic lines identical.
A --diagnostic deck is compared the same way and reported on a DIAG line, but
it never counts toward the result: it is a known failure of the base, shown so
that a change in how it fails stays visible.
Exit status 0 when every counted deck passes and at least one restart file
and one netCDF variable of the counted decks were compared.
"""
import glob
import os
import sys

import netCDF4
import numpy as np


def compare(a, b, deck):
    """Differences (list of str) and counts for one deck."""
    diffs = []
    rc = [open(os.path.join(x, "rc.txt")).read().strip() for x in (a, b)]
    names = {
        ext: (sorted(os.path.basename(p) for p in glob.glob(f"{a}/*{ext}")),
              sorted(os.path.basename(p) for p in glob.glob(f"{b}/*{ext}")))
        for ext in (".restart", ".nc")
    }
    for ext, (na, nb) in names.items():
        if na != nb:
            diffs.append(f"{deck}: {ext} file sets differ")
    nres = nres_eq = nvar = nvar_eq = 0
    for f in names[".restart"][0]:
        if f not in names[".restart"][1]:
            continue
        nres += 1
        with open(os.path.join(a, f), "rb") as x, open(os.path.join(b, f), "rb") as y:
            if x.read() == y.read():
                nres_eq += 1
            else:
                diffs.append(f"{deck}/{f}")
    for f in names[".nc"][0]:
        if f not in names[".nc"][1]:
            continue
        x, y = netCDF4.Dataset(os.path.join(a, f)), netCDF4.Dataset(os.path.join(b, f))
        if set(x.variables) != set(y.variables):
            diffs.append(f"{deck}/{f}: variable sets differ")
        for v in x.variables:
            if v not in y.variables:
                continue
            nvar += 1
            p, q = np.asarray(x[v][:]), np.asarray(y[v][:])
            if p.dtype == q.dtype and p.shape == q.shape and p.tobytes() == q.tobytes():
                nvar_eq += 1
            else:
                diffs.append(f"{deck}/{f}:{v}")
    cyc = [[l for l in open(os.path.join(x, "run.log")) if l.startswith("cycle=")]
           for x in (a, b)]
    if cyc[0] != cyc[1]:
        diffs.append(f"{deck}: cycle lines")
    line = (f"{deck}: exit {rc[0]}/{rc[1]}, restart {nres_eq}/{nres}, netCDF "
            f"variables {nvar_eq}/{nvar}, {len(cyc[0])} cycle lines")
    return rc, diffs, (nres, nres_eq, nvar, nvar_eq), line


a_dir, b_dir = sys.argv[1], sys.argv[2]
diagnostic = set()
args = sys.argv[3:]
while args:
    if args[0] == "--diagnostic" and len(args) > 1:
        diagnostic.add(args[1])
        args = args[2:]
    else:
        sys.exit(f"unknown argument {args[0]}")

bad = 0
tot = [0, 0, 0, 0]
for deck in sorted(os.listdir(a_dir)):
    rc, diffs, counts, line = compare(os.path.join(a_dir, deck),
                                      os.path.join(b_dir, deck), deck)
    if deck in diagnostic:
        state = "identical" if not diffs and rc[0] == rc[1] else "DIFFERENT"
        print(f"DIAG (not counted) {line}; A and B {state}")
        for d in diffs:
            print(f"DIAG DIFF {d}")
        continue
    for i, x in enumerate(rc):
        if x != "0":
            diffs.append(f"{deck}: exit code {x} on {'AB'[i]} (must be 0)")
    for d in diffs:
        print(f"DIFF {d}")
    bad += len(diffs)
    tot = [t + c for t, c in zip(tot, counts)]
    print(("ok   " if not diffs else "FAIL ") + line)
print(f"counted decks: restart {tot[1]}/{tot[0]} byte-identical, netCDF variables "
      f"{tot[3]}/{tot[2]} byte-equal, {bad} failures")
sys.exit(0 if bad == 0 and tot[0] > 0 and tot[2] > 0 else 1)
