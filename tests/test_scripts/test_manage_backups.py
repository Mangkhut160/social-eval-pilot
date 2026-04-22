from __future__ import annotations

import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import manage_backups


def write_valid_manifest(bundle_dir: Path, *, compose_project: str = "socialevalpilot") -> None:
    (bundle_dir / "manifest.json").write_text(
        (
            '{"backup_id":"backup-20260418T120000Z","schema_version":1,'
            '"deployment_shape":"single-host-compose","compose_file":"docker-compose.prod.yml",'
            '"postgres_user":"socialeval","postgres_db":"socialeval",'
            f'"compose_project":"{compose_project}","services":["postgres","redis","api","worker","frontend","nginx"],'
            '"volumes":["appdata","redisdata"],'
            '"artifacts":{"postgres_dump":"postgres.dump","appdata_archive":"appdata.tar.gz","redis_archive":"redisdata.tar.gz"}}\n'
        ),
        encoding="utf-8",
    )


def write_valid_tar_gz(path: Path) -> None:
    with tarfile.open(path, "w:gz"):
        pass


def test_parse_args_accepts_runtime_flags_after_create_subcommand(tmp_path: Path) -> None:
    args = manage_backups.parse_args(
        [
            "create",
            "--deploy-dir",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "custom-backups"),
            "--compose-project",
            "pilotcustom",
            "--dry-run",
        ]
    )

    assert args.command == "create"
    assert args.deploy_dir == tmp_path
    assert args.output_dir == tmp_path / "custom-backups"
    assert args.compose_project == "pilotcustom"
    assert args.dry_run is True


def test_detect_compose_cli_falls_back_to_legacy_docker_compose(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class FakeResult:
        def __init__(self, returncode: int) -> None:
            self.returncode = returncode

    def fake_run(cmd: list[str], **_: object) -> FakeResult:
        calls.append(cmd)
        if cmd[:3] == ["docker", "compose", "version"]:
            return FakeResult(1)
        if cmd[:2] == ["docker-compose", "--version"]:
            return FakeResult(0)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(manage_backups.subprocess, "run", fake_run)

    assert manage_backups.detect_compose_cli() == ("docker-compose",)
    assert calls == [["docker", "compose", "version"], ["docker-compose", "--version"]]


def test_compose_prefix_supports_legacy_docker_compose_cli(tmp_path: Path) -> None:
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path, compose_cli=("docker-compose",))

    assert manage_backups.compose_prefix(runtime) == [
        "docker-compose",
        "-p",
        "socialevalpilot",
        "-f",
        "docker-compose.prod.yml",
    ]


def test_build_manifest_includes_expected_metadata(tmp_path: Path) -> None:
    deploy_dir = tmp_path / "deploy"
    output_dir = deploy_dir / "backups"
    bundle_dir = output_dir / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)

    created_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    manifest = manage_backups.build_manifest(
        backup_id="backup-20260418T120000Z",
        created_at=created_at,
        deploy_dir=deploy_dir,
        output_dir=output_dir,
        bundle_dir=bundle_dir,
        compose_project="socialevalpilot",
        postgres_user="socialeval",
        postgres_db="socialeval",
    )

    assert manifest["schema_version"] == 1
    assert manifest["backup_id"] == "backup-20260418T120000Z"
    assert manifest["created_at_utc"] == "2026-04-18T12:00:00Z"
    assert manifest["deployment_shape"] == "single-host-compose"
    assert manifest["compose_file"] == "docker-compose.prod.yml"
    assert manifest["postgres_user"] == "socialeval"
    assert manifest["postgres_db"] == "socialeval"
    assert manifest["compose_project"] == "socialevalpilot"
    assert manifest["services"] == ["postgres", "redis", "api", "worker", "frontend", "nginx"]
    assert manifest["volumes"] == ["appdata", "redisdata"]
    assert manifest["artifacts"] == {
        "postgres_dump": "postgres.dump",
        "appdata_archive": "appdata.tar.gz",
        "redis_archive": "redisdata.tar.gz",
    }
    assert manifest["bundle_path"] == str(bundle_dir)


