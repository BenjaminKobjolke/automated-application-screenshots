# Command Line Arguments

Run via `uv run screenshot-tool [options]` (or `start.bat`).

| Option | Argument | Description | Default |
|---|---|---|---|
| `--config`, `-c` | `PATH` | App config JSON file describing the target application (see [CONFIG.md](CONFIG.md)) | `config/keyboard-layout-watcher.json` |
| `--output`, `-o` | `DIR` | Output directory. Screenshots are saved as `<DIR>/<language-code>/<screenshot_filename>` | `output_dir` from config |
| `--start-from`, `-s` | `CODE` | Language code to start from; earlier languages are skipped. Useful to resume an aborted run | first language |
| `--delay`, `-d` | `SECONDS` | Delay after each language change before capturing (float) | `delay_after_change` from config |
| `--list`, `-l` | | List all supported language codes from the config and exit | |
| `--help`, `-h` | | Show usage help and exit | |

## Examples

```
uv run screenshot-tool                                   # Capture all languages
uv run screenshot-tool --list                            # Show all language codes
uv run screenshot-tool --start-from de                   # Resume from German
uv run screenshot-tool --output ./imgs                   # Custom output directory
uv run screenshot-tool --delay 0.5                       # Wait 0.5s between captures
uv run screenshot-tool --config config/other-app.json    # Other target app
```

## Exit codes

- `0` — all screenshots captured (or `--list`/`--help` shown)
- `1` — window not found, unknown language code, config error, or at least one capture failed
