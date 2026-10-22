#!/usr/bin/env python3
"""Regenerate the book's figures outside a render, and keep the figure manifest `FIGURES.md` (README, "Where things
live").

    python3 tools/render_figures.py                       # every figure, to build/figures/<chapter>/<label>.svg|pdf|png
    python3 tools/render_figures.py --chapters ch05,ch06  # one or more chapters only
    python3 tools/render_figures.py --out DIR             # another output directory (build/ is gitignored)
    python3 tools/render_figures.py --manifest            # also rewrite FIGURES.md (all chapters)
    python3 tools/render_figures.py --check               # exit 1 if FIGURES.md differs from what the draw finds

Each figure cell of book/chapters (a `{python}` cell with a `#| label: fig-...`) is run the way the render runs it
(tools/check_fig_output.py: from its chapter directory, the cell's last expression or pyplot's current figure) and
saved as SVG (what the HTML book embeds), PDF (what the PDF book embeds) and PNG (100 dpi, to look at). OUT/index.json
records, per label, the chapter and the sha256 of the SVG, the same fingerprint as `tools/contact_sheet.py draw`, so two
draws compare byte for byte. A cell that cannot be drawn is listed and the exit status is 1.

The manifest is measured, not written by hand: while a cell draws, the chapter modules of `snapy_report` are dropped
from `sys.modules` (so module-level reads happen again) and every file the cell opens under the report directory is
recorded. Per figure it lists the section file, the `snapy_report` modules the cell imports (its figure module, and
the chapter helpers that module uses), the data files it reads, and, per data file, the scripts under `src/` that
name it (the ones that write it; for a JSON file a snapy run wrote, its `provenance` field names the run).
`tools/render_gate.py` checks the manifest statically on every render (gate
`figure manifest`: every figure cell is listed, with the figure modules its code imports, and every listed path
exists); a draw is needed only to rewrite it. Needs numpy, matplotlib and `snapy_report` (`pip install -e src`).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_fig_output as cfo  # noqa: E402

REPORT = cfo.REPORT
MANIFEST = "FIGURES.md"
DEFAULT_OUT = Path("build") / "figures"
_SKIP_SUFFIXES = {".py", ".pyc", ".pyi", ".so", ".pth"}

_reads: list[str] | None = None  # files opened while a cell draws; None outside a draw


def _audit(event, args):
    if _reads is not None and event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.fsdecode(args[0])
        _reads.append(os.path.abspath(path))


def _chapter_module(name: str) -> bool:
    return re.match(r"snapy_report\.(ch\d\d|app[a-z])(\.|$)", name) is not None


def imported_modules(code: str) -> list[str]:
    """the `snapy_report` modules a cell's code imports by name, as written (static)"""
    names = []
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names if a.name.startswith("snapy_report")]
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("snapy_report"):
            if re.search(r"\.(figures|checks)$", node.module):
                # `from snapy_report.ch05.figures import fig_x` imports the module fig_x
                names += [f"{node.module}.{a.name}" for a in node.names]
            else:
                names.append(node.module)
    return sorted(set(names))


def figure_modules(code: str) -> list[str]:
    return [m for m in imported_modules(code) if re.search(r"\.figures\.[A-Za-z_]\w*$", m)]


def _module_path(name: str, report: Path) -> str:
    base = report / "src" / Path(*name.split("."))
    path = base / "__init__.py" if base.is_dir() else base.with_suffix(".py")
    return path.relative_to(report).as_posix()


def _rel(path: str, report: Path) -> str | None:
    p = Path(path)
    try:
        rel = p.resolve().relative_to(report.resolve())
    except ValueError:
        return None
    # A dot-directory at the top of the report is never figure data: it is somewhere a tool keeps its
    # own files. setup.sh installs into .report-env/ by default, and the matplotlib inside its virtual
    # environment opens its bundled fonts while a figure draws, which would otherwise be recorded as
    # that figure's data and rewrite FIGURES.md with three .ttf paths.
    if (p.suffix in _SKIP_SUFFIXES or "__pycache__" in rel.parts or rel.parts[0] == "build"
            or rel.parts[0].startswith(".") or not p.is_file()):
        return None
    return rel.as_posix()


