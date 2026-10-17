"""Central logging for the screenshot tool.

All application code logs through ``AppLogger`` instead of ``print`` so output can
be level-filtered or silenced from a single place.
"""

import logging
import sys
from typing import TextIO

_LOGGER_NAME = "screenshot_tool"
_DEFAULT_LEVEL = "INFO"


class AppLogger:
    """Thin wrapper over the stdlib logger — the one logging entry point."""

    _logger: logging.Logger | None = None

    @classmethod
    def configure(cls, level: str = _DEFAULT_LEVEL, stream: TextIO = sys.stdout) -> None:
        """Initialise the underlying logger. Safe to call more than once."""
        logger = logging.getLogger(_LOGGER_NAME)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        handler = next(
            (existing for existing in logger.handlers if isinstance(existing, logging.StreamHandler)),
            None,
        )
        if handler is None:
            # Plain messages keep the CLI output easy to read.
            handler = logging.StreamHandler(stream)
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
        else:
            handler.setStream(stream)
        cls._logger = logger

    @classmethod
    def _get(cls) -> logging.Logger:
        if cls._logger is None:
            cls.configure()
        assert cls._logger is not None
        return cls._logger

    @classmethod
    def debug(cls, message: str) -> None:
        cls._get().debug(message)

    @classmethod
    def info(cls, message: str) -> None:
        cls._get().info(message)

    @classmethod
    def warning(cls, message: str) -> None:
        cls._get().warning(message)

    @classmethod
    def error(cls, message: str) -> None:
        cls._get().error(message)
