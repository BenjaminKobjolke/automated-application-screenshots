"""Tiny adb and emulator stand-in for Android live-session integration tests."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def _state() -> Path:
    return Path(os.environ["FAKE_ANDROID_STATE"])


def _running() -> Path:
    path = _state() / "running"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log(message: str) -> None:
    with (_state() / "calls.log").open("a", encoding="utf-8") as stream:
        stream.write(message + "\n")


def _adb(args: list[str]) -> int:
    _log("adb " + " ".join(args))
    if args == ["devices"]:
        print("List of devices attached")
        for item in sorted(_running().iterdir()):
            print(f"{item.name}\tdevice")
        return 0

    if len(args) < 3 or args[0] != "-s":
        return 0
    serial = args[1]
    command = args[2:]
    if command == ["emu", "avd", "name"]:
        path = _running() / serial
        if path.exists():
            print(path.read_text(encoding="utf-8"))
        print("OK")
    elif command == ["wait-for-device"]:
        return 0
    elif command == ["shell", "getprop", "sys.boot_completed"]:
        print("1")
    elif command == ["emu", "kill"]:
        _log("kill " + serial)
        (_running() / serial).unlink(missing_ok=True)
    return 0


def _emulator(args: list[str]) -> int:
    try:
        avd = args[args.index("-avd") + 1]
    except (ValueError, IndexError):
        return 2
    serial_number = next(
        number for number in range(5554, 10000, 2)
        if not (_running() / f"emulator-{number}").exists()
    )
    serial = f"emulator-{serial_number}"
    running = _running() / serial
    running.write_text(avd, encoding="utf-8")
    _log(f"start {avd} {serial}")
    while running.exists():
        time.sleep(0.1)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        return 2
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == "adb":
        return _adb(args)
    if mode == "emulator":
        return _emulator(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