def writers(data: str, report: Path) -> list[str]:
    """the scripts under src/ (figure modules excepted) that name a data file: the ones that write it"""
    name = Path(data).name
    hits = []
    for py in sorted((report / "src").rglob("*.py")):
        if "/figures/" in py.as_posix() or "tests" in py.parts:
            continue
        if name in py.read_text(encoding="utf-8", errors="replace"):
            hits.append(py.relative_to(report).as_posix())
    return hits


def _has_provenance(path: Path) -> bool:
    try:
        return path.suffix == ".json" and "provenance" in json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, TypeError):
        return False


def render(out: Path, chapters=None, report: Path = REPORT, formats=("svg", "pdf", "png"), record=False):
    """draw every figure cell (of `chapters`, if given) to out/<chapter>/<label>.<fmt>; return (index, rows) where
    rows holds, with `record`, what each figure imports and reads"""
    global _reads
    src = report / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    if record:
        sys.addaudithook(_audit)
    out = out if out.is_absolute() else report / out
    index, rows = {}, {}
    for cell in cfo.figure_cells(report):
        if chapters and cell.chapter not in chapters:
            continue
        if record:
            for name in [m for m in sys.modules if _chapter_module(m)]:
                del sys.modules[name]
            _reads = []
        reads = None
        try:
            fig = cfo.draw(cell)
            reads, _reads = _reads, None  # what the draw read, not what the saves below write
            if not isinstance(fig.canvas, FigureCanvasAgg):
                FigureCanvasAgg(fig)
            svg = cfo.svg(fig)
            dest = out / cell.chapter
            dest.mkdir(parents=True, exist_ok=True)
            if "svg" in formats:
                (dest / f"{cell.label}.svg").write_bytes(svg)
            if "pdf" in formats:
                fig.savefig(dest / f"{cell.label}.pdf", format="pdf", metadata={"CreationDate": None})
            if "png" in formats:
                fig.savefig(dest / f"{cell.label}.png", dpi=100, metadata={"Software": None})
            index[cell.label] = {"chapter": cell.chapter, "svg_sha256": hashlib.sha256(svg).hexdigest()}
        except Exception as e:  # noqa: BLE001 - listed, and the exit status says so
            index[cell.label] = {"chapter": cell.chapter, "error": f"{type(e).__name__}: {e}"[:200]}
        finally:
            plt.close("all")
            _reads = None
        if record:
            # the chapter modules this cell loaded (purged before it), less the packages themselves
            mods = sorted(m for m in sys.modules if _chapter_module(m) and m.count(".") >= 2
                          and not m.endswith((".figures", ".checks")) and getattr(sys.modules[m], "__file__", None))
            data = sorted({r for r in (_rel(p, report) for p in reads or []) if r and not r.endswith(".qmd")})
            rows[cell.label] = {"chapter": cell.chapter, "qmd": cell.qmd.relative_to(report).as_posix(),
                                "modules": [_module_path(m, report) for m in mods], "data": data}
    out.mkdir(parents=True, exist_ok=True)
    if not chapters:
        (out / "index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return index, rows


def manifest_text(rows: dict, report: Path = REPORT) -> str:
    lines = [
        "# Figure manifest",
        "",
        "Generated by `python3 tools/render_figures.py --manifest`; do not edit by hand (README, \"Where things live\").",
        "Per figure: the section file that draws it, the `snapy_report` modules it runs (its figure module first),",
        "and the data files it reads, each with the scripts under `src/` that name it (the ones that write it) or,",
        "for a file a snapy run wrote, a pointer to the run recorded in the file.",
        "",
        "Regenerate every figure: `python3 tools/render_figures.py` (to `build/figures/<chapter>/`); one chapter:",
        "`python3 tools/render_figures.py --chapters ch05`. The book itself draws them in the render",
        "(`quarto render book/`), from the same cells.",
    ]
    by_chapter: dict[str, list[str]] = {}
    for label, r in rows.items():
        by_chapter.setdefault(r["chapter"], []).append(label)
    for ch in sorted(by_chapter, key=lambda c: (not c.startswith("ch"), c)):
        lines += ["", f"## {ch}", "", "| figure | section file | code | data (written by) |", "|---|---|---|---|"]
        for label in sorted(by_chapter[ch]):
            r = rows[label]
            mods = sorted(r["modules"], key=lambda m: ("/figures/" not in m, m))
            code = "<br>".join(f"`{m.removeprefix('src/')}`" for m in mods) or "(in the cell)"
            data = []
            for d in r["data"]:
                w = [f"`{x.removeprefix('src/')}`" for x in writers(d, report)]
                if not w and _has_provenance(report / d):
                    w = ["a snapy run, named in the file's `provenance`"]
                data.append(f"`{d}`" + (" (" + ", ".join(w) + ")" if w else ""))
            qmd = r["qmd"].removeprefix("book/chapters/")
            lines.append(f"| `{label}` | `{qmd}` | {code} | {'<br>'.join(data) or '-'} |")
    return "\n".join(lines) + "\n"


def parse_manifest(text: str) -> dict[str, dict]:
    """{label: {"qmd", "code": [paths under src/], "data": [paths]}} from FIGURES.md"""
    rows = {}
    for line in text.splitlines():
        m = re.match(r"\| `(fig-[\w-]+)` \| `([^`]+)` \| (.*?) \| (.*) \|$", line)
        if m:
            rows[m.group(1)] = {"qmd": m.group(2), "code": re.findall(r"`([^`]+)`", m.group(3)),
                                "data": re.findall(r"`([^`]+)`(?: \(|<br>|$)", m.group(4))}
    return rows


def check_manifest(report: Path = REPORT) -> list[str]:
    """static: every figure cell is in FIGURES.md with its section file and the figure modules its code imports,
    and every path the manifest lists exists"""
    path = report / MANIFEST
    if not path.exists():
        return [f"{MANIFEST} is missing: `python3 tools/render_figures.py --manifest` writes it"]
    rows = parse_manifest(path.read_text(encoding="utf-8"))
    problems = []
    cells = cfo.figure_cells(report)
    for cell in cells:
        r = rows.get(cell.label)
        qmd = cell.qmd.relative_to(report / "book" / "chapters").as_posix()
        if r is None:
            problems.append(f"{cell.label} ({qmd}) is not in {MANIFEST}")
            continue
        if r["qmd"] != qmd:
            problems.append(f"{cell.label}: {MANIFEST} says {r['qmd']}, the cell is in {qmd}")
        for m in figure_modules(cell.code):
            if _module_path(m, report).removeprefix("src/") not in r["code"]:
                problems.append(f"{cell.label}: imports {m}, not listed in {MANIFEST}")
    labels = {c.label for c in cells}
    for label, r in rows.items():
        if label not in labels:
            problems.append(f"{label} is in {MANIFEST} but no figure cell has that label")
        for p in [f"src/{c}" for c in r["code"]] + r["data"]:
            if not (report / p).exists():
                problems.append(f"{label}: {p} (listed in {MANIFEST}) does not exist")
    if problems:
        problems.append(f"rewrite it with `python3 tools/render_figures.py --manifest` in the same commit")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--chapters", default="", help="comma-separated chapter ids (ch05, appe, ...); default all")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory, relative to the report")
    ap.add_argument("--formats", default="svg,pdf,png")
    ap.add_argument("--manifest", action="store_true", help=f"rewrite {MANIFEST} (draws every chapter)")
    ap.add_argument("--check", action="store_true", help=f"exit 1 if {MANIFEST} differs from what the draw finds")
    args = ap.parse_args(argv)
    chapters = {c.strip() for c in args.chapters.split(",") if c.strip()} or None
    record = args.manifest or args.check
    if record and chapters:
        ap.error("--manifest and --check draw every chapter; drop --chapters")
    formats = tuple(f.strip() for f in args.formats.split(",") if f.strip())
    index, rows = render(args.out, chapters, REPORT, formats, record)
    errors = [k for k, v in index.items() if "error" in v]
    out = args.out if args.out.is_absolute() else REPORT / args.out
    print(f"render_figures: drew {len(index) - len(errors)} figure(s) to {out}"
          + (f"; {len(errors)} could not be drawn:" if errors else ""))
    for k in errors:
        print(f"  ✗ {k}: {index[k]['error']}")
    status = 1 if errors else 0
    if record and not errors:
        text = manifest_text(rows)
        path = REPORT / MANIFEST
        if args.manifest:
            path.write_text(text, encoding="utf-8")
            print(f"render_figures: wrote {MANIFEST} ({len(rows)} figures)")
        elif not path.exists() or path.read_text(encoding="utf-8") != text:
            print(f"render_figures: {MANIFEST} is out of date: `python3 tools/render_figures.py --manifest`")
            status = 1
        else:
            print(f"render_figures: {MANIFEST} is up to date")
    return status


if __name__ == "__main__":
    sys.exit(main())
