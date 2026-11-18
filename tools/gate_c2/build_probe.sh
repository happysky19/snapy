#!/bin/bash
# Compile onhost_probe.cpp against a built tree, with that tree's own test
# compile and link flags: build_probe.sh <tree> <out_dir> <probe.cpp>
set -eu
tree=$1; out=$2; srcf=$3
mkdir -p "$out"
F=$tree/build/tests/CMakeFiles/test_pressure_scan_x1.release.dir
DEF=$(grep '^CXX_DEFINES' "$F/flags.make" | cut -d= -f2-)
INC=$(grep '^CXX_INCLUDES' "$F/flags.make" | cut -d= -f2-)
FL=$(grep '^CXX_FLAGS' "$F/flags.make" | cut -d= -f2-)
LINK=$(sed "s|CMakeFiles/test_pressure_scan_x1.release.dir/test_pressure_scan_x1.cpp.o -o test_pressure_scan_x1.release|$out/onhost_probe.o -o $out/onhost_probe|; s|\.\./lib/|$tree/build/lib/|g" "$F/link.txt")
c++ $DEF $INC $FL -c "$srcf" -o "$out/onhost_probe.o"
eval "$LINK"
echo "built $out/onhost_probe"
