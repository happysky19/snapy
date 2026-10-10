"""Combined ablations: test additivity and the A8 / A10 interaction."""
import numpy as np, sys, json
import t1lsnap as T, ablate as A
rows={}
for nz in [int(a) for a in sys.argv[1:]] or [32,64,128]:
    out={}
    out['base'],_=A.run(nz)
    out['A8'],_=A.run(nz, abl=dict(gw_wall1side=True))
    out['A10'],_=A.run(nz, wb4=False)
    out['A8+A10'],_=A.run(nz, abl=dict(gw_wall1side=True), wb4=False)
    out['A4+A7 (cov off, curv off)'],_=A.run(nz, cov=False, curv=False)
    out['A8+A1'],_=A.run(nz, abl=dict(gw_wall1side=True))  # placeholder
    print(f"nz={nz}")
    for k in ('base','A8','A10','A8+A10','A4+A7 (cov off, curv off)'):
        v=out[k]
        print(f"   {k:28s} rel={v:+.6e}  x nz^2={v*nz*nz:+9.4f}  x nz^3={v*nz**3:+10.2f}")
    d8=out['A8']-out['base']; d10=out['A10']-out['base']; d=out['A8+A10']-out['base']
    print(f"   additivity: dA8 {d8:+.4e} + dA10 {d10:+.4e} = {d8+d10:+.4e}  vs joint {d:+.4e}  "
          f"(nonlinearity {(d-(d8+d10))/abs(d):+.2%})")
    # the wall term with wb4 off
    print(f"   A8 shift with wb4 ON  x nz^3 = {d8*nz**3:+8.2f} ; with wb4 OFF x nz^3 = {(out['A8+A10']-out['A10'])*nz**3:+8.2f}")