def test_plan_create_commands_builds_expected_backup_steps(tmp_path: Path) -> None:
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"

    plan = manage_backups.plan_create_commands(
        runtime=runtime,
        bundle_dir=bundle_dir,
        postgres_user="socialeval",
        postgres_db="socialeval",
    )

    assert plan[0] == ["mkdir", "-p", str(bundle_dir)]
    assert plan[1] == [
        "docker",
        "compose",
        "-p",
        "socialevalpilot",
        "-f",
        "docker-compose.prod.yml",
        "exec",
        "-T",
        "postgres",
        "pg_dump",
        "-U",
        "socialeval",
        "-d",
        "socialeval",
        "-Fc",
    ]
    assert plan[2] == [
        "docker",
        "run",
        "--rm",
        "-v",
        "socialevalpilot_appdata:/volume:ro",
        "-v",
        f"{bundle_dir}:/backup",
        "alpine:3.20",
        "tar",
        "-czf",
        "/backup/appdata.tar.gz",
        "-C",
        "/volume",
        ".",
    ]
    assert plan[3] == [
        "docker",
        "run",
        "--rm",
        "-v",
        "socialevalpilot_redisdata:/volume:ro",
        "-v",
        f"{bundle_dir}:/backup",
        "alpine:3.20",
        "tar",
        "-czf",
        "/backup/redisdata.tar.gz",
        "-C",
        "/volume",
        ".",
    ]


def test_enforce_restore_safety_guards_require_explicit_confirmation() -> None:
    with pytest.raises(ValueError, match="--allow-destructive-restore"):
        manage_backups.enforce_restore_safety_guards(
            allow_destructive_restore=False,
            expected_backup_id="backup-20260418T120000Z",
            manifest={
                "backup_id": "backup-20260418T120000Z",
                "schema_version": 1,
                "deployment_shape": "single-host-compose",
                "compose_file": "docker-compose.prod.yml",
                "postgres_user": "socialeval",
                "postgres_db": "socialeval",
                "compose_project": "socialevalpilot",
                "services": ["postgres", "redis", "api", "worker", "frontend", "nginx"],
                "volumes": ["appdata", "redisdata"],
                "artifacts": {
                    "postgres_dump": "postgres.dump",
                    "appdata_archive": "appdata.tar.gz",
                    "redis_archive": "redisdata.tar.gz",
                },
            },
            runtime=manage_backups.RuntimePaths.from_deploy_dir(Path.cwd(), compose_project="socialevalpilot"),
            postgres_user="socialeval",
            postgres_db="socialeval",
        )

    with pytest.raises(ValueError, match="does not match manifest backup_id"):
        manage_backups.enforce_restore_safety_guards(
            allow_destructive_restore=True,
            expected_backup_id="wrong-id",
            manifest={
                "backup_id": "backup-20260418T120000Z",
                "schema_version": 1,
                "deployment_shape": "single-host-compose",
                "compose_file": "docker-compose.prod.yml",
                "postgres_user": "socialeval",
                "postgres_db": "socialeval",
                "compose_project": "socialevalpilot",
                "services": ["postgres", "redis", "api", "worker", "frontend", "nginx"],
                "volumes": ["appdata", "redisdata"],
                "artifacts": {
                    "postgres_dump": "postgres.dump",
                    "appdata_archive": "appdata.tar.gz",
                    "redis_archive": "redisdata.tar.gz",
                },
            },
            runtime=manage_backups.RuntimePaths.from_deploy_dir(Path.cwd(), compose_project="socialevalpilot"),
            postgres_user="socialeval",
            postgres_db="socialeval",
        )

    manage_backups.enforce_restore_safety_guards(
        allow_destructive_restore=True,
        expected_backup_id="backup-20260418T120000Z",
        manifest={
            "backup_id": "backup-20260418T120000Z",
                "schema_version": 1,
                "deployment_shape": "single-host-compose",
                "compose_file": "docker-compose.prod.yml",
                "postgres_user": "socialeval",
                "postgres_db": "socialeval",
                "compose_project": "socialevalpilot",
                "services": ["postgres", "redis", "api", "worker", "frontend", "nginx"],
                "volumes": ["appdata", "redisdata"],
                "artifacts": {
                "postgres_dump": "postgres.dump",
                "appdata_archive": "appdata.tar.gz",
                "redis_archive": "redisdata.tar.gz",
            },
        },
        runtime=manage_backups.RuntimePaths.from_deploy_dir(Path.cwd(), compose_project="socialevalpilot"),
        postgres_user="socialeval",
        postgres_db="socialeval",
    )


def test_handle_restore_validates_required_artifacts_before_destructive_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)
    write_valid_manifest(bundle_dir)
    (bundle_dir / "postgres.dump").write_bytes(b"dump")
    write_valid_tar_gz(bundle_dir / "appdata.tar.gz")
    # Intentionally missing redisdata.tar.gz

    calls: list[list[str]] = []

    def fake_run_command(cmd: list[str], cwd: Path) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(manage_backups, "run_command", fake_run_command)

    with pytest.raises(FileNotFoundError, match="redisdata.tar.gz"):
        manage_backups.handle_restore(
            runtime,
            bundle_dir=bundle_dir,
            postgres_user="socialeval",
            postgres_db="socialeval",
            allow_destructive_restore=True,
            confirm_backup_id="backup-20260418T120000Z",
            dry_run=False,
        )

    assert calls == []


