"""
Screenshot utility for Panel apps.

Captures the current layout state (with live widget values and full
styling) by saving to HTML via Panel's save(), then rendering to PNG
with Playwright.

Usage — programmatic (from any callback):

    from screenshot import save_screenshot

    def on_run(event):
        path = save_screenshot(app)
        print(f"Saved: {path}")

    app = pn.Column("# My App", slider)
"""

import logging
import os
import re
import tempfile
import threading
from datetime import datetime

import panel as pn
from bokeh.resources import INLINE

log = logging.getLogger(__name__)



def _fix_panel_css_paths(html_path: str) -> None:
    """Replace relative Panel CSS paths with CDN URLs so the HTML
    renders correctly when opened as a local file."""
    with open(html_path, "r") as f:
        html = f.read()

    version = pn.__version__
    cdn_base = f"https://cdn.holoviz.org/panel/{version}/dist"

    # Replace relative paths like: static/extensions/panel/css/markdown.css?v=1.8.7
    html = re.sub(
        r"static/extensions/panel/([^\"'?\s]+)(\?[^\"']*)?",
        lambda m: f"{cdn_base}/{m.group(1)}",
        html,
    )

    with open(html_path, "w") as f:
        f.write(html)


def _render_html_to_png(html_path: str, output_path: str) -> None:
    """Render an HTML file to PNG using Playwright. Thread-safe."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(f"file://{html_path}", wait_until="networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path=output_path, full_page=True)
        browser.close()


def save_screenshot(
    layout,
    save_dir: str = "screenshots",
    filename: str | None = None,
) -> str:
    """
    Take a screenshot of a Panel layout and save it as a PNG file.

    Captures the current widget state. Safe to call from any Panel
    callback — Playwright runs in a separate thread automatically.

    Args:
        layout: The Panel component to capture (Column, Row, etc.),
                or a callable returning one.
        save_dir: Directory to save screenshots in.
        filename: Output filename. Defaults to screenshot_YYYYMMDD_HHMMSS.png.

    Returns:
        Absolute path to the saved PNG file.
    """
    target = layout() if callable(layout) else layout
    os.makedirs(save_dir, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"

    output_path = os.path.abspath(os.path.join(save_dir, filename))
    tmp_html_path = None

    try:
        # Save current layout state as standalone HTML (runs on caller thread)
        fd, tmp_html_path = tempfile.mkstemp(suffix=".html", dir=save_dir)
        os.close(fd)
        target.save(tmp_html_path, resources=INLINE)
        _fix_panel_css_paths(tmp_html_path)
        log.info("Saved HTML (%d bytes)", os.path.getsize(tmp_html_path))

        # Playwright must run outside the asyncio event loop, so use a thread
        error = [None]

        def _render():
            try:
                _render_html_to_png(tmp_html_path, output_path)
            except Exception as e:
                error[0] = e

        t = threading.Thread(target=_render, daemon=True)
        t.start()
        t.join()

        if error[0]:
            raise error[0]

        log.info("Screenshot saved to %s", output_path)
        return output_path

    finally:
        if tmp_html_path and os.path.exists(tmp_html_path):
            os.unlink(tmp_html_path)
