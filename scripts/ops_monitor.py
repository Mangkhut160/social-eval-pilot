from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


DEFAULT_ENDPOINT = "http://127.0.0.1:8000/api/admin/operations/overview"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate SocialEval operations overview and emit alert exit codes.",
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Admin operations overview endpoint URL.")
    parser.add_argument("--api-key", default="", help="Optional API key for X-API-Key auth.")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP timeout seconds when fetching endpoint.")
    parser.add_argument("--input-file", type=Path, default=None, help="Read overview JSON from file.")
    parser.add_argument("--max-recovering", type=int, default=0, help="Maximum allowed recovering task count.")
    parser.add_argument("--max-recent-failures", type=int, default=0, help="Maximum allowed recent failure count.")
    parser.add_argument("--max-pending-reviews", type=int, default=10, help="Maximum allowed pending review count.")
    return parser.parse_args(argv)


def fetch_overview(endpoint: str, api_key: str, timeout: int) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = Request(endpoint, headers=headers, method="GET")
    with urlopen(request, timeout=max(timeout, 1)) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def evaluate_alerts(
    overview: dict[str, Any],
    *,
    max_recovering: int,
    max_recent_failures: int,
    max_pending_reviews: int,
) -> list[str]:
    alerts: list[str] = []

    task_counts = overview.get("task_counts", {})
    recovering = int(task_counts.get("recovering", 0))
    if recovering > max_recovering:
        alerts.append(f"recovering task count {recovering} exceeds threshold {max_recovering}")

    recent_failures = overview.get("recent_failures", [])
    recent_failure_count = len(recent_failures) if isinstance(recent_failures, list) else 0
    if recent_failure_count > max_recent_failures:
        alerts.append(
            f"recent failure count {recent_failure_count} exceeds threshold {max_recent_failures}"
        )

    pending_reviews = int(overview.get("pending_reviews", 0))
    if pending_reviews > max_pending_reviews:
        alerts.append(f"pending review count {pending_reviews} exceeds threshold {max_pending_reviews}")

    dependencies = overview.get("dependencies", {})
    if isinstance(dependencies, dict):
        for name, check in dependencies.items():
            status = ""
            detail = ""
            if isinstance(check, dict):
                status = str(check.get("status", ""))
                detail = str(check.get("detail", ""))
            if status and status != "ok":
                alerts.append(f"dependency {name} status={status} detail={detail}")

    return alerts


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        if args.input_file is not None:
            overview = json.loads(args.input_file.read_text(encoding="utf-8"))
        else:
            overview = fetch_overview(args.endpoint, args.api_key, args.timeout)
    except Exception as exc:
        print(f"ALERT: failed to load operations overview: {exc}", file=sys.stderr)
        return 1

    alerts = evaluate_alerts(
        overview,
        max_recovering=args.max_recovering,
        max_recent_failures=args.max_recent_failures,
        max_pending_reviews=args.max_pending_reviews,
    )
    if alerts:
        for alert in alerts:
            print(f"ALERT: {alert}")
        return 2

    print("OK: no alert conditions detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
