# Screenshot Utility for Panel Apps

## Overview

Server-side screenshot utility that captures Panel app layouts as PNG files, preserving current widget values and styling. Built with Panel's `save()` for HTML serialization and Playwright (headless Chromium) for rendering.

## Architecture

```
save_screenshot(layout)
    |
    v
layout.save() --> temp HTML file (Bokeh INLINE resources)
    |
    v
_fix_panel_css_paths() --> rewrite relative CSS to CDN URLs
    |
    v
Playwright (in thread) --> open file://, screenshot, save PNG
    |
    v
cleanup temp HTML, return path
```

## Key Files

- `screenshot.py` — core library: `save_screenshot()`
- `demo_app.py` — example app

## Issues Faced and Design Choices

### 1. Playwright vs Selenium

**Choice: Playwright.** Simpler API, built-in `playwright install chromium` (no separate driver management), faster headless execution, and `wait_until="networkidle"` for reliable page load detection.

### 2. Capturing live widget state (not defaults)

**Problem:** The initial approach used Playwright to visit the running server URL. This opens a *new* Panel session with default widget values — it cannot see the user's current widget state.

**Rejected alternative:** `html2canvas` / `dom-to-image-more` (client-side JS capture). These capture the live DOM state but produce degraded styling — Panel uses shadow DOM and complex CSS that these libraries cannot faithfully reproduce.

**Solution:** Use Panel's `layout.save()` which serializes the current Bokeh model state (including widget values) to a standalone HTML file. Playwright then opens this local file (`file://` protocol) and screenshots it with full browser rendering fidelity.

### 3. Playwright sync API inside asyncio loop

**Problem:** Panel callbacks run inside Tornado's asyncio event loop. Playwright's sync API raises `Error: It looks like you are using Playwright Sync API inside the asyncio loop`.

**Solution:** Run Playwright in a `threading.Thread`. The `save()` call (pure serialization) runs on the caller thread, then the Playwright rendering runs in a daemon thread. `thread.join()` blocks until the screenshot is complete, making `save_screenshot()` a simple blocking call from the caller's perspective.

### 4. Event loop deadlock (earlier Playwright-visits-server approach)

**Problem:** When using Playwright to visit the live server URL, the `on_click` callback blocks the Tornado event loop. Playwright's headless browser tries to connect to the same server, but the server can't serve the page while the callback is blocked — deadlock.

**Solution:** This was resolved by switching to the `save()` + local file approach. Playwright opens a `file://` URL, so it never connects to the Panel server. No deadlock possible.

### 5. Panel CSS paths broken in saved HTML

**Problem:** When `layout.save()` is called from within a running server session, Panel writes CSS references as relative paths (`static/extensions/panel/css/markdown.css?v=X.Y.Z`). These resolve fine on a running server but fail when the HTML is opened via `file://` — resulting in missing styles and invisible Markdown content.

When `save()` is called outside a server session (standalone script), Panel uses CDN URLs (`https://cdn.holoviz.org/panel/X.Y.Z/dist/css/markdown.css`) which work everywhere.

**Solution:** `_fix_panel_css_paths()` post-processes the saved HTML, replacing relative `static/extensions/panel/...` paths with CDN URLs based on the installed Panel version.

### 6. Reactive `pn.bind()` values in saved HTML

**Investigated but not an issue:** Panel internally evaluates `pn.bind()` references and stores the resolved values (plain strings, etc.) on the pane objects. The `.object` property of a Markdown pane with `pn.bind()` is already a string like `"**TestUser**: 7.5"` at the time `save()` is called. No special resolution step is needed.

## API

### `save_screenshot(layout, save_dir="screenshots", filename=None) -> str`

Blocking call. Safe to use from any Panel callback. Returns absolute path to saved PNG.

```python
def on_run(event):
    path = save_screenshot(params_panel, save_dir="reports")
    # path = "/abs/path/to/reports/screenshot_20260208_091732.png"
```

The `layout` argument can be a Panel component or a callable returning one (use `lambda: app` for circular references).

## Dependencies

- `panel` — app framework
- `playwright` — headless browser rendering
- Chromium browser: installed via `playwright install chromium`
