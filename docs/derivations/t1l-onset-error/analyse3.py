import json, numpy as np, os
HERE=os.path.dirname(os.path.abspath(__file__))
rows=[json.loads(l) for l in open(os.path.join(HERE,'out','rows.jsonl'))]
rows+=[json.loads(l) for l in open(os.path.join(HERE,'out','rows128.jsonl'))]
rows.sort(key=lambda r:r['nz'])
nz=np.array([r['nz'] for r in rows],float); dz=1/nz
keys=[k for k in rows[0] if k!='nz']
print("two-term fit c2 dz^2 + c3 dz^3 on the FINEST THREE (32,64,128) vs ALL FOUR")
print(f"{'term':38s}{'c2(fine3)':>11s}{'c3(fine3)':>11s}{'c2(all4)':>11s}{'c3(all4)':>11s}{'maxresid(fine3)':>17s}")
for k in keys:
    y=np.array([r.get(k,np.nan) for r in rows],float)
    out=[]
    for sl in (slice(1,4), slice(0,4)):
        m=np.isfinite(y[sl])
        d=dz[sl][m]; yy=y[sl][m]
        B=np.stack([d**2,d**3]).T
        c,*_=np.linalg.lstsq(B,yy,rcond=None)
        out.append(c)
        if sl.start==1:
            res=np.abs((B@c-yy)/np.where(yy!=0,yy,1)).max()
    print(f"{k:38s}{out[0][0]:+11.3f}{out[0][1]:+11.1f}{out[1][0]:+11.3f}{out[1][1]:+11.1f}{res:17.1e}")
base=np.array([r['base'] for r in rows])
a8=np.array([r['A8 curv flux: wall rows one-sided'] for r in rows])
a6=np.array([r['A6 gravity work -> cell form'] for r in rows])
print("\nresidual error after the A8 wall-curvature closure is applied:")
for i,n in enumerate(nz):
    print(f"  nz{int(n):4d}  base {base[i]:+.5e}  +A8 -> {base[i]+a8[i]:+.5e}   x nz^2 = {(base[i]+a8[i])*n*n:+8.4f}")
r=base+a8
print("  local log2 order of the residual:", " ".join(f"{np.log2(r[i]/r[i+1]):.3f}" for i in range(3)))
print("\nresidual error after A6 (face work -> cell work):")
for i,n in enumerate(nz):
    print(f"  nz{int(n):4d}  -> {base[i]+a6[i]:+.5e}   x nz^2 = {(base[i]+a6[i])*n*n:+8.4f}")
