from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import yaml


COMPOSE_FILE = "docker-compose.prod.yml"
DEFAULT_COMPOSE_PROJECT = "socialevalpilot"
DEPLOYMENT_SHAPE = "single-host-compose"
SERVICES = ["postgres", "redis", "api", "worker", "frontend", "nginx"]
VOLUMES = ["appdata", "redisdata"]
ARTIFACTS = {
    "postgres_dump": "postgres.dump",
    "appdata_archive": "appdata.tar.gz",
    "redis_archive": "redisdata.tar.gz",
}
BACKUP_STOPPED_SERVICES = {"api", "worker", "redis"}
RESTORE_STOPPED_SERVICES = {"api", "worker", "frontend", "nginx", "redis"}
SCHEMA_VERSION = 1


def add_runtime_args(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    default_deploy_dir: Path | str = (
        argparse.SUPPRESS if suppress_defaults else Path(__file__).resolve().parents[1]
    )
    default_output_dir: Path | None | str = argparse.SUPPRESS if suppress_defaults else None
    default_compose_project: str = (
        argparse.SUPPRESS if suppress_defaults else DEFAULT_COMPOSE_PROJECT
    )

    parser.add_argument(
        "--deploy-dir",
        type=Path,
        default=default_deploy_dir,
        help="Deployment directory that contains docker-compose.prod.yml.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help="Backup root directory. Defaults to <deploy-dir>/backups.",
    )
    parser.add_argument(
        "--compose-project",
        default=default_compose_project,
        help="Compose project name used for scoped service/volume names.",
    )


@dataclass(frozen=True)
class RuntimePaths:
    deploy_dir: Path
    compose_file: Path
    output_dir: Path
    compose_project: str
    compose_cli: tuple[str, ...] = ("docker", "compose")

    @classmethod
    def from_deploy_dir(
        cls,
        deploy_dir: Path,
        output_dir: Path | None = None,
        compose_project: str = DEFAULT_COMPOSE_PROJECT,
        compose_cli: tuple[str, ...] = ("docker", "compose"),
    ) -> "RuntimePaths":
        resolved_deploy = deploy_dir.expanduser().resolve()
        resolved_output = (
            output_dir.expanduser().resolve()
            if output_dir is not None
            else (resolved_deploy / "backups").resolve()
        )
        return cls(
            deploy_dir=resolved_deploy,
            compose_file=resolved_deploy / COMPOSE_FILE,
            output_dir=resolved_output,
            compose_project=compose_project,
            compose_cli=compose_cli,
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and restore single-host SocialEval backup bundles."
    )
    add_runtime_args(parser)

    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a timestamped backup bundle.")
    add_runtime_args(create_parser, suppress_defaults=True)
    create_parser.add_argument("--postgres-user", default="socialeval", help="PostgreSQL user.")
    create_parser.add_argument("--postgres-db", default="socialeval", help="PostgreSQL database.")
    create_parser.add_argument("--dry-run", action="store_true", help="Print planned commands without executing.")

    restore_parser = subparsers.add_parser("restore", help="Restore data from an existing backup bundle.")
    add_runtime_args(restore_parser, suppress_defaults=True)
    restore_parser.add_argument(
        "--bundle-dir",
        type=Path,
        required=True,
        help="Path to a backup bundle directory that contains manifest.json.",
    )
    restore_parser.add_argument("--postgres-user", default="socialeval", help="PostgreSQL user.")
    restore_parser.add_argument("--postgres-db", default="socialeval", help="PostgreSQL database.")
    restore_parser.add_argument(
        "--allow-destructive-restore",
        action="store_true",
        help="Required safety flag for restore execution.",
    )
    restore_parser.add_argument(
        "--confirm-backup-id",
        default=None,
        help="Must exactly match manifest backup_id.",
    )
    restore_parser.add_argument("--dry-run", action="store_true", help="Print planned commands without executing.")

    return parser.parse_args(argv)


def build_backup_id(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return f"backup-{current.strftime('%Y%m%dT%H%M%SZ')}"


def build_manifest(
    *,
    backup_id: str,
    created_at: datetime,
    deploy_dir: Path,
    output_dir: Path,
    bundle_dir: Path,
    compose_project: str,
    postgres_user: str,
    postgres_db: str,
) -> dict[str, object]:
    _ = deploy_dir, output_dir
    return {
        "schema_version": SCHEMA_VERSION,
        "backup_id": backup_id,
        "created_at_utc": created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deployment_shape": DEPLOYMENT_SHAPE,
        "compose_file": COMPOSE_FILE,
        "postgres_user": postgres_user,
        "postgres_db": postgres_db,
        "compose_project": compose_project,
        "services": SERVICES,
        "volumes": VOLUMES,
        "artifacts": ARTIFACTS,
        "bundle_path": str(bundle_dir),
    }


def plan_create_commands(
    *,
    runtime: RuntimePaths,
    bundle_dir: Path,
    postgres_user: str,
    postgres_db: str,
) -> list[list[str]]:
    appdata_volume = compose_volume_name(runtime, "appdata")
    redisdata_volume = compose_volume_name(runtime, "redisdata")
    return [
        ["mkdir", "-p", str(bundle_dir)],
        [
            *compose_prefix(runtime),
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            postgres_user,
            "-d",
            postgres_db,
            "-Fc",
        ],
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{appdata_volume}:/volume:ro",
            "-v",
            f"{bundle_dir}:/backup",
            "alpine:3.20",
            "tar",
            "-czf",
            "/backup/appdata.tar.gz",
            "-C",
            "/volume",
            ".",
        ],
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{redisdata_volume}:/volume:ro",
            "-v",
            f"{bundle_dir}:/backup",
            "alpine:3.20",
            "tar",
            "-czf",
            "/backup/redisdata.tar.gz",
            "-C",
            "/volume",
            ".",
        ],
    ]


