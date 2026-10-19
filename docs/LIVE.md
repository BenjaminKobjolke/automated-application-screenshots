# Live Flutter sessions

Live mode is for quick UI iteration. The screenshot tool starts Flutter once, keeps the app and its connector connection alive, then accepts commands to list screens, reload code, and capture a named screen.

## Configure an app

Add a `live` object to the app's screenshot config:

```json
{
  "output_dir": "output",
  "live": {
    "target": "android_emulator",
    "avd": "Pixel_7_API_34",
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

`target` is `windows` or `android_emulator`. `--target` can override it for one run. For Android, the tool reuses an already running emulator or starts the configured `avd`; `headless: true` starts a new emulator without a window. Windows Flutter needs an unlocked interactive desktop. Android can run headless.

`emulator` and `adb` are taken from PATH, otherwise from `ANDROID_HOME` or `ANDROID_SDK_ROOT` (`emulator/`, `platform-tools/`); if none has them, `start` fails with an error naming the missing program and where it looked.

`port` is the local TCP port the app connects to. The tool derives `AUTOMATION_HOST`: Windows uses `127.0.0.1:<port>` and the Android emulator uses `10.0.2.2:<port>`. `flutter` is a command prefix (`["flutter"]` by default), `run_args` adds arguments to `flutter run`, and `project_dir` resolves relative to the config file. `app_settings` are sent with each reset. Keep credentials out of committed example configs; use a local config for test account tokens.

`start_timeout` covers Flutter's build, app launch, and connection. Reload, navigation, and screenshot requests have a 60 second timeout.

## Run and send commands

Start the tool from a terminal:

```text
uv run screenshot-tool --config path/to/app.json --live
uv run screenshot-tool --config path/to/app.json --live --target windows
```

The process reads one JSON object per line from stdin and writes exactly one JSON response line to stdout. Logs go to stderr. A caller can include an `id`; the matching response echoes it.

```json
{"command":"start","id":1}
{"command":"screens","id":2}
{"command":"shot","screen":"home","out":"output/home.png","id":3}
{"command":"reload","id":4}
{"command":"stop","id":5}
```

`start` launches the app and resets it. `screens` returns the connector's screen registry. `shot` navigates to the requested screen and saves its PNG to `out`. `reload` tries hot reload, hot restart, then relaunch if Flutter exits. Its `outcome` is `reloaded`, `restarted`, `relaunched`, or `compile_error`; compile details are returned in `output`. Send `stop` or close stdin to clean up the Flutter process and any emulator this tool started. An emulator that was already running is left open.

Before `start`, commands other than `stop` return `{"ok":false,"error":"not started"}`. Malformed JSON and unknown commands return an error response; the process remains available for the next line.

## Connector protocol

The connector connects to `AUTOMATION_HOST` over TCP and handles one JSON command at a time. The tool uses these live commands:

| Tool sends | Connector replies |
|---|---|
| `{"command":"list_screens"}` | `{"event":"screens","screens":[...]}` |
| `{"command":"navigate","screen":"home"}` | `{"event":"navigated","screen":"home"}` |
| `{"command":"screenshot","name":"home","pixel_ratio":1.0}` | Existing `screenshot` event with a base64 PNG |
| `{"command":"reset","settings":{}}` | `{"event":"reset_done"}` |

Any operation can reply with the existing `error` event and a message. After a hot restart the app reconnects; the tool accepts the new connection and resets it before continuing. The shared connector guide covers screen registration, debug-only use, test login setup, and screen preparation.

## Troubleshooting

- **Flutter command not found:** set `flutter` to the installed command prefix, such as `["fvm", "flutter"]`.
- **Android app cannot connect:** use the derived emulator address `10.0.2.2`, and check that the configured port is available.
- **No app connection before timeout:** confirm the connector is enabled in the debug build and that `project_dir` points to the Flutter app.
- **Windows screenshots fail on a locked or minimized desktop:** unlock the desktop, restore the app window, then request the screenshot again.
- **Hot reload reports a compile error:** fix the reported Dart error and send `reload` again. If reload cannot update the app, the tool attempts a hot restart or relaunch.

Live mode is separate from `--demo`: it does not record video or run scripted demo steps. Existing demo and network modes continue to use their existing commands.
