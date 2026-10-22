#!/usr/bin/env python3
"""What it would take to move the kintera citation pin up to snapy's floor.

The report carries two kintera revisions on purpose (tools/env-pins.json,
`scientific_packages.kintera._why_build_differs_from_pin`):

  tools/package-pins.json   c55b13b2 (v2.6.2)  the commit the chapters CITE
  tools/env-pins.json       b6ad3739 (v2.6.3)  the commit setup.sh INSTALLS,
                                               because snapy at code_pin.yml says
                                               find_package(Kintera 2.6.3 REQUIRED)

They should be one revision. They are not, and the reason is structural rather than clerical: the
commit that satisfies snapy's floor is the commit that rewrote `src/kinetics/evaporation.cpp` and
`src/kinetics/kinetics.cpp` -- the "explicit same-call rate constants for the kinetics Jacobian"
change -- and chapter 10's kinetics section cites those very files by line. Every revision at or
above the floor contains that rewrite, so no choice of revision avoids it.

This tool says exactly which citations survive the move and which do not. For each

    https://github.com/chengcli/kintera/blob/<sha>/<path>#L<a>[-L<b>]

it reads the cited lines at the old sha and at the new one and compares them byte for byte:

  identical     the sha can be swapped and the citation still points at the same code
  moved         the same code is there, at different line numbers; it prints the new range
  BLOCKED       the cited code is not there any more; the claim it carries has to be re-read
                against the new revision by the chapter's owner

A run needs a kintera clone holding both revisions (`KINTERA_REPO`, else `--clone`); it makes no
network call of its own and changes nothing. Exit 0 when nothing is blocked, 1 otherwise.

    KINTERA_REPO=../kintera python3 tools/kintera_pin_migration.py
    python3 tools/kintera_pin_migration.py --clone /path/to/kintera --json out.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent

CITE = re.compile(
    r"https://github\.com/chengcli/kintera/blob/(?P<sha>[0-9a-f]{40})/"
    r"(?P<path>[^)#\s\"']+)"
    r"(?:\#L(?P<a>\d+)(?:-L(?P<b>\d+))?)?"
)
SUFFIXES = {".qmd", ".md", ".json", ".tsv", ".py", ".yml", ".out", ".log"}


def blob(clone: Path, sha: str, path: str) -> list[str] | None:
    r = subprocess.run(["git", "-C", str(clone), "show", f"{sha}:{path}"],
                       capture_output=True, text=True)
    return r.stdout.splitlines() if r.returncode == 0 else None


def occurrences(hay: list[str], needle: list[str]) -> list[int]:
    if not needle:
        return []
    n = len(needle)
    return [i for i in range(len(hay) - n + 1) if hay[i:i + n] == needle]


def pins() -> tuple[str, str]:
    old = json.loads((HERE / "package-pins.json").read_text())["kintera"]
    env = json.loads((HERE / "env-pins.json").read_text())
    return old, env["scientific_packages"]["kintera"]["build"]


def find_clone(given: str | None) -> Path | None:
    for c in (given, os.environ.get("KINTERA_REPO", ""),
              os.environ.get("SNAPY_REPORT_ENV", "") and
              str(Path(os.environ["SNAPY_REPORT_ENV"]) / "src" / "kintera")):
        if c and (Path(c) / ".git").exists():
            return Path(c)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--clone", help="a kintera clone holding both revisions")
    ap.add_argument("--json", help="write the full result here")
    ap.add_argument("--quiet", action="store_true", help="only the summary and the blockers")
    args = ap.parse_args()

    old, new = pins()
    clone = find_clone(args.clone)
    if clone is None:
        print("kintera_pin_migration: no kintera clone (set KINTERA_REPO or pass --clone);")
        print("  nothing checked. `bash setup.sh --with-native` leaves one in .report-env/src/kintera.")
        return 0
    for sha in (old, new):
        if subprocess.run(["git", "-C", str(clone), "cat-file", "-e", sha + "^{commit}"],
                          capture_output=True).returncode != 0:
            print(f"kintera_pin_migration: {clone} does not hold {sha[:8]}; "
                  "fetch it, or point --clone at a complete clone.")
            return 0

    cache: dict[tuple[str, str], list[str] | None] = {}

    def lines(sha: str, path: str):
        if (sha, path) not in cache:
            cache[(sha, path)] = blob(clone, sha, path)
        return cache[(sha, path)]

    identical, moved, blocked = [], [], []
    for f in sorted(p for p in REPORT.rglob("*")
                    if p.is_file() and p.suffix in SUFFIXES
                    and not any(part.startswith(".") for part in p.relative_to(REPORT).parts)):
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        for m in CITE.finditer(text):
            if m.group("sha") != old:
                continue
            rel = f.relative_to(REPORT).as_posix()
            rec = {"file": rel, "line": text[:m.start()].count("\n") + 1, "target": m.group("path")}
            o, n = lines(old, rec["target"]), lines(new, rec["target"])
            if o is None or n is None:
                rec["why"] = "the file does not exist at one of the two revisions"
                blocked.append(rec)
                continue
            if m.group("a") is None:
                (identical if o == n else blocked).append(
                    rec | {"why": "whole file, unchanged" if o == n else "whole file, changed"})
                continue
            a, b = int(m.group("a")), int(m.group("b") or m.group("a"))
            rec["range"] = [a, b]
            if max(len(o), len(n)) < b:
                rec["why"] = f"L{a}-L{b} is past the end of the file"
                blocked.append(rec)
            elif o[a - 1:b] == n[a - 1:b]:
                identical.append(rec | {"why": f"L{a}-L{b} identical"})
            else:
                hits = occurrences(n, o[a - 1:b])
                if len(hits) == 1:
                    rec["new_range"] = [hits[0] + 1, hits[0] + 1 + (b - a)]
                    rec["why"] = f"same code, now L{rec['new_range'][0]}-L{rec['new_range'][1]}"
                    moved.append(rec)
                else:
                    rec["why"] = (f"the {b - a + 1} cited line(s) occur {len(hits)} times at "
                                  f"{new[:8]}: the cited code is gone, so the claim this citation "
                                  "carries has to be re-read against the new revision")
                    blocked.append(rec)

    total = len(identical) + len(moved) + len(blocked)
    print(f"kintera citations at {old[:8]} (v from package-pins.json) -> {new[:8]} (env-pins.json build)")
    print(f"  {total} citation(s) found")
    print(f"    identical, the sha can simply be swapped : {len(identical)}")
    print(f"    same code at new line numbers            : {len(moved)}")
    print(f"    BLOCKED, the cited code is gone          : {len(blocked)}")

    if moved and not args.quiet:
        print("\nmoved:")
        for r in moved:
            print(f"  {r['file']}:{r['line']}  {r['target']}  "
                  f"L{r['range'][0]}-L{r['range'][1]} -> L{r['new_range'][0]}-L{r['new_range'][1]}")
    if blocked:
        print(f"\nblocked -- chapter work, at {new}:")
        for r in blocked:
            rng = f"L{r['range'][0]}-L{r['range'][1]}" if "range" in r else "whole file"
            print(f"  {r['file']}:{r['line']}")
            print(f"      cites kintera {r['target']} {rng}")
            print(f"      {r['why']}")
        chapters = sorted({r["file"] for r in blocked if r["file"].startswith("book/")})
        if chapters:
            print("\n  chapter files that must change before the pin can move:")
            for c in chapters:
                print(f"    {c}")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"old": old, "new": new, "identical": identical, "moved": moved,
             "blocked": blocked}, indent=1) + "\n")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
