import numpy as np, os, sys
import t1lsnap as T, t1lop as O, t1lmodel as Mod, t1lmop as MO
nz=int(sys.argv[1])
blk=T.build(nz, workdir=os.path.join(T.HERE,'probe',f'n{nz}_covW')); wb,_,_=T.base_state(blk,nz)
coord=blk.module('coord')
x2v=coord.buffer('x2v').numpy()[3:-3]; dz=float(coord.buffer('dx1f')[0]); dx=float(coord.buffer('dx2f')[0])
nx=x2v.size
rho_i=T.interior(wb)[0,0,0].numpy(); p_i=T.interior(wb)[4,0,0].numpy()
mdl=Mod.T1L(nz,nx,dz,dx,T.KX,T.INFO['mu'],T.INFO['K'],1.0,1.0-T.BETA,T.BETA)
Mn = MO.mode_operator(mdl, rho_i, p_i, T.KX, x2v)
Ms,_ = O.mode_operator(blk, wb, T.KX, eps=1e-6, dt=1.0)
sc = np.abs(Ms).max()
print(f"nz={nz}  |M_snapy|max={sc:.4e}  max|dM|={np.abs(Mn-Ms).max():.4e}  rel={np.abs(Mn-Ms).max()/sc:.3e}")
# per-block breakdown
names=['r','v1','v2','p']
for a in range(4):
  row=[]
  for b in range(4):
    d=np.abs(Mn[a*nz:(a+1)*nz, b*nz:(b+1)*nz]-Ms[a*nz:(a+1)*nz, b*nz:(b+1)*nz]).max()
    row.append(f"{names[a]}<-{names[b]}:{d:.2e}")
  print("  "+" ".join(row))
vn,_=O.leading(Mn); vs,_=O.leading(Ms)
print(f"  Omega model={vn[0].real!r} snapy={vs[0].real!r} rel_model={vn[0].real/T.SIGMA-1:+.6e}")
