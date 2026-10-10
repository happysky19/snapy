import numpy as np, os, sys, json
import t1lsnap as T, t1lop as O, t1lmodel as Mod, t1lmop as MO
from numpy.polynomial.legendre import leggauss
GAMMA=Mod.GAMMA; GM1=Mod.GM1
xg,wg=leggauss(14)
def cellavg(f,a,b):
    c=0.5*(a+b); h=0.5*(b-a)
    return sum(wg[q]*f(c+h*xg[q]) for q in range(len(xg)))/2.
beta=T.BETA
T0=lambda z:1.-beta*z
p0a=lambda z:T0(z)**(1./beta)
r0a=lambda z:p0a(z)/T0(z)

def setup(nz, ic="point"):
    blk=T.build(nz, workdir=os.path.join(T.HERE,'probe',f'n{nz}_covW'))
    coord=blk.module('coord'); dz=float(coord.buffer('dx1f')[0]); dx=float(coord.buffer('dx2f')[0])
    x2v=coord.buffer('x2v').numpy()[3:-3]; nx=x2v.size
    if ic=="point":
        wb,_,_=T.base_state(blk,nz)
        rho_i=T.interior(wb)[0,0,0].numpy(); p_i=T.interior(wb)[4,0,0].numpy()
    else:
        import torch, snapy
        zf=np.arange(nz+1)*dz
        ra=np.array([cellavg(r0a,zf[i],zf[i+1]) for i in range(nz)])
        pa=np.array([cellavg(p0a,zf[i],zf[i+1]) for i in range(nz)])
        eos=blk.module('hydro.eos')
        w=torch.zeros((eos.nvar(),1,nx+6,nz+6),dtype=torch.float64)
        w[0,:,:, 3:-3]=torch.as_tensor(ra); w[4,:,:,3:-3]=torch.as_tensor(pa)
        I2,I1=slice(3,-3),slice(3,-3)
        dx1f=coord.buffer('dx1f')[I1].contiguous()
        wbb,res,sw=snapy.balance_column(w[:,:,I2,I1].contiguous(),dx1f,1.0,True,1e-14,400)
        rho_i=wbb[0,0,0].numpy(); p_i=wbb[4,0,0].numpy()
    return blk,dz,dx,x2v,nx,rho_i,p_i

def run(nz, abl=None, wb4=True, cov=True, gw="face", curv=True, ic="point"):
    blk,dz,dx,x2v,nx,rho_i,p_i=setup(nz,ic)
    mdl=Mod.T1L(nz,nx,dz,dx,T.KX,T.INFO['mu'],T.INFO['K'],1.0,1.0-beta,beta,
                wb4=wb4,cov=cov,gw=gw,curv=curv)
    mdl.abl=abl or {}
    M=MO.mode_operator(mdl,rho_i,p_i,T.KX,x2v)
    v,_=O.leading(M)
    return v[0].real/T.SIGMA-1., M

zfun=lambda nz: np.arange(nz+1)/nz
cfun=lambda nz: (np.arange(nz)+0.5)/nz

def exact_arrays(nz):
    zf=zfun(nz); zc=cfun(nz)
    return dict(Rf=r0a(zf), Pf=p0a(zf), Zf=np.sqrt(GAMMA*p0a(zf)*r0a(zf)),
                hf=GAMMA*p0a(zf)/(GM1*r0a(zf)), dh=np.full(nz,-GAMMA*beta/GM1))

if __name__=="__main__":
    nzs=[int(a) for a in sys.argv[1:]] or [16,32,64,128]
    out=[]
    for nz in nzs:
        ex=exact_arrays(nz)
        base,Mb=run(nz)
        # base face density actually used
        blk,dz,dx,x2v,nx,rho_i,p_i=setup(nz)
        mdl=Mod.T1L(nz,nx,dz,dx,T.KX,T.INFO['mu'],T.INFO['K'],1.0,1.0-beta,beta)
        w0=np.zeros((4,nx,nz+6)); w0[0,:,3:-3]=rho_i[None,:]; w0[3,:,3:-3]=p_i[None,:]
        wm=mdl.fill_ghosts(w0.copy()); lo,hi,pref,dref,dsf=mdl.reference(wm)
        dp=wm[3]-pref; dr=wm[0]-dref; il,iu=mdl.il,mdl.iu
        for q in (dp,dr):
            q[:,:il]=q[:,il:il+3][:,::-1]; q[:,iu+1:]=q[:,iu+1-3:iu+1][:,::-1]
        prR,_=Mod.recon_c5(dr); ppR,_=Mod.recon_c5(dp)
        Rf=(prR+dsf)[0,il:iu+2]; Pf=(ppR+lo)[0,il:iu+2]
        cases={
         "A1 face density R_f -> rho_a(z_f)": dict(abl=dict(dsf_off=ex['Rf']-Rf)),
         "A2 impedance Z_f -> sqrt(g p rho)": dict(abl=dict(Zf=ex['Zf'])),
         "A3 energy-flux enthalpy -> exact": dict(abl=dict(hf=ex['hf'])),
         "A4 covariance OFF":                 dict(cov=False),
         "A5 covariance d1[h] -> exact":      dict(abl=dict(cov_dh=ex['dh'])),
         "A6 gravity work -> cell form":      dict(gw="cell"),
         "A7 face grav work, no curv flux":   dict(curv=False),
         "A8 curv flux: wall rows one-sided": dict(abl=dict(gw_wall1side=True)),
         "A9 vertical recon C5 -> C7":        dict(abl=dict(recon7=True)),
         "A10 SNAP_WB_REF4 OFF":              dict(wb4=False),
         "A11 base state -> cell averages":   dict(ic="avg"),
        }
        row=dict(nz=nz, base=base)
        for k,kw in cases.items():
            try:
                r,_=run(nz,**kw)
                row[k]=r-base
            except Exception as e:
                row[k]=None; print("FAIL",k,e, flush=True)
        out.append(row)
        print("ROW "+json.dumps(row), flush=True)
    json.dump(out, open(os.path.join(T.HERE,'out','ablation.json'),'w'), indent=1)
