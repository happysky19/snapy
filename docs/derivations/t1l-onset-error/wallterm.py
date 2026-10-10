"""Analytic evaluation of the wall gravity-work term against the measured eigenvalue shift."""
import numpy as np, os, sys
import t1lsnap as T, t1lop as O, t1lmodel as Mod, t1lmop as MO, ablate as A
GM1=Mod.GM1
for nz in [int(a) for a in sys.argv[1:]] or [16,32,64]:
    blk,dz,dx,x2v,nx,rho_i,p_i=A.setup(nz)
    base,Mb=A.run(nz)
    val,vec=np.linalg.eig(Mb)
    j=np.argmax(np.where(np.abs(val.imag)<1e-6*np.abs(val.real)+1e-12,val.real,-np.inf))
    R=vec[:,j]; lam=val[j]
    vl,vL=np.linalg.eig(Mb.conj().T); jl=np.argmin(np.abs(vl-np.conj(lam)))
    L=vL[:,jl]
    # normalise the right mode on w, and report the adjoint energy component near the walls
    Lr=L.reshape(4,nz); Rr=R.reshape(4,nz)
    Lr=Lr/np.abs(Lr).max()
    print(f"nz={nz} |adjoint| at cells 0,1,2 / mid / -3,-2,-1 for rows (r,v1,v2,p):")
    for v,name in enumerate(['r','v1','v2','p']):
        a=np.abs(Lr[v])
        print(f"   {name:3s} {a[0]:.3e} {a[1]:.3e} {a[2]:.3e} | {a[nz//2]:.3e} | {a[-3]:.3e} {a[-2]:.3e} {a[-1]:.3e}")
    # analytic wall term: energy-row source +/- g dz/12 d_z(rho0 w) at the two wall cells
    # d_z(rho0 w) from the discrete mode (centred difference of the cell values)
    m=rho_i*Rr[1]
    dm=np.zeros(nz, complex)
    dm[1:-1]=(m[2:]-m[:-2])/(2*dz)
    dm[0]=(-3*m[0]+4*m[1]-m[2])/(2*dz); dm[-1]=(3*m[-1]-4*m[-2]+m[-3])/(2*dz)
    Tpsi=np.zeros(4*nz, complex)
    Tpsi[3*nz+0]  = +GM1*(dz/12.)*dm[0]      # energy row -> primitive p row: multiply by (gamma-1)
    Tpsi[3*nz+nz-1]= -GM1*(dz/12.)*dm[-1]
    den=np.vdot(L,R)
    pred=(np.vdot(L,Tpsi)/den).real
    print(f"   analytic wall gravity-work dOmega = {pred:+.6e}   -> rel {pred/T.SIGMA:+.6e}")
    print(f"   measured A8 (wall curv one-sided) rel = (see ablation table)")