def plan_restore_commands(
    *,
    runtime: RuntimePaths,
    bundle_dir: Path,
    postgres_user: str,
    postgres_db: str,
) -> list[list[str]]:
    appdata_volume = compose_volume_name(runtime, "appdata")
    redisdata_volume = compose_volume_name(runtime, "redisdata")
    return [
        [
            *compose_prefix(runtime),
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            postgres_user,
            "-d",
            postgres_db,
            "-c",
            "DROP SCHEMA public CASCADE; CREATE SCHEMA public;",
        ],
        [
            *compose_prefix(runtime),
            "exec",
            "-T",
            "postgres",
            "pg_restore",
            "-U",
            postgres_user,
            "-d",
            postgres_db,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
        ],
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{appdata_volume}:/volume",
            "-v",
            f"{bundle_dir}:/backup:ro",
            "alpine:3.20",
            "sh",
            "-c",
            "find /volume -mindepth 1 -maxdepth 1 -exec rm -rf -- {} \\; && tar -xzf /backup/appdata.tar.gz -C /volume",
        ],
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{redisdata_volume}:/volume",
            "-v",
            f"{bundle_dir}:/backup:ro",
            "alpine:3.20",
            "sh",
            "-c",
            "find /volume -mindepth 1 -maxdepth 1 -exec rm -rf -- {} \\; && tar -xzf /backup/redisdata.tar.gz -C /volume",
        ],
    ]