def test_handle_restore_blocks_mismatched_postgres_target_before_destructive_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)
    write_valid_manifest(bundle_dir)
    (bundle_dir / "postgres.dump").write_bytes(b"dump")
    write_valid_tar_gz(bundle_dir / "appdata.tar.gz")
    write_valid_tar_gz(bundle_dir / "redisdata.tar.gz")

    calls: list[list[str]] = []

    def fake_run_command(cmd: list[str], cwd: Path) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(manage_backups, "run_command", fake_run_command)

    with pytest.raises(ValueError, match="postgres target"):
        manage_backups.handle_restore(
            runtime,
            bundle_dir=bundle_dir,
            postgres_user="socialeval",
            postgres_db="otherdb",
            allow_destructive_restore=True,
            confirm_backup_id="backup-20260418T120000Z",
            dry_run=False,
        )

    assert calls == []


def test_handle_restore_blocks_mismatched_compose_project_before_destructive_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path, compose_project="socialevalpilot")
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)
    write_valid_manifest(bundle_dir, compose_project="anotherproject")
    (bundle_dir / "postgres.dump").write_bytes(b"dump")
    write_valid_tar_gz(bundle_dir / "appdata.tar.gz")
    write_valid_tar_gz(bundle_dir / "redisdata.tar.gz")

    calls: list[list[str]] = []

    def fake_run_command(cmd: list[str], cwd: Path) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(manage_backups, "run_command", fake_run_command)

    with pytest.raises(ValueError, match="compose project"):
        manage_backups.handle_restore(
            runtime,
            bundle_dir=bundle_dir,
            postgres_user="socialeval",
            postgres_db="socialeval",
            allow_destructive_restore=True,
            confirm_backup_id="backup-20260418T120000Z",
            dry_run=False,
        )

    assert calls == []


def test_handle_restore_blocks_invalid_tar_archive_before_destructive_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)
    write_valid_manifest(bundle_dir)
    (bundle_dir / "postgres.dump").write_bytes(b"dump")
    (bundle_dir / "appdata.tar.gz").write_bytes(b"not-a-tar")
    write_valid_tar_gz(bundle_dir / "redisdata.tar.gz")

    calls: list[list[str]] = []

    def fake_run_command(cmd: list[str], cwd: Path) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(manage_backups, "run_command", fake_run_command)

    with pytest.raises(ValueError, match="invalid tar archive"):
        manage_backups.handle_restore(
            runtime,
            bundle_dir=bundle_dir,
            postgres_user="socialeval",
            postgres_db="socialeval",
            allow_destructive_restore=True,
            confirm_backup_id="backup-20260418T120000Z",
            dry_run=False,
        )

    assert calls == []


def test_handle_restore_blocks_truncated_tar_archive_before_destructive_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)
    write_valid_manifest(bundle_dir)
    (bundle_dir / "postgres.dump").write_bytes(b"dump")
    write_valid_tar_gz(bundle_dir / "appdata.tar.gz")
    write_valid_tar_gz(bundle_dir / "redisdata.tar.gz")
    truncated = (bundle_dir / "appdata.tar.gz").read_bytes()[:-1]
    (bundle_dir / "appdata.tar.gz").write_bytes(truncated)

    calls: list[list[str]] = []

    def fake_run_command(cmd: list[str], cwd: Path) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(manage_backups, "run_command", fake_run_command)

    with pytest.raises(ValueError, match="invalid tar archive"):
        manage_backups.handle_restore(
            runtime,
            bundle_dir=bundle_dir,
            postgres_user="socialeval",
            postgres_db="socialeval",
            allow_destructive_restore=True,
            confirm_backup_id="backup-20260418T120000Z",
            dry_run=False,
        )

    assert calls == []


def test_load_and_validate_restore_bundle_rejects_symlinked_artifacts(tmp_path: Path) -> None:
    source_dir = tmp_path / "source-bundle"
    source_dir.mkdir()
    write_valid_manifest(source_dir)
    (source_dir / "postgres.dump").write_bytes(b"dump")
    write_valid_tar_gz(source_dir / "appdata.tar.gz")
    write_valid_tar_gz(source_dir / "redisdata.tar.gz")

    bundle_dir = tmp_path / "linked-bundle"
    bundle_dir.mkdir()
    for name in ("manifest.json", "postgres.dump", "appdata.tar.gz", "redisdata.tar.gz"):
        (bundle_dir / name).symlink_to(source_dir / name)

    with pytest.raises(ValueError, match="symlink"):
        manage_backups.load_and_validate_restore_bundle(bundle_dir)


