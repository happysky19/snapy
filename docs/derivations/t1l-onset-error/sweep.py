import numpy as np, os, sys, json, time
import t1lsnap as T, t1lop as O
nz=int(sys.argv[1]); tag=sys.argv[2]; gw=os.environ.get('T1L_GW','face'); rtype=os.environ.get('T1L_RECON','weno5')
if rtype!='weno5':
    orig=T.R.card_text; T.R.card_text=lambda m,n,g,t,c: orig(m,n,g,t,c).replace("type: weno5","type: "+rtype)
blk=T.build(nz,gw=gw,workdir=os.path.join(T.HERE,'probe',f'n{nz}_{tag}'))
wb,res,sw=T.base_state(blk,nz)
M,L0=O.mode_operator(blk,wb,T.KX,eps=1e-6,dt=1.0)
np.save(os.path.join(T.HERE,'out',f'M_n{nz}_{tag}.npy'),M)
v,_=O.leading(M)
rec=dict(nz=nz,tag=tag,gw=gw,recon=rtype,wb4=os.environ.get('SNAP_WB_REF4'),cov=os.environ.get('SNAP_FLUX_COVARIANCE'),
         omega=float(v[0].real),rel=float(v[0].real/T.SIGMA-1),imag=float(v[0].imag),L0=float(np.abs(L0).max()),
         sigma2=float(v[1].real))
print("RESULT "+json.dumps(rec),flush=True)
