"""First-order perturbation theory for EVERY ablated term: dOmega_k = <psiL, T_k psiR>/<psiL,psiR>.
Discrete inner product: plain Euclidean sum over the 4 nz primitive rows (uniform grid, so the
cell volume dz is a constant that cancels in the ratio).  Wall rows are ordinary rows of M."""
import numpy as np, os, sys, json
import t1lsnap as T, t1lop as O, t1lmodel as Mod, t1lmop as MO, ablate as A
for nz in [int(a) for a in sys.argv[1:]] or [64]:
    ex=A.exact_arrays(nz)
    blk,dz,dx,x2v,nx,rho_i,p_i=A.setup(nz)
    base,Mb=A.run(nz)
    val,vec=np.linalg.eig(Mb)
    j=np.argmax(np.where(np.abs(val.imag)<1e-6*np.abs(val.real)+1e-12,val.real,-np.inf))
    R=vec[:,j]; lam=val[j]
    vl,vL=np.linalg.eig(Mb.conj().T); jl=np.argmin(np.abs(vl-np.conj(lam)))
    L=vL[:,jl]; den=np.vdot(L,R)
    nb=1
    rows=np.zeros(4*nz,bool)
    for v in range(4):
        rows[v*nz]=True; rows[v*nz+nz-1]=True
    cases={
     "A1 face density R_f -> rho_a(z_f)": None,
     "A2 impedance Z_f -> sqrt(g p rho)": dict(abl=dict(Zf=ex['Zf'])),
     "A3 energy-flux enthalpy -> exact":  dict(abl=dict(hf=ex['hf'])),
     "A4 covariance OFF":                 dict(cov=False),
     "A5 covariance d1[h] -> exact":      dict(abl=dict(cov_dh=ex['dh'])),
     "A6 gravity work -> cell form":      dict(gw="cell"),
     "A7 face grav work, no curv flux":   dict(curv=False),
     "A8 curv flux: wall rows one-sided": dict(abl=dict(gw_wall1side=True)),
     "A9 vertical recon C5 -> C7":        dict(abl=dict(recon7=True)),
     "A10 SNAP_WB_REF4 OFF":              dict(wb4=False),
    }
    # A1 needs the actually-used face density
    mdl=Mod.T1L(nz,nx,dz,dx,T.KX,T.INFO['mu'],T.INFO['K'],1.0,1.0-A.beta,A.beta)
    w0=np.zeros((4,nx,nz+6)); w0[0,:,3:-3]=rho_i[None,:]; w0[3,:,3:-3]=p_i[None,:]
    wm=mdl.fill_ghosts(w0.copy()); lo,hi,pref,dref,dsf=mdl.reference(wm)
    dp=wm[3]-pref; dr=wm[0]-dref; il,iu=mdl.il,mdl.iu
    for q in (dp,dr):
        q[:,:il]=q[:,il:il+3][:,::-1]; q[:,iu+1:]=q[:,iu+1-3:iu+1][:,::-1]
    prR,_=Mod.recon_c5(dr); Rf=(prR+dsf)[0,il:iu+2]
    cases["A1 face density R_f -> rho_a(z_f)"]=dict(abl=dict(dsf_off=ex['Rf']-Rf))
    print(f"=== nz={nz}  Omega={lam.real!r}  rel={base:+.6e}")
    print(f"{'term':38s}{'1st-order dOmega/sig':>22s}{'exact ablation':>17s}{'ratio':>8s}{'wall-cell share':>17s}{'x nz^2':>9s}{'x nz^3':>10s}")
    tot=0.
    for k,kw in cases.items():
        r,Ma=A.run(nz,**kw)
        Tk=Mb-Ma
        first=(np.vdot(L,Tk@R)/den).real
        pred=-first/T.SIGMA
        wall=(np.vdot(L*rows,Tk@R)/den).real
        tot+=pred
        print(f"{k:38s}{pred:+22.6e}{r-base:+17.6e}{pred/(r-base) if r!=base else np.nan:+8.3f}"
              f"{wall/first if first else np.nan:+17.3f}{pred*nz**2:+9.3f}{pred*nz**3:+10.2f}")
    print(f"{'(sum of the ten first-order shifts)':38s}{tot:+22.6e}{'':17s}{'':8s}{'':17s}{tot*nz**2:+9.3f}{tot*nz**3:+10.2f}")
