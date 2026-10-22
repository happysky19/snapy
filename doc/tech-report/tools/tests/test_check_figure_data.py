"""The figure-data check: what it reads out of a file, what it reads off a figure, and what it
refuses to call a match.

These use synthetic series and a synthetic figure rather than the report's own, so they say what the
tool decides rather than what today's chapters happen to contain.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_figure_data as cfd  # noqa: E402


# ------------------------------------------------------------------ reference series --

def test_a_csv_header_names_the_columns_when_there_is_one_name_each():
    text = "# x1,a,b (c = 1, rho = 2)\n1,2,3\n4,5,6\n7,8,9\n"
    assert dict(cfd.series_from_csv(text)) == {
        "x1": [1.0, 4.0, 7.0], "a": [2.0, 5.0, 8.0], "b": [3.0, 6.0, 9.0]}


def test_a_comment_that_is_prose_does_not_become_column_names():
    """`# rows NH3,H2S,NH4SH(s); columns before,after` describes the layout, it does not name the
    two columns. A wrong name is worse than none, so this falls back to positions."""
    text = "# rows NH3,H2S,NH4SH(s); columns before,after [kg m^-3]\n1,2\n3,4\n5,6\n"
    assert sorted(dict(cfd.series_from_csv(text))) == ["column0", "column1"]


def test_json_lists_dicts_and_table_columns_all_become_series():
    doc = {"provenance": {"sha": "deadbeef", "ranks": 1},
           "rh": [5.0, 10.0, 20.0],
           "eps": {"32": -1.0, "64": -2.0, "128": -3.0},
           "passes": [[1, 10.0], [2, 20.0], [3, 30.0]]}
    got = dict(cfd.series_from_json(doc))
    assert got["/rh"] == [5.0, 10.0, 20.0]
    assert got["/eps"] == [-1.0, -2.0, -3.0]          # keys ordered numerically, not as text
    assert got["/passes[:][1] (column)"] == [10.0, 20.0, 30.0]
    assert not any("provenance" in k for k in got)     # a run record, not a plotted quantity


# -------------------------------------------------------------------------- matching --

REF = [1.0, 2.0, 3.0, 4.0]


def match(plot, ref=REF, rtol=1e-9, atol=1e-12):
    return cfd.find_match(ref, [("p", plot)], rtol, atol)


def test_the_same_numbers_match():
    assert match([1.0, 2.0, 3.0, 4.0])[1] == "as committed"


def test_a_reversed_axis_matches_and_says_so():
    assert "reversed" in match([4.0, 3.0, 2.0, 1.0])[1]


def test_a_longer_plotted_series_matches_on_the_slice_that_contains_it():
    assert "slice [2:6]" in match([9.0, 9.0, 1.0, 2.0, 3.0, 4.0])[1]


def test_a_log_axis_plotting_magnitudes_matches_through_a_named_sign_transform():
    how = cfd.find_match([-1.0, -2.0, -3.0], [("p", [1.0, 2.0, 3.0])], 1e-9, 1e-12)[1]
    assert how in ("negated", "absolute value")


def test_a_sign_flip_is_never_absorbed_as_a_scale_factor():
    """-1 as a free factor would hide a sign error; it has to be named instead."""
    assert cfd._is_unit_factor(-1.0) is False
    assert cfd._is_unit_factor(-10.0) is False


def test_a_unit_conversion_matches_and_names_the_factor():
    name, how = match([1e4, 2e4, 3e4, 4e4])
    assert name == "p" and "scaled by 10000" in how


def test_an_arbitrary_factor_is_not_a_match():
    """A free factor would absorb the very error this exists to catch: scaled by 1.000001 is a
    difference, not a unit."""
    assert match([v * 1.000001 for v in REF]) == (None, None)
    assert match([v * 3.7 for v in REF]) == (None, None)


def test_a_single_value_off_by_more_than_the_tolerance_is_not_a_match():
    bad = [1.0, 2.0, 3.0 * (1 + 1e-6), 4.0]
    assert match(bad) == (None, None)


def test_a_difference_below_the_tolerance_is_a_match():
    assert match([1.0, 2.0, 3.0 * (1 + 1e-12), 4.0])[0] == "p"


@pytest.mark.parametrize("k,ok", [(1.0, True), (10.0, True), (1e-4, True), (0.5, True),
                                  (1.5, True), (60.0, True), (1.000001, False),
                                  (1.001, False), (3.7, False)])
def test_only_unit_like_factors_are_allowed(k, ok):
    assert cfd._is_unit_factor(k) is ok


def test_worst_difference_points_at_the_element_that_moved():
    near = cfd.worst_difference(REF, [("p", [1.0, 2.0, 3.5, 4.0])])
    assert near[0] == "p" and near[2] == 2 and near[3] == 3.5 and near[4] == 3.0


# ----------------------------------------------------------------------- fingerprints --

def test_a_fingerprint_moves_when_a_value_moves():
    a = cfd.fingerprint([1.0, 2.0, 3.0])
    b = cfd.fingerprint([1.0, 2.0, 3.0 * (1 + 1e-6)])
    assert a["sha256"] != b["sha256"]
    assert "max" in cfd.fingerprint_delta(a, b)


def test_a_fingerprint_ignores_a_change_below_the_matching_tolerance():
    """The digest and the matcher have to agree about what unchanged means, or the check
    contradicts itself."""
    a = cfd.fingerprint([1.0, 2.0, 3.0])
    b = cfd.fingerprint([1.0, 2.0, 3.0 * (1 + 1e-15)])
    assert a["sha256"] == b["sha256"]


def test_a_length_change_is_reported_as_one():
    a, b = cfd.fingerprint([1.0, 2.0, 3.0]), cfd.fingerprint([1.0, 2.0])
    assert cfd.fingerprint_delta(a, b) == "length 3 -> 2"


# --------------------------------------------------------------------- plotted series --

def test_lines_scatter_and_bars_are_all_read_off_the_figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot([1.0, 2.0, 3.0], [10.0, 20.0, 30.0])
    ax.scatter([4.0, 5.0], [40.0, 50.0])
    ax.bar([0, 1, 2], [7.0, 8.0, 9.0])
    got = dict(cfd.plotted_series(fig))
    plt.close(fig)
    assert got["axes0.line0.y"] == [10.0, 20.0, 30.0]
    assert got["axes0.coll0.y"] == [40.0, 50.0]
    assert got["axes0.bars.height"] == [7.0, 8.0, 9.0]


def test_the_snapshot_keeps_the_fingerprints_and_the_links():
    results = [{"label": "fig-x", "chapter": "ch09", "error": None,
                "series": {"axes0.line0.y": cfd.fingerprint([1.0, 2.0])},
                "matches": [{"file": "d.csv", "series": "a", "plotted_as": "axes0.line0.y",
                             "how": "as committed"}]}]
    snap = cfd.snapshot(results)
    assert snap["fig-x"]["links"] == {"d.csv::a": "as committed"}
    assert snap["fig-x"]["series"]["axes0.line0.y"]["n"] == 2
    json.dumps(snap)  # the baseline has to be serialisable


def test_a_figure_that_failed_to_draw_is_not_baselined():
    assert cfd.snapshot([{"label": "fig-y", "chapter": "ch09", "error": "ValueError: boom"}]) == {}
