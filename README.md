# Automated Application Screenshots

Automated screenshot capture tool for Windows applications. Two modes:

- **Language screenshots** — cycles through an app's language dropdown and saves one screenshot per language to `screenshots/<language-code>/screenshot.png`.
- **Demo recordings** — launches an app that implements the [automation interface](docs/AUTOMATION_INTERFACE.md), records a scripted demo of it, and exports animated **GIF/MP4** plus PNG stills.
- **Composition** — joins the recordings into the artifacts a README actually shows: a captioned feature tour (rendered with Remotion), slideshow GIFs, inline feature GIFs — each optionally held to a size budget.

The target application is defined by a JSON config file — either in `config/` here, or kept in the app's own repo (FastCalculator keeps its demo config in `calculator/tools/create_media/` with a `create_demos.bat` next to it). Ships with a config for **KeyboardLayoutWatcher** (41 languages).

## What you can build

| I want to... | Start here |
|---|---|
| find out what this can do at all | [docs/DEMO_COOKBOOK.md](docs/DEMO_COOKBOOK.md) — every capability as a question |
| write the config | [docs/CONFIG.md](docs/CONFIG.md) — every key, plus `config/example-full.json` |
| make my app recordable | [docs/AUTOMATION_INTERFACE.md](docs/AUTOMATION_INTERFACE.md), or the [connector library](../automated-application-screenshots-python-connector) for Python apps |
| write the demo scripts | the connector's `docs/WRITING_DEMOS.md` |
| get a clean, repeatable recording | [docs/RECORDING_ENVIRONMENT.md](docs/RECORDING_ENVIRONMENT.md) |
| put the result in a README | [docs/PUBLISHING.md](docs/PUBLISHING.md) |
| see what one config does | `screenshot-tool --config app.json --list` |

The split, if you are wondering which repo to read: **this tool does everything
outside the app** (launch, record, compose, publish); the **connector does
everything inside it** (steps, players, demo registry).

## Requirements

- Windows
- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) (`winget install astral-sh.uv`)
- The target application must be running and its window visible
- **Node.js 18+ only for the `tour` compose step** (Remotion). Recording and the
  GIF steps are pure Python; run `npm install` in `composer/` before your first
  tour.

## Installation

```
install.bat
```

Runs `uv sync` to install dependencies.

## Usage

1. Start the target application (e.g. KeyboardLayoutWatcher).
2. Run the tool:

   ```
   start.bat
   ```

   or

   ```
   uv run screenshot-tool
   ```

3. Press **F1** to begin. The tool brings the window to the foreground, cycles through every language in the dropdown, and captures a screenshot for each.
4. A summary of captured vs. failed languages is printed at the end.

### CLI options

| Option | Description | Default |
|---|---|---|
| `--config`, `-c` | App config JSON file | `config/keyboard-layout-watcher.json` |
| `--output`, `-o` | Output directory | from config |
| `--start-from`, `-s` | Language code to start from (skips earlier ones) | first language |
| `--delay`, `-d` | Seconds to wait after each language change | from config |
| `--list`, `-l` | List what the config can record and build, and exit | |
| `--demo` | Record demo `<id>` (or `all`) of the configured app and exit | |
| `--compose` | Build the config's compose steps (`all`, or a matching output/type) | `all` |

`list_supported_languages.bat` is a shortcut for `--list`. Details: [docs/COMMAND_LINE_ARGUMENTS.md](docs/COMMAND_LINE_ARGUMENTS.md).

## Demo recordings

For apps implementing the automation interface (CLI args + socket events, see [docs/AUTOMATION_INTERFACE.md](docs/AUTOMATION_INTERFACE.md)); Python apps get the app-side implementation ready-made from the [automated-screenshot-connector](../automated-application-screenshots-python-connector) library:

```
uv run screenshot-tool --config path/to/your-app-demos.json --demo 1
```

The tool launches the app with the demo id, an event port, and the configured window size; the app reports its native window handle over the socket (no window guessing); the tool moves the window into the monitor's work area (so the taskbar never shows up in the capture) and records it while the app plays its scripted demo, saves stills whenever the app requests one, and exports `demo.gif` / `demo.mp4` to `<output_dir>/demos/<demo_name>/`. The app config gains two sections:

```json
"launch": {
  "command": ["uv", "run", "python", "main.py",
              "--automation-demo", "{demo_id}", "--automation-demo-port", "{port}",
              "--automation-demo-width", "{width}", "--automation-demo-height", "{height}"],
  "cwd": "D:/GIT/BenjaminKobjolke/calculator"
},
"demos": [
  {"id": 1, "name": "basic-math", "fps": 10, "formats": ["gif", "mp4"], "width": 640, "height": 420,
   "app_settings": {"editor/font_point_size": 18},
   "languages": ["en", "de"]}
]
```

### Composing the artifacts

Recording produces intermediates — one clip per chapter, one still per theme.
`--compose` builds what actually gets published out of them:

```json
"compose": [
  {"type": "tour",       "group": "tour",    "output": "tour/feature-tour.mp4",
   "intro": {"title": "Your App", "subtitle": "a feature tour"}},
  {"type": "stills_gif", "demo": "themes",   "output": "themes/themes.gif", "hold": 2.0},
  {"type": "mp4_gif",    "group": "feature", "output": "features/{name}.gif",
   "max_size": "2MB", "fit": ["colors", "fps"]}
]
```

```
uv run screenshot-tool --config app.json --demo all --compose   # record, then build
uv run screenshot-tool --config app.json --compose themes       # rebuild just one
```

Chapters carry a `group` and a `caption`; the tour joins them in `id` order and
burns each caption over the start of its chapter. `max_size` states how big an
artifact may be and `fit` which settings may be traded away to get there — at
most three encodes, keeping the best quality that fits. Details:
[docs/CONFIG.md](docs/CONFIG.md#compose-array-optional).

### Multi-language demos

A demo listing `languages` records once per language into `<output_dir>/demos/<demo_name>/<lang>/`; each run passes `--automation-demo-language <lang>` so the app can switch its UI language. With a top-level `"texts_dir": "texts"`, the matching `texts/<lang>.json` (placeholder → localized string, e.g. `{"price": "preis"}`) is also passed as `--automation-demo-texts`, letting demo scripts type localized text via `{placeholder}`s. Details: [docs/CONFIG.md](docs/CONFIG.md), [docs/AUTOMATION_INTERFACE.md](docs/AUTOMATION_INTERFACE.md).

Keep hands off mouse/keyboard while recording — the window must stay frontmost and unobstructed. A config may contain both `languages` (dropdown mode, top-level) and `demos`.

## Configuration

Each target application gets one JSON file in `config/`:

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

- `process_name` — process to find the window by; `title_substring` is the fallback window-title match
- `dropdown_relative_pos` — `[x, y]` click position of the language dropdown, relative to the window's top-left corner
- `languages` — map of language code to the exact display name shown in the dropdown; codes are used as output subfolder names and iterated alphabetically
- `delay_after_change` — seconds to wait after each language switch before capturing

To target another application, copy `config/keyboard-layout-watcher.json`, adjust the values, and run with `--config config/your-app.json`. Details: [docs/CONFIG.md](docs/CONFIG.md).

## How it works

1. Finds the target window by process name, falling back to a window-title match.
2. Clicks the language dropdown at the configured position and presses `Home` to select the first entry.
3. For each language: reads the selected dropdown value via UI Automation, captures the window region as PNG, then presses `Down` to advance.

## License

MIT — see [LICENSE](LICENSE).
