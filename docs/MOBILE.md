# Recording mobile apps (Flutter, Android)

Mobile apps have no desktop window, so the tool cannot launch or capture them.
In **network mode** the roles flip: the tool runs on the PC and *listens*; the
app runs on a phone or emulator, *connects* over the LAN, plays the demo,
records the video on the device and captures stills in-app. The tool receives
both and writes the same output layout as desktop demos, so `compose` and
[PUBLISHING.md](PUBLISHING.md) work unchanged.

Flutter apps get all of this from the
[Flutter connector](https://github.com/BenjaminKobjolke/automated-application-screenshots-flutter-connector)
(`D:\GIT\BenjaminKobjolke\automated-application-screenshots-flutter-connector`).
`block-screen-app` is the working reference. Wire protocol details:
[AUTOMATION_INTERFACE.md](AUTOMATION_INTERFACE.md#7-network-mode-mobile--flutter).

## 1. One-time app setup

1. Add the connector as a path dependency:

   ```yaml
   dependencies:
     automated_screenshot_connector:
       path: ../automated-application-screenshots-flutter-connector
   ```

   The connector pulls in `flutter_screen_recording`, which pins
   `flutter_foreground_task ^9`. If the app already uses `^11`, add
   `dependency_overrides: { flutter_foreground_task: ^11.0.1 }` (same Dart
   API). Android minSdk 23; the plugin's manifest brings its own foreground
   service and permissions.

2. Wrap the `MaterialApp` in `AutomationDemoHost` and give it a registry, an
   `onPrepare` that resets the app to a clean state (apply the config's
   `app_settings`, pop to home, dismiss dialogs) and an `onRestore` that undoes
   it once the tool disconnects:

   ```dart
   AutomationDemoHost(
     registry: buildDemoRegistry(navigatorKey),
     onPrepare: demo.prepare,   // apply app_settings, pop to home
     onRestore: demo.restore,   // give the device its own settings back
     child: MaterialApp(navigatorKey: navigatorKey, home: const HomeScreen()),
   )
   ```

   `app_settings` are written to the app's real stores, so without `onRestore`
   the device keeps the demo account and demo backend URL after the run.

   Without `--dart-define=AUTOMATION_HOST=...` the host renders the child and
   does nothing, so release builds are unaffected.

3. Put `key: const ValueKey('settings_button')` on every widget a demo taps.

4. Write the demos (`DemoScript`s in a `DemoRegistry`) — see the connector's
   `docs/WRITING_DEMOS.md`. Or skip the registry and script the demo in the
   tool config with `steps` (below).

## 2. Tool config

Replace `launch` with `network`; `process_name` / `title_substring` are not
needed. `formats` decides whether the phone records: `["gif", "mp4"]` records
(the GIF is derived on the PC from the mp4), `["png"]` is stills only — no
recording, no consent prompt.

```json
{
  "output_dir": "../../output",
  "network": { "port": 8765, "accept_timeout": 300 },
  "demos": [
    { "id": 1, "name": "overview", "formats": ["gif", "mp4"], "fps": 10,
      "app_settings": { "api_base_url": "https://demo.example", "code": "DEMO" } },
    { "id": 2, "name": "settings", "formats": ["png"],
      "steps": [ { "type": "tap", "key": "settings_button" },
                 { "type": "pause", "seconds": 1 },
                 { "type": "screenshot", "name": "settings" } ] }
  ]
}
```

- `app_settings` reach the app's `onPrepare` verbatim (keys are the app's own,
  e.g. its SharedPreferences keys).
- `pixel_ratio` (default `1.0`) scales in-app stills; `2.0` doubles them.
- `steps` (optional) sends the script instead of using a registered demo:
  `tap`, `type_text`, `pause`, `screenshot`, `custom`.
- `languages` + `texts_dir` work as on desktop: one run per language, the
  app gets `language` and `texts` in the start command.
- `fps` only drives the derived GIF; the device encoder decides the video.
- `width`/`height`/`crop` are unused — the recording is the device's native
  resolution. Use `compose` size fitting if files come out too big.

Full key reference: [CONFIG.md](CONFIG.md); loadable example:
`config/example-network.json`.

## 3. Recording a run

Both machines on the same LAN (an emulator reaches the host PC at `10.0.2.2`),
and the PC's firewall must allow inbound TCP on the configured port — a network
Windows classifies as *Public* drops the device's connection silently, and
neither side logs it.

Either side may be started first: the tool waits `network.accept_timeout`
seconds for the app (default 30 s), and the app (from connector 0.1.0 on)
retries for 3 minutes, which comfortably covers a `fvm flutter run` build and
install.

1. **PC** — start the tool; it listens and waits `network.accept_timeout`
   seconds (default 30 s) for the app:

   ```
   uv run screenshot-tool --config path/to/app-demos.json --demo all
   ```

   `block-screen-app` wraps this as `tools\create_media\record_demos.bat`.

2. **Device** — run the app in demo mode with the PC's address:

   ```
   fvm flutter run --dart-define=AUTOMATION_HOST=192.168.1.10:8765
   ```

   `block-screen-app`: `tools\run_demo_device.bat` (reads `AUTOMATION_HOST`
   from `tools\config.bat`).

3. **Consent tap** — before every video demo Android shows the system
   screen-recording dialog; tap *Start now* on the device. Recording starts
   after the dialog, so it is not in the video. Stills-only demos never ask.

4. Keep hands off the device while it plays. Output lands in
   `<output_dir>/demos/<name>[/<lang>]/`: `demo.mp4`, `demo.gif`, one
   `<still>.png` per screenshot step.

One connection serves the whole `--demo all` run; the app stays open between
demos. `network.accept_timeout` sets how long the tool waits to accept the
app's connection (default 30 s); raise it when the run first boots an emulator
and builds the app, which takes minutes. That window is the *tool's* only — the
app keeps retrying on its side, so a tool started second is still picked up. The
other timeouts are the desktop ones: 60 s between events, 300 s per demo. A
failed step (missing key, no focused field, unknown custom
action) arrives as an `error` event and fails that run with the reason.

## 4. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `App never connected to the demo port.` | Wrong `AUTOMATION_HOST`, or the PC's firewall is dropping the port. On Windows: `New-NetFirewallRule -DisplayName "screenshot-tool demo port" -Direction Inbound -Protocol TCP -LocalPort <port> -Action Allow -Profile Any` in an elevated shell; check the listener with `netstat -ano \| findstr <port>`. |
| App connects, then `No demo event for 60s` on a video demo | The consent dialog is waiting on the device. |
| `App reported: no widget with ValueKey("...")` | The key is missing or on the wrong widget (put it on the `IconButton`, not the `Icon`), or a dialog covers the screen — reset in `onPrepare`. |
| `App reported: type_text: no text field has focus` | Tap the field first (`tap` step on its key) or give it `autofocus`. |
| `screen recording was not started` | Consent declined, or the plugin's foreground service could not start (check `POST_NOTIFICATIONS`, minSdk 23). |
| The app's own foreground service stopped after a video demo | The recorder plugin calls `FlutterForegroundTask.stopService()` on stop. Expected; demos should not depend on it. |
| Video is huge | Native resolution (e.g. 1080×2400). Add a `compose` step with `width` / `max_size`. |

## Out of scope (for now)

Windows-desktop Flutter (use launch mode once the app exposes an HWND), iOS
(the plugin uses ReplayKit; untested), audio, single-consent multi-demo
recording (needs custom native code).