def test_handle_restore_validates_postgres_dump_before_destructive_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)
    write_valid_manifest(bundle_dir)
    (bundle_dir / "postgres.dump").write_bytes(b"dump")
    write_valid_tar_gz(bundle_dir / "appdata.tar.gz")
    write_valid_tar_gz(bundle_dir / "redisdata.tar.gz")

    calls: list[list[str]] = []

    def fake_run_command(cmd: list[str], cwd: Path) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(manage_backups, "run_command", fake_run_command)
    monkeypatch.setattr(manage_backups, "list_running_services", lambda runtime: ["postgres"])
    monkeypatch.setattr(
        manage_backups,
        "validate_postgres_dump_archive",
        lambda runtime, dump_file: (_ for _ in ()).throw(ValueError("invalid postgres dump")),
    )

    with pytest.raises(ValueError, match="invalid postgres dump"):
        manage_backups.handle_restore(
            runtime,
            bundle_dir=bundle_dir,
            postgres_user="socialeval",
            postgres_db="socialeval",
            allow_destructive_restore=True,
            confirm_backup_id="backup-20260418T120000Z",
            dry_run=False,
        )

    assert calls == []


def test_handle_restore_requires_postgres_service_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)
    write_valid_manifest(bundle_dir)
    (bundle_dir / "postgres.dump").write_bytes(b"dump")
    write_valid_tar_gz(bundle_dir / "appdata.tar.gz")
    write_valid_tar_gz(bundle_dir / "redisdata.tar.gz")

    calls: list[list[str]] = []

    def fake_run_command(cmd: list[str], cwd: Path) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(manage_backups, "run_command", fake_run_command)
    monkeypatch.setattr(manage_backups, "list_running_services", lambda runtime: [])
    monkeypatch.setattr(manage_backups, "validate_postgres_dump_archive", lambda runtime, dump_file: None)

    with pytest.raises(ValueError, match="postgres service must be running"):
        manage_backups.handle_restore(
            runtime,
            bundle_dir=bundle_dir,
            postgres_user="socialeval",
            postgres_db="socialeval",
            allow_destructive_restore=True,
            confirm_backup_id="backup-20260418T120000Z",
            dry_run=False,
        )

    assert calls == []


def test_handle_restore_blocks_when_writer_services_are_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)
    write_valid_manifest(bundle_dir)
    (bundle_dir / "postgres.dump").write_bytes(b"dump")
    write_valid_tar_gz(bundle_dir / "appdata.tar.gz")
    write_valid_tar_gz(bundle_dir / "redisdata.tar.gz")

    calls: list[list[str]] = []

    def fake_run_command(cmd: list[str], cwd: Path) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(manage_backups, "run_command", fake_run_command)
    monkeypatch.setattr(manage_backups, "list_running_services", lambda runtime: ["postgres", "api", "redis"])
    monkeypatch.setattr(manage_backups, "validate_postgres_dump_archive", lambda runtime, dump_file: None)

    with pytest.raises(ValueError, match="stop these services"):
        manage_backups.handle_restore(
            runtime,
            bundle_dir=bundle_dir,
            postgres_user="socialeval",
            postgres_db="socialeval",
            allow_destructive_restore=True,
            confirm_backup_id="backup-20260418T120000Z",
            dry_run=False,
        )

    assert calls == []


def test_plan_restore_commands_replace_volume_contents_including_hidden_entries(tmp_path: Path) -> None:
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"

    plan = manage_backups.plan_restore_commands(
        runtime=runtime,
        bundle_dir=bundle_dir,
        postgres_user="socialeval",
        postgres_db="socialeval",
    )

    assert plan[2][-1] == (
        "find /volume -mindepth 1 -maxdepth 1 -exec rm -rf -- {} \\; && "
        "tar -xzf /backup/appdata.tar.gz -C /volume"
    )
    assert plan[3][-1] == (
        "find /volume -mindepth 1 -maxdepth 1 -exec rm -rf -- {} \\; && "
        "tar -xzf /backup/redisdata.tar.gz -C /volume"
    )