def enforce_restore_safety_guards(
    *,
    allow_destructive_restore: bool,
    expected_backup_id: str | None,
    manifest: dict[str, object],
    runtime: RuntimePaths,
    postgres_user: str,
    postgres_db: str,
) -> None:
    manifest_backup_id = str(manifest.get("backup_id", ""))

    if not allow_destructive_restore:
        raise ValueError("Restore blocked: pass --allow-destructive-restore to continue.")
    if expected_backup_id != manifest_backup_id:
        raise ValueError(
            f"Restore blocked: --confirm-backup-id '{expected_backup_id}' does not match manifest backup_id '{manifest_backup_id}'."
        )

    expected_fields: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "deployment_shape": DEPLOYMENT_SHAPE,
        "compose_file": COMPOSE_FILE,
        "postgres_user": postgres_user,
        "postgres_db": postgres_db,
        "compose_project": runtime.compose_project,
        "services": SERVICES,
        "volumes": VOLUMES,
        "artifacts": ARTIFACTS,
    }
    for field_name, expected_value in expected_fields.items():
        actual_value = manifest.get(field_name)
        if actual_value != expected_value:
            if field_name == "compose_project":
                raise ValueError(
                    "Restore blocked: bundle compose project does not match the selected compose project. "
                    "Pass --compose-project with the same value used during backup creation."
                )
            if field_name in {"postgres_user", "postgres_db"}:
                raise ValueError(
                    "Restore blocked: postgres target does not match the backup manifest. "
                    "Use the same --postgres-user and --postgres-db values used during backup creation."
                )
            raise ValueError(
                f"Restore blocked: manifest field '{field_name}' is incompatible. "
                f"Expected {expected_value!r}, got {actual_value!r}."
            )


def run_command(cmd: Sequence[str], cwd: Path) -> int:
    result = subprocess.run(list(cmd), cwd=cwd, check=False)
    return result.returncode


