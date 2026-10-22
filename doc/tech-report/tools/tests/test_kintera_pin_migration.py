"""The kintera pin cannot move while chapter 10 cites code that the new revision rewrote.

These build a two-commit git repository rather than reaching for the real kintera, so the test says
what the tool decides, not what today's upstream happens to contain.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kintera_pin_migration as kpm


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def two_commit_clone(tmp_path):
    repo = tmp_path / "kintera"
    (repo / "src").mkdir(parents=True)
    git_init = subprocess.run(["git", "init", "-q", str(repo)], capture_output=True)
    assert git_init.returncode == 0
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "src" / "a.cpp").write_text("\n".join(f"line {i}" for i in range(1, 11)) + "\n")
    # b.cpp is never touched, so a citation into it keeps its line numbers across the move
    (repo / "src" / "b.cpp").write_text("\n".join(f"kept {i}" for i in range(1, 6)) + "\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "old")
    old = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    # three new lines on top: "line 4" survives but moves; "line 9" is replaced outright
    body = ["new a", "new b", "new c"] + [f"line {i}" for i in range(1, 9)] + ["REPLACED"]
    (repo / "src" / "a.cpp").write_text("\n".join(body) + "\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "new")
    new = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    return repo, old, new


def run(tmp_path, monkeypatch, report_text, old, new, repo):
    report = tmp_path / "report"
    (report / "tools").mkdir(parents=True)
    (report / "book").mkdir()
    (report / "book" / "ch.qmd").write_text(report_text)
    (report / "tools" / "package-pins.json").write_text(json.dumps({"kintera": old, "pyharp": "f" * 40}))
    (report / "tools" / "env-pins.json").write_text(json.dumps(
        {"scientific_packages": {"kintera": {"build": new, "build_version": "9.9.9"}}}))
    monkeypatch.setattr(kpm, "REPORT", report)
    monkeypatch.setattr(kpm, "HERE", report / "tools")
    monkeypatch.setenv("KINTERA_REPO", str(repo))
    monkeypatch.setattr(sys, "argv", ["kintera_pin_migration.py"])
    return kpm.main()


def cite(sha, a, b, f="a.cpp"):
    return (f"[`kintera {f}:{a}-{b}`]"
            f"(https://github.com/chengcli/kintera/blob/{sha}/src/{f}#L{a}-L{b})")


def test_code_that_only_moved_is_not_a_blocker(tmp_path, monkeypatch, capsys):
    repo, old, new = two_commit_clone(tmp_path)
    assert run(tmp_path, monkeypatch, cite(old, 4, 5), old, new, repo) == 0
    out = capsys.readouterr().out
    assert "same code at new line numbers            : 1" in out
    assert "BLOCKED, the cited code is gone          : 0" in out
    assert "L4-L5 -> L7-L8" in out


def test_code_the_new_revision_rewrote_blocks_the_move(tmp_path, monkeypatch, capsys):
    repo, old, new = two_commit_clone(tmp_path)
    assert run(tmp_path, monkeypatch, cite(old, 9, 10), old, new, repo) == 1
    out = capsys.readouterr().out
    assert "BLOCKED, the cited code is gone          : 1" in out
    assert "book/ch.qmd" in out
    assert "chapter files that must change before the pin can move" in out


def test_unchanged_lines_need_only_the_sha_swapped(tmp_path, monkeypatch, capsys):
    repo, old, new = two_commit_clone(tmp_path)
    assert run(tmp_path, monkeypatch, cite(old, 1, 2, "b.cpp"), old, new, repo) == 0
    assert "identical, the sha can simply be swapped : 1" in capsys.readouterr().out


def test_without_a_clone_it_checks_nothing_and_does_not_fail(tmp_path, monkeypatch, capsys):
    repo, old, new = two_commit_clone(tmp_path)
    monkeypatch.delenv("KINTERA_REPO", raising=False)
    monkeypatch.setenv("SNAPY_REPORT_ENV", str(tmp_path / "nowhere"))
    assert run(tmp_path, monkeypatch, cite(old, 1, 2, "b.cpp"), old, new, tmp_path / "nowhere") == 0
    assert "no kintera clone" in capsys.readouterr().out
