"""Focused tests for Flutter daemon parsing and command construction."""

from pathlib import Path
from unittest.mock import MagicMock

from screenshot_tool.flutter_daemon import DaemonMessage, FlutterDaemon, parse_daemon_line
from screenshot_tool.live_config import LiveSettings, LiveTarget


def settings(**overrides: object) -> LiveSettings:
    values: dict[str, object] = {
        "target": LiveTarget.ANDROID_EMULATOR,
        "port": 45123,
        "flutter": ("fvm", "flutter"),
        "run_args": ("--verbose", "--no-pub"),
        "project_dir": Path("app"),
    }
    values.update(overrides)
    return LiveSettings(**values)  # type: ignore[arg-type]


def test_parse_daemon_event_list():
    messages, log = parse_daemon_line(
        '[{"event":"app.started","params":{"appId":"abc"}},'
        '{"id":"1","result":{"code":0}}]'
    )
    assert [message.event for message in messages] == ["app.started", None]
    assert messages[0].params == {"appId": "abc"}
    assert log is None


def test_parse_daemon_non_json_as_log_text():
    messages, log = parse_daemon_line("Building Windows application...")
    assert messages == ()
    assert log == "Building Windows application..."


def test_run_command_derives_host_and_resolves_flutter_prefix(monkeypatch):
    daemon = FlutterDaemon(settings())
    monkeypatch.setattr("screenshot_tool.flutter_daemon.shutil.which", lambda name: "/tools/fvm")

    command = daemon.build_command("emulator-5556")

    assert command == [
        "/tools/fvm",
        "flutter",
        "run",
        "--machine",
        "-d",
        "emulator-5556",
        "--dart-define=AUTOMATION_HOST=10.0.2.2:45123",
        "--verbose",
        "--no-pub",
    ]


def test_windows_run_command_uses_windows_host():
    daemon = FlutterDaemon(settings(target=LiveTarget.WINDOWS, flutter=("flutter",), run_args=()))

    assert daemon.build_command("windows") == [
        "flutter",
        "run",
        "--machine",
        "-d",
        "windows",
        "--dart-define=AUTOMATION_HOST=127.0.0.1:45123",
    ]


def test_restart_requires_explicit_zero_result_code(monkeypatch):
    daemon = FlutterDaemon(settings())
    daemon._process = MagicMock()
    daemon._process.poll.return_value = None
    daemon._app_id = "app"
    monkeypatch.setattr(
        daemon,
        "_rpc",
        lambda *args: DaemonMessage(event=None, params={}, response_id="1", result={}),
    )

    result = daemon.restart(full=False, timeout=1)

    assert not result.success


def test_restart_accepts_only_zero_result_code(monkeypatch):
    daemon = FlutterDaemon(settings())
    daemon._process = MagicMock()
    daemon._process.poll.return_value = None
    daemon._app_id = "app"
    monkeypatch.setattr(
        daemon,
        "_rpc",
        lambda *args: DaemonMessage(event=None, params={}, response_id="1", result={"code": 0}),
    )

    assert daemon.restart(full=False, timeout=1).success
