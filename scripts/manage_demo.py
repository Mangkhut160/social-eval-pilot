from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


COMPOSE_PROJECT = "socialevalpilot"
COMPOSE_FILE = "docker-compose.prod.yml"
PINGGY_SSH_HOST = "a.pinggy.io"
PINGGY_SSH_PORT = 443
PINGGY_SSH_USER = "qr"


@dataclass(frozen=True)
class RuntimePaths:
    deploy_dir: Path
    compose_file: Path
    tunnel_log: Path
    tunnel_pid: Path

    @classmethod
    def from_deploy_dir(cls, deploy_dir: Path) -> "RuntimePaths":
        resolved = deploy_dir.expanduser().resolve()
        return cls(
            deploy_dir=resolved,
            compose_file=resolved / COMPOSE_FILE,
            tunnel_log=resolved / "pinggy.log",
            tunnel_pid=resolved / "pinggy.pid",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="管理本地文科论文评价系统演示部署。"
    )
    parser.add_argument(
        "--deploy-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Deployment directory that contains docker-compose.prod.yml.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("up", help="Start the demo stack in detached mode.")
    subparsers.add_parser("down", help="Stop the demo stack.")
    subparsers.add_parser("status", help="Show current compose status.")
    subparsers.add_parser("urls", help="Print the fixed local demo entrypoints.")

    logs_parser = subparsers.add_parser("logs", help="Tail compose logs.")
    logs_parser.add_argument("services", nargs="*", help="Optional services to filter.")
    logs_parser.add_argument("--tail", type=int, default=100, help="Number of lines to show.")

    tunnel_up_parser = subparsers.add_parser(
        "tunnel-up", help="Start the temporary Pinggy tunnel for external demo access."
    )
    tunnel_up_parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Seconds to wait for Pinggy to print the public URL.",
    )
    subparsers.add_parser("tunnel-down", help="Stop the temporary Pinggy tunnel.")
    return parser.parse_args()


def compose_command(runtime: RuntimePaths, *args: str) -> list[str]:
    if not runtime.compose_file.exists():
        raise FileNotFoundError(f"Missing compose file: {runtime.compose_file}")
    return [
        "docker-compose",
        "-p",
        COMPOSE_PROJECT,
        "-f",
        runtime.compose_file.name,
        *args,
    ]


def run_command(cmd: Sequence[str], cwd: Path) -> int:
    result = subprocess.run(list(cmd), cwd=cwd, check=False)
    return result.returncode


def extract_tunnel_url(log_path: Path) -> str | None:
    if not log_path.exists():
        return None
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("https://"):
            return stripped
    return None


def get_lan_ip() -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_pid(pid_path: Path) -> int | None:
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def handle_up(runtime: RuntimePaths) -> int:
    return run_command(compose_command(runtime, "up", "-d"), runtime.deploy_dir)


def handle_down(runtime: RuntimePaths) -> int:
    return run_command(compose_command(runtime, "down"), runtime.deploy_dir)


def handle_status(runtime: RuntimePaths) -> int:
    return run_command(compose_command(runtime, "ps"), runtime.deploy_dir)


def handle_logs(runtime: RuntimePaths, services: list[str], tail: int) -> int:
    return run_command(
        compose_command(runtime, "logs", f"--tail={tail}", *services),
        runtime.deploy_dir,
    )


def handle_urls(runtime: RuntimePaths) -> int:
    print("Local demo: http://127.0.0.1")
    lan_ip = get_lan_ip()
    if lan_ip is not None:
        print(f"LAN demo: http://{lan_ip}")
    tunnel_url = extract_tunnel_url(runtime.tunnel_log)
    if tunnel_url is not None:
        print(f"Tunnel demo: {tunnel_url}")
    return 0


def handle_tunnel_up(runtime: RuntimePaths, timeout: int) -> int:
    existing_pid = read_pid(runtime.tunnel_pid)
    if existing_pid is not None and is_process_running(existing_pid):
        existing_url = extract_tunnel_url(runtime.tunnel_log)
        if existing_url is not None:
            print(existing_url)
        else:
            print(f"Tunnel already running with pid {existing_pid}.")
        return 0

    runtime.tunnel_log.write_text("", encoding="utf-8")
    with runtime.tunnel_log.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [
                "ssh",
                "-p",
                str(PINGGY_SSH_PORT),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                f"UserKnownHostsFile={Path.home() / '.ssh' / 'known_hosts'}",
                "-o",
                "ServerAliveInterval=30",
                "-o",
                "ExitOnForwardFailure=yes",
                "-R0:localhost:80",
                f"{PINGGY_SSH_USER}@{PINGGY_SSH_HOST}",
            ],
            cwd=runtime.deploy_dir,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    runtime.tunnel_pid.write_text(str(process.pid), encoding="utf-8")

    deadline = time.time() + max(timeout, 1)
    while time.time() < deadline:
        tunnel_url = extract_tunnel_url(runtime.tunnel_log)
        if tunnel_url is not None:
            print(tunnel_url)
            return 0
        if process.poll() is not None:
            break
        time.sleep(1)

    print(
        f"Tunnel process started with pid {process.pid}, but no public URL was found yet.",
        file=sys.stderr,
    )
    return 1


def handle_tunnel_down(runtime: RuntimePaths) -> int:
    pid = read_pid(runtime.tunnel_pid)
    if pid is None:
        print("No demo tunnel process recorded.")
        return 0

    if not is_process_running(pid):
        runtime.tunnel_pid.unlink(missing_ok=True)
        print(f"Tunnel pid {pid} is no longer running.")
        return 0

    os.kill(pid, signal.SIGTERM)
    runtime.tunnel_pid.unlink(missing_ok=True)
    print(f"Stopped tunnel pid {pid}.")
    return 0


def main() -> int:
    args = parse_args()
    runtime = RuntimePaths.from_deploy_dir(args.deploy_dir)

    if args.command == "up":
        return handle_up(runtime)
    if args.command == "down":
        return handle_down(runtime)
    if args.command == "status":
        return handle_status(runtime)
    if args.command == "logs":
        return handle_logs(runtime, args.services, args.tail)
    if args.command == "urls":
        return handle_urls(runtime)
    if args.command == "tunnel-up":
        return handle_tunnel_up(runtime, args.timeout)
    if args.command == "tunnel-down":
        return handle_tunnel_down(runtime)

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
