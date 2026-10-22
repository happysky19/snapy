#!/usr/bin/env bash
# One command that turns a fresh machine into one that can reproduce this report.
#
#     bash setup.sh                 # the report: checks, figures, every gate, the HTML and the PDF
#     bash setup.sh --with-native   # the above, plus the pinned snapy/kintera/pyharp/pydisort build
#
# Everything lands under one prefix (default ./.report-env) and nothing is installed system-wide:
# no package manager, no sudo, no write outside the prefix and the repository. Every download is
# checked against the sha256 committed in tools/env-pins.json before it is unpacked. Versions come
# from tools/env-pins.json (Quarto, TinyTeX, Universal Ctags, NetCDF, HDF5), tools/requirements.txt
# (Python), code_pin.yml (snapy) and tools/package-pins.json (kintera, pyharp).
#
# When it finishes it writes <prefix>/activate. Source that and every command in README.md,
# FIGURES.md, AUTHOR-CHECKLIST.md and the chapters' `run:` tags works as written:
#
#     source .report-env/activate
#     python3 tools/render_gate.py book/
#
# activate also points every cache -- TeX, Jupyter, matplotlib, pip, XDG, SNAPY_REPORT_CACHE -- inside
# the prefix. That is not a nicety: LuaTeX aborts with "no writeable cache path" and tools/code_anchors.py
# fails outright when $HOME is read-only, which is the normal state on a shared or containerised host.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="$HERE/.report-env"
WITH_NATIVE=0
FORCE_NETCDF_BUILD=0
PRINT_DIGESTS=0
JOBS="$( (command -v nproc >/dev/null && nproc) || sysctl -n hw.ncpu 2>/dev/null || echo 4)"

usage() {
  sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

Options:
  --prefix DIR           where to install (default: doc/tech-report/.report-env)
  --with-native          also build pydisort, pyharp, kintera and snapy at their pins
  --force-netcdf-build   build NetCDF and HDF5 from source even if the machine already has them
  --jobs N               parallel compile jobs (default: all cores)
  --print-digests        download every artifact and print its sha256, then stop
  -h, --help             this text
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="$(mkdir -p "$2" && cd "$2" && pwd)"; shift 2 ;;
    --with-native) WITH_NATIVE=1; shift ;;
    --force-netcdf-build) FORCE_NETCDF_BUILD=1; shift ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --print-digests) PRINT_DIGESTS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "setup.sh: unknown option $1 (try --help)" >&2; exit 2 ;;
  esac
done

PINS="$HERE/tools/env-pins.json"
DL="$PREFIX/downloads"
SRC="$PREFIX/src"
CACHE="$PREFIX/cache"
LOGS="$PREFIX/logs"

# Progress goes to stderr so that a function can return a value on stdout: `fetch` prints the path of
# the file it verified, and `$(fetch ...)` must capture that and nothing else.
step()  { printf '\n\033[1m==> %s\033[0m\n' "$*" >&2; }
info()  { printf '    %s\n' "$*" >&2; }
die()   { printf '\n\033[31msetup.sh: %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight --

step "Preflight"

for t in curl tar make cmake git; do
  command -v "$t" >/dev/null || die "\`$t\` is not on PATH; it is needed to build the dependencies"
done
command -v cc >/dev/null || command -v gcc >/dev/null || die "no C compiler on PATH"
command -v c++ >/dev/null || command -v g++ >/dev/null || die "no C++ compiler on PATH"

# The interpreter to build the virtual environment with: the newest of python3.13/3.12/3.11 present,
# else `python3` if it is inside the window env-pins.json allows.
PY_MIN="$(python3 -c "import json;print(json.load(open('$PINS'))['python']['minimum'])" 2>/dev/null || echo 3.11)"
PY_MAX="$(python3 -c "import json;print(json.load(open('$PINS'))['python']['below'])" 2>/dev/null || echo 3.14)"
PYTHON=""
for c in python3.13 python3.12 python3.11 python3; do
  command -v "$c" >/dev/null || continue
  if "$c" - "$PY_MIN" "$PY_MAX" <<'EOF' >/dev/null 2>&1
import sys
lo = tuple(int(p) for p in sys.argv[1].split("."))
hi = tuple(int(p) for p in sys.argv[2].split("."))
sys.exit(0 if lo <= sys.version_info[:2] < hi else 1)
EOF
  then PYTHON="$(command -v "$c")"; break; fi
done
[ -n "$PYTHON" ] || die "no Python in [$PY_MIN, $PY_MAX) on PATH; env-pins.json explains why that window"
info "python      $("$PYTHON" -V 2>&1) at $PYTHON"

case "$(uname -s)" in
  Linux)  OS=linux ;;
  Darwin) OS=darwin ;;
  *) die "unsupported OS $(uname -s); add its artifacts to tools/env-pins.json" ;;
