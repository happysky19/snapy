#!/usr/bin/env python3
"""The x1 reference's H_ref survives a restart bitwise.

The factored x1 reference rows divide out exp(-z / H_ref), with H_ref set once at setup from the
bottom cells (MeshImpl::set_x1_href). A restart must not recompute it from the restart state's
bottom cells, which have moved by then: the restart file carries it. straka_single.yaml (one
block, CPU) runs straight to T2, and again stopped at T1 and resumed from that restart; the
final hydro_u of the two must be bitwise equal. The test also checks that the bottom row's
min p/rho did move by T1, so a recomputed H_ref would differ."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_restart_output_schedule import restart_tensors, write_case

T1, T2 = 30.0, 60.0
NG = 3


def bottom_min_rt(t):
  u = t["hydro_u"]
  rho = u[0]
  e = u[4] - 0.5 * (u[1] ** 2 + u[2] ** 2 + u[3] ** 2) / rho
  p = 0.4 * e  # gammad 1.4 in straka_single.yaml
  return float((p / rho)[..., NG:-NG, NG].min())  # interior x2, bottom x1 row


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--build-dir", required=True)
  ap.add_argument("--build-type", required=True)
  a = ap.parse_args()
  build = Path(a.build_dir).resolve()
  exe = build / "bin" / f"straka.{a.build_type}"
  base_yaml = Path(__file__).resolve().parent.parent / "examples" / "straka_single.yaml"
  work = build / "tests" / "restart_x1_href"
  env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1")
  restart = {"type": "restart", "dt": T1}

  straight = write_case(base_yaml, work / "straight", T2, [restart])
  subprocess.run([str(exe), straight.name], cwd=straight.parent, env=env, check=True,
                 stdout=subprocess.DEVNULL)
  files = sorted(straight.parent.glob("*.restart"))
  at = {round(float(restart_tensors(f)["last_time"].item()), 6): f for f in files}
  t1 = min(t for t in at if t >= T1 - 1e-9)
  t2 = max(at)
  first = restart_tensors(at[t1])

  resumed = write_case(base_yaml, work / "resumed", T2, [restart])
  subprocess.run([str(exe), resumed.name, "--restart", str(at[t1])], cwd=resumed.parent,
                 env=env, check=True, stdout=subprocess.DEVNULL)
  rfiles = sorted(resumed.parent.glob("*.restart"))
  r_at = {round(float(restart_tensors(f)["last_time"].item()), 6): f for f in rfiles}
  end_a = restart_tensors(at[t2])
  end_b = restart_tensors(r_at[max(r_at)])

  ua, ub = end_a["hydro_u"], end_b["hydro_u"]
  same = max(r_at) == t2 and torch.equal(ua, ub)
  moved = "x1_href" in first and \
      abs(bottom_min_rt(first) / 9.8 - float(first["x1_href"].item())) > 0.
  print(f"resume at t = {t1:g} s to {t2:g} s: hydro_u bitwise equal: {same}; "
        f"max |diff| = {float((ua - ub).abs().max()) if ua.shape == ub.shape else 'shape'}")
  if "x1_href" in first:
    print(f"stored H_ref = {float(first['x1_href'].item())!r} m; "
          f"bottom-row min (p/rho)/g at t = {t1:g} s = {bottom_min_rt(first) / 9.8!r} m")
  else:
    print("the restart file carries no x1_href")
  ok = same and moved
  print("### restart x1 H_ref test " + ("passed" if ok else "FAILED") + ". ###")
  return 0 if ok else 1


if __name__ == "__main__":
  sys.exit(main())
