# Recording environment

A demo records the machine it runs on. Whatever is on the desktop, in the app's
profile, or in its recent-files list is in the video — and it re-records
differently tomorrow. This is what to control, what the tool already does for
you, and what has to live in your own launch script.

The worked example throughout is fman's launcher
(`fman/tools/create_media/run_fman_demo.bat`), which is where most of this was
learned the expensive way.

## What the tool does for you

### A bare desktop

Before launching the app, the tool minimizes every visible top-level window and
waits ~1.2 s for the shell to finish animating. Turn it off with
`"launch": {"minimize_all": false}`.

Two independent reasons, both fatal to a take:

- Capture reads screen **pixels** at the target window's rect. Anything drawn
  over it — a notification, a chat window, the console the tool itself spawns
  per demo — is burned into every frame.
- If the app records semi-transparent, whatever sits **behind** it shows
  through. A leftover window puts its contents on camera without ever
  overlapping the target.

It enumerates windows and minimizes each one rather than calling the shell's
`MinimizeAll` (the Win+D shortcut), which *toggles* rather than minimizes and is
ignored outright in some states — it reports success while leaving windows on
screen. The shell's own classes are skipped, or the screen would go black
instead of clear. The log line says how many were minimized; a
"Minimized 0 window(s)" on a take that came out wrong is the tell.

### The interpreter

The tool runs under `uv`, whose virtualenv is first on the child process's
`PATH` and contains none of the recorded app's dependencies — an app launched
through a plain `python` would fail to import itself. The tool therefore
**removes its own virtualenv** from the environment it hands to the app. Set
`"launch": {"inherit_env": true}` if your app genuinely wants it.

### An isolated profile

`"launch": {"env": {...}}` sets environment variables for the child, expanding
`{temp}`, `{demo_id}`, `{name}` and `{lang}`:

```json
"launch": {
  "command": ["...", "{demo_id}", "{port}"],
  "env": {"MYAPP_DATA_DIR": "{temp}/myapp-demo-profile"}
}
```

For a Qt app, the connector's `prepare_demo_settings` does the QSettings
equivalent — a wiped temp INI namespace seeded from `app_settings`.

That covers the simple case entirely. The rest below is app-specific content,
and a config format for it would be a worse shell script than the one you can
already write.

## What belongs in your launch script

The tool runs `launch.command`; making that a small script of your own is the
supported way to do everything here.

### Fixtures

A demo that creates, renames, moves or deletes files must start from the same
state every time, or the second recording differs from the first:

```bat
set "SCRATCH=%TEMP%\myapp-demo-%1"
if exist "%SCRATCH%" rmdir /s /q "%SCRATCH%"
mkdir "%SCRATCH%"
xcopy /q /y "%CD%\examples\*" "%SCRATCH%\" >nul
```

Commit the fixtures. `%1` is the demo id, so each demo gets its own scratch
folder and demos cannot interfere with one another.

### Plugins and persisted UI state

Third-party plugins add key bindings that beat the app's own and commands that
change what a typed query resolves to. Persisted zoom, volume and window
opacity make a re-recording look different from the first take. Wipe the
plugin folder each run, and have the app **pin** every visual value the script
depends on rather than reading it from the profile.

### Isolate behaviour, inherit look

You usually want the opposite of full isolation for appearance: a demo showing
the default theme, when every other screenshot shows your real one, reads as a
different app. Copy just the files that carry the look into the throwaway
profile — for fman, one `Settings.json` plus the `Themes` folder — and leave
everything else isolated.

### Priming caches

If the app downloads something on first use — a codec, a model, a runtime — it
will download it *on camera*, behind a progress dialog. Copy the cached file
into the throwaway profile before launching, and warn if it is not there:

```bat
if not exist "%PROFILE%\libmpv-2.dll" (
    if exist "%APPDATA%\myapp\libmpv-2.dll" (
        copy /y "%APPDATA%\myapp\libmpv-2.dll" "%PROFILE%\" >nul
    ) else (
        echo WARNING: no cached codec - this demo would record its download.
    )
)
```

### Live data

Some demos need something that *moves*: a log view following the end of a file
cannot be shown with a static file. Start a background writer just before the
app, with a lifetime a little longer than the demo:

```bat
start "" /b powershell -NoProfile -Command ^
  "1..40 | ForEach-Object { Add-Content -LiteralPath $env:LOGFILE -Value ('line {0}' -f $_); Start-Sleep -Milliseconds 1500 }"
```

### Demo-only appearance tweaks

A clip published at 800 px from a 1280 px capture shows every font at 0.625×.
A demo-only stylesheet that bumps the font sizes — dropped into the throwaway
profile for those demo ids only — keeps the UI legible without changing the app.

## Privacy

Anything the app derives from *your* machine is on camera: recent paths, search
results, autocomplete suggestions, window titles of other documents. Before
publishing a demo that shows any suggestion list, work out where each entry can
come from and close the ones that reach outside the fixtures — usually by
seeding the app's own history with enough entries that it never falls back to
your home directory, and by keeping queries short enough not to hit a system-wide
search index.

This is the one item on this page that no tool can check for you.

## Proving it worked

Add `verify` checks to the demo (see [CONFIG.md](CONFIG.md#demos-array-demo-mode)).
A demo can play to the end, report every event and still have missed — a dialog
stole a keystroke, a viewer never took focus. Pick a side effect that only
happens if the risky step really landed: a file the demo creates, a setting only
one code path writes. It turns "the video looks wrong" into a failed run.