esac
case "$(uname -m)" in
  x86_64|amd64)  ARCH=x86_64 ;;
  arm64|aarch64) ARCH=aarch64 ;;
  *) die "unsupported CPU $(uname -m); add its artifacts to tools/env-pins.json" ;;
esac
# TinyTeX and Quarto ship one universal macOS build, so darwin needs no architecture.
if [ "$OS" = darwin ]; then PLATFORM=darwin; else PLATFORM="$OS-$ARCH"; fi
info "platform    $PLATFORM"
info "prefix      $PREFIX"
info "jobs        $JOBS"

mkdir -p "$DL" "$SRC" "$LOGS" "$PREFIX/bin" \
         "$CACHE"/{pip,xdg,matplotlib,ipython,jupyter/runtime,jupyter/data,tmp,snapy-report,texmf-var,texmf-config}

# setup.sh is itself subject to the read-only $HOME it exists to work around: pip and matplotlib are
# both run below. activate exports the full set for every later session.
export MPLCONFIGDIR="$CACHE/matplotlib" XDG_CACHE_HOME="$CACHE/xdg" TMPDIR="$CACHE/tmp"

# Read one field out of env-pins.json.
pin() { "$PYTHON" -c "
import json,sys
d=json.load(open('$PINS'))
for k in sys.argv[1:]:
    d = d[int(k)] if isinstance(d, list) else d[k]
print(' '.join(d) if isinstance(d,list) else d)" "$@"; }

# pin_artifact <section> <name> -> prints 'url sha256 strip', falling back to the 'source' artifact
# for the platform-independent tarballs.
pin_artifact() {
  "$PYTHON" -c "
import json,sys
sec,name,plat = sys.argv[1],sys.argv[2],sys.argv[3]
a = json.load(open('$PINS'))[sec][name]['artifacts']
e = a.get(plat) or a.get('source')
if e is None:
    sys.exit('no artifact for %s/%s on %s' % (sec,name,plat))
print(e['url'], e['sha256'], e.get('strip',1))" "$1" "$2" "$3"
}

# fetch <url> <sha256> -> downloads once into $DL and verifies, or dies.
fetch() {
  local url="$1" want="$2" out="$DL/$(basename "$1")" got
  if [ ! -f "$out" ]; then
    info "download  $(basename "$url")"
    curl -fsSL --retry 3 -o "$out.part" "$url" || die "could not download $url"
    mv "$out.part" "$out"
  fi
  got="$(sha256sum "$out" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "$out" | cut -d' ' -f1)"
  if [ "$PRINT_DIGESTS" = 1 ]; then printf '    %s  %s\n' "$got" "$(basename "$url")" >&2; return 0; fi
  [ "$got" = "$want" ] || die "sha256 mismatch for $url
    committed in tools/env-pins.json: $want
    the file that was served:         $got
  Refusing to unpack it. If upstream re-cut the release, re-record the digest with --print-digests."
  echo "$out"
}

# unpack <tarball> <destdir> <strip>
unpack() {
  mkdir -p "$2"
  tar -x -f "$1" -C "$2" --strip-components="$3"
}

if [ "$PRINT_DIGESTS" = 1 ]; then
  step "Digests of every pinned artifact on $PLATFORM"
  for spec in "render quarto" "render tinytex" "render universal-ctags" "native netcdf-c" "native hdf5"; do
    read -r u s _ <<<"$(pin_artifact ${spec% *} ${spec#* } "$PLATFORM")"
    fetch "$u" "$s" >/dev/null
  done
  exit 0
fi

# ------------------------------------------------------------------- quarto --

step "Quarto $(pin render quarto version)"
if [ ! -x "$PREFIX/quarto/bin/quarto" ]; then
  read -r URL SHA STRIP <<<"$(pin_artifact render quarto "$PLATFORM")"
  unpack "$(fetch "$URL" "$SHA")" "$PREFIX/quarto" "$STRIP"
fi
ln -sf "$PREFIX/quarto/bin/quarto" "$PREFIX/bin/quarto"
info "$("$PREFIX/bin/quarto" --version 2>/dev/null || echo '?')"

# ------------------------------------------------------------------ tinytex --

step "TinyTeX $(pin render tinytex version) ($(pin render tinytex scheme))"
if [ ! -d "$PREFIX/tinytex/bin" ]; then
  read -r URL SHA STRIP <<<"$(pin_artifact render tinytex "$PLATFORM")"
  unpack "$(fetch "$URL" "$SHA")" "$PREFIX/tinytex" "$STRIP"
fi
TEXBIN="$(dirname "$(find "$PREFIX/tinytex/bin" -name lualatex -type f -o -name lualatex -type l | head -1)")"
[ -n "$TEXBIN" ] || die "the TinyTeX tarball carried no lualatex"
for b in "$TEXBIN"/*; do ln -sf "$b" "$PREFIX/bin/$(basename "$b")"; done

# The two variables that decide where LuaTeX may write. A TinyTeX unpacked in place resolves both
# inside its own tree, but tlmgr, a relocated tree or a read-only $HOME can send them under $HOME,
# and luaotfload then dies with "system : no writeable cache path, quiting" before the first page.
export TEXMFVAR="$CACHE/texmf-var" TEXMFCACHE="$CACHE/texmf-var" TEXMFCONFIG="$CACHE/texmf-config"
export TEXMFHOME="$CACHE/texmf-home" PATH="$PREFIX/bin:$PATH"
mkdir -p "$TEXMFVAR" "$TEXMFCONFIG" "$TEXMFHOME"

# Pin the package repository before installing anything. Scheme 1 ships no koma-script, so the class
# the book is built on would otherwise come from a rolling mirror on the day of the render -- and did
# break that way once, when koma-script 3.49.3 dropped the \ifstr that book/_tex/theme.tex calls.
# env-pins.json explains the date. tlmgr must update itself from the same snapshot first: the one in
# the tarball is older than the snapshot's and refuses to install until it matches. The snapshot is
# immutable, so that self-update is reproducible.
TLNET="$(pin render tinytex tlnet_repository)"
info "package repository pinned to $TLNET"
{
  "$PREFIX/bin/tlmgr" option repository "$TLNET"
  "$PREFIX/bin/tlmgr" update --self
} >"$LOGS/tlmgr.log" 2>&1 || info "tlmgr could not reach the pinned snapshot; see logs/tlmgr.log"

info "adding the LaTeX packages the book loads"
tlmgr_pkgs="$(pin render tinytex tlmgr_packages)"
# tlmgr exits non-zero when any name in the list is already part of the scheme, so its exit status
# says nothing useful here. Ask kpsewhich afterwards instead, which answers the question we have.
"$PREFIX/bin/tlmgr" install $tlmgr_pkgs >>"$LOGS/tlmgr.log" 2>&1 || true
missing=""
for probe in scrbook.cls fontspec.sty caption.sty tcolorbox.sty unicode-math.sty koma-script.sty; do
  case "$probe" in koma-script.sty) continue ;; esac
  "$PREFIX/bin/kpsewhich" "$probe" >/dev/null 2>&1 || missing="$missing $probe"
done
if [ -n "$missing" ]; then
  info "the pinned snapshot did not provide:$missing (see logs/tlmgr.log)"
else
  info "scrbook $("$PREFIX/bin/kpsewhich" scrbook.cls | xargs grep -m1 -o '[0-9]\{4\}/[0-9/]* v[0-9.a-z]*')"
fi
"$PREFIX/bin/luaotfload-tool" --update >"$LOGS/luaotfload.log" 2>&1 || true
info "$("$PREFIX/bin/lualatex" --version 2>/dev/null | head -1)"

# ------------------------------------------------------------------- ctags --

step "Universal Ctags $(pin render universal-ctags version)"
if [ ! -x "$PREFIX/uctags/bin/ctags" ]; then
  read -r URL SHA STRIP <<<"$(pin_artifact render universal-ctags "$PLATFORM")"
  unpack "$(fetch "$URL" "$SHA")" "$SRC/ctags" "$STRIP"
  # The release tarball ships a generated ./configure, so no autoconf/automake is needed here.
  ( cd "$SRC/ctags" \
    && ./configure --prefix="$PREFIX/uctags" $(pin render universal-ctags configure) \
    && make -s -j"$JOBS" && make -s install ) >"$LOGS/ctags.log" 2>&1 \
    || die "Universal Ctags did not build; see $LOGS/ctags.log"
fi
ln -sf "$PREFIX/uctags/bin/ctags" "$PREFIX/bin/ctags"
info "$("$PREFIX/bin/ctags" --version | head -1)"

# ------------------------------------------------------------------ netcdf --

step "NetCDF"
NETCDF_ROOT=""
nc_ok() {
  local v want="$(pin native netcdf-c minimum)"
  command -v nc-config >/dev/null || return 1
  v="$(nc-config --version 2>/dev/null | awk '{print $2}')" || return 1
  [ -r "$(nc-config --includedir 2>/dev/null)/netcdf.h" ] || return 1
  "$PYTHON" - "$v" "$want" <<'EOF'
import sys
f=lambda s: tuple(int(p) for p in s.split(".")[:3])
sys.exit(0 if f(sys.argv[1]) >= f(sys.argv[2]) else 1)
EOF
}
if [ "$FORCE_NETCDF_BUILD" = 0 ] && nc_ok; then
  NETCDF_ROOT="$(nc-config --prefix)"
  info "using the NetCDF already installed: $(nc-config --version) at $NETCDF_ROOT"
else
  info "no usable NetCDF found; building the pinned one from source"
  if [ ! -f "$PREFIX/netcdf/include/netcdf.h" ]; then
    HDF5_ARG=()
    if ! command -v h5cc >/dev/null; then
      info "HDF5 $(pin native hdf5 version) from source (netcdf-c needs it)"
      read -r URL SHA STRIP <<<"$(pin_artifact native hdf5 "$PLATFORM")"
      unpack "$(fetch "$URL" "$SHA")" "$SRC/hdf5" "$STRIP"
      cmake -S "$SRC/hdf5" -B "$SRC/hdf5-build" -DCMAKE_BUILD_TYPE=Release \
            -DCMAKE_INSTALL_PREFIX="$PREFIX/netcdf" $(pin native hdf5 cmake) >"$LOGS/hdf5.log" 2>&1 \
        && cmake --build "$SRC/hdf5-build" -j"$JOBS" --target install >>"$LOGS/hdf5.log" 2>&1 \
        || die "HDF5 did not build; see $LOGS/hdf5.log"
    fi
    info "netcdf-c $(pin native netcdf-c version) from source"
    read -r URL SHA STRIP <<<"$(pin_artifact native netcdf-c "$PLATFORM")"
    unpack "$(fetch "$URL" "$SHA")" "$SRC/netcdf" "$STRIP"
    cmake -S "$SRC/netcdf" -B "$SRC/netcdf-build" -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_INSTALL_PREFIX="$PREFIX/netcdf" -DCMAKE_PREFIX_PATH="$PREFIX/netcdf" \
          $(pin native netcdf-c cmake) >"$LOGS/netcdf.log" 2>&1 \
      && cmake --build "$SRC/netcdf-build" -j"$JOBS" --target install >>"$LOGS/netcdf.log" 2>&1 \
      || die "netcdf-c did not build; see $LOGS/netcdf.log"
  fi
  NETCDF_ROOT="$PREFIX/netcdf"
  info "built $("$PREFIX/netcdf/bin/nc-config" --version 2>/dev/null || echo netcdf) at $NETCDF_ROOT"
fi

# ------------------------------------------------------- python environment --

step "Python environment"
export PIP_CACHE_DIR="$CACHE/pip"
if [ ! -x "$PREFIX/venv/bin/python" ]; then
  "$PYTHON" -m venv "$PREFIX/venv"
fi
VPY="$PREFIX/venv/bin/python"
"$VPY" -m pip install --quiet --upgrade pip setuptools wheel >"$LOGS/pip.log" 2>&1
info "installing tools/requirements.txt"
"$VPY" -m pip install --quiet -r "$HERE/tools/requirements.txt" >>"$LOGS/pip.log" 2>&1 \
  || die "the pinned Python environment did not install; see $LOGS/pip.log"
info "installing snapy_report (src/)"
"$VPY" -m pip install --quiet -e "$HERE/src" --no-deps >>"$LOGS/pip.log" 2>&1 \
  || die "snapy_report did not install; see $LOGS/pip.log"
info "$("$VPY" -c 'import numpy,sympy,matplotlib;print("numpy",numpy.__version__,"sympy",sympy.__version__,"matplotlib",matplotlib.__version__)')"

# --------------------------------------------------- the snapy pin for ctags --

# tools/code_anchors.py resolves every {{< code >}} at code_pin.yml. Given a clone that holds the pin
# in SNAPY_REPO it never touches the network; without one it fetches into SNAPY_REPORT_CACHE on every
# run. Cloning it once here makes the render offline and reproducible.
step "The snapy clone the code citations resolve against"
PIN_SHA="$("$VPY" -c "
import re;print(re.search(r'^sha:\s*(\S+)', open('$HERE/code_pin.yml').read(), re.M).group(1))")"
if [ ! -d "$PREFIX/snapy-pin/.git" ]; then
  git clone --quiet --filter=blob:none --no-checkout https://github.com/chengcli/snapy.git "$PREFIX/snapy-pin"
fi
git -C "$PREFIX/snapy-pin" fetch --quiet origin "$PIN_SHA" 2>/dev/null || git -C "$PREFIX/snapy-pin" fetch --quiet origin
git -C "$PREFIX/snapy-pin" checkout --quiet --detach "$PIN_SHA"
info "chengcli/snapy at $PIN_SHA"

# ------------------------------------------------------------------ activate --

step "Writing $PREFIX/activate"
cat > "$PREFIX/activate" <<EOF
# Written by doc/tech-report/setup.sh. Source it, do not run it:
#     source $(basename "$PREFIX")/activate
# It puts the pinned toolchain first on PATH and points every cache inside the prefix, so nothing
# the report runs needs a writable \$HOME.

export SNAPY_REPORT_ENV="$PREFIX"
export PATH="$PREFIX/venv/bin:$PREFIX/bin:\$PATH"

# Universal Ctags for tools/code_anchors.py, and the clone it resolves the pin in.
export CTAGS="$PREFIX/uctags/bin/ctags"
export SNAPY_REPO="$PREFIX/snapy-pin"

# Quarto runs the {python} cells with this interpreter, not the one it finds first.
export QUARTO_PYTHON="$PREFIX/venv/bin/python"

# NetCDF for the pinned snapy/pyharp/kintera builds.
export NETCDF_ROOT="$NETCDF_ROOT"
export CMAKE_PREFIX_PATH="$NETCDF_ROOT\${CMAKE_PREFIX_PATH:+:\$CMAKE_PREFIX_PATH}"
export LD_LIBRARY_PATH="$NETCDF_ROOT/lib:$NETCDF_ROOT/lib64\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"

# Every cache, inside the prefix. TEXMFVAR/TEXMFCACHE are the ones LuaTeX needs: without a writable
# one luaotfload stops with "system : no writeable cache path, quiting" and no PDF is produced.
export TEXMFVAR="$CACHE/texmf-var"
export TEXMFCACHE="$CACHE/texmf-var"
export TEXMFCONFIG="$CACHE/texmf-config"
export TEXMFHOME="$CACHE/texmf-home"
export SNAPY_REPORT_CACHE="$CACHE/snapy-report"
export XDG_CACHE_HOME="$CACHE/xdg"
export XDG_DATA_HOME="$CACHE/xdg/data"
export XDG_CONFIG_HOME="$CACHE/xdg/config"
export MPLCONFIGDIR="$CACHE/matplotlib"
export JUPYTER_RUNTIME_DIR="$CACHE/jupyter/runtime"
export JUPYTER_DATA_DIR="$CACHE/jupyter/data"
export JUPYTER_PLATFORM_DIRS=1
# Every figure cell starts an IPython kernel, and IPython writes its profile under ~/.ipython. Left
# at the default on a read-only \$HOME it warns twice per kernel, which is 112 lines of warning in a
# full render and fails render_gate.py's "stdout" gate.
export IPYTHONDIR="$CACHE/ipython"
export PIP_CACHE_DIR="$CACHE/pip"
export TMPDIR="$CACHE/tmp"

# matplotlib must not try to open a display in a figure cell.
export MPLBACKEND=Agg
EOF
info "done"

# -------------------------------------------------------- the native build --

if [ "$WITH_NATIVE" = 1 ]; then
  step "The pinned scientific packages"
  # shellcheck disable=SC1090
  source "$PREFIX/activate"
  PYHARP_SHA="$("$VPY" -c "import json;print(json.load(open('$HERE/tools/package-pins.json'))['pyharp'])")"
  # kintera comes from env-pins.json, not package-pins.json: package-pins.json holds the commit the
  # chapters CITE (v2.6.2), and snapy's own CMakeLists.txt at code_pin.yml requires at least 2.6.3.
  # env-pins.json explains the split in scientific_packages.kintera._why_build_differs_from_pin.
  KINTERA_SHA="$(pin scientific_packages kintera build)"

  # pydisort first: FindDisort.cmake of all three others locates it by importing it, and when the
  # import fails CMake reports the confusing "cmake_path CONVERT called with an unknown action".
  info "pydisort $(pin scientific_packages pydisort version) (PyPI; the report pins no pydisort)"
  "$VPY" -m pip install --quiet "pydisort==$(pin scientific_packages pydisort version)" \
    >"$LOGS/pydisort.log" 2>&1 || die "pydisort did not install; see $LOGS/pydisort.log"

  build_pinned() {  # build_pinned <name> <repo> <sha>
    local name="$1" repo="$2" sha="$3" dir="$SRC/$1"
    info "$name at $sha"
    [ -d "$dir/.git" ] || git clone --quiet "https://github.com/$repo.git" "$dir"
    git -C "$dir" fetch --quiet origin "$sha" 2>/dev/null || git -C "$dir" fetch --quiet origin
    git -C "$dir" checkout --quiet --detach "$sha"
    git -C "$dir" submodule update --quiet --init --recursive 2>/dev/null || true
    "$VPY" -m pip install --quiet --no-build-isolation "$dir" >"$LOGS/$name.log" 2>&1 \
      || die "$name did not build at $sha; see $LOGS/$name.log"
  }
  build_pinned pyharp  chengcli/pyharp  "$PYHARP_SHA"
  build_pinned kintera chengcli/kintera "$KINTERA_SHA"

  info "verifying the pins satisfy snapy's own floors"
  "$VPY" "$HERE/tools/check_env.py" --installed || die "the installed packages do not satisfy snapy's floors"

  info "configuring snapy at $PIN_SHA"
  cmake -S "$PREFIX/snapy-pin" -B "$PREFIX/snapy-build" -DCMAKE_BUILD_TYPE=Release -DNETCDF=ON \
        -DPython3_EXECUTABLE="$VPY" >"$LOGS/snapy-configure.log" 2>&1 \
    || die "snapy did not configure at the pin; see $LOGS/snapy-configure.log"
  cmake --build "$PREFIX/snapy-build" -j"$JOBS" >"$LOGS/snapy-build.log" 2>&1 \
    || die "snapy did not build at the pin; see $LOGS/snapy-build.log"
  info "snapy built; its test binaries are in $PREFIX/snapy-build"
  echo "export SNAP_PIN_BUILD=\"$PREFIX/snapy-build\"" >> "$PREFIX/activate"
fi

# -------------------------------------------------------------------- done --

step "Checking the pins are consistent"
# Through the clone made above, so the floor check reads snapy's own CMakeLists.txt at the pin
# instead of skipping -- that check is the whole reason this gate exists.
SNAPY_REPO="$PREFIX/snapy-pin" KINTERA_REPO="$SRC/kintera" \
  "$VPY" "$HERE/tools/check_env.py" || die "tools/check_env.py refused the committed pins"

cat <<EOF

$(printf '\033[32mReady.\033[0m') Start every session with

    source $(python3 -c "import os.path,sys;print(os.path.relpath(sys.argv[1]))" "$PREFIX")/activate

and then, from doc/tech-report:

    python3 tools/code_anchors.py check      # the code citations resolve at the pin
    python3 -m pytest tools/tests -q         # the gate tests
    python3 tools/render_figures.py          # every figure, to build/figures/
    python3 tools/render_gate.py book/       # the source gates, the HTML and the PDF
EOF
