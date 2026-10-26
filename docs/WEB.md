# Web projects

The screenshot tool can open web applications in Playwright, capture configured pages, and record connector-driven demos. This supports web apps before they embed the JavaScript connector: a plain run captures pages by itself, while `--demo` needs the connector to be present in the page.

## Browser setup

Microsoft Edge is the default browser channel and must be installed on the machine. To use Playwright's bundled Chromium instead, set `web.channel` to `"chromium"` and install its browser once:

```powershell
uv run playwright install chromium
```

Runs are headless by default. Set `web.headless` to `false` to see the browser. For a local development site using a self-signed certificate, set `web.ignore_https_errors` to `true`.

## AX Suite example

The public repository includes [`config/ax-suite.example.json`](../config/ax-suite.example.json). Copy it to `config/ax-suite.local.json`, then put a viewer account's API key in `web.login_header.value`. Local config files matching `config/*.local.json` are ignored by Git. Keep the key in that file; the tool does not include it in logs or settings representations. The browser adds the header only to requests for the configured application's exact origin.

The AX Suite header login only opens `/admin/overview`; other admin pages redirect there. The example therefore lists `/admin/login` and `/admin/overview`, and starts demo 1 at `/admin/overview`.

```powershell
uv run screenshot-tool --config config/ax-suite.local.json
uv run screenshot-tool --config config/ax-suite.local.json --list
uv run screenshot-tool --config config/ax-suite.local.json --demo 1 --compose
```

The plain run saves the configured viewport screenshots under `output_dir/pages/de/`. The demo saves stills and requested MP4/GIF outputs under `output_dir/demos/overview/de/`. Demo recording requires the web connector and its registered demo script to be embedded by the target site.

## WebSocket contract

The browser opens the configured application URL with these query parameters appended to the demo path. Existing query parameters are retained:

```text
?automation-demo=<id>&automation-demo-port=<port>
&automation-demo-language=<language>   (only for a language run)
```

The tool listens on `127.0.0.1` using an ephemeral port for each run. The page connects to `ws://127.0.0.1:<port>/`. The server accepts only a WebSocket handshake whose `Origin` exactly matches the configured application's origin. Send one JSON object per WebSocket text message; do not use newline framing. There is no `hwnd` in web events.

On the first accepted connection, the tool sends one `start` message for the run. `language` is omitted when no language was selected; `steps` may be empty. The shape matches network mode, except it omits `video` and `pixel_ratio`:

```json
{
  "command": "start",
  "demo": 1,
  "language": "de",
  "settings": {"api_base_url": "https://demo.example"},
  "texts": {"price": "Preis"},
  "steps": []
}
```

The page reports lifecycle events and screenshot requests:

```json
{"event": "demo_started", "demo": 1}
{"event": "screenshot", "name": "overview"}
{"event": "demo_ended", "demo": 1}
{"event": "error", "message": "unknown demo 7"}
```

For each screenshot request, the tool captures the current browser viewport as `<name>.png`, then acknowledges it:

```json
{"command": "screenshot_done", "name": "overview"}
```

The connector should wait for that acknowledgement before moving to the next step so the saved image reflects the requested state. A page navigation may close its WebSocket; the tool accepts a reconnect during the same run and does not resend `start`. The connector is responsible for retaining its demo state across page loads.

Timeouts are 30 seconds for the first connection, 60 seconds between events, and 300 seconds per demo. On timeout or a connector error, the tool exports any partial recording it has and exits with an error. The tool closes the browser when the demo ends.

The browser records WebM at the configured viewport size. The tool cuts from `demo_started` through `demo_ended` plus a short tail, converts it to H.264 MP4 at the demo's `fps`, and derives a GIF from that MP4 when requested. MP4 is retained whenever either GIF or MP4 output is requested.

See [CONFIG.md](CONFIG.md#web-object-web-target) for all web settings and [AUTOMATION_INTERFACE.md](AUTOMATION_INTERFACE.md#9-web-apps) for the compatibility note.
