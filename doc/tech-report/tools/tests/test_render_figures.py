"""tools/render_figures.py: regenerate the figures, and keep the figure manifest FIGURES.md.

The committed FIGURES.md lists every figure cell of the book; a small report tree (one chapter, a module `demo_data`
in its `src/` that reads a JSON file) checks the draw (files written, data recorded) and the static manifest check.
Needs matplotlib. Run from the report directory: `python3 -m pytest tools/tests`.
"""

import sys
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import render_figures  # noqa: E402

MODULE = '''
import json
from pathlib import Path
import matplotlib
from matplotlib.figure import Figure

matplotlib.rcParams["svg.hashsalt"] = "demo"  # as figstyle does: SVG ids fixed, so two draws give the same bytes


def make_fig():
    values = json.loads((Path(__file__).parent / "data" / "values.json").read_text())
    fig = Figure(figsize=(3.0, 2.0))
    fig.add_subplot().plot(values)
    return fig
'''

QMD = '''# One {#sec-ch01}

```{python}
#| label: fig-ch01-demo
#| fig-cap: "A demo."
from demo_data import make_fig
make_fig()
```
'''


def tree(tmp_path):
    (tmp_path / "book" / "chapters").mkdir(parents=True)
    (tmp_path / "book" / "chapters" / "01-one.qmd").write_text(QMD)
    pkg = tmp_path / "src" / "demo_data"
    (pkg / "data").mkdir(parents=True)
    (pkg / "__init__.py").write_text(MODULE)
    (pkg / "data" / "values.json").write_text("[1, 3, 2]")
    sys.modules.pop("demo_data", None)
    return tmp_path


def test_the_committed_manifest_lists_every_figure():
    assert render_figures.check_manifest() == []


def test_draw_writes_each_format_and_records_the_data(tmp_path):
    report = tree(tmp_path)
    index, rows = render_figures.render(report / "out", report=report, record=True)
    assert set(index) == {"fig-ch01-demo"} and "svg_sha256" in index["fig-ch01-demo"]
    for fmt in ("svg", "pdf", "png"):
        assert (report / "out" / "ch01" / f"fig-ch01-demo.{fmt}").stat().st_size > 0
    assert rows["fig-ch01-demo"]["data"] == ["src/demo_data/data/values.json"]
    assert rows["fig-ch01-demo"]["qmd"] == "book/chapters/01-one.qmd"


def test_a_redraw_is_byte_identical(tmp_path):
    report = tree(tmp_path)
    first, _ = render_figures.render(report / "a", report=report, formats=("svg",))
    second, _ = render_figures.render(report / "b", report=report, formats=("svg",))
    assert first == second


def test_the_static_check_flags_a_missing_row_and_a_missing_path(tmp_path):
    report = tree(tmp_path)
    assert "is missing" in render_figures.check_manifest(report)[0]
    (report / "FIGURES.md").write_text("# Figure manifest\n")
    assert "not in FIGURES.md" in render_figures.check_manifest(report)[0]
    _, rows = render_figures.render(report / "out", report=report, record=True)
    (report / "FIGURES.md").write_text(render_figures.manifest_text(rows, report))
    assert render_figures.check_manifest(report) == []
    (report / "src" / "demo_data" / "data" / "values.json").unlink()
    msgs = render_figures.check_manifest(report)
    assert any("values.json" in m and "does not exist" in m for m in msgs)


def test_figure_modules_are_read_from_the_imports():
    code = ("from snapy_report.ch05.figures.fig_a import make_fig\n"
            "from snapy_report.ch06.figures import fig_b\n"
            "import snapy_report.ch07.figures.fig_c as c\n"
            "from snapy_report import figstyle as fs\n")
    assert render_figures.figure_modules(code) == [
        "snapy_report.ch05.figures.fig_a", "snapy_report.ch06.figures.fig_b", "snapy_report.ch07.figures.fig_c"]


def test_a_tool_s_own_directory_is_not_figure_data(tmp_path):
    """setup.sh installs into doc/tech-report/.report-env, and the matplotlib in its virtual
    environment opens its bundled fonts while a figure draws. Those are not that figure's data:
    recording them rewrote FIGURES.md with three .ttf paths under the prefix."""
    report = tree(tmp_path)
    font = report / ".report-env" / "venv" / "lib" / "matplotlib" / "fonts" / "STIXGeneral.ttf"
    font.parent.mkdir(parents=True)
    font.write_bytes(b"not really a font")
    assert render_figures._rel(str(font), report) is None
    # a real data file next to it still counts
    data = report / "src" / "demo_data" / "data" / "values.json"
    assert render_figures._rel(str(data), report) == "src/demo_data/data/values.json"
