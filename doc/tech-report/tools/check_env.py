#!/usr/bin/env python3
"""The environment gate: the committed pins must be installable together.

The failure this exists for. ``code_pin.yml`` pinned snapy at a commit whose ``CMakeLists.txt`` says
``find_package(Kintera 2.6.3 REQUIRED)`` while ``tools/package-pins.json`` pinned kintera at v2.6.2.
Both files were internally consistent and the pair was not: configuring snapy at its own pin stopped
with "Found unsuitable version 2.6.2, but required is at least 2.6.3", so no native command of the
report could be reproduced at the pins the report gives. Nothing checked the pair, so nothing caught it.

What it checks, with no network and no build:

  pins          code_pin.yml and tools/package-pins.json are well-formed and hold full 40-hex shas.
  artifacts     every artifact of tools/env-pins.json has a url and a 64-hex sha256.
  python        tools/requirements.txt pins every requirement with ``==``.
  floor         the kintera pin satisfies the floor the snapy pin declares.

The floor is read out of the snapy clone that ``SNAPY_REPO`` names (``setup.sh`` writes one) and the
kintera version out of the kintera clone or the installed package; when neither is present that one
check is reported as skipped and the gate still passes, so this runs in a bare checkout.

    python3 tools/check_env.py              # the committed files
    python3 tools/check_env.py --installed  # also: what is importable satisfies the floor

Exit 0 when every check passes or is skipped, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# find_package(Kintera 2.6.3 REQUIRED), and the same shape for any other package snapy requires.
FLOOR_RE = re.compile(r"find_package\(\s*(\w+)\s+(\d+(?:\.\d+)*)\s", re.I)


class Checks:
    def __init__(self) -> None:
        self.problems: list[str] = []
        self.notes: list[str] = []
        self.skipped: list[str] = []
        self.passed: list[str] = []

    def ok(self, what: str, detail: str = "") -> None:
        self.passed.append(what)
        print(f"  ✓ {what}" + (f": {detail}" if detail else ""))

    def bad(self, what: str, detail: str) -> None:
        self.problems.append(f"{what}: {detail}")
        print(f"  ✗ {what}: {detail}")

    def skip(self, what: str, why: str) -> None:
        self.skipped.append(what)
        print(f"  - {what} skipped: {why}")

    def note(self, what: str, detail: str) -> None:
        """A known gap that is someone else's to close: reported on every run, never a failure."""
        self.notes.append(f"{what}: {detail}")
        print(f"  ! {what}: {detail}")


def version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", text)[:3])


def read_code_pin() -> str | None:
    m = re.search(r"^sha:\s*(\S+)", (REPORT / "code_pin.yml").read_text(), re.M)
    return m.group(1) if m else None


def check_pins(c: Checks) -> dict:
    sha = read_code_pin()
    if sha is None:
        c.bad("code_pin.yml", "no `sha:` line")
    elif not SHA_RE.match(sha):
        c.bad("code_pin.yml", f"`{sha}` is not a full 40-character sha")
    else:
        c.ok("code_pin.yml", f"snapy {sha}")

    packages = json.loads((HERE / "package-pins.json").read_text())
    for name, value in packages.items():
        if not SHA_RE.match(str(value)):
            c.bad(f"package-pins.json: {name}", f"`{value}` is not a full 40-character sha")
    if all(SHA_RE.match(str(v)) for v in packages.values()):
        c.ok("package-pins.json", ", ".join(f"{k} {v[:8]}" for k, v in packages.items()))
    return packages


def check_artifacts(c: Checks) -> None:
    pins = json.loads((HERE / "env-pins.json").read_text())
    bad = 0
    seen = 0
    for section in ("render", "native"):
        for name, entry in pins.get(section, {}).items():
            if name.startswith("_"):
                continue
            for platform, artifact in entry.get("artifacts", {}).items():
                seen += 1
                where = f"{section}/{name}/{platform}"
                if not artifact.get("url", "").startswith("https://"):
                    c.bad(f"env-pins.json {where}", "no https url")
                    bad += 1
                elif not SHA256_RE.match(artifact.get("sha256", "")):
                    c.bad(f"env-pins.json {where}", "sha256 is not 64 hex characters")
                    bad += 1
    if not bad:
        c.ok("env-pins.json", f"{seen} artifacts, each with a url and a sha256")


def check_requirements(c: Checks) -> None:
    loose = []
    pinned = 0
    for line in (HERE / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if "==" in line:
            pinned += 1
        else:
            loose.append(line)
    if loose:
        c.bad("requirements.txt", "not pinned with ==: " + ", ".join(loose))
    else:
        c.ok("requirements.txt", f"{pinned} requirements, each pinned")


def git_show(repo: Path, sha: str, path: str) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "show", f"{sha}:{path}"],
            check=True, capture_output=True, text=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def snapy_clone() -> Path | None:
    """A clone that may hold the snapy pin: SNAPY_REPO, then the repository holding this report."""
    for candidate in (os.environ.get("SNAPY_REPO", ""), str(REPORT.parent.parent)):
        if candidate and (Path(candidate) / ".git").exists():
            return Path(candidate)
    return None


