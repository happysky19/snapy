import numpy as np, os
import t1lsnap as T, t1lmodel as Mod, t1lmop as MO, t1lop as O, ablate as A
import torch, snapy
from numpy.polynomial.legendre import leggauss
nz=128
blk=T.build(nz, workdir=os.path.join(T.HERE,'probe',f'n{nz}_covW'))
coord=blk.module('coord'); dz=float(coord.buffer('dx1f')[0]); dx=float(coord.buffer('dx2f')[0])
x2v=coord.buffer('x2v').numpy()[3:-3]; nx=x2v.size
zf=np.arange(nz+1)*dz
ra=np.array([A.cellavg(A.r0a,zf[i],zf[i+1]) for i in range(nz)])
pa=np.array([A.cellavg(A.p0a,zf[i],zf[i+1]) for i in range(nz)])
eos=blk.module('hydro.eos')
w=torch.zeros((eos.nvar(),1,nx+6,nz+6),dtype=torch.float64)
w[0,:,:,3:-3]=torch.as_tensor(ra); w[4,:,:,3:-3]=torch.as_tensor(pa)
dx1f=coord.buffer('dx1f')[3:-3].contiguous()
for rtol in (2e-14,5e-14,1e-13):
    try:
        wbb,res,sw=snapy.balance_column(w[:,:,3:-3,3:-3].contiguous(),dx1f,1.0,True,rtol,400)
        print("rtol",rtol,"res",res,"sweeps",sw); break
    except Exception as e:
        print("rtol",rtol,"FAIL",e)
rho_i=wbb[0,0,0].numpy(); p_i=wbb[4,0,0].numpy()
mdl=Mod.T1L(nz,nx,dz,dx,T.KX,T.INFO['mu'],T.INFO['K'],1.0,1.0-A.beta,A.beta)
M=MO.mode_operator(mdl,rho_i,p_i,T.KX,x2v)
v,_=O.leading(M)
r=v[0].real/T.SIGMA-1.
base=3.702031877710343e-04
print(f"A11 nz=128: rel={r:+.6e}  delta={r-base:+.6e}  x nz^2={(r-base)*nz*nz:+8.3f}")
