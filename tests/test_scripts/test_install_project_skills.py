from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import install_project_skills


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "install_project_skills.py"
)


def test_install_project_skills_creates_symlinks_for_each_skill(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    skill_root = repo_root / "agent-skills"
    target_dir = tmp_path / "target-skills"

    for skill_name in ("skill-one", "skill-two"):
        skill_dir = skill_root / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill_name}\ndescription: test\n---\n", encoding="utf-8"
        )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(repo_root),
            "--target-dir",
            str(target_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (target_dir / "skill-one").exists()
    assert (target_dir / "skill-two").exists()
    assert (target_dir / "skill-one").resolve() == skill_root / "skill-one"
    assert (target_dir / "skill-two").resolve() == skill_root / "skill-two"


def test_install_symlink_falls_back_to_windows_junction_on_privilege_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill_dir = tmp_path / "repo" / "agent-skills" / "skill-one"
    skill_dir.mkdir(parents=True)
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    calls: dict[str, tuple[Path, Path]] = {}

    def fake_symlink_to(self: Path, target: Path, target_is_directory: bool = False) -> None:
        err = OSError("missing privilege")
        err.winerror = 1314  # type: ignore[attr-defined]
        raise err

    def fake_create_windows_junction(source: Path, link_path: Path) -> None:
        calls["junction"] = (source, link_path)

    monkeypatch.setattr(Path, "symlink_to", fake_symlink_to)
    monkeypatch.setattr(
        install_project_skills,
        "_create_windows_junction",
        fake_create_windows_junction,
    )
    monkeypatch.setattr(install_project_skills.os, "name", "nt")

    install_project_skills.install_symlink(skill_dir.resolve(), target_dir.resolve())

    assert calls["junction"] == (
        skill_dir.resolve(),
        (target_dir / skill_dir.name).resolve(),
    )


def test_install_project_skills_fails_when_no_skills_exist(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "agent-skills").mkdir(parents=True)
    target_dir = tmp_path / "target-skills"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(repo_root),
            "--target-dir",
            str(target_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "No project skills found" in result.stderr
