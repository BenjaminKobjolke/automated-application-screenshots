# Automation Interface — make your app demo-recordable

Any desktop app can be recorded by this tool as an animated demo (GIF/MP4 plus
PNG stills). The app implements a small contract: four CLI arguments and three
JSON events over a localhost socket. FastCalculator
(`D:\GIT\BenjaminKobjolke\calculator`) is the working reference implementation.

## 1. CLI arguments your app must accept

Namespaced so they never clash with your app's own arguments:

```
--automation-demo <id>            play the demo with this id, then exit
--automation-demo-port <port>     connect to the tool's event socket on 127.0.0.1
--automation-demo-width <px>      resize the window to this width  (optional)
--automation-demo-height <px>     resize the window to this height (optional)
--automation-demo-settings <path> JSON file with app-specific settings (optional)
```

Rules:

- `--automation-demo` alone (no port) must work too: the demo plays visually
  without reporting events. This is how you develop demos manually.
- The other arguments are only valid together with `--automation-demo`.
- `--automation-demo-settings` points to a temp file the tool writes from the
  config's `app_settings`: one JSON object, e.g.
  `{"editor/font_point_size": "18"}`. One file instead of one argument per
  setting keeps the command line short at any settings count; the tool deletes
  it after the run. Keys are **your app's own dialect** — FastCalculator
  interprets them as QSettings keys seeded into the wiped demo settings
  namespace before the window is built. Ignore or warn on keys you don't know.
- Note: the recording contains **physical** pixels. On a 150 % scaled display a
  640×420 window records as 960×630.

## 2. Expected app behavior in demo mode

1. **Deterministic state** — start clean (default theme/geometry/content), and
   never touch the real user's settings. FastCalculator redirects `QSettings`
   to a wiped temp-dir INI file for this.
2. **Resize** to the given width/height before showing the window.
3. **Connect** to `127.0.0.1:<port>` (plain TCP). If the connection fails,
   keep playing the demo visually — never crash because the tool is absent.
4. **Play the demo**: scripted UI actions with human-like pacing (type
   character by character, pause so viewers can read results).
5. **Send events** (section 3) — `demo_started` (with your window's native
   handle) when playing begins, `screenshot` whenever the UI is set up for a
   still, `demo_ended` when done.
6. **Quit yourself** about 1 second after `demo_ended` (the hold keeps the
   final state in the recording). The tool kills the process if it lingers
   longer than 10 s.

## 3. Socket protocol

One JSON object per newline-terminated UTF-8 line, client (app) → server
(tool) only. No replies.

```json
{"event": "demo_started", "demo": 1, "hwnd": 264854}
{"event": "screenshot", "name": "basic-results"}
{"event": "demo_ended", "demo": 1}
```

- `demo_started` **must** carry `hwnd`: your window's native Win32 handle.
  This is how the tool knows exactly which window to record — no title or
  process guessing. Getting it: Qt `int(self.winId())` (after `show()`),
  tkinter `root.winfo_id()`, Win32 apps have it directly. Missing/invalid
  `hwnd` aborts the recording.
- `screenshot.name` becomes the still's filename (`<name>.png`) — keep it
  filesystem-friendly and unique within the demo.
- Recording runs from `demo_started` to `demo_ended` (plus a short tail).
- Tool-side timeouts: 30 s to connect, 60 s max between events, 300 s per demo.
  On violation the tool stops, still exports the partial recording, and exits 1.

## 4. Python apps: use the connector library

Don't copy code — add the ready-made connector as a path dependency
(`D:\GIT\BenjaminKobjolke\automated-application-screenshots-python-connector`):

```toml
dependencies = ["automated-screenshot-connector"]

[tool.uv.sources]
automated-screenshot-connector = { path = "../automated-application-screenshots-python-connector" }
```

It ships the step model (`TypeText`, `Pause`, `Command`, `Screenshot`,
`DemoScript`), the socket `DemoClient`, `parse_demo_args` (consumes only the
`--automation-demo*` options, returns your app's own args untouched), and for
Qt apps `automated_screenshot_connector.qt` with the typing `DemoPlayer` and
`prepare_demo_settings` (wiped temp QSettings namespace + `--automation-demo-set`
seeding). Core is stdlib-only; the qt module needs your app's PySide6. Your app
keeps only its demo content (`DEMOS: dict[int, DemoScript]`). See the library
README for the wiring snippet; FastCalculator's `main.py` is the working example.

## 5. Reference client for non-Python apps (stdlib only, copy-paste)

```python
import json
import socket


class DemoClient:
    """Reports demo progress to the recording tool; no-op without a port."""

    def __init__(self, port: int | None) -> None:
        self._sock = None
        if port is not None:
            try:
                self._sock = socket.create_connection(("127.0.0.1", port), timeout=5)
            except OSError:
                pass  # tool absent: demo still plays visually

    def _send(self, payload: dict) -> None:
        if self._sock is None:
            return
        try:
            self._sock.sendall(json.dumps(payload).encode("utf-8") + b"\n")
        except OSError:
            self._sock = None

    def send_started(self, demo_id: int, hwnd: int) -> None:
        self._send({"event": "demo_started", "demo": demo_id, "hwnd": hwnd})

    def send_screenshot(self, name: str) -> None:
        self._send({"event": "screenshot", "name": name})

    def send_ended(self, demo_id: int) -> None:
        self._send({"event": "demo_ended", "demo": demo_id})
```

## 6. Tool-side config

Add `launch` + `demos` to your app's config JSON (may coexist with the
language-screenshot `languages` section):

```json
{
  "process_name": "python.exe",
  "title_substring": "FastCalculator",
  "output_dir": "screenshots/fastcalculator",
  "launch": {
    "command": ["uv", "run", "python", "main.py",
                "--automation-demo", "{demo_id}",
                "--automation-demo-port", "{port}",
                "--automation-demo-width", "{width}",
                "--automation-demo-height", "{height}"],
    "cwd": "D:/GIT/BenjaminKobjolke/calculator"
  },
  "demos": [
    {"id": 1, "name": "basic-math", "fps": 10, "formats": ["gif", "mp4"],
     "width": 640, "height": 420,
     "app_settings": {"editor/font_point_size": 18}}
  ]
}
```

- `{demo_id}`, `{port}`, `{width}`, `{height}` are substituted per argument.
- `fps` defaults to 10 (the realistic capture ceiling), `formats` to `["gif"]`.
- `width`/`height` are required only if the command uses their placeholders.
- `app_settings` (optional object) is written to a temp JSON file and passed
  as a single `--automation-demo-settings <path>` — keys mean whatever your
  app decides (section 1).

Run:

```
uv run screenshot-tool --config config/yourapp.json --demo 1
uv run screenshot-tool --config config/yourapp.json --demo all
```

Output lands in `<output_dir>/demos/<demo_name>/`: `demo.gif`, `demo.mp4`,
and one `<name>.png` per screenshot event.

## 7. Compatibility checklist

- [ ] `--automation-demo <id>` plays the demo and exits on its own
- [ ] Works without `--automation-demo-port` (manual run, no crash)
- [ ] Window resizes to `--automation-demo-width/height`
- [ ] `--automation-demo-settings` JSON applied before the window shows
- [ ] Demo starts from clean, deterministic state; user settings untouched
- [ ] Events sent: `demo_started` (with `hwnd`), `screenshot` per still, `demo_ended`
- [ ] App quits ~1 s after `demo_ended`
- [ ] Keep hands off mouse/keyboard while recording (window must stay
      frontmost and unobstructed)
