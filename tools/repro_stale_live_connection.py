"""Reproduce a leftover app connecting to a fresh live session before installation.

The connector connects once per app launch and retries for 3 minutes, so a
freshly launched app that finds no listener keeps waiting. A new live session
opens its listener before building, the waiting app connects, and the install
then kills it: the stale connection the live start must skip.
See docs/LIVE.md "Reproducing a leftover app connection".
"""

import argparse
import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
STALE_LINE = "Ignoring stale app connection"
_POLL_SECONDS = 0.25
_RETRY_LOOP_SECONDS = 5


def adb(serial: str, *args: str) -> str:
    result = subprocess.run(
        ["adb", "-s", serial, *args], capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


def server_lines(port: int, state: str) -> list[str]:
    """Netstat lines whose local port is `port` in `state`."""
    output = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, check=False
    ).stdout
    pattern = re.compile(rf"[:.]{port}\s+\S+\s+{state}\s")
    return [line.strip() for line in output.splitlines() if pattern.search(line)]


def now() -> str:
    return datetime.now(UTC).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", required=True, type=Path)
    parser.add_argument("--config", required=True, help="live config, relative to --app-dir")
    parser.add_argument("--package", required=True, help="Android application id")
    parser.add_argument("--session", required=True, type=Path, help="new live session folder")
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--port", type=int, default=8766)
    return parser.parse_args()


def launch_leftover(args: argparse.Namespace) -> str:
    """Restart the installed app so it waits in its connect-retry loop."""
    adb(args.serial, "shell", "am", "force-stop", args.package)
    adb(args.serial, "shell", "monkey", "-p", args.package,
        "-c", "android.intent.category.LAUNCHER", "1")
    time.sleep(_RETRY_LOOP_SECONDS)
    return adb(args.serial, "shell", "pidof", args.package)


def watch_start(args: argparse.Namespace, old_pid: str) -> dict[str, object]:
    command = [
        "uv", "run", "--project", str(TOOL_ROOT), "screenshot-tool",
        "--config", args.config, "--live-start", str(args.session),
    ]
    start = subprocess.Popen(command, cwd=args.app_dir, stdout=subprocess.PIPE, text=True)
    result: dict[str, object] = {"connected_at": None, "connection": None, "replaced_at": None}
    while start.poll() is None:
        if result["replaced_at"] is None:
            if adb(args.serial, "shell", "pidof", args.package) != old_pid:
                result["replaced_at"] = now()
            elif result["connected_at"] is None:
                lines = server_lines(args.port, "ESTABLISHED")
                if lines:
                    result["connected_at"] = now()
                    result["connection"] = lines[0]
        time.sleep(_POLL_SECONDS)
    assert start.stdout is not None
    result["start_response"] = start.stdout.read().strip()
    return result


def main() -> int:
    args = parse_args()
    if server_lines(args.port, "LISTENING"):
        print(json.dumps({"ok": False, "error": f"port {args.port} is already in use"}))
        return 1
    old_pid = launch_leftover(args)
    if not old_pid:
        print(json.dumps({"ok": False, "error": "leftover app did not start"}))
        return 1
    result = watch_start(args, old_pid)
    log = args.session / "live.log"
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    # Keep daemon output out of the report; the fixed marker is sufficient evidence.
    stale = [STALE_LINE for line in text.splitlines() if STALE_LINE in line]
    response = str(result["start_response"])
    start_ok = '"ok": true' in response or '"ok":true' in response
    summary = {
        "old_app_pid": old_pid,
        "old_app_connected_before_install": result["connected_at"] is not None,
        "connected_at": result["connected_at"],
        "connection": result["connection"],
        "replaced_at": result["replaced_at"],
        "start_ok": start_ok,
        "stale_log_lines": stale,
    }
    summary["ok"] = bool(summary["old_app_connected_before_install"] and start_ok and stale)
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
