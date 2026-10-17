"""Routing the centralized logger to a new command output stream."""

import io
import logging

from screenshot_tool.app_logger import AppLogger


def test_configure_replaces_existing_handler_stream():
    logger = logging.getLogger("screenshot_tool")
    original_handlers = list(logger.handlers)
    original_streams = [handler.stream for handler in original_handlers]
    first_stream = io.StringIO()
    second_stream = io.StringIO()
    try:
        AppLogger.configure(stream=first_stream)
        AppLogger.info("first")
        AppLogger.configure(stream=second_stream)
        AppLogger.info("second")

        assert first_stream.getvalue() == "first\n"
        assert second_stream.getvalue() == "second\n"
    finally:
        for handler in list(logger.handlers):
            if handler not in original_handlers:
                logger.removeHandler(handler)
                handler.close()
        for handler, stream in zip(original_handlers, original_streams):
            handler.setStream(stream)
