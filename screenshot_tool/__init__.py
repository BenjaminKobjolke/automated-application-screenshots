"""Automated Screenshot Tool for Multi-Language Windows Applications."""

from .automation import DropdownAutomation
from .capture import WindowCapture
from .cli import ScreenshotCLI
from .dropdown_reader import DropdownReader
from .window_finder import WindowFinder

__all__ = [
    "DropdownAutomation",
    "DropdownReader",
    "WindowCapture",
    "ScreenshotCLI",
    "WindowFinder",
]
