# Setting up a machine for this report

```bash
cd doc/tech-report
bash setup.sh                     # the report: checks, figures, every gate, the HTML and the PDF
source .report-env/activate
```

That is the whole thing. Add `--with-native` to also build pydisort, pyharp, kintera and snapy at
their pins, which is what the `ctest` and do-card commands in the chapters need.

Nothing is installed system-wide: no package manager, no `sudo`, no write outside the prefix and the
repository. Every download is checked against the sha256 committed in `tools/env-pins.json` before it
is unpacked; a mismatch stops the run rather than installing the file.

## What it installs, and where each version comes from

| | version | pinned in | why that version |
|---|---|---|---|
| Python | 3.11–3.13 | `tools/env-pins.json` | torch 2.10.0 publishes no wheel below 3.11; CI uses 3.12 |
| numpy, sympy, matplotlib | 2.4.6, 1.14.0, 3.11.2 | `tools/requirements.txt` | the versions the report's committed numbers were produced with |
| torch | 2.10.0 | `tools/requirements.txt` | what the cards and data provenance record throughout |
| Quarto | 1.10.19 | `tools/env-pins.json` | `QUARTO_VERSION` of `.github/workflows/tech-report.yml` |
| TinyTeX | v2026.10, scheme 1 | `tools/env-pins.json` | the workflow asks `quarto-actions/setup` for `tinytex: true` |
| Universal Ctags | 6.2.1 | `tools/env-pins.json` | `CTAGS_VERSION` of the workflow and of `tools/code_anchors.py:50` |
| NetCDF | 4.9.3, built | `tools/env-pins.json` | `-DNETCDF=ON` in the snapy, pyharp and kintera builds |
| HDF5 | 1.14.6, built | `tools/env-pins.json` | netcdf-c is a thin layer over it, so both come from the pin or neither does |
| pydisort | 1.8.13 | `tools/env-pins.json` | the report pins no pydisort; `FindDisort.cmake` needs it importable |
| pyharp | `47217158` | `tools/package-pins.json` | the report's pin |
| kintera | `b6ad3739` (v2.6.3) | `tools/env-pins.json` | see "The two kintera revisions" below |
| snapy | `ccf40f95` | `code_pin.yml` | the report's pin |

`tools/requirements-linux-x86_64.lock.txt` is the exact Python closure verified on linux-x86_64;
install it instead of `tools/requirements.txt` when you need that environment byte for byte.

## Why `activate` sets so many cache variables

Because a read-only `$HOME` is normal on a shared or containerised host, and almost everything here
defaults its cache under `$HOME`. Left alone, LuaTeX stops before the first page with

```
luaotfload | load : FATAL ERROR
luaotfload | load :   × "luaotfload-init.lua:301: system : no writeable cache path, quiting".
```

and no PDF is produced. `tools/code_anchors.py:51`, `tools/check_provenance.py:126` and
`tools/check_citations.py:407` default to `~/.cache/...` the same way, and matplotlib and Jupyter do
too. `activate` points `TEXMFVAR`, `TEXMFCACHE`, `TEXMFCONFIG`, `TEXMFHOME`, `SNAPY_REPORT_CACHE`,
`XDG_*`, `MPLCONFIGDIR`, `IPYTHONDIR`, `JUPYTER_*`, `PIP_CACHE_DIR` and `TMPDIR` inside the prefix, so
none of them ever looks at `$HOME`. `IPYTHONDIR` matters more than it looks: every figure cell starts
an IPython kernel, and at the default each one warns twice that `~/.ipython` is not writable, which is
112 lines of warning in a full render and fails `render_gate.py`'s `stdout` gate.

It also sets `SNAPY_REPO` to a clone of `chengcli/snapy` at `code_pin.yml`, which `setup.sh` makes.
With it, `tools/code_anchors.py` resolves every `{{< code >}}` without touching the network; without
it, the tool fetches into `SNAPY_REPORT_CACHE` on every run.

## The two kintera revisions

`tools/package-pins.json` and `tools/env-pins.json` name different kintera commits on purpose.

- **`tools/package-pins.json`: `c55b13b2` (v2.6.2)** is the commit the chapters *cite*. 296 citations
  in 70 files resolve there, and `tools/ratchet_gate.py` counts any other kintera sha as `offpin`.
