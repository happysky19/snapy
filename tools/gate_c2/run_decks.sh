#!/bin/bash
# Run every gate deck with one build: run_decks.sh <tree> <decks> <runs> <site>
# Each deck runs in its own folder with the kintera data files beside it.
set -u
tree=$1; decks=$2; runs=$3; sp=$4
declare -A EXE=([straka_single]=straka [shock]=shock [bryan]=bryan
  [shallow_xy_single]=shallow_xy [jupiter_evap_precip_1d]=jupiter_evap_precip_1d)
for d in straka_single shock bryan shallow_xy_single jupiter_evap_precip_1d; do
  r=$runs/$d; rm -rf "$r"; mkdir -p "$r"; cd "$r" || exit 1
  cp "$decks/$d.yaml" .
  for f in "$tree"/build/tests/*.dat "$sp"/kintera/data/*; do
    [ -e "$f" ] && cp -n "$f" .
  done
  arg=$d.yaml
  [ "$d" = jupiter_evap_precip_1d ] && arg="-i $d.yaml"
  "$tree/build/bin/${EXE[$d]}.release" $arg > run.log 2>&1
  rc=$?
  echo "$rc" > rc.txt
  echo "run $(basename "$(dirname "$runs")")/$(basename "$runs") $d rc=$rc" \
    "restart=$(ls *.restart 2>/dev/null | wc -l) netcdf=$(ls *.nc 2>/dev/null | wc -l)"
done
