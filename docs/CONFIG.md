# Config File

Each target application is described by one JSON file, by convention stored in `config/`. The default config is `config/keyboard-layout-watcher.json`; another file can be selected with `--config` (see [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)).

All keys are required. A missing file, invalid JSON, or missing key aborts with a clear error message.

## Example

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

## Values

### `process_name` (string)

Executable name of the target application, e.g. `"KeyboardLayoutWatcher.exe"`. The tool first tries to find the application window by this process name.

### `title_substring` (string)

Fallback window search: if no window is found by `process_name`, the tool searches for a visible window whose title contains this substring.

### `dropdown_relative_pos` (array of two integers)

`[x, y]` pixel position of the language dropdown, relative to the top-left corner of the application window. The tool clicks this position to focus the dropdown before cycling through languages. Adjust when the target app's layout changes or when targeting a different application.

### `output_dir` (string)

Default output directory for screenshots. Each language gets its own subfolder: `<output_dir>/<language-code>/<screenshot_filename>`. Relative paths resolve against the current working directory. Can be overridden per run with `--output`.

### `screenshot_filename` (string)

Filename of the screenshot saved inside each language subfolder, e.g. `"screenshot.png"`.

### `delay_after_change` (number)

Seconds to wait after each language switch before capturing, so the UI can finish redrawing. Increase for slow applications. Can be overridden per run with `--delay`.

### `languages` (object)

Map of language code → exact display name as it appears in the application's dropdown, e.g. `"de": "Deutsch"`.

- The display name is used to read back which language is currently selected (via UI Automation); it must match the dropdown entry exactly (a case-insensitive fallback exists).
- The code is used as the output subfolder name.
- Languages are iterated in alphabetical order of the codes, which must match the order of entries in the application's dropdown.

## Adding a new application

1. Copy `config/keyboard-layout-watcher.json` to `config/your-app.json`.
2. Set `process_name` and `title_substring` for the target app.
3. Determine the dropdown position relative to the window's top-left corner and set `dropdown_relative_pos`.
4. Fill `languages` with the codes and exact dropdown display names, in the dropdown's (alphabetical) order.
5. Run: `uv run screenshot-tool --config config/your-app.json`
