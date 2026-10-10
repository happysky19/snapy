#!/bin/bash
# Environment wrapper for the T1L onset-error scripts in this directory.
#
# The three paths below were ABSOLUTE in the run that produced the numbers in
# ../t1l-onset-error-theory.md; they pointed into the author's scratch workspace on dungeon3
# and are rewritten here as environment variables so the scripts are portable:
#
#   T1L_PYB  directory holding the snapy python extension built at 37dce4ef
#            (was <workspace>/finalhead-20261009/pyb-cpu/lib.linux-x86_64-cpython-311)
#   T1L_PY   python 3.11 interpreter with numpy, sympy and torch
#            (was <workspace>/snapy-kintera130/.venv-kintera130-py311/bin/python)
#   the working directory, which was <workspace>/t1l-theory-20261009, is now this directory
#
# t1lsnap.py additionally imports run_t1l.py from a drivers/ subdirectory; those three driver
# scripts (run_t1l.py, evp_t1l.py, fit_t1l.py) are Xi Zhang's and are not redistributed here.

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${T1L_PYB:?set T1L_PYB to the directory holding the snapy extension built at 37dce4ef}"
export SNAP_WB_REF4=1 SNAP_FLUX_COVARIANCE=1 OMP_NUM_THREADS=4
cd "$HERE"
exec "${T1L_PY:-python3}" -u "$@"
