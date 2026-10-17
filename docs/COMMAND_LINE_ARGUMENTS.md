# Command Line Arguments

Run via `uv run screenshot-tool [options]` (or `start.bat`) **from this repo**.

From another repo — which is where a consuming app's config and runner `.bat`
live — the tool is reached with `uv run --project <tool-dir> screenshot-tool
[options]`; that runs the tool in its own environment while the config path and
the current directory stay the app's. The shipped
[`templates/create_demos.bat`](../templates/create_demos.bat) does exactly this,
taking `<tool-dir>` from the `SCREENSHOT_TOOL_DIR` environment variable and
falling back to a checkout next to the app's repo.

| Option | Argument | Description | Default |
|---|---|---|---|
| `--config`, `-c` | `PATH` | App config JSON file describing the target application (see [CONFIG.md](CONFIG.md)) | `config/keyboard-layout-watcher.json` |
| `--output`, `-o` | `DIR` | Output directory. Screenshots are saved as `<DIR>/<language-code>/<screenshot_filename>` | `output_dir` from config |
| `--start-from`, `-s` | `CODE` | Language code to start from; earlier languages are skipped. Useful to resume an aborted run | first language |
| `--delay`, `-d` | `SECONDS` | Delay after each language change before capturing (float) | `delay_after_change` from config |
| `--list`, `-l` | | List what the config can record and build — demos with their ids, groups, formats and languages, then the compose steps, then the language codes — and exit | |
| `--demo` | `ID\|all` | Record the given demo (or all demos) defined in the config and exit — launches the app itself, exports GIF/MP4 + stills (see [AUTOMATION_INTERFACE.md](AUTOMATION_INTERFACE.md)). A demo with `languages` records once per language. Not combinable with `--list`/`--start-from` | |
| `--compose` | `ALL\|NAME` | Build the config's `compose` steps and exit: the joined tour, slideshow GIFs, inline GIFs (see [CONFIG.md](CONFIG.md#compose-array-optional)). `NAME` matches a step's `output` path or its `type`; omitted, it means all. Combine with `--demo` to record and then build — a failed recording stops the build rather than composing stale inputs. Not combinable with `--list`/`--start-from` | `all` |
| `--live` | | Start a configured Flutter app and read JSON-lines live commands from stdin until `stop` or EOF. Requires `live` in the config; not combinable with `--demo`, `--compose`, `--list` or `--start-from`. Logs go to stderr and command responses to stdout. See [LIVE.md](LIVE.md) | |
| `--target` | `windows\|android_emulator` | Override `live.target` for this run; requires `--live` | `live.target` |
| `--help`, `-h` | | Show usage help and exit | |

## Examples

```
uv run screenshot-tool                                   # Capture all languages
uv run screenshot-tool --list                            # Show all language codes
uv run screenshot-tool --start-from de                   # Resume from German
uv run screenshot-tool --output ./imgs                   # Custom output directory
uv run screenshot-tool --delay 0.5                       # Wait 0.5s between captures
uv run screenshot-tool --config config/other-app.json    # Other target app
uv run screenshot-tool --config app.json --demo 1        # Record demo 1
uv run screenshot-tool --config app.json --demo all      # Record every demo
uv run screenshot-tool --config app.json --compose       # Build every artifact
uv run screenshot-tool --config app.json --compose tour  # Rebuild just the tour
uv run screenshot-tool --config app.json --demo all --compose   # Record, then build
uv run screenshot-tool --config app.json --list          # What can this config do?
uv run screenshot-tool --config app.json --live          # Serve live commands
uv run screenshot-tool --config app.json --live --target windows
```

## Exit codes

- `0` — all screenshots captured / all demos recorded (or `--list`/`--help` shown)
- `1` — window not found, unknown language code or demo id, config error, at least one capture failed, a demo ended abnormally (partial recording still exported), a `verify` check failed, or a compose step failed
- `2` — invalid command-line arguments, including an incompatible live-mode option
