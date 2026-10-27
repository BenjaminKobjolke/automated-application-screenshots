"""Shared fixtures for integration tests."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

from screenshot_tool.live_config import LiveSettings, LiveTarget
from screenshot_tool.live_session import LiveSession

FAKE_DAEMON = Path(__file__).parents[1] / "fixtures" / "fake_flutter_daemon.py"


def available_port() -> int:
    """Return an available ephemeral loopback port."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


@pytest.fixture
def free_port() -> int:
    """Return an available port for an integration test server."""
    return available_port()


@pytest.fixture
def live_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, free_port: int) -> LiveSession:
    """Create a live session backed by the fake Flutter daemon."""
    control = tmp_path / "control"
    monkeypatch.setenv("FLUTTER_FAKE_CONTROL", str(control))
    settings = LiveSettings(
        target=LiveTarget.WINDOWS,
        port=free_port,
        flutter=(sys.executable, str(FAKE_DAEMON)),
        project_dir=tmp_path,
        start_timeout=10,
    )
    session = LiveSession(settings)
    yield session
    session.stop()
