from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import ops_monitor


def test_evaluate_alerts_returns_empty_list_for_healthy_overview() -> None:
    overview = {
        "task_counts": {"recovering": 0},
        "recent_failures": [],
        "pending_reviews": 1,
        "dependencies": {
            "database": {"status": "ok", "detail": "ok"},
            "redis": {"status": "ok", "detail": "ok"},
            "storage": {"status": "ok", "detail": "ok (local)"},
        },
    }

    alerts = ops_monitor.evaluate_alerts(
        overview,
        max_recovering=0,
        max_recent_failures=0,
        max_pending_reviews=3,
    )

    assert alerts == []


def test_evaluate_alerts_flags_threshold_breaches_and_dependency_errors() -> None:
    overview = {
        "task_counts": {"recovering": 2},
        "recent_failures": [{"task_id": "task-1"}],
        "pending_reviews": 5,
        "dependencies": {
            "database": {"status": "ok", "detail": "ok"},
            "redis": {"status": "error", "detail": "connection refused"},
        },
    }

    alerts = ops_monitor.evaluate_alerts(
        overview,
        max_recovering=0,
        max_recent_failures=0,
        max_pending_reviews=3,
    )

    assert any("recovering task count" in alert for alert in alerts)
    assert any("recent failure count" in alert for alert in alerts)
    assert any("pending review count" in alert for alert in alerts)
    assert any("redis" in alert for alert in alerts)


def test_main_exits_non_zero_when_alerts_found_in_file_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    overview_path = tmp_path / "overview.json"
    overview_path.write_text(
        json.dumps(
            {
                "task_counts": {"recovering": 1},
                "recent_failures": [],
                "pending_reviews": 0,
                "dependencies": {"database": {"status": "ok", "detail": "ok"}},
            }
        ),
        encoding="utf-8",
    )

    exit_code = ops_monitor.main(
        [
            "--input-file",
            str(overview_path),
            "--max-recovering",
            "0",
            "--max-recent-failures",
            "0",
            "--max-pending-reviews",
            "0",
        ]
    )

    assert exit_code == 2
    output = capsys.readouterr().out
    assert "ALERT" in output


def test_main_prints_ok_and_returns_zero_for_healthy_remote_overview(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        ops_monitor,
        "fetch_overview",
        lambda endpoint, api_key, timeout: {
            "task_counts": {"recovering": 0},
            "recent_failures": [],
            "pending_reviews": 0,
            "dependencies": {
                "database": {"status": "ok", "detail": "ok"},
                "redis": {"status": "ok", "detail": "ok"},
                "storage": {"status": "ok", "detail": "ok (local)"},
            },
        },
    )

    exit_code = ops_monitor.main(
        [
            "--endpoint",
            "http://127.0.0.1:8000/api/admin/operations/overview",
            "--api-key",
            "secret-api-key",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert output.strip() == "OK: no alert conditions detected"


def test_main_returns_one_when_remote_overview_load_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raise_fetch_error(endpoint: str, api_key: str, timeout: int) -> dict:
        raise RuntimeError("network down")

    monkeypatch.setattr(ops_monitor, "fetch_overview", raise_fetch_error)

    exit_code = ops_monitor.main(["--endpoint", "http://127.0.0.1:8000/api/admin/operations/overview"])

    assert exit_code == 1
    error_output = capsys.readouterr().err
    assert "failed to load operations overview" in error_output


def test_main_exits_two_when_task_queue_dependency_is_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        ops_monitor,
        "fetch_overview",
        lambda endpoint, api_key, timeout: {
            "task_counts": {"recovering": 0},
            "recent_failures": [],
            "pending_reviews": 0,
            "dependencies": {
                "database": {"status": "ok", "detail": "ok"},
                "task_queue": {
                    "status": "error",
                    "detail": "no workers responded to celery ping",
                },
            },
        },
    )

    exit_code = ops_monitor.main(["--endpoint", "http://127.0.0.1:8000/api/admin/operations/overview"])

    assert exit_code == 2
    output = capsys.readouterr().out
    assert "task_queue" in output
