# Live Flutter sessions

Live mode is for quick UI iteration. The screenshot tool starts Flutter once, keeps the app and its connector connection alive, then accepts commands to list screens, reload code, capture a named screen, forward live gestures, read visible text, tap by text or key, type text, and press keys. Detached calls let a caller start, control and stop a session with separate one-shot commands.

## Configure an app

Add a `live` object to the app's screenshot config:

```json
{
  "output_dir": "output",
  "live": {
    "target": "android_emulator",
    "avd": "Pixel_7_API_34",
    "devices": {"phone": "Pixel_9", "tablet": "Pixel_Tablet"},
    "headless": false,
    "port": 8766,
    "flutter": ["fvm", "flutter"],
    "run_args": ["--flavor", "dev"],
    "project_dir": "../..",
    "app_settings": {"demo_account_token": ""},
    "start_timeout": 900
  }
}
```

`target` is `windows` or `android_emulator`. `--target` can override it for one run. For Android, `avd` is the default emulator and `devices` optionally maps short names to AVD names. Pass `--live-device NAME` to select one of those names for a run. The tool matches a requested AVD exactly: if a different emulator is already running, it starts the requested AVD and stops only the emulator it started when the session receives `stop`; a matching emulator that was already running is reused and left open. Without an AVD request, the first running emulator is reused. `headless: true` starts a new emulator without a window. A new emulator starts with `-crash-report-mode disabled`, so a pending crash report from an earlier crash never blocks start-up. Windows Flutter needs an unlocked interactive desktop. Android can run headless.

`emulator` and `adb` are taken from PATH, otherwise from `ANDROID_HOME` or `ANDROID_SDK_ROOT` (`emulator/`, `platform-tools/`); if none has them, `start` fails with an error naming the missing program and where it looked.

`port` is the local TCP port the app connects to. The tool derives `AUTOMATION_HOST`: Windows uses `127.0.0.1:<port>` and the Android emulator uses `10.0.2.2:<port>`. `flutter` is a command prefix (`["flutter"]` by default), `run_args` adds arguments to `flutter run`, and `project_dir` resolves relative to the config file. `app_settings` are sent with each reset. Keep credentials out of committed example configs; use a local config for test account tokens.

`start_timeout` covers Flutter's build, app launch, and connection. Reload, navigation, and screenshot requests have a 60 second timeout.

## Run and send commands

Start the tool from a terminal:

```text
uv run screenshot-tool --config path/to/app.json --live
uv run screenshot-tool --config path/to/app.json --live --target windows
uv run screenshot-tool --config path/to/app.json --live --live-device tablet
```

The process reads one JSON object per line from stdin and writes exactly one JSON response line to stdout. Logs go to stderr. A caller can include an `id`; the matching response echoes it.

```json
{"command":"start","id":1}
{"command":"screens","id":2}
{"command":"shot","screen":"home","out":"output/home.png","theme":"dark","id":3}
{"command":"gesture","kind":"tap","at":[0.5,0.4],"id":4}
{"command":"reload","id":5}
{"command":"read_text","id":6}
{"command":"tap_text","text":"Open details","id":7}
{"command":"tap_key","key":"details_button","id":8}
{"command":"type_text","text":"hello","field":"Name","id":9}
{"command":"press_key","key":"escape","id":10}
{"command":"stop","id":11}
```

`start` launches the app and resets it. `screens` returns the connector's screen registry. `shot` navigates to the requested screen and saves its PNG to `out`. It accepts optional `theme` (`dark` or `light`), `section` (a non-empty key registered for that screen), `full` (`true` for a stitched full-length PNG), `record_id` (an integer id for the record the screen opens, such as a todo id; only for screens whose `screens` entry has `record_id`), `language` (a UI language code such as `de` or `en-US`, passed to the app's prepare callback on `navigate`), and `orientation` (`portrait` or `landscape`, Android only). Orientation is restored after each shot, and natural tablet orientation is handled automatically. For example:

```json
{"command":"shot","screen":"habit_edit","out":"output/habit-edit.png","theme":"dark","section":"additional_information"}
{"command":"shot","screen":"home","out":"output/home-full.png","full":true}
{"command":"shot","screen":"todo_detail","out":"output/todo-11551.png","record_id":11551}
{"command":"shot","screen":"home","out":"output/home-de.png","language":"de"}
{"command":"shot","screen":"browser","out":"output/browser-tablet-landscape.png","orientation":"landscape"}
```

Callers such as the Tickets Watcher can read the keys of `live.devices` to list available devices. Android orientation values are always `portrait` and `landscape`.

