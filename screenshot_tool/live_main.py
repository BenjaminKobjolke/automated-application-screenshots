"""Argument handling and dispatch for live screenshot commands."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from typing import TextIO

from .app_logger import AppLogger
from .live_cli import LiveCLI
from .live_config import LiveSettings, LiveTarget
from .live_session import LiveSession


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add interactive and one-shot live commands to the screenshot parser."""
    parser.add_argument(
        "--live",
        action="store_true",
        help="Keep a Flutter app running and accept JSON-lines live commands",
    )
    parser.add_argument("--live-start", metavar="FOLDER", help="Start a detached live session")
    parser.add_argument(
        "--live-send",
        metavar=("FOLDER", "JSON"),
        nargs=2,
        help="Send one JSON live command to a detached session",
    )
    parser.add_argument("--live-stop", metavar="FOLDER", help="Stop a detached live session")
    parser.add_argument(
        "--target",
        choices=[target.value for target in LiveTarget],
        help="Override the live config target",
    )
    parser.add_argument("--live-device", metavar="NAME", help="Use the named live.devices AVD")
    parser.add_argument(
        "--skip-idle-check",
        action="store_true",
        help="Start without checking whether someone is using the PC",
    )


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Reject incompatible screenshot and live command combinations."""
    one_shot_modes = [
        args.live_start is not None,
        args.live_send is not None,
        args.live_stop is not None,
    ]
    if sum(one_shot_modes) > 1:
        parser.error("--live-start, --live-send and --live-stop cannot be combined")
    if args.live and any(one_shot_modes):
        parser.error("--live cannot be combined with a detached live command")
    if args.live_start is not None and not args.config:
        parser.error("--live-start requires --config")
    if args.target and not (args.live or args.live_start):
        parser.error("--target requires --live or --live-start")
    if args.live_device and not (args.live or args.live_start):
        parser.error("--live-device requires --live or --live-start")
    if args.live and (args.demo or args.compose or args.list or args.start_from):
        parser.error("--live cannot be combined with --demo, --compose, --list or --start-from")
    if args.live_start is not None and (args.demo or args.compose or args.list or args.start_from):
        parser.error(
            "--live-start cannot be combined with --demo, --compose, --list or --start-from"
        )


def is_one_shot(args: argparse.Namespace) -> bool:
    """Return whether the selected command is a detached-session call."""
    return args.live_send is not None or args.live_stop is not None


def resolve_settings(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    configured: LiveSettings | None,
) -> LiveSettings | None:
    """Resolve and validate settings for interactive or detached live startup."""
    if not args.live and args.live_start is None:
        return None
    if configured is None:
        parser.error("live mode requires a config with a live section")
    settings = configured
    if args.target:
        settings = replace(settings, target=LiveTarget(args.target))
    if args.live_device:
        if settings.target is not LiveTarget.ANDROID_EMULATOR:
            parser.error("--live-device requires the android_emulator target")
        if args.live_device not in settings.devices:
            configured_devices = ", ".join(sorted(settings.devices)) or "none"
            parser.error(
                f"--live-device {args.live_device!r} is not in live.devices "
                f"(configured: {configured_devices})"
            )
        settings = replace(settings, avd=settings.devices[args.live_device])
    return settings


def dispatch_one_shot(args: argparse.Namespace) -> int:
    """Run a detached-session call before the ordinary config and idle checks."""
    from . import live_detached

    if args.live_send is not None:
        folder, request = args.live_send
        return live_detached.send(folder, request)
    if args.live_stop is not None:
        return live_detached.stop(args.live_stop)
    raise ValueError("no detached live command was selected")


def run_live(
    args: argparse.Namespace,
    settings: LiveSettings,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Start live mode or serve a detached session."""
    if args.live_start is not None:
        from . import live_detached

        return live_detached.start(args.live_start, settings)
    AppLogger.info("Starting live screenshot session")
    return LiveCLI(
        LiveSession(settings),
        sys.stdin if stdin is None else stdin,
        sys.stdout if stdout is None else stdout,
    ).run()
