"""The four-cell face window of the fourth-order reference and its weights."""
import matplotlib.pyplot as plt
from snapy_report import figstyle as fs


def make_fig():
    fs.apply()
    fig,ax=plt.subplots(figsize=(fs.DOUBLE,2.6))
    for i,w in zip(range(-2,2),['-1/12','7/12','7/12','-1/12']):
        ax.plot(i+.5,0,'o',color=fs.SKY,ms=9)
        ax.text(i+.5,.24,w,ha='center')
        ax.text(i+.5,-.24,'i'+(f'{i:+}' if i else ''),ha='center')
    for i in range(-2,3):
        ax.plot([i,i],[-.1,.1],color=fs.BLACK)
    ax.plot([-2.5,2.5],[0,0],color=fs.BLACK,lw=.6)
    ax.text(0,.65,'face density from four cell references; interior offsets in cell widths',ha='center')
    ax.text(0,-.65,'wall face, window kept inside the owned cells: (25,-23,13,-3)/12',ha='center',fontsize=8)
    ax.set(xlim=(-3,3),ylim=(-.9,.9));ax.axis('off')
    return fig
