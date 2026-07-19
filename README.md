# Automated Application Screenshots

Automated screenshot capture tool for Windows applications. Two modes:

- **Language screenshots** — cycles through an app's language dropdown and saves one screenshot per language to `screenshots/<language-code>/screenshot.png`.
- **Demo recordings** — launches an app that implements the [automation interface](docs/AUTOMATION_INTERFACE.md), records a scripted demo of it, and exports animated **GIF/MP4** plus PNG stills.

The target application is defined by a JSON config file — either in `config/` here, or kept in the app's own repo (FastCalculator keeps its demo config in `calculator/tools/media/` with a `create_demos.bat` next to it). Ships with a config for **KeyboardLayoutWatcher** (41 languages).

## Requirements

- Windows
- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) (`winget install astral-sh.uv`)
- The target application must be running and its window visible

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
| `--list`, `-l` | List all supported language codes and exit | |
| `--demo` | Record demo `<id>` (or `all`) of the configured app and exit | |

`list_supported_languages.bat` is a shortcut for `--list`. Details: [docs/COMMAND_LINE_ARGUMENTS.md](docs/COMMAND_LINE_ARGUMENTS.md).

## Demo recordings

For apps implementing the automation interface (CLI args + socket events, see [docs/AUTOMATION_INTERFACE.md](docs/AUTOMATION_INTERFACE.md)); Python apps get the app-side implementation ready-made from the [automated-screenshot-connector](../automated-application-screenshots-python-connector) library:

```
uv run screenshot-tool --config path/to/your-app-demos.json --demo 1
```

The tool launches the app with the demo id, an event port, and the configured window size; the app reports its native window handle over the socket (no window guessing); the tool records that window while the app plays its scripted demo, saves stills whenever the app requests one, and exports `demo.gif` / `demo.mp4` to `<output_dir>/demos/<demo_name>/`. The app config gains two sections:

```json
"launch": {
  "command": ["uv", "run", "python", "main.py",
              "--automation-demo", "{demo_id}", "--automation-demo-port", "{port}",
              "--automation-demo-width", "{width}", "--automation-demo-height", "{height}"],
  "cwd": "D:/GIT/BenjaminKobjolke/calculator"
},
"demos": [
  {"id": 1, "name": "basic-math", "fps": 10, "formats": ["gif", "mp4"], "width": 640, "height": 420,
   "app_settings": {"editor/font_point_size": 18}}
]
```

Keep hands off mouse/keyboard while recording — the window must stay frontmost and unobstructed. A config may contain both `languages` and `demos`.

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