def list_running_services(runtime: RuntimePaths) -> list[str]:
    result = subprocess.run(
        [*compose_prefix(runtime), "ps", "--status", "running", "--services"],
        cwd=runtime.deploy_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise ValueError(f"Unable to inspect running services before restore: {stderr or result.returncode}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def detect_compose_cli() -> tuple[str, ...]:
    probes = [
        (("docker", "compose"), ["docker", "compose", "version"]),
        (("docker-compose",), ["docker-compose", "--version"]),
    ]
    for cli, probe in probes:
        result = subprocess.run(probe, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if result.returncode == 0:
            return cli
    raise RuntimeError(
        "Neither 'docker compose' nor 'docker-compose' is available. Install a supported Compose CLI first."
    )


def service_uses_named_volume(service_config: dict[str, object], volume_name: str) -> bool:
    volumes = service_config.get("volumes", [])
    if not isinstance(volumes, list):
        return False

    for entry in volumes:
        if isinstance(entry, str):
            source = entry.split(":", 1)[0]
            if source == volume_name:
                return True
            continue
        if isinstance(entry, dict):
            if entry.get("type") == "volume" and entry.get("source") == volume_name:
                return True

    return False


def validate_named_docker_volumes_exist(runtime: RuntimePaths) -> None:
    expected = [compose_volume_name(runtime, volume) for volume in VOLUMES]
    result = subprocess.run(
        ["docker", "volume", "inspect", *expected],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(
            "Volume target validation failed: expected Docker volumes are missing or unreadable"
            f"{': ' + stderr if stderr else ''}"
        )


def validate_runtime_volume_targets(runtime: RuntimePaths) -> None:
    compose_config = yaml.safe_load(runtime.compose_file.read_text(encoding="utf-8")) or {}
    services = compose_config.get("services", {})
    declared_volumes = compose_config.get("volumes", {})
    if not isinstance(services, dict) or not isinstance(declared_volumes, dict):
        raise ValueError("Volume target validation failed: invalid compose file structure.")

    for volume_name in VOLUMES:
        if volume_name not in declared_volumes:
            raise ValueError(
                f"Volume target validation failed: compose file does not declare volume '{volume_name}'."
            )

    required_mounts = {
        "api": "appdata",
        "worker": "appdata",
        "redis": "redisdata",
    }
    for service_name, volume_name in required_mounts.items():
        service_config = services.get(service_name)
        if not isinstance(service_config, dict):
            raise ValueError(
                f"Volume target validation failed: compose file is missing service '{service_name}'."
            )
        if not service_uses_named_volume(service_config, volume_name):
            raise ValueError(
                f"Volume target validation failed: service '{service_name}' does not mount volume '{volume_name}'."
            )

    validate_named_docker_volumes_exist(runtime)


def compose_prefix(runtime: RuntimePaths) -> list[str]:
    return [
        *runtime.compose_cli,
        "-p",
        runtime.compose_project,
        "-f",
        runtime.compose_file.name,
    ]


def compose_volume_name(runtime: RuntimePaths, base_volume: str) -> str:
    return f"{runtime.compose_project}_{base_volume}"


def format_command(
    cmd: Sequence[str],
    *,
    stdin_path: Path | None = None,
    stdout_path: Path | None = None,
) -> str:
    rendered = " ".join(shlex.quote(part) for part in cmd)
    if stdin_path is not None:
        rendered = f"{rendered} < {shlex.quote(str(stdin_path))}"
    if stdout_path is not None:
        rendered = f"{rendered} > {shlex.quote(str(stdout_path))}"
    return rendered


def print_plan(
    plan: list[list[str]],
    *,
    stdin_paths: dict[int, Path] | None = None,
    stdout_paths: dict[int, Path] | None = None,
) -> None:
    stdin_paths = stdin_paths or {}
    stdout_paths = stdout_paths or {}
    for idx, cmd in enumerate(plan, start=1):
        print(
            f"[{idx}] "
            f"{format_command(cmd, stdin_path=stdin_paths.get(idx - 1), stdout_path=stdout_paths.get(idx - 1))}"
        )


def validate_regular_file(path: Path, *, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required restore artifact: {path}")
    if path.is_symlink():
        raise ValueError(f"Restore blocked: {label} must not be a symlink: {path}")
    if not path.is_file():
        raise ValueError(f"Restore blocked: {label} must be a regular file: {path}")


def validate_tar_archive(path: Path, *, label: str) -> None:
    validate_regular_file(path, label=label)
    result = subprocess.run(
        ["tar", "-tzf", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Restore blocked: invalid tar archive for {label}: {path}")


def validate_postgres_dump_archive(runtime: RuntimePaths, dump_file: Path) -> None:
    validate_regular_file(dump_file, label="postgres.dump")
    with dump_file.open("rb") as dump_in:
        result = subprocess.run(
            [*compose_prefix(runtime), "exec", "-T", "postgres", "pg_restore", "--list"],
            cwd=runtime.deploy_dir,
            stdin=dump_in,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
        )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(
            "Restore blocked: postgres.dump failed pg_restore --list validation"
            f"{': ' + stderr if stderr else ''}"
        )


def ensure_restore_window(runtime: RuntimePaths) -> None:
    running_services = set(list_running_services(runtime))
    blocked = sorted(running_services.intersection(RESTORE_STOPPED_SERVICES))
    if blocked:
        raise ValueError(
            "Restore blocked: stop these services before restore: " + ", ".join(blocked)
        )
    if "postgres" not in running_services:
        raise ValueError("Restore blocked: postgres service must be running before restore.")


def ensure_backup_window(runtime: RuntimePaths) -> None:
    running_services = set(list_running_services(runtime))
    blocked = sorted(running_services.intersection(BACKUP_STOPPED_SERVICES))
    if blocked:
        raise ValueError(
            "Backup blocked: stop these services before backup: " + ", ".join(blocked)
        )
    if "postgres" not in running_services:
        raise ValueError("Backup blocked: postgres service must be running before backup.")


def handle_create(runtime: RuntimePaths, *, postgres_user: str, postgres_db: str, dry_run: bool) -> int:
    if not runtime.compose_file.exists():
        raise FileNotFoundError(f"Missing compose file: {runtime.compose_file}")

    created_at = datetime.now(timezone.utc)
    backup_id = build_backup_id(created_at)
    bundle_dir = runtime.output_dir / backup_id
    manifest_path = bundle_dir / "manifest.json"
    pg_dump_path = bundle_dir / "postgres.dump"
    plan = plan_create_commands(
        runtime=runtime,
        bundle_dir=bundle_dir,
        postgres_user=postgres_user,
        postgres_db=postgres_db,
    )

    if dry_run:
        print_plan(plan, stdout_paths={1: pg_dump_path})
        return 0

    ensure_backup_window(runtime)
    validate_runtime_volume_targets(runtime)

    bundle_dir.mkdir(parents=True, exist_ok=True)

    pg_dump_cmd = plan[1]
    with pg_dump_path.open("wb") as dump_file:
        result = subprocess.run(pg_dump_cmd, cwd=runtime.deploy_dir, stdout=dump_file, check=False)
    if result.returncode != 0:
        return result.returncode

    for cmd in plan[2:]:
        rc = run_command(cmd, runtime.deploy_dir)
        if rc != 0:
            return rc

    manifest = build_manifest(
        backup_id=backup_id,
        created_at=created_at,
        deploy_dir=runtime.deploy_dir,
        output_dir=runtime.output_dir,
        bundle_dir=bundle_dir,
        compose_project=runtime.compose_project,
        postgres_user=postgres_user,
        postgres_db=postgres_db,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(str(bundle_dir))
    return 0


def handle_restore(
    runtime: RuntimePaths,
    *,
    bundle_dir: Path,
    postgres_user: str,
    postgres_db: str,
    allow_destructive_restore: bool,
    confirm_backup_id: str | None,
    dry_run: bool,
) -> int:
    if not runtime.compose_file.exists():
        raise FileNotFoundError(f"Missing compose file: {runtime.compose_file}")

    manifest = load_and_validate_restore_bundle(bundle_dir)
    enforce_restore_safety_guards(
        allow_destructive_restore=allow_destructive_restore,
        expected_backup_id=confirm_backup_id,
        manifest=manifest,
        runtime=runtime,
        postgres_user=postgres_user,
        postgres_db=postgres_db,
    )

    plan = plan_restore_commands(
        runtime=runtime,
        bundle_dir=bundle_dir,
        postgres_user=postgres_user,
        postgres_db=postgres_db,
    )
    if dry_run:
        print_plan(plan, stdin_paths={1: bundle_dir / ARTIFACTS["postgres_dump"]})
        return 0

    ensure_restore_window(runtime)
    validate_postgres_dump_archive(runtime, bundle_dir / ARTIFACTS["postgres_dump"])
    validate_runtime_volume_targets(runtime)

    rc = run_command(plan[0], runtime.deploy_dir)
    if rc != 0:
        return rc

    dump_file = bundle_dir / "postgres.dump"
    with dump_file.open("rb") as dump_in:
        restore_result = subprocess.run(plan[1], cwd=runtime.deploy_dir, stdin=dump_in, check=False)
    if restore_result.returncode != 0:
        return restore_result.returncode

    for cmd in plan[2:]:
        rc = run_command(cmd, runtime.deploy_dir)
        if rc != 0:
            return rc

    return 0


def load_and_validate_restore_bundle(bundle_dir: Path) -> dict[str, object]:
    manifest_path = bundle_dir / "manifest.json"
    dump_path = bundle_dir / ARTIFACTS["postgres_dump"]
    appdata_archive = bundle_dir / ARTIFACTS["appdata_archive"]
    redis_archive = bundle_dir / ARTIFACTS["redis_archive"]

    validate_regular_file(manifest_path, label="manifest.json")
    validate_regular_file(dump_path, label="postgres.dump")
    validate_tar_archive(appdata_archive, label="appdata archive")
    validate_tar_archive(redis_archive, label="redis archive")

    return json.loads(manifest_path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runtime = RuntimePaths.from_deploy_dir(
        args.deploy_dir,
        args.output_dir,
        args.compose_project,
        detect_compose_cli(),
    )

    if args.command == "create":
        return handle_create(
            runtime,
            postgres_user=args.postgres_user,
            postgres_db=args.postgres_db,
            dry_run=args.dry_run,
        )
    if args.command == "restore":
        return handle_restore(
            runtime,
            bundle_dir=args.bundle_dir.expanduser().resolve(),
            postgres_user=args.postgres_user,
            postgres_db=args.postgres_db,
            allow_destructive_restore=args.allow_destructive_restore,
            confirm_backup_id=args.confirm_backup_id,
            dry_run=args.dry_run,
        )

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
