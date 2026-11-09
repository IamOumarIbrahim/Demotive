"""The walkthrough in the Pinterest Mass Downloader README, made with Demotive.

usage (from the Demotive folder):
    python examples/pinterest_mass_downloader.py PATH/TO/pinterest-mass-downloader REFERENCE.jpg takes/pinterest
    python -m demotive.compose takes/pinterest demo.mp4 --gif demo.gif ^
        --logo P --title "Pinterest Mass Downloader" ^
        --subtitle "Bulk-download pictures, videos & GIFs, keeping only the ones you want" ^
        --outro-title "Get started" --outro-subtitle "Windows · Python 3.10+" ^
        --outro-line "pip install -r requirements.txt" --outro-line "python pinterest_downloader.py"

The app gets its own throw-away settings folder, so nothing personal is filmed.
"""

import os
import shutil
import sys

APP_DIR, REF, WORK = (os.path.abspath(a) for a in sys.argv[1:4])
QUERY = sys.argv[4] if len(sys.argv) > 4 else "fortnite llama"
sys.path.insert(0, APP_DIR)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["APPDATA"] = os.path.join(WORK, "appdata")
shutil.rmtree(os.environ["APPDATA"], ignore_errors=True)
OUT = os.path.join(WORK, "downloads")
os.makedirs(os.path.join(OUT, ".reference"), exist_ok=True)
REF = shutil.copy(REF, os.path.join(OUT, ".reference", os.path.basename(REF)))

from pinmass import settings  # noqa: E402

settings.save(dict(settings.DEFAULTS, folder=OUT, image=50, look=True, colors=False,
                   color_tolerance=50, closeness=50, appearance="Dark",
                   recent=["cat aesthetic", "anime wallpaper"]))

from pinmass.gui import App  # noqa: E402

from demotive import Director  # noqa: E402

app = App()


def script(d: Director):
    yield from d.wait(1.2)

    yield from d.caption("Type what you're looking for")
    yield from d.focus(app.search.master.master, 1.55)
    yield from d.move(app.search, dx=-120)
    yield from d.click()
    yield from d.type(app.search, QUERY, after=app._update_mode_hint)
    yield from d.wait(0.8)

    yield from d.caption("Choose how many pictures, videos and GIFs")
    yield from d.focus(app.rows["image"].master.master, 1.5)
    yield from d.drag_slider(app.rows["image"].slider, 8)
    yield from d.wait(0.6)

    yield from d.caption("Drop in a picture you like")
    yield from d.focus(None)
    yield from d.scroll(app.left_scroll._parent_canvas, 0.27)
    yield from d.drag_file(REF, onto=app.drop, on_drop=lambda: app._load_reference(REF))
    yield from d.focus(app.drop.master.master, 1.45)
    yield from d.wait(1.6)

    yield from d.caption("Match its look, its colors, or both")
    yield from d.move(app.match_boxes["colors"], dx=-40)
    yield from d.click(lambda: (app.colors.set(True), app._refresh_match_ui()))
    yield from d.wait(0.6)
    yield from d.scroll(app.left_scroll._parent_canvas, 0.52)
    yield from d.focus(app.color_box, 1.45, pad=10)
    yield from d.wait(1.2)

    yield from d.caption("Tolerance: same color amounts  ↔  any amounts")
    yield from d.drag_slider(app.tol_slider, 15, dur=1.0)
    yield from d.wait(0.7)
    yield from d.drag_slider(app.tol_slider, 85, dur=1.2)
    yield from d.wait(0.6)
    yield from d.drag_slider(app.tol_slider, 70, dur=0.6)
    yield from d.wait(0.8)

    yield from d.caption("…or pick your own colors (click one to remove it)")
    yield from d.move(app.pick_btn)
    yield from d.click(lambda: app.add_color("#ff2d95"))
    yield from d.wait(1.3)
    yield from d.move(app.swatch_labels[-1], dx=20)
    yield from d.click(lambda: app._remove_color(len(app.palette.shares) - 1))
    yield from d.wait(1.0)

    yield from d.caption("Hit Download: matches stream in with their score")
    yield from d.focus(None)
    yield from d.move(app.go_btn)
    yield from d.click(app.start)
    yield from d.wait(1.5)
    yield from d.move((d.W // 2 + 250, 380), 1.2)
    yield from d.speed(4)
    yield from d.until(lambda: not app.running)
    yield from d.speed(1)
    yield from d.wait(1.0)
    yield from d.focus(app.gallery.master, 1.12, pad=4)
    yield from d.wait(2.5)
    yield from d.focus(None)

    yield from d.caption("Open Phone to browse & share from your phone")
    yield from d.move(app.phone_btn)
    yield from d.click(app.open_phone)
    app.phone_win.attributes("-topmost", True)
    app.phone_win.geometry(f"520x700+{app.winfo_rootx() + 460}+{app.winfo_rooty() + 60}")
    yield from d.wait(0.8)
    yield from d.move((800, 400), 0.8)
    yield from d.wait(3.5)
    yield from d.caption(None)
    yield from d.wait(0.6)


d = Director(app, WORK)
app.protocol("WM_DELETE_WINDOW", app._close)
d.run(script)
