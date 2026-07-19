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

- `id` (integer) — passed to the app as `--automation-demo <id>`; selects which app-side demo script runs. **Need not be unique** — several entries may share an `id` to record the same app-side demo at different sizes/settings (see [Variants](#variants-of-one-demo-eg-landscape--portrait)). `--demo all` records every entry; `--demo <id>` records every entry with that id.
- `name` (string) — output subfolder name. Must be distinct per entry (it, not `id`, keys the output folder), so same-`id` variants need different names.
- `fps` (integer, default 10) — capture frame rate; ~10 is the realistic ceiling.
- `formats` (array of `"gif"`/`"mp4"`, default `["gif"]`) — exports to produce.
- `width` / `height` (integers, optional) — window size the app must adopt. Recordings contain physical pixels: on a 150 % scaled display, 640×420 records as 960×630. The tool moves the window into the monitor's work area before recording, so the taskbar never appears in the capture — unless the window (in physical pixels) is larger than the work area itself; then the tool logs a warning and the fix is a smaller `width`/`height`.
- `app_settings` (object, optional) — opaque app-specific settings. The tool writes them to a temp JSON file and passes it as a single `--automation-demo-settings <path>` (deleted after the run). The key dialect is the app's own (FastCalculator: QSettings keys). Anything the app reads **at startup** can go here — e.g. a full color theme is just the set of keys the app loads on launch, so a themed demo is fully reproducible from the config, no runtime commands needed.
- `crop` (object, optional) — pixels removed from each captured frame: `{"top", "right", "bottom", "left"}` (any subset, default 0). The tool already captures the window's real visible bounds (`DwmGetWindowAttribute` extended frame bounds) clamped to the monitor work area, so the invisible resize border and the taskbar never appear; use `crop` only for residual trimming (e.g. a rounded-corner pixel or a themed 1px edge). Applied in physical pixels, identically to every frame. MP4 export pads an odd resulting side by 1px (x264 needs even dimensions).
- `languages` (array of strings, optional) — record the demo once per language code. Each run passes `--automation-demo-language <lang>` to the app (which must set its UI language accordingly; requires connector >= 0.3.0) and writes to the `<lang>/` subfolder. Omitted or empty: one run, no language subfolder. `--demo <id>` always runs all of a demo's languages. Note: this per-demo key is unrelated to the top-level `languages` object of language mode.

### `languages` (object, language mode)

Map of language code → exact display name as it appears in the application's dropdown, e.g. `"de": "Deutsch"`.

- The display name is used to read back which language is currently selected (via UI Automation); it must match the dropdown entry exactly (a case-insensitive fallback exists).
- The code is used as the output subfolder name.
- Languages are iterated in alphabetical order of the codes, which must match the order of entries in the application's dropdown.

## Variants of one demo (e.g. landscape + portrait)

To record the **same** demo at more than one size or with different display
settings, add multiple `demos[]` entries that share the same `id` (the app-side
script) but have distinct `name`s and their own `width`/`height`/`app_settings`.
`--demo all` records them all; each writes to its own `<name>/` folder.

```json
"demos": [
  { "id": 1, "name": "basic-math",          "width": 640, "height": 420,
    "app_settings": { "editor/font_point_size": 32, "window/margin": 20 } },
  { "id": 1, "name": "basic-math-portrait", "width": 460, "height": 640,
    "app_settings": { "editor/font_point_size": 28, "window/margin": 30 } }
]
```

**What lives where** — the boundary that decides config-only vs. app change:

| Vary this per variant | Where |
|---|---|
| size, `fps`, `formats`, font, margins, theme, `languages` | the config (JSON) — no app change |
| the typed content / steps | the app-side demo script, keyed by `id` |

Two entries with the same `id` always play the **same** steps. If a variant needs
**different content** (e.g. more lines to fill a taller portrait window), give it a
**new `id`** and add a matching demo script in the app — content cannot be changed
from the config alone.

(Same-`id` entries share the temp file `demo-<id>-settings.json`, but runs are
sequential, so there is no collision.)

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
