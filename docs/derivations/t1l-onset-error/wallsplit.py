import numpy as np, os, sys
import t1lsnap as T, t1lop as O, t1lmodel as Mod, t1lmop as MO, ablate as A
GM1=Mod.GM1
print("per-wall decomposition of the analytic wall gravity-work term, and the adjoint scaling")
for nz in [int(a) for a in sys.argv[1:]] or [32,64,128]:
    blk,dz,dx,x2v,nx,rho_i,p_i=A.setup(nz)
    base,Mb=A.run(nz)
    val,vec=np.linalg.eig(Mb)
    j=np.argmax(np.where(np.abs(val.imag)<1e-6*np.abs(val.real)+1e-12,val.real,-np.inf))
    R=vec[:,j]; lam=val[j]
    vl,vL=np.linalg.eig(Mb.conj().T); jl=np.argmin(np.abs(vl-np.conj(lam)))
    L=vL[:,jl]; den=np.vdot(L,R)
    Rr=R.reshape(4,nz); Lr=L.reshape(4,nz)
    m=rho_i*Rr[1]
    dm0=(-3*m[0]+4*m[1]-m[2])/(2*dz); dmN=(3*m[-1]-4*m[-2]+m[-3])/(2*dz)
    def proj(idx, val_):
        v=np.zeros(4*nz,complex); v[3*nz+idx]=val_
        return (np.vdot(L,v)/den).real
    bot=proj(0,   +GM1*(dz/12.)*dm0)
    top=proj(nz-1,-GM1*(dz/12.)*dmN)
    tot=bot+top
    print(f" nz={nz:4d}  bottom {bot:+.5e} ({bot/tot*100:5.1f}%)  top {top:+.5e} ({top/tot*100:5.1f}%)  total {tot:+.5e}")
    print(f"          rel: bottom {bot/T.SIGMA:+.5e}  top {top/T.SIGMA:+.5e}  total {tot/T.SIGMA:+.5e}  x nz^3 = {tot/T.SIGMA*nz**3:+.2f}")
    # adjoint scaling near the wall: |L_p[0]| / |L_p|max
    s=np.abs(Lr[3]); print(f"          adjoint p row: |L_p[0]|/max={s[0]/s.max():.4e}  |L_p[-1]|/max={s[-1]/s.max():.4e}  (x nz: {s[0]/s.max()*nz:.4f}, {s[-1]/s.max()*nz:.4f})")
