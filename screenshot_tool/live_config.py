"""Typed configuration and target-derived values for live Flutter sessions."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, NoReturn


class LiveTarget(Enum):
    """Device family that receives the Flutter application."""

    WINDOWS = "windows"
    ANDROID_EMULATOR = "android_emulator"


@dataclass(frozen=True)
class LiveSettings:
    """Settings needed to start and connect a live Flutter app."""

    target: LiveTarget
    port: int
    avd: str | None = None
    headless: bool = False
    flutter: tuple[str, ...] = ("flutter",)
    run_args: tuple[str, ...] = ()
    project_dir: Path = Path(".")
    app_settings: dict[str, Any] = field(default_factory=dict)
    start_timeout: int | float = 600


_LIVE_KEYS = {
    "target",
    "avd",
    "headless",
    "port",
    "flutter",
    "run_args",
    "project_dir",
    "app_settings",
    "start_timeout",
}


def _fail(config_path: Path, message: str) -> NoReturn:
    raise SystemExit(f"ERROR: Config {config_path}: {message}")


def _string_list(
    config_path: Path, data: dict[str, Any], key: str, default: list[str]
) -> tuple[str, ...]:
    value = data.get(key, default)
    is_non_empty_string_list = (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) for item in value)
    )
    if not is_non_empty_string_list:
        _fail(config_path, f"live.{key} must be a non-empty list of strings")
    return tuple(value)


def _is_valid_port(port: Any) -> bool:
    if isinstance(port, bool) or not isinstance(port, int):
        return False
    return 1 <= port <= 65535


def _run_args(config_path: Path, data: dict[str, Any]) -> tuple[str, ...]:
    value = data.get("run_args", [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _fail(config_path, "live.run_args must be a list of strings")
    return tuple(value)


def parse_live(config_path: Path, data: Any) -> LiveSettings:
    """Validate a live config section and resolve its app directory."""
    if not isinstance(data, dict):
        _fail(config_path, "live must be an object")
    unknown = set(data) - _LIVE_KEYS
    if unknown:
        _fail(config_path, f"live has unknown option(s): {', '.join(sorted(unknown))}")

    target_value = data.get("target")
    try:
        target = LiveTarget(target_value)
    except (ValueError, TypeError):
        _fail(config_path, "live.target must be 'windows' or 'android_emulator'")

    port = data.get("port")
    if not _is_valid_port(port):
        _fail(config_path, "live.port must be an integer from 1 to 65535")

    avd = data.get("avd")
    if avd is not None and (not isinstance(avd, str) or not avd):
        _fail(config_path, "live.avd must be a non-empty string when provided")
    headless = data.get("headless", False)
    if not isinstance(headless, bool):
        _fail(config_path, "live.headless must be a boolean")

    raw_project_dir = data.get("project_dir", ".")
    if not isinstance(raw_project_dir, str) or not raw_project_dir:
        _fail(config_path, "live.project_dir must be a non-empty string")
    project_dir = Path(raw_project_dir)
    if not project_dir.is_absolute():
        project_dir = config_path.parent / project_dir

    app_settings = data.get("app_settings", {})
    if not isinstance(app_settings, dict):
        _fail(config_path, "live.app_settings must be an object")

    start_timeout = data.get("start_timeout", 600)
    is_positive_timeout = (
        not isinstance(start_timeout, bool)
        and isinstance(start_timeout, (int, float))
        and start_timeout > 0
    )
    if not is_positive_timeout:
        _fail(config_path, "live.start_timeout must be a positive number of seconds")

    return LiveSettings(
        target=target,
        port=port,
        avd=avd,
        headless=headless,
        flutter=_string_list(config_path, data, "flutter", ["flutter"]),
        run_args=_run_args(config_path, data),
        project_dir=project_dir.resolve(),
        app_settings=app_settings,
        start_timeout=start_timeout,
    )


def automation_host(target: LiveTarget, port: int) -> str:
    """Derive the host address the app uses to reach the tool."""
    if not _is_valid_port(port):
        raise ValueError("port must be an integer from 1 to 65535")
    hosts = {
        LiveTarget.WINDOWS: "127.0.0.1",
        LiveTarget.ANDROID_EMULATOR: "10.0.2.2",
    }
    try:
        host = hosts[target]
    except KeyError as error:
        raise ValueError(f"unsupported live target: {target!r}") from error
    return f"{host}:{port}"


def device_id(target: LiveTarget, emulator_serial: str | None = None) -> str:
    """Return Flutter's device id for the selected target."""
    if target is LiveTarget.WINDOWS:
        return "windows"
    if target is LiveTarget.ANDROID_EMULATOR and emulator_serial:
        return emulator_serial
    raise ValueError("an emulator serial is required for android_emulator")