def test_handle_create_dry_run_outputs_pg_dump_redirection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path, tmp_path / "custom backups")

    class FixedDateTime:
        @staticmethod
        def now(tz: timezone) -> datetime:
            return datetime(2026, 4, 18, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(manage_backups, "datetime", FixedDateTime)

    rc = manage_backups.handle_create(
        runtime,
        postgres_user="socialeval",
        postgres_db="socialeval",
        dry_run=True,
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert f"> '{runtime.output_dir}/backup-20260418T120000Z/postgres.dump'" in out


def test_handle_create_blocks_when_writer_services_are_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)

    monkeypatch.setattr(manage_backups, "list_running_services", lambda runtime: ["postgres", "api", "redis"])

    with pytest.raises(ValueError, match="stop these services"):
        manage_backups.handle_create(
            runtime,
            postgres_user="socialeval",
            postgres_db="socialeval",
            dry_run=False,
        )


def test_handle_create_requires_postgres_service_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)

    monkeypatch.setattr(manage_backups, "list_running_services", lambda runtime: [])

    with pytest.raises(ValueError, match="postgres service must be running"):
        manage_backups.handle_create(
            runtime,
            postgres_user="socialeval",
            postgres_db="socialeval",
            dry_run=False,
        )


def test_validate_runtime_volume_targets_rejects_missing_service_mount(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text(
        """
services:
  redis:
    image: redis:7
    volumes:
      - redisdata:/data
  api:
    image: app
    volumes:
      - appdata:/app/data
  worker:
    image: app
  postgres:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  appdata:
  pgdata:
  redisdata:
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)

    monkeypatch.setattr(manage_backups, "validate_named_docker_volumes_exist", lambda runtime: None)

    with pytest.raises(ValueError, match="worker"):
        manage_backups.validate_runtime_volume_targets(runtime)


def test_handle_create_blocks_when_volume_targets_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)

    monkeypatch.setattr(manage_backups, "list_running_services", lambda runtime: ["postgres"])
    monkeypatch.setattr(
        manage_backups,
        "validate_runtime_volume_targets",
        lambda runtime: (_ for _ in ()).throw(ValueError("volume targets invalid")),
    )

    with pytest.raises(ValueError, match="volume targets invalid"):
        manage_backups.handle_create(
            runtime,
            postgres_user="socialeval",
            postgres_db="socialeval",
            dry_run=False,
        )


def test_handle_restore_blocks_when_volume_targets_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = runtime.output_dir / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)
    write_valid_manifest(bundle_dir)
    (bundle_dir / "postgres.dump").write_bytes(b"dump")
    write_valid_tar_gz(bundle_dir / "appdata.tar.gz")
    write_valid_tar_gz(bundle_dir / "redisdata.tar.gz")

    calls: list[list[str]] = []

    def fake_run_command(cmd: list[str], cwd: Path) -> int:
        calls.append(cmd)
        return 0

    monkeypatch.setattr(manage_backups, "run_command", fake_run_command)
    monkeypatch.setattr(manage_backups, "list_running_services", lambda runtime: ["postgres"])
    monkeypatch.setattr(manage_backups, "validate_postgres_dump_archive", lambda runtime, dump_file: None)
    monkeypatch.setattr(
        manage_backups,
        "validate_runtime_volume_targets",
        lambda runtime: (_ for _ in ()).throw(ValueError("volume targets invalid")),
    )

    with pytest.raises(ValueError, match="volume targets invalid"):
        manage_backups.handle_restore(
            runtime,
            bundle_dir=bundle_dir,
            postgres_user="socialeval",
            postgres_db="socialeval",
            allow_destructive_restore=True,
            confirm_backup_id="backup-20260418T120000Z",
            dry_run=False,
        )

    assert calls == []


def test_handle_restore_dry_run_outputs_pg_restore_redirection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    runtime = manage_backups.RuntimePaths.from_deploy_dir(tmp_path)
    bundle_dir = tmp_path / "restore bundle" / "backup-20260418T120000Z"
    bundle_dir.mkdir(parents=True)
    write_valid_manifest(bundle_dir)
    (bundle_dir / "postgres.dump").write_bytes(b"dump")
    write_valid_tar_gz(bundle_dir / "appdata.tar.gz")
    write_valid_tar_gz(bundle_dir / "redisdata.tar.gz")

    rc = manage_backups.handle_restore(
        runtime,
        bundle_dir=bundle_dir,
        postgres_user="socialeval",
        postgres_db="socialeval",
        allow_destructive_restore=True,
        confirm_backup_id="backup-20260418T120000Z",
        dry_run=True,
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert f"< '{bundle_dir / 'postgres.dump'}'" in out
