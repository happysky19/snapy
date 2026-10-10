import sys, json, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drivers'))
import numpy as np
import evp_t1l as E

eps = 1e-3
racs = {n: E.rac(eps, n) for n in (48, 64, 96)}
rc = racs[96]; ra = E.RA_FACTOR * rc
sig = {n: E.solve(ra, eps, n) for n in (48, 64, 96, 128)}
f = E.solve(ra, eps, 96, full=True)
out = dict(eps=eps, beta=E.beta_of(eps), Ra_c=rc, Ra_c_n=racs, Ra=ra,
           mu=E.mu_of(ra, eps), K=E.CP*E.mu_of(ra, eps), kx=E.KX,
           sigma=sig[96], sigma_n=sig, residual=f['residual'],
           sigma2=f['sigma2'])
print(json.dumps(out, indent=1, default=float))
np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'evp_e1e-3_n96.npz'),
         z=f['z'], q=f['q'], sigma=f['sigma'], **{k: f[k] for k in ('T','p','rho','mu','K')},
         beta=E.beta_of(eps), Ra=ra, kx=E.KX, eps=eps)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'out','evp_e1e-3.json'),'w'), indent=1, default=float)
