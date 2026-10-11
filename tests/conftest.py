"""Keep unit tests from stopping the developer's FancyZones process."""

import pytest

from screenshot_tool import fancyzones


@pytest.fixture(autouse=True)
def disable_fancyzones_process_lookup(monkeypatch):
    """Unit tests never discover a real FancyZones process."""
    monkeypatch.setattr(fancyzones, "_running", lambda: [])
