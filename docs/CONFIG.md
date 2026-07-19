# Config File

Each target application is described by one JSON file. It can live in this repo's `config/` (default: `config/keyboard-layout-watcher.json`) or in the target app's own repo next to a runner script (FastCalculator keeps `calculator/tools/create_media/fastcalculator.json` beside `create_demos.bat`). Select it with `--config` (see [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)).

A config can define either or both modes:

- **Language screenshots** — requires the `languages` section (plus the dropdown keys below).
- **Demo recordings** — requires the `demos` + `launch` sections (see [AUTOMATION_INTERFACE.md](AUTOMATION_INTERFACE.md) for the app-side contract).

Always required: `process_name`, `title_substring`, `output_dir`. A missing file, invalid JSON, or missing required key aborts with a clear error message.

## Example: language screenshots

```json
{
  "process_name": "KeyboardLayoutWatcher.exe",
  "title_substring": "Keyboard Layout Watcher",
  "dropdown_relative_pos": [175, 248],
  "output_dir": "screenshots",
  "screenshot_filename": "screenshot.png",
  "delay_after_change": 0.3,
  "languages": {
    "de": "Deutsch",
    "en": "English"
  }
}
```

## Example: demo recordings

```json
{
  "process_name": "python.exe",
  "title_substring": "FastCalculator",
  "output_dir": "output",
  "texts_dir": "texts",
  "launch": {
    "command": ["uv", "run", "python", "main.py",
                "--automation-demo", "{demo_id}",
                "--automation-demo-port", "{port}",
                "--automation-demo-width", "{width}",
                "--automation-demo-height", "{height}"],
    "cwd": "../.."
  },
  "demos": [
    {
      "id": 1,
      "name": "basic-math",
      "fps": 10,
      "formats": ["gif", "mp4"],
      "width": 640,
      "height": 420,
      "app_settings": { "editor/font_point_size": 18 },
      "languages": ["en", "de"]
    }
  ]
}
```

## Values

### `process_name` (string)

Executable name of the target application, e.g. `"KeyboardLayoutWatcher.exe"`. In language mode the tool finds the application window by this process name. (In demo mode the window comes from the `hwnd` the app reports over the socket — no searching.)

### `title_substring` (string)

Fallback window search for language mode: if no window is found by `process_name`, the tool searches for a visible window whose title contains this substring.

### `dropdown_relative_pos` (array of two integers, language mode)

`[x, y]` pixel position of the language dropdown, relative to the top-left corner of the application window. The tool clicks this position to focus the dropdown before cycling through languages. Adjust when the target app's layout changes or when targeting a different application.

### `output_dir` (string)

Output root. Language mode: `<output_dir>/<language-code>/<screenshot_filename>` (overridable with `--output`). Demo mode: `<output_dir>/demos/<demo-name>/` receives `demo.gif`, `demo.mp4`, and the stills; a demo with `languages` writes to `<output_dir>/demos/<demo-name>/<lang>/` instead, once per language. Relative paths resolve against the current working directory.

### `screenshot_filename` (string, language mode)

Filename of the screenshot saved inside each language subfolder, e.g. `"screenshot.png"`.

### `delay_after_change` (number, language mode)

Seconds to wait after each language switch before capturing, so the UI can finish redrawing. Increase for slow applications. Can be overridden per run with `--delay`.

### `launch` (object, demo mode)

How to start the target application.

- `command` (array of strings) — the argv to run. Placeholders `{demo_id}`, `{port}`, `{width}`, `{height}` are substituted per argument. `{width}`/`{height}` require the demo to define `width`/`height`.
- `cwd` (string, optional) — working directory for the command; relative paths resolve against the tool's current working directory.

### `texts_dir` (string, demo mode, optional)

Folder with one demo-text JSON file per language, named `<lang>.json` (like an app's `locales/` folder), resolved against the current working directory. On a language run the tool passes `<texts_dir>/<lang>.json` to the app as `--automation-demo-texts <path>`; the app fills `{placeholder}`s in its demo scripts from it (connector: `localize_script`, requires connector >= 0.4.0). A missing file fails that run with a clear error. Ignored for runs without a language.

Example `texts/de.json`:

```json
{ "price": "preis" }
```

### `demos` (array, demo mode)

One entry per recordable demo:

- `id` (integer) — passed to the app as `--automation-demo <id>`.
- `name` (string) — output subfolder name.
- `fps` (integer, default 10) — capture frame rate; ~10 is the realistic ceiling.
- `formats` (array of `"gif"`/`"mp4"`, default `["gif"]`) — exports to produce.
- `width` / `height` (integers, optional) — window size the app must adopt. Recordings contain physical pixels: on a 150 % scaled display, 640×420 records as 960×630.
- `app_settings` (object, optional) — opaque app-specific settings. The tool writes them to a temp JSON file and passes it as a single `--automation-demo-settings <path>` (deleted after the run). The key dialect is the app's own (FastCalculator: QSettings keys).
- `languages` (array of strings, optional) — record the demo once per language code. Each run passes `--automation-demo-language <lang>` to the app (which must set its UI language accordingly; requires connector >= 0.3.0) and writes to the `<lang>/` subfolder. Omitted or empty: one run, no language subfolder. `--demo <id>` always runs all of a demo's languages. Note: this per-demo key is unrelated to the top-level `languages` object of language mode.

### `languages` (object, language mode)

Map of language code → exact display name as it appears in the application's dropdown, e.g. `"de": "Deutsch"`.

- The display name is used to read back which language is currently selected (via UI Automation); it must match the dropdown entry exactly (a case-insensitive fallback exists).
- The code is used as the output subfolder name.
- Languages are iterated in alphabetical order of the codes, which must match the order of entries in the application's dropdown.

## Adding a new application (language screenshots)

1. Copy `config/keyboard-layout-watcher.json` to `config/your-app.json`.
2. Set `process_name` and `title_substring` for the target app.
3. Determine the dropdown position relative to the window's top-left corner and set `dropdown_relative_pos`.
4. Fill `languages` with the codes and exact dropdown display names, in the dropdown's (alphabetical) order.
5. Run: `uv run screenshot-tool --config config/your-app.json`

## Adding a new application (demo recordings)

1. Make the app implement the automation contract — Python apps use the [automated-screenshot-connector](https://github.com/BenjaminKobjolke/automated-application-screenshots-python-connector) library; the full contract is in [AUTOMATION_INTERFACE.md](AUTOMATION_INTERFACE.md).
2. Write a config with `launch` + `demos` (see the FastCalculator example above), ideally in the app's repo next to a runner `.bat`.
3. Run: `uv run screenshot-tool --config path/to/your-app.json --demo all`
