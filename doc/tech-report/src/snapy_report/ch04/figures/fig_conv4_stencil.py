"""The stencil of the fourth-order x1 cell-average to point conversion (ch04 _conv4).

Cartoon. It draws the three-cell stencil of Q (eq-ch04-conv4-op), the cell averages it reads, the point value
it hands the equation of state, and the two ends of a block: a physical wall on the left and an x1 seam on the
right, with the ghost cells the outermost stencil reaches. It mirrors the lambda `lap` and the weights of
`conv4_x1_weights` in src/hydro/hydro_forward.cpp at the code pin; nothing is read from disk and no number is
plotted.
"""
from snapy_report import figstyle as fs

NG = 2          # ghost cells drawn at each end (the book's decks use 3; two fit the page)
NOWN = 6        # owned cells drawn


def make_fig():
    fig, ax = fs.new_figure("double", 2.25)
    fs.cartoon(ax)
    y, h = 0.0, 0.9
    x0 = -NG                                  # the leftmost ghost starts here
    for k in range(-NG, NOWN + NG):
        ghost = k < 0 or k >= NOWN
        fs.cell(ax, k, y, 1.0, h, kind="ghost" if ghost else "fluid",
                fill=not ghost and k == 2)
        fs.cell_marker(ax, k + 0.5, y + 0.5 * h)
    # the converted cell i and its stencil
    ax.plot([2.5], [y + 0.5 * h], ls="none", marker="s", ms=6, mfc=fs.GREEN, mec=fs.BLACK, mew=0.5, zorder=5)
    fs.bracket(ax, (1.0, y), (4.0, y), label="the three cells of $k^{\\pm}_i$", offset=0.18)
    for k, name in ((1.5, "$i-1$"), (2.5, "$i$"), (3.5, "$i+1$")):
        ax.text(k, y + h + 0.12, name, ha="center", va="bottom", fontsize=fs.SMALL_PT)
    # the ends of the block
    fs.wall_line(ax, (0.0, y - 0.12), (0.0, y + h + 0.12))
    fs.seam(ax, (NOWN, y - 0.2), (NOWN, y + h + 0.2))
    ax.text(0.0, y - 0.62, "physical $x_1$ wall", ha="left", va="top", fontsize=fs.SMALL_PT)
    ax.text(NOWN, y - 0.62, "$x_1$ block seam", ha="right", va="top", fontsize=fs.SMALL_PT)
    # the outermost owned cell reaches a ghost; the outermost ghost is not converted
    fs.bracket(ax, (-1.0, y + h + 0.42), (2.0, y + h + 0.42),
               label="the stencil of cell $0$ reaches a ghost", offset=-0.18)
    ax.text(-NG + 0.5, y + 0.5 * h - 0.62, "not converted", ha="center", va="top", fontsize=fs.SMALL_PT,
            color=fs.PURPLE)
    ax.annotate("", xy=(-NG + 0.5, y - 0.06), xytext=(-NG + 0.5, y - 0.5),
                arrowprops=dict(arrowstyle="-", lw=0.7, color=fs.PURPLE))
    # legend, by shape and colour together (STYLE 6.2)
    ax.plot([], [], ls="none", marker="o", ms=5, mfc=fs.SKY, mec=fs.BLACK, mew=0.5,
            label="cell average $\\overline{\\mathbf{U}}$")
    ax.plot([], [], ls="none", marker="s", ms=6, mfc=fs.GREEN, mec=fs.BLACK, mew=0.5,
            label="point value $\\overline{\\mathbf{U}} - \\mathsf{Q}\\overline{\\mathbf{U}}$")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2,
              fontsize=fs.SMALL_PT, handletextpad=0.3, columnspacing=1.4)
    ax.set_xlim(-NG - 0.4, NOWN + NG + 0.4)
    ax.set_ylim(y - 1.5, y + h + 1.15)
    return fig
