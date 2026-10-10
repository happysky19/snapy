import numpy as np, json, sys
# baseline rel_err of the numpy-assembled L_h (t_model2.py, column "rel_model")
nz   = np.array([16., 32., 64., 128.])
yNP  = np.array([7.832348e-02, 1.188683e-02, 1.984346e-03, 3.702032e-04])
ySN  = np.array([7.832803483250861e-02, 1.1887922757627178e-02,
                 1.9848972540159604e-03, 3.7033119647889023e-04])
dz = 1./nz
print("nz      numpy L_h        compiled solver   diff")
for i in range(4):
    print(f"{nz[i]:5.0f}  {yNP[i]:+.6e}   {ySN[i]:+.6e}   {(yNP[i]-ySN[i])/ySN[i]:+.2e}")
print("\nmeasured (Xi): nz32 +1.18e-2  nz64 +1.98e-3")
print(f"  gate nz32: {yNP[1]/1.18e-2-1:+.4f}   gate nz64: {yNP[2]/1.98e-3-1:+.4f}")
print("\npairwise local order log2(y_i/y_{i+1}):")
for i in range(3):
    print(f"  {nz[i]:.0f}->{nz[i+1]:.0f}: ratio {yNP[i]/yNP[i+1]:.4f}  log2 {np.log2(yNP[i]/yNP[i+1]):.4f}")

def fit(basis, names, y=yNP, d=dz, use=slice(None)):
    B = np.stack([b(d[use]) for b in basis]).T
    c, *_ = np.linalg.lstsq(B, y[use], rcond=None)
    pred = np.stack([b(dz) for b in basis]).T @ c
    rel = (pred-y)/y
    return c, rel

models = {
 "c2 dz^2 + c3 dz^3":            ([lambda d: d**2, lambda d: d**3], ["c2","c3"]),
 "c2 dz^2 + c3 dz^3 + c4 dz^4":  ([lambda d: d**2, lambda d: d**3, lambda d: d**4], ["c2","c3","c4"]),
 "a dz^2 + b dz^2 log(dz)":      ([lambda d: d**2, lambda d: d**2*np.log(d)], ["a","b"]),
 "a dz^2 log(dz) only":          ([lambda d: d**2*np.log(d)], ["b"]),
 "c2 dz^2 only":                 ([lambda d: d**2], ["c2"]),
 "c3 dz^3 only":                 ([lambda d: d**3], ["c3"]),
}
print("\n--- least squares on all four nz (relative residual at each nz) ---")
for nm,(b,names) in models.items():
    c, rel = fit(b, names)
    print(f"{nm:32s} " + " ".join(f"{n}={v:+.4g}" for n,v in zip(names,c))
          + "   resid " + " ".join(f"{r:+.1e}" for r in rel) + f"   max {np.abs(rel).max():.1e}")
print("\n--- two-point exact fits (dz^2+dz^3) on consecutive pairs ---")
for i in range(3):
    A = np.array([[dz[i]**2, dz[i]**3],[dz[i+1]**2, dz[i+1]**3]])
    c = np.linalg.solve(A, yNP[i:i+2])
    print(f"  nz {nz[i]:.0f},{nz[i+1]:.0f}: c2={c[0]:+.4f} c3={c[1]:+.3f}")
print("\n--- extrapolated dz^2 coefficient (Richardson on dz^2 assumption) ---")
for i in range(3):
    print(f"  nz {nz[i]:.0f},{nz[i+1]:.0f}: c2_eff={(4*yNP[i+1]-yNP[i])/(3*dz[i+1]**2):+.4f}")
