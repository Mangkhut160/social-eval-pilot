from __future__ import annotations

from pathlib import Path

import pytest

from scripts import manage_demo


def test_extract_tunnel_url_returns_https_url_when_present(tmp_path: Path) -> None:
    log_path = tmp_path / "pinggy.log"
    log_path.write_text(
        "\n".join(
            [
                "Allocated port 5 for remote forward to localhost:80",
                "http://demo.example",
                "https://demo.example",
            ]
        ),
        encoding="utf-8",
    )

    assert manage_demo.extract_tunnel_url(log_path) == "https://demo.example"


def test_extract_tunnel_url_returns_none_when_log_missing(tmp_path: Path) -> None:
    assert manage_demo.extract_tunnel_url(tmp_path / "missing.log") is None


def test_handle_urls_prints_fixed_local_and_lan_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = manage_demo.RuntimePaths.from_deploy_dir(tmp_path)

    monkeypatch.setattr(manage_demo, "get_lan_ip", lambda: "192.168.1.7")
    monkeypatch.setattr(
        manage_demo,
        "extract_tunnel_url",
        lambda _: "https://demo.run.pinggy-free.link",
    )

    exit_code = manage_demo.handle_urls(runtime)

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "http://127.0.0.1" in output
    assert "http://192.168.1.7" in output
    assert "https://demo.run.pinggy-free.link" in output


def test_handle_up_runs_detached_compose_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docker-compose.prod.yml").write_text("services: {}\n", encoding="utf-8")
    runtime = manage_demo.RuntimePaths.from_deploy_dir(tmp_path)
    calls: list[tuple[list[str], Path]] = []

    def fake_run(cmd: list[str], cwd: Path) -> int:
        calls.append((cmd, cwd))
        return 0

    monkeypatch.setattr(manage_demo, "run_command", fake_run)

    exit_code = manage_demo.handle_up(runtime)

    assert exit_code == 0
    assert calls == [
        (
            [
                "docker-compose",
                "-p",
                "socialevalpilot",
                "-f",
                "docker-compose.prod.yml",
                "up",
                "-d",
            ],
            tmp_path,
        )
    ]


def test_handle_logs_passes_tail_and_services(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docker-compose.prod.yml").write_text("services: {}\n", encoding="utf-8")
    runtime = manage_demo.RuntimePaths.from_deploy_dir(tmp_path)
    calls: list[tuple[list[str], Path]] = []

    def fake_run(cmd: list[str], cwd: Path) -> int:
        calls.append((cmd, cwd))
        return 0

    monkeypatch.setattr(manage_demo, "run_command", fake_run)

    exit_code = manage_demo.handle_logs(runtime, ["api", "worker"], tail=25)

    assert exit_code == 0
    assert calls == [
        (
            [
                "docker-compose",
                "-p",
                "socialevalpilot",
                "-f",
                "docker-compose.prod.yml",
                "logs",
                "--tail=25",
                "api",
                "worker",
            ],
            tmp_path,
        )
    ]


def test_handle_tunnel_down_returns_zero_when_pid_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = manage_demo.RuntimePaths.from_deploy_dir(tmp_path)

    exit_code = manage_demo.handle_tunnel_down(runtime)

    assert exit_code == 0
    assert "No demo tunnel process recorded." in capsys.readouterr().out
