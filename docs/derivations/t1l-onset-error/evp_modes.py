import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'drivers'))
import numpy as np, json
import evp_t1l as E
row = json.load(open(os.path.join(HERE, 'out', 'evp_e1e-3.json')))
E.HERE = HERE   # write modes/ into my folder
E.modes([dict(eps=row['eps'], Ra=row['Ra'], mu=row['mu'], K=row['K'], beta=row['beta'])])
