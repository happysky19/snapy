"""Write the gate decks: five examples/*.yaml, 20 steps, every cycle written.

  python make_decks.py <examples_dir> <out_dir>

Only these keys change; the physics of each deck is the repository's:
  integration.nlim = 20, integration.ncycle_out = 1,
  every netcdf output: dt = 1e-9 (a file per cycle, same variables),
  restart output: replaced by one with dt = 1e-9 (FP64 state per cycle).
"""
import os
import sys

import yaml

# deck -> example executable (build/bin/<exe>.release)
DECKS = {
    "straka_single": "straka",  # dry, lmars, weno5, gravity, reflecting x1
    "shock": "shock",  # hllc, weno5 shock, outflow
    "bryan": "bryan",  # moist, lmars
    "shallow_xy_single": "shallow_xy",  # shallow-roe
    "jupiter_evap_precip_1d": "jupiter_evap_precip_1d",  # moist 1-D, hllc
}

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name in DECKS:
    with open(os.path.join(src, name + ".yaml")) as f:
        d = yaml.safe_load(f)
    d["integration"]["nlim"] = 20
    d["integration"]["ncycle_out"] = 1
    outs = [o for o in d.get("outputs", []) if o["type"] != "restart"]
    for o in outs:
        if o["type"] == "netcdf":
            o["dt"] = 1.0e-9
    outs.append({"type": "restart", "dt": 1.0e-9})
    d["outputs"] = outs
    with open(os.path.join(out, name + ".yaml"), "w") as f:
        yaml.safe_dump(d, f, sort_keys=False)
    print(f"deck {name}: examples/{name}.yaml -> {DECKS[name]}.release")