- **`tools/env-pins.json`: `b6ad3739` (v2.6.3)** is the commit that must be *installed*. snapy at
  `code_pin.yml` says, at `CMakeLists.txt:104`, `find_package(Kintera 2.6.3 REQUIRED)`, so v2.6.2
  cannot configure it:

  ```
  Could NOT find Kintera: Found unsuitable version "2.6.2", but required is at least "2.6.3"
    Reason given by package: snapy requires kintera >= 2.6.3 (... explicit kinetics rate constants
    from forward_with_rate_constants()), found 2.6.2
  ```

  v2.6.3 is the smallest revision at or above that floor — exactly one commit after the citation pin.

Until this report was audited there was one field for both questions, and it held v2.6.2, so no
native command of the report could be reproduced at the pins the report gives.

**The citation pin is still below the floor, and closing that is chapter work, not setup work.**
The reason is structural, not clerical: the commit that satisfies snapy's floor *is* the commit that
rewrote `src/kinetics/evaporation.cpp` and `src/kinetics/kinetics.cpp` — the explicit same-call rate
constants for the kinetics Jacobian — and chapter 10's kinetics section cites those files by line.
Every revision at or above the floor contains that rewrite, so no choice of revision avoids it.

`python3 tools/kintera_pin_migration.py` checks every kintera citation at both revisions and compares
the cited lines byte for byte. Against a clone holding both (`bash setup.sh --with-native` leaves one
in `.report-env/src/kintera`):

```
194 citation(s) found
  identical, the sha can simply be swapped : 180
  same code at new line numbers            :   4
  BLOCKED, the cited code is gone          :  10
```

The ten are eight in `book/chapters/10-moist-coupling/_kinetics.qmd` and two in
`reviews/code-anchors-unmapped*.tsv`. The tool prints each one with its file, line and cited range,
and exits 1 while any remains. Until a chapter owner re-reads those claims against v2.6.3, moving the
pin would either point at code that is not there or raise ch10's ratchet `offpin` count — a bare move
takes the total from 92 to 230 and fails nine chapters. The project's own rule for the snapy pin says
the same thing: `code_anchors.py bump` lists the cited symbols whose body changed so their claims can
be re-read. `python3 tools/check_env.py` reports the gap on every run so it stays visible.

## The pins are installed, not just written down

The default route **builds** the pinned NetCDF and the pinned HDF5 and then checks that `nc-config`
reports exactly the pinned version. It used to prefer whatever the machine already had and only build
when it found nothing usable, which meant the documented reproduction silently linked against a
different library on every host — 4.8.1 here against a 4.9.3 pin. A pin nobody installs is not a pin.

`bash setup.sh --allow-host-netcdf` is the deliberate opt-out. It still refuses anything below the
`minimum` in `tools/env-pins.json`, and it says in as many words that the result is not the
documented route.

## The TeX pin fails loudly or not at all

Every step that pins TeX is fatal: pointing `tlmgr` at the dated snapshot, `tlmgr`'s self-update from
that same snapshot, and the package install. After them `setup.sh` reads back the repository actually
in effect and compares it with the pinned one, so a silent fall-back to a default mirror cannot pass,
and a package the snapshot cannot serve stops setup and names itself.

That matters because carrying on is precisely what broke the PDF: a repository step that reported a
failure and continued let the render pull koma-script 3.49.3 from a rolling mirror.

`setup.sh` also records `tlmgr list --only-installed` in `.report-env/tex-packages.lock`, so "the
render fetched nothing" is checkable rather than assumed:

```bash
diff .report-env/tex-packages.lock <(tlmgr list --only-installed | sort)
```

Any difference is a package that arrived at render time.

## The gate

```bash
python3 tools/check_env.py              # the committed pins are consistent and installable
python3 tools/check_env.py --installed  # also: what is importable clears snapy's floors
```

It fails when a pin is not a full sha, when an artifact has no url or no sha256, when a Python
requirement is not pinned with `==`, or when the kintera revision `setup.sh` installs is below the
floor the snapy pin declares. It is cheap, needs no network and no build, and exists because the
v2.6.2/2.6.3 contradiction was invisible to every gate the report already had: both files were
internally consistent and nothing compared the pair.

## What was and was not verified

Verified on linux-x86_64 (RHEL 9, glibc 2.34, GCC 11.5.0, Python 3.11.13) from a fresh clone with an
empty prefix: the download-and-verify path, Quarto, TinyTeX, Universal Ctags built from source, the
pinned NetCDF 4.9.3 + HDF5 1.14.6 source build, the Python environment, and the HTML and PDF render.

Not exercised: the macOS and linux-aarch64 branches. Their artifacts are in `tools/env-pins.json`
with digests taken from the files those URLs serve, but the install path itself has only been run on
linux-x86_64.
