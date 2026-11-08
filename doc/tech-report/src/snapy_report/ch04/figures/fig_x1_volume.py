"""The radial x1 volume coordinate: a uniform r grid is a stretched v grid, and the wall mirror.

Cartoon of CoordinateImpl::x1_row_faces, src/coord/coordinate.cpp:546-562
@68f4e066974ede87e4379285c4fba895b970b7f1. Panel (a) maps twelve equal radial
cells on r in [1, 2] to their widths in v = r^3/3; panel (b) shows the three
ghost volumes mirrored about an inner wall face. It reads no data file: both
panels are computed from r here, with the same arithmetic as the check
src/snapy_report/ch04/checks/x1volume_check.py claims C5 and C7.
"""
import numpy as np

from snapy_report import figstyle as fs

NG = 3


def make_fig():
    fig, axes = fs.new_figure("double", 2.7, ncols=2)
    _widths(axes[0])
    _mirror(axes[1])
    fs.panel_labels(axes)
    return fig


def _widths(ax):
    """(a) twelve equal cells in r, and the same cells in v = r^3/3."""
    fs.cartoon(ax)
    r = np.linspace(1.0, 2.0, 13)
    v = r ** 3 / 3.0
    rs = (r - r[0]) / (r[-1] - r[0])          # both rows drawn on the same span
    vs = (v - v[0]) / (v[-1] - v[0])
    top, bot, h = 1.30, 0.45, 0.40
    for i in range(12):
        fs.cell(ax, rs[i], top, rs[i + 1] - rs[i], h, fill=True)
        fs.cell(ax, vs[i], bot, vs[i + 1] - vs[i], h, fill=True)
    ax.text(-0.05, top + 0.5 * h, "$r$", ha="right", va="center", fontsize=fs.LABEL_PT)
    ax.text(-0.05, bot + 0.5 * h, "$v$", ha="right", va="center", fontsize=fs.LABEL_PT)
    ax.text(0.5, top + h + 0.10, "twelve cells of equal $\\Delta x_1$, $r\\in[1,2]$",
            ha="center", va="bottom", fontsize=fs.SMALL_PT)
    for i, side in ((0, "narrowest"), (11, "widest")):
        fs.bracket(ax, (vs[i], bot), (vs[i + 1], bot), None, offset=0.10)
        ax.text(0.5 * (vs[i] + vs[i + 1]), bot - 0.24, side, ha="center", va="top",
                fontsize=fs.SMALL_PT, color=fs.VERMILLION)
    ratio = np.diff(v).max() / np.diff(v).min()
    ax.text(0.5, bot - 0.52,
            f"in $v=r^3/3$ the widest cell is ${ratio:.2f}$ times\n"
            "the narrowest; in $r$ they are all equal",
            ha="center", va="top", fontsize=fs.SMALL_PT)
    ax.set_xlim(-0.18, 1.04)
    ax.set_ylim(-0.70, 1.95)


def _mirror(ax):
    """(b) the ghost volumes mirrored about an inner wall face."""
    fs.cartoon(ax)
    r_int = np.linspace(1.0, 1.9, 7)
    v_int = r_int ** 3 / 3.0
    ghost = 2.0 * v_int[0] - v_int[1:NG + 1][::-1]
    v = np.concatenate([ghost, v_int])
    s = (v - v[0]) / (v[-1] - v[0])
    bot, h = 1.05, 0.42
    for i in range(len(s) - 1):
        kind = "ghost" if i < NG else "fluid"
        fs.cell(ax, s[i], bot, s[i + 1] - s[i], h, kind=kind, fill=True)
    fs.wall_line(ax, (s[NG], bot - 0.06), (s[NG], bot + h + 0.06))
    ax.text(s[NG], bot + h + 0.12, "wall face", ha="center", va="bottom",
            fontsize=fs.SMALL_PT)
    for k in range(NG):
        y = bot - 0.16 - 0.30 * k
        for side, (lo, hi) in zip((-1, 1), ((s[NG - 1 - k], s[NG - k]),
                                            (s[NG + k], s[NG + 1 + k]))):
            ax.plot([lo, lo, hi, hi], [y + 0.07, y, y, y + 0.07], color=fs.GREEN, lw=0.9)
            x, ha = (lo - 0.02, "right") if side < 0 else (hi + 0.02, "left")
            ax.text(x, y, f"$\\Delta v_{{{k}}}$", ha=ha, va="center",
                    fontsize=fs.SMALL_PT, color=fs.GREEN)
        ax.plot([s[NG], s[NG]], [y, bot], color=fs.GREY, lw=0.6, ls=":", zorder=0)
    ax.text(0.5, bot - 1.10,
            "each ghost volume is the interior one reflected in $v$,\n"
            "so the two one-sided states meet on the wall face",
            ha="center", va="top", fontsize=fs.SMALL_PT)
    ax.set_xlim(-0.14, 1.14)
    ax.set_ylim(-0.70, 1.95)
