"""Demo Panel app showing both programmatic and button screenshot usage."""

import asyncio

import panel as pn
from screenshot import save_screenshot

pn.extension()

slider = pn.widgets.FloatSlider(name="Value", start=0, end=10, value=5)
text = pn.widgets.TextInput(name="Name", placeholder="Enter something...")
display = pn.pane.Markdown(pn.bind(lambda v, n: f"**{n}**: {v}", slider, text))

# --- Programmatic usage: screenshot on "Run" ---
run_btn = pn.widgets.Button(name="Run Report", button_type="success", width=200)

params_panel = pn.Column(
    "## Parameters",
    slider,
    text,
    display,
)


async def on_run(event):
    """Handle the Run Report button click.

    Captures the current app state as a PNG screenshot and logs the
    resulting file path.  Runs the blocking screenshot capture in a
    separate thread so the Tornado event loop stays responsive.

    Args:
        event: The Bokeh button-click event (unused, required by
            ``on_click`` callback signature).
    """
    path = await asyncio.to_thread(save_screenshot, lambda: app)
    print(f"Screenshot saved to {path}")


run_btn.on_click(on_run)


app = pn.Column(
    "# Demo App",
    params_panel,
    pn.layout.Divider(),
    pn.Row(run_btn)
)
app.servable()
