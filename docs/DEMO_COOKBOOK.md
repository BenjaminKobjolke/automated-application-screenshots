# Demo cookbook

What this thing can do, as questions. Each answer is three lines and a link —
this is the index, not the manual.

If you are starting from nothing, read [CONFIG.md](CONFIG.md) first, then come
back here to find the piece you need.

At any point, `screenshot-tool --config your-app.json --list` prints what your
config can record and build, which is usually faster than re-reading the JSON.

---

## Recording

**Want to record a demo at all?**
Make the app implement the automation contract, then give it a `launch` section
and one `demos` entry. Python apps use the connector library and write nothing
by hand. → [AUTOMATION_INTERFACE.md](AUTOMATION_INTERFACE.md), [CONFIG.md](CONFIG.md#demos-array-demo-mode)

**Want a still, not a video?**
`Screenshot("name")` in the demo script saves `name.png`. A demo with
`"formats": []` records nothing but its stills. → [CONFIG.md](CONFIG.md#demos-array-demo-mode)

**Want the same demo at two sizes (landscape and portrait)?**
Two `demos` entries with the same `id` and different `name`/`width`/`height`.
Same script, two folders. → [CONFIG.md](CONFIG.md#variants-of-one-demo-eg-landscape--portrait)

**Want the demo in five languages?**
`"languages": ["en", "de", ...]` on the demo, and a `texts_dir` holding the
wording. One script records once per language. → [CONFIG.md](CONFIG.md#texts_dir-string-demo-mode-optional)

**Want to know how long a script runs before spending a take on it?**
`estimated_duration(script)` in the connector. The tool aborts a demo at 300 s.
→ connector `docs/WRITING_DEMOS.md`

**Want one screenshot per installed theme, plugin or locale — without editing the
config when one is added?**
Register a script *factory* instead of a script; it is called at lookup time and
builds the steps from whatever is installed. → connector `docs/WRITING_DEMOS.md`

**Want to iterate on pacing without running the tool?**
Start the app with `--automation-demo <id>` and no port. The connector's client
degrades to a no-op and the demo just plays. → connector `docs/WRITING_DEMOS.md`

---

## Getting a clean recording

**Want the recording to stop catching your other windows?**
Nothing to do — the tool minimizes everything before launching the app. Turn it
off with `"minimize_all": false`. → [RECORDING_ENVIRONMENT.md](RECORDING_ENVIRONMENT.md#a-bare-desktop)

**Want the app to run against a throwaway profile?**
`"launch": {"env": {"APP_PROFILE": "{temp}/myapp-demo"}}` — no wrapper script
needed for the simple case. → [RECORDING_ENVIRONMENT.md](RECORDING_ENVIRONMENT.md#an-isolated-profile)

**Want a demo that resets its files every run, so a destructive script is
repeatable?**
Wipe and re-seed a scratch folder from committed fixtures in your launch script.
→ [RECORDING_ENVIRONMENT.md](RECORDING_ENVIRONMENT.md#fixtures)

**Want something *changing* on screen — a growing log, a progress bar?**
Start a background writer before the app, with a lifetime just longer than the
demo. → [RECORDING_ENVIRONMENT.md](RECORDING_ENVIRONMENT.md#live-data)

**Want the app's font bigger, only for the recording?**
`app_settings` if the app reads it at startup; otherwise inject a demo-only
stylesheet in the launch script. → [CONFIG.md](CONFIG.md#demos-array-demo-mode)

**Want to be sure the demo actually did what it says?**
`verify` checks a side effect after the run — a file that must exist, a setting
that must have been written. A silent miss fails the run instead of shipping.
→ [CONFIG.md](CONFIG.md#demos-array-demo-mode)

**Your app fails to start only when the tool launches it?**
The tool runs under `uv`; its virtualenv is dropped from the child's `PATH` for
exactly that reason. If your app *wants* it, set `"inherit_env": true`.
→ [RECORDING_ENVIRONMENT.md](RECORDING_ENVIRONMENT.md#the-interpreter)

---

## Building the artifacts

**Want a caption over each chapter of a feature tour?**
Give the chapters a `group` and a `caption`, add a `tour` compose step, run
`--compose`. Needs Node.js. → [CONFIG.md](CONFIG.md#type-tour)

**Want an intro and outro card?**
`"intro": {"title": ..., "subtitle": ...}` on the tour step. → [CONFIG.md](CONFIG.md#type-tour)

**Want the tour's typography to match your brand?**
One file: `composer/src/theme.ts`. → [CONFIG.md](CONFIG.md#type-tour)

**Want a slideshow GIF of your themes?**
Record a stills-only demo, then a `stills_gif` step. The stills are the list —
adding a theme needs no config change. → [CONFIG.md](CONFIG.md#type-stills_gif)

**Want a GIF next to a paragraph in the README?**
A `mp4_gif` step. GitHub only renders a video player for a bare attachment URL
alone on its line, so a GIF is the only moving image that can sit inline.
→ [PUBLISHING.md](PUBLISHING.md)

**Want the GIF to stay under 2 MB without hand-tuning colours?**
`"max_size": "2MB"` plus `"fit": ["colors", "fps"]` — the knobs it may move.
Everything you left out is a constraint. → [CONFIG.md](CONFIG.md#size-budgets)

**Want to record and build in one command?**
`--demo all --compose`. A failed recording stops the build rather than composing
stale inputs. → [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)

**Want to rebuild one artifact without re-recording?**
`--compose features/goto.gif` — the selector matches an output path or a step
type. → [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)

---

## Shipping

**Want to know what to commit and what to ignore?**
Commit the composed artifact; ignore the per-chapter clips and per-theme stills.
→ [PUBLISHING.md](PUBLISHING.md#artifacts-vs-intermediates)

**Want a video player in your README?**
It is not the committed MP4 — GitHub plays only an uploaded attachment URL, on a
line of its own. → [PUBLISHING.md](PUBLISHING.md)

**Want to check a demo does not put your real folders on camera?**
Anything the app suggests from your machine — recent paths, search results — is
on screen. Seed the app's own history so it never falls back to yours.
→ [RECORDING_ENVIRONMENT.md](RECORDING_ENVIRONMENT.md#privacy)
