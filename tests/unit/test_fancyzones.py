"""FancyZones pause and restoration behavior."""

from unittest.mock import MagicMock

import psutil
import pytest

from screenshot_tool import fancyzones


def process(command):
    result = MagicMock(spec=psutil.Process)
    result.cmdline.return_value = command
    return result


def test_no_running_process_has_no_side_effects(monkeypatch):
    lookup = MagicMock(return_value=[])
    popen = MagicMock()
    monkeypatch.setattr(fancyzones, "_running", lookup)
    monkeypatch.setattr(fancyzones.subprocess, "Popen", popen)

    with fancyzones.paused():
        pass

    popen.assert_not_called()


def test_running_process_is_terminated_and_restarted(monkeypatch):
    command = ["C:/PowerToys.FancyZones.exe", "123"]
    proc = process(command)
    running = MagicMock(side_effect=[[proc], []])
    popen = MagicMock()
    monkeypatch.setattr(fancyzones, "_running", running)
    monkeypatch.setattr(fancyzones.subprocess, "Popen", popen)

    with fancyzones.paused():
        proc.cmdline.assert_called_once_with()
        proc.terminate.assert_called_once_with()
        proc.wait.assert_called_once_with(timeout=fancyzones.STOP_TIMEOUT_S)
        popen.assert_not_called()

    popen.assert_called_once_with(
        command,
        creationflags=fancyzones.subprocess.DETACHED_PROCESS
        | fancyzones.subprocess.CREATE_NEW_PROCESS_GROUP,
    )


def test_running_process_is_restarted_when_block_raises(monkeypatch):
    command = ["FancyZones.exe", "123"]
    proc = process(command)
    monkeypatch.setattr(fancyzones, "_running", MagicMock(side_effect=[[proc], []]))
    popen = MagicMock()
    monkeypatch.setattr(fancyzones.subprocess, "Popen", popen)

    with pytest.raises(RuntimeError, match="recording failed"):
        with fancyzones.paused():
            raise RuntimeError("recording failed")

    popen.assert_called_once()


def test_disabled_does_not_look_up_processes(monkeypatch):
    lookup = MagicMock()
    monkeypatch.setattr(fancyzones, "_running", lookup)

    with fancyzones.paused(enabled=False):
        pass

    lookup.assert_not_called()


def test_access_denied_continues_without_restarting(monkeypatch):
    proc = process(["FancyZones.exe", "123"])
    proc.terminate.side_effect = psutil.AccessDenied(pid=123)
    monkeypatch.setattr(fancyzones, "_running", lambda: [proc])
    popen = MagicMock()
    monkeypatch.setattr(fancyzones.subprocess, "Popen", popen)
    body = MagicMock()

    with fancyzones.paused():
        body()

    body.assert_called_once_with()
    popen.assert_not_called()


def test_does_not_start_duplicate_process(monkeypatch):
    proc = process(["FancyZones.exe", "123"])
    existing = process(["FancyZones.exe", "456"])
    monkeypatch.setattr(fancyzones, "_running", MagicMock(side_effect=[[proc], [existing]]))
    popen = MagicMock()
    monkeypatch.setattr(fancyzones.subprocess, "Popen", popen)

    with fancyzones.paused():
        pass

    popen.assert_not_called()


def test_restart_error_is_logged_and_swallowed(monkeypatch):
    proc = process(["FancyZones.exe", "123"])
    monkeypatch.setattr(fancyzones, "_running", MagicMock(side_effect=[[proc], []]))
    monkeypatch.setattr(fancyzones.subprocess, "Popen", MagicMock(side_effect=OSError("denied")))
    error = MagicMock()
    monkeypatch.setattr(fancyzones.AppLogger, "error", error)

    with fancyzones.paused():
        pass

    assert "FancyZones.exe" in error.call_args.args[0]
