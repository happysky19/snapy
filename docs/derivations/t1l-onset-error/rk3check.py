"""Time-discretisation (rk3, fixed dt) contribution to the measured growth rate."""
import numpy as np, math, sys
import t1lsnap as T, ablate as A
for nz in [32,64,128]:
    blk=T.build(nz)
    wb,_,_=T.base_state(blk,nz)
    import torch
    bv,_=blk.initialize({'hydro_w': wb.clone()})
    dt=float(blk.max_time_step(bv))
    lam=T.SIGMA*(1+ {32:1.188683e-02,64:1.984346e-03,128:3.702032e-04}[nz])
    z=lam*dt
    R=1+z+z**2/2+z**3/6
    lam_fd=math.log(R)/dt
    print(f"nz={nz:4d} dt={dt:.6e}  C_z={math.sqrt(1.4)*dt*nz:.4f}  lam*dt={z:.3e}  "
          f"rk3 lam_discrete-lam = {(lam_fd-lam):+.3e}  relative to sigma: {(lam_fd-lam)/T.SIGMA:+.3e}")
