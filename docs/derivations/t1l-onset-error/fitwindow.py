"""Reproduce fit_t1l.py's growth-rate fit on the EXACT linear evolution of the discrete
operator, to separate the fit-window error from the eigenvalue error."""
import numpy as np, os, sys, math
import t1lsnap as T, t1lop as O, t1lmodel as Mod, t1lmop as MO, ablate as A
HERE=T.HERE
SIG=T.SIGMA
def fitslope(t,a,t0,t1):
    s=(t>=t0)&(t<=t1)
    return float(np.polyfit(t[s],np.log(np.abs(a[s])),1)[0])
for nz in [int(x) for x in sys.argv[1:]] or [32,64,128]:
    m=np.load(os.path.join(HERE,'modes',f'mode_e1e-03_n{nz}.npz'))
    blk,dz,dx,x2v,nx,rho_i,p_i=A.setup(nz)
    base,M=A.run(nz)
    lam,V=np.linalg.eig(M)
    Vi=np.linalg.inv(V)
    Tb=p_i/rho_i
    seed=np.zeros((4,nz),complex)
    seed[0]=m['r']; seed[1]=m['w']; seed[2]=m['u']; seed[3]=Tb*m['r']+rho_i*m['theta']
    s0=seed.reshape(-1)
    wE=m['w']; nE=(rho_i*np.abs(wE)**2).sum(); nEi=(rho_i*np.abs(wE)**2)[1:-1].sum()
    # exact semi-discrete evolution, sampled like the driver (40 points per e-fold)
    t=np.arange(0, 5.4/SIG, 1.0/(40*SIG))
    c=Vi@s0
    Aw=np.empty(t.size,complex); Awi=np.empty(t.size,complex)
    for i,tt in enumerate(t):
        y=(V@(c*np.exp(lam*tt))).reshape(4,nz)
        Aw[i]=(rho_i*y[1]*wE.conj()).sum()/nE
        Awi[i]=(rho_i*y[1]*wE.conj())[1:-1].sum()/nEi
    lam1=lam[np.argmax(lam.real)].real
    e1,e3,e5=1/SIG,3/SIG,5/SIG
    s15=fitslope(t,Aw,e1,e5); s13=fitslope(t,Aw,e1,e3); s35=fitslope(t,Aw,e3,e5)
    s15i=fitslope(t,Awi,e1,e5)
    print(f"nz={nz:4d} lam1={lam1!r}  rel(lam1)={lam1/SIG-1:+.6e}")
    print(f"      fit[1,5] ={s15!r} rel={s15/SIG-1:+.6e}   fit-window shift vs lam1 = {(s15-lam1)/SIG:+.3e}")
    print(f"      fit[1,3] rel={s13/SIG-1:+.6e}  fit[3,5] rel={s35/SIG-1:+.6e}  window_spread={(s35-s13)/SIG:+.3e}")
    print(f"      nowall   rel={s15i/SIG-1:+.6e}")
    # sub-dominant eigenvalue and seed contamination
    o=np.argsort(-lam.real)
    print(f"      lam2={lam[o[1]].real:+.6e} gap={(lam1-lam[o[1]].real)/SIG:.3f} sigma ; "
          f"|c2/c1| at t=0 -> {abs(c[o[1]])/abs(c[o[0]]):.3e}, at 1 efold -> "
          f"{abs(c[o[1]]*np.exp(lam[o[1]]*e1))/abs(c[o[0]]*np.exp(lam[o[0]]*e1)):.3e}")
