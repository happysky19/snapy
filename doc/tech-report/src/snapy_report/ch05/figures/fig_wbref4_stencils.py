"""The SNAP_WB_REF4 face stencil (chapter 5): the four-cell window of the face density.

The face density at face f is the derivative at that face of the quartic through the primitive at five faces
(four cells), centred in the interior and kept inside the owned cells at a clamped wall, so the ghosts are never
read. x1 to the right. Cartoon; no data. Code it depicts: src/hydro/wb_ref4.cpp, `wb_ref4_stencils` step 1 and
`wb_ref4_faces`, at the code pin.
"""
from snapy_report.ch05 import _style as fs
from snapy_report.ch05 import _draw as d


def make_fig():
    fig, ax = fs.new_figure("double", 1.9)
    fs.cartoon(ax)
    d.row(ax, 0, 6, y=0.0, ghosts_lo=2)
    d.wall_at(ax, 0.0, y=0.0)
    for k in range(4):
        fs.cell_value(ax, k + 0.5, 0.8)
    for f in range(0, 5):
        fs.face_value(ax, f, 0.3)
    fs.bracket(ax, (0, 0.0), (4, 0.0), label="wall face: cells $i_s \\ldots i_s+3$")
    d.text(ax, 7.2, 0.3, "interior: $(-1, 7, 7, -1)/12$", ha="left")
    d.text(ax, 7.2, 0.9, "wall face: $(25, -23, 13, -3)/12$", ha="left")
    ax.set_xlim(-2.4, 10.4)
    ax.set_ylim(-0.75, 1.45)
    return fig