`section` and `full` cannot be combined. The language applies to that shot only; a shot without it sends no language and the app opens in its default language. An app that does not apply the requested language also shows its default language. A request without the other optional fields keeps the existing behavior. `screens` includes `sections` only for screens that register them and `record_id` (the id's meaning) only for screens that accept one. An id sent to a screen that takes none returns the app's error as `ok:false`. The request `id` remains a response-correlation id and is never forwarded as a record id. Invalid option values and connector errors return `ok:false` with an `error` message. Reload tries hot reload, hot restart, then relaunch if Flutter exits. Its `outcome` is `reloaded`, `restarted`, `relaunched`, `compile_error`, `unresponsive` or `failed`. An `unresponsive` result means the app did not answer the hot restart; the tool stops the Flutter process and the next `reload` relaunches it. Compile details are returned in `output`. Send `stop` or close stdin to clean up the Flutter process and any emulator this tool started. An emulator that was already running is left open.

Before `start`, commands other than `stop` return `{"ok":false,"error":"not started"}`. Malformed JSON and unknown commands return an error response; the process remains available for the next line.

### Reading and acting on text

`read_text` returns visible entries in app reading order. Each entry has `text`, `kind` (`text`, `button` or `text_field`), `enabled` and `bounds` (`[left, top, right, bottom]` fractions of the app view). Text fields may also include `label`, `hint` and `value`; absent optional fields are omitted. Unknown entry kinds are skipped so a newer connector can add kinds without breaking older tools.

`tap_text` requires a non-empty `text`. It matches exactly by default; set `match` to `contains` for a substring match. `index` optionally selects a zero-based match when more than one item matches. If no item matches, or several match without an index, the connector error names the candidates. `tap_key` requires a non-empty `key` matching a widget's `ValueKey<String>`. `type_text` requires non-empty `text` and types into the focused field; optional `field` first focuses a field by its label or hint. `press_key` requires one of `enter`, `tab`, `shift_tab`, `escape`, `backspace`, `arrow_up`, `arrow_down`, `arrow_left` or `arrow_right`.

Successful replies use the connector's event and are returned to the CLI as `ok:true`: `read_text` includes `entries`; `tap_text` and `type_text` include `text`; `tap_key` and `press_key` include `key`. A connector `error` event becomes `ok:false` with its message, and the live session remains available for another command.

```json
{"command":"read_text","id":12}
{"command":"tap_text","text":"Open details","match":"contains","index":0,"id":13}
{"command":"tap_key","key":"details_button","id":14}
{"command":"type_text","text":"ada@example.com","field":"Email","id":15}
{"command":"press_key","key":"shift_tab","id":16}
```

## Connector protocol

### Gestures and current-state shots

`gesture` sends a `tap`, `drag`, or `pinch` without navigating. Points are `[x,y]` fractions from `0` to `1` across the app view. Add both `screen` and `section` to target a registered section instead; a section requires its screen. `tap` uses `at`; `drag` uses `from` and `to`; `pinch` uses `center` and a positive `scale` (above `1` zooms in, below `1` zooms out). `duration_ms` is optional; the connector uses 100 ms for taps and 300 ms for drags and pinches by default. Invalid values and connector errors return `ok:false` with the error message.

A `shot` without `screen` captures the current app state without sending `navigate`, preserving zoom or pan. It still requires `out`; `theme` and `full` are allowed. `section`, `record_id`, and `language` require a named `screen`.

```json
{"command":"shot","screen":"todo_detail","record_id":11551,"out":"output/detail.png"}
{"command":"gesture","kind":"tap","at":[0.5,0.4]}
{"command":"shot","out":"output/open.png"}
{"command":"gesture","kind":"pinch","center":[0.5,0.5],"scale":2.0}
{"command":"shot","out":"output/zoomed.png"}
{"command":"gesture","kind":"drag","from":[0.5,0.5],"to":[0.7,0.4]}
{"command":"shot","out":"output/moved.png"}
```

The same commands work with `windows` and `android_emulator` targets.

The connector connects to `AUTOMATION_HOST` over TCP and handles one JSON command at a time. The tool uses these live commands:

| Tool sends | Connector replies |
|---|---|
| `{"command":"list_screens"}` | `{"event":"screens","screens":[...]}` |
| `{"command":"set_theme","theme":"dark"}` | `{"event":"theme_set","theme":"dark"}`; an app without a theme hook reports an `error` |
| `{"command":"navigate","screen":"habit_edit","section":"additional_information"}` | `{"event":"navigated","screen":"habit_edit"}` after scrolling; unknown sections report an `error` naming the key and screen |
| `{"command":"navigate","screen":"todo_detail","record_id":11551}` | `{"event":"navigated","screen":"todo_detail"}` after opening that record; screens without record support report an `error` |
| `{"command":"navigate","screen":"home","language":"de"}` | `{"event":"navigated","screen":"home"}` after the app's prepare callback receives the language |
| `{"command":"gesture","kind":"tap","at":[0.5,0.4]}` | `{"event":"gestured","kind":"tap"}` |
| `{"command":"gesture","kind":"drag","from":[0.2,0.5],"to":[0.8,0.5],"duration_ms":400}` | `{"event":"gestured","kind":"drag"}` |
| `{"command":"gesture","kind":"pinch","center":[0.5,0.5],"scale":2.0,"screen":"image_viewer","section":"image"}` | `{"event":"gestured","kind":"pinch"}` |
| `{"command":"read_text"}` | `{"event":"visible_text","entries":[...]}` |
| `{"command":"tap_text","text":"Sign in","match":"exact","index":0}` | `{"event":"text_tapped","text":"Sign in"}` |
| `{"command":"tap_key","key":"login_button"}` | `{"event":"key_tapped","key":"login_button"}` |
| `{"command":"type_text","text":"me@example.com","field":"Email"}` | `{"event":"text_typed","text":"me@example.com"}` |
| `{"command":"press_key","key":"shift_tab"}` | `{"event":"key_pressed","key":"shift_tab"}` |
| `{"command":"screenshot","name":"home","pixel_ratio":1.0,"full":true}` | Existing `screenshot` event with one base64 PNG of the full scrollable content |
| `{"command":"screenshot","name":"current","pixel_ratio":1.0}` | Existing `screenshot` event; sent without `navigate` for a current-state shot |
| `{"command":"reset","settings":{}}` | `{"event":"reset_done"}` |

The `section`, `record_id` and `language` fields on `navigate` and the `full` field on `screenshot` are optional. `list_screens` screen items may include a `sections` array of registered section keys and a `record_id` string describing the accepted id (for example, `todo id`). See the connector's `docs/LIVE_SCREENS.md` for registering record screens. Apps must expose a theme hook to support `set_theme`; when no hook is available they should send an `error` event such as `theme switching is not supported by this app`.

Any operation can reply with the existing `error` event and a message. After a hot restart the app reconnects; the tool accepts the new connection and resets it before continuing. The shared connector guide covers screen registration, debug-only use, test login setup, and screen preparation.

## Troubleshooting

- **Flutter command not found:** set `flutter` to the installed command prefix, such as `["fvm", "flutter"]`.
- **Android app cannot connect:** use the derived emulator address `10.0.2.2`, and check that the configured port is available.
- **No app connection before timeout:** confirm the connector is enabled in the debug build and that `project_dir` points to the Flutter app.
- **Windows screenshots fail on a locked or minimized desktop:** unlock the desktop, restore the app window, then request the screenshot again.
- **Hot reload reports a compile error:** fix the reported Dart error and send `reload` again. If reload cannot update the app, the tool attempts a hot restart or relaunch.
- **Reload reports `unresponsive`:** the app froze (for example, an Android ANR); this is not a code error. Check the emulator log, then send `reload` to relaunch or send `stop` and `start` again.
- **Timed out waiting for `theme_set`:** the connector does not support theme switching yet. Update it to handle `set_theme` and reply with `theme_set`; older connectors ignore this command and the tool waits up to 60 seconds.

Live mode is separate from `--demo`: it does not record video or run scripted demo steps. Existing demo and network modes continue to use their existing commands.

### Detached session

Use separate foreground calls when the caller cannot keep the live JSON-lines stream open. The start command uses the live config and returns after Flutter connects and the app has been reset. It prints a JSON success response such as `{"ok":true,"device":"windows"}`:

```text
uv run screenshot-tool --config path/to/app.json --live-start path/to/session
uv run screenshot-tool --live-send path/to/session '{"command":"read_text"}'
uv run screenshot-tool --live-send path/to/session '{"command":"tap_text","text":"Open details"}'
uv run screenshot-tool --live-send path/to/session '{"command":"shot","out":"C:/temp/current.png"}'
uv run screenshot-tool --live-stop path/to/session
```

Each `--live-send` call accepts any live JSON command, including `shot` with `out`, and prints one JSON response. Use an absolute screenshot output path: a relative `out` is resolved from the background process's working directory, which is the directory from which `--live-start` was called.

Exit codes are `0` for success (including stopping an already stopped session), `1` for a live command or startup failure, `2` for invalid command-line usage, and `3` when `--live-send` cannot find or reach a session. A second start using a folder that already has a live session is refused.

The session folder contains `live-session.json` with the loopback port, random per-session token and process id, plus `live.log` with the detached server output. The control server listens on `127.0.0.1` only and requires its session token. `--live-stop` is idempotent: it ends the Flutter session and removes the session file; calling it when no session exists succeeds and reports `stopped:false`.

### Environment

The Flutter process inherits the environment of the process that starts live mode, including when started through `--live-start`. A driver script can set `APPDATA` or an app-specific environment variable to a temporary profile folder before invoking `--live-start`; Flutter and the app receive that value.
