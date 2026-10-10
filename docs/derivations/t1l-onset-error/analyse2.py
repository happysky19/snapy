import json, numpy as np, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
rows=[json.loads(l) for l in open(os.path.join(HERE,'out','rows.jsonl'))]
extra=os.path.join(HERE,'out','rows128.jsonl')
if os.path.exists(extra):
    rows += [json.loads(l) for l in open(extra)]
rows.sort(key=lambda r: r['nz'])
nzs=np.array([r['nz'] for r in rows],float); dz=1.0/nzs
keys=[k for k in rows[0] if k not in ('nz',)]
def two(y,d):
    B=np.stack([d**2,d**3]).T
    c,*_=np.linalg.lstsq(B,y,rcond=None); return c
hdr=f"{'term':38s}"+"".join(f"{int(n):>13d}" for n in nzs)+"  local log2 order"+"      c2       c3"
print(hdr); print("-"*len(hdr))
for k in keys:
    v=np.array([r.get(k,np.nan) for r in rows],float)
    o=[np.log2(v[i]/v[i+1]) if v[i]*v[i+1]>0 else np.nan for i in range(len(v)-1)]
    m=np.isfinite(v)
    c=two(v[m],dz[m]) if m.sum()>=2 else [np.nan,np.nan]
    print(f"{k:38s}"+"".join(f"{x:+13.4e}" for x in v)+"  "+" ".join(f"{x:5.2f}" for x in o)
          +f"  {c[0]:+8.3f} {c[1]:+8.1f}")
print("\nimplied pure coefficients  term*nz^2 (c2 if 2nd order) and term*nz^3 (c3 if 3rd order):")
for k in keys:
    v=np.array([r.get(k,np.nan) for r in rows],float)
    print(f"{k:38s} nz^2: "+" ".join(f"{x:+9.3f}" for x in v*nzs**2)
          +"   nz^3: "+" ".join(f"{x:+9.2f}" for x in v*nzs**3))