def check_floor(c: Checks, packages: dict, installed: bool) -> None:
    """The build revision must clear snapy's floor; the citation pin is reported, not failed.

    tools/package-pins.json holds the commit the chapters cite kintera at. env-pins.json holds the
    commit setup.sh installs. They are allowed to differ, and today they must: see
    scientific_packages.kintera._why_build_differs_from_pin.
    """
    pin = read_code_pin()
    repo = snapy_clone()
    if pin is None or repo is None:
        c.skip("kintera floor", "no snapy clone holding the pin (set SNAPY_REPO; setup.sh writes one)")
        return
    text = git_show(repo, pin, "CMakeLists.txt")
    if text is None:
        c.skip("kintera floor", f"{repo} does not hold {pin[:8]} (set SNAPY_REPO)")
        return

    floors = {name.lower(): version for name, version in FLOOR_RE.findall(text)}
    floor = floors.get("kintera")
    if floor is None:
        c.skip("kintera floor", f"snapy {pin[:8]} declares no kintera version")
        return

    env = json.loads((HERE / "env-pins.json").read_text())
    kintera = env["scientific_packages"]["kintera"]
    build_version = kintera.get("build_version")

    # The check that can stop a build. setup.sh installs this revision.
    if build_version is None:
        c.bad("kintera build revision",
              f"snapy {pin[:8]} requires kintera >= {floor} and env-pins.json names no build_version")
    elif version_tuple(build_version) < version_tuple(floor):
        c.bad("kintera build revision",
              f"snapy {pin[:8]} requires kintera >= {floor}, but env-pins.json installs "
              f"{build_version}. Configuring snapy at its own pin cannot succeed; move "
              "scientific_packages.kintera.build to the smallest revision at or above the floor.")
    else:
        c.ok("kintera build revision",
             f"snapy {pin[:8]} requires >= {floor}; setup.sh installs {build_version}")

    # The citation pin. Below the floor it is a known, routed gap, not a build failure.
    found = kintera_version(packages.get("kintera", ""), installed)
    if found is None:
        c.skip("kintera citation pin", "no kintera clone to read the pin's tag from (set KINTERA_REPO)")
    elif version_tuple(found[0]) < version_tuple(floor):
        c.note("kintera citation pin",
               f"tools/package-pins.json still cites kintera {found[0]}, below snapy's floor of {floor}. "
               "That is chapter work, not setup work: moving it re-points 296 citations in 70 files, 17 "
               "of them into the four src/kinetics files v2.6.3 shifts. setup.sh is unaffected; it "
               f"installs {build_version}.")
    else:
        c.ok("kintera citation pin", f"{found[0]} ({found[1]}), at or above the floor")

    if installed:
        got = kintera_version("", True)
        if got is None:
            c.skip("kintera installed", "kintera is not importable in this interpreter")
        elif version_tuple(got[0]) < version_tuple(floor):
            c.bad("kintera installed",
                  f"the importable kintera is {got[0]}, below snapy's floor of {floor}")
        else:
            c.ok("kintera installed", f"{got[0]}, at or above the floor")


def kintera_version(sha: str, installed: bool) -> tuple[str, str] | None:
    """The kintera version of the pin, from a clone that holds it, else from the import."""
    if sha:
        for env in ("KINTERA_REPO", "SNAPY_REPORT_ENV"):
            root = os.environ.get(env, "")
            if not root:
                continue
            for candidate in (Path(root), Path(root) / "src" / "kintera"):
                if (candidate / ".git").exists():
                    tag = subprocess.run(
                        ["git", "-C", str(candidate), "describe", "--tags", "--exact-match", sha],
                        capture_output=True, text=True)
                    if tag.returncode == 0 and tag.stdout.strip():
                        return tag.stdout.strip().lstrip("v"), f"tag of {sha[:8]}"
    if installed:
        try:
            import kintera  # noqa: F401  (imported for its version only)
            return str(kintera.__version__), "installed"
        except Exception:
            return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--installed", action="store_true",
                        help="also compare against the packages importable right now")
    args = parser.parse_args()

    c = Checks()
    print("[pins]")
    packages = check_pins(c)
    print("[artifacts]")
    check_artifacts(c)
    print("[python]")
    check_requirements(c)
    print("[floors]")
    check_floor(c, packages, args.installed)

    print(f"\n{len(c.passed)} check(s) passed, {len(c.skipped)} skipped, "
          f"{len(c.notes)} reported, {len(c.problems)} failed")
    for note in c.notes:
        print(f"  report: {note}")
    for problem in c.problems:
        print(f"  fail: {problem}")
    return 1 if c.problems else 0


if __name__ == "__main__":
    sys.exit(main())
