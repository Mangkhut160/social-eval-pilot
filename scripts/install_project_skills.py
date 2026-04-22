from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install project-scoped skills into a local agent skills directory."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root that contains the agent-skills/ directory.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path.home() / ".agents" / "skills",
        help="Directory where skill symlinks will be created.",
    )
    return parser.parse_args()


def find_skill_dirs(repo_root: Path) -> list[Path]:
    skills_root = repo_root / "agent-skills"
    if not skills_root.exists():
        return []

    skill_dirs: list[Path] = []
    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        skill_dirs.append(skill_file.parent.resolve())
    return skill_dirs


def install_symlink(skill_dir: Path, target_dir: Path) -> None:
    link_path = (target_dir / skill_dir.name).resolve()

    if link_path.exists():
        if link_path.resolve() == skill_dir:
            return
        raise FileExistsError(f"Refusing to overwrite existing path: {link_path}")

    try:
        link_path.symlink_to(skill_dir, target_is_directory=True)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            _create_windows_junction(skill_dir, link_path)
            return
        raise


def _create_windows_junction(source: Path, link_path: Path) -> None:
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Failed to create junction"
        raise OSError(message)


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    target_dir = args.target_dir.expanduser().resolve()
    skill_dirs = find_skill_dirs(repo_root)

    if not skill_dirs:
        print(f"No project skills found under {repo_root / 'agent-skills'}", file=sys.stderr)
        return 1

    target_dir.mkdir(parents=True, exist_ok=True)

    for skill_dir in skill_dirs:
        install_symlink(skill_dir, target_dir)
        print(f"linked {target_dir / skill_dir.name} -> {skill_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
