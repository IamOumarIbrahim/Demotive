"""Drive a Tkinter / CustomTkinter app from a script while recording it.

    from demotive import Director

    def script(d):
        yield from d.caption("Type what you're looking for")
        yield from d.focus(app.search, zoom=1.5)
        yield from d.move(app.search)
        yield from d.click()
        yield from d.type(app.search, "hello")
        yield from d.wait(1)

    Director(app, "takes/run1").run(script)

Every step is a generator, so the app keeps running smoothly between steps.
Nothing touches the real mouse or keyboard: actions call your widgets
directly and the cursor, clicks and zooms are logged for the composer to draw.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Callable, Iterator

Step = Iterator[float]


class Director:
    def __init__(self, app, workdir: str, size: tuple[int, int] = (1320, 860),
                 pos: tuple[int, int] = (300, 70), fps: int = 30, topmost: bool = True):
        self.app = app
        self.work = os.path.abspath(workdir)
        os.makedirs(self.work, exist_ok=True)
        self.W, self.H = size
        self.fps = fps
        self.events: list[dict] = []
        app.geometry(f"{self.W}x{self.H}+{pos[0]}+{pos[1]}")
        if topmost:
            app.attributes("-topmost", True)
        self._cap = None
        self._stop = os.path.join(self.work, "stop")

    # ── logging ─────────────────────────────────────────────────────────
    def log(self, kind: str, **kw):
        self.events.append({"t": time.time(), "type": kind, **kw})

    # ── geometry helpers ────────────────────────────────────────────────
    def center(self, widget, dx: int = 0, dy: int = 0) -> tuple[int, int]:
        self.app.update_idletasks()
        return (widget.winfo_rootx() - self.app.winfo_rootx() + widget.winfo_width() // 2 + dx,
                widget.winfo_rooty() - self.app.winfo_rooty() + widget.winfo_height() // 2 + dy)

    def rect(self, widget, pad: int = 12) -> list[int]:
        self.app.update_idletasks()
        x = widget.winfo_rootx() - self.app.winfo_rootx()
        y = widget.winfo_rooty() - self.app.winfo_rooty()
        return [x - pad, y - pad, x + widget.winfo_width() + pad, y + widget.winfo_height() + pad]

    def _point(self, target, dx=0, dy=0):
        return target if isinstance(target, tuple) else self.center(target, dx, dy)

    # ── steps ───────────────────────────────────────────────────────────
    def wait(self, seconds: float) -> Step:
        yield seconds

    def move(self, target, dur: float = 0.7, dx: int = 0, dy: int = 0) -> Step:
        """Glide the cursor to a widget (or an (x, y) point in the window)."""
        x, y = self._point(target, dx, dy)
        self.log("move", x=x, y=y, dur=dur)
        yield dur + 0.05

    def click(self, action: Callable | None = None) -> Step:
        """Show a click; run *action* (e.g. button.invoke) at the same moment."""
        self.log("click")
        if action:
            action()
        yield 0.18

    def caption(self, text: str | None) -> Step:
        """Show a numbered step caption until the next one (None hides it)."""
        self.log("caption", text=text)
        yield 0

    def focus(self, target=None, zoom: float = 1.45, pad: int = 8) -> Step:
        """Zoom the camera onto a widget (or [x0, y0, x1, y1]); None zooms out."""
        if target is None:
            self.log("focus", rect=None, zoom=1.0)
        else:
            r = list(target) if isinstance(target, (list, tuple)) else self.rect(target, pad)
            self.log("focus", rect=r, zoom=zoom)
        yield 0

    def speed(self, factor: float) -> Step:
        """Fast-forward from here (e.g. 4) until speed(1)."""
        self.log("speed", factor=factor)
        yield 0

    def type(self, entry, text: str, cps: float = 11, after: Callable | None = None) -> Step:
        entry.focus_set()
        for ch in text:
            entry.insert("end", ch)
            if after:
                after()
            yield 1 / cps

    def drag_slider(self, slider, to: float, dur: float = 0.9, steps: int = 24) -> Step:
        """Drag a ttk/CTk slider to *to*, calling its command as a user would."""
        start = slider.get()
        yield from self.move(self._knob(slider, start), 0.6)
        self.log("press")
        cmd = getattr(slider, "_command", None)
        for i in range(1, steps + 1):
            v = start + (to - start) * (i / steps) ** 0.8
            slider.set(v)
            if cmd:
                cmd(v)
            x, y = self._knob(slider, v)
            self.log("move", x=x, y=y, dur=dur / steps)
            yield dur / steps
        self.log("release")
        yield 0.3

    def _knob(self, slider, value):
        self.app.update_idletasks()
        try:
            lo = float(slider.cget("from_"))
        except Exception:
            lo = float(slider.cget("from"))
        hi = float(slider.cget("to"))
        frac = (value - lo) / (hi - lo) if hi != lo else 0
        x = slider.winfo_rootx() - self.app.winfo_rootx()
        y = slider.winfo_rooty() - self.app.winfo_rooty() + slider.winfo_height() // 2
        return int(x + 10 + frac * (slider.winfo_width() - 20)), y

    def scroll(self, canvas, to: float, dur: float = 0.8, steps: int = 20) -> Step:
        """Smoothly scroll a Canvas (or CTkScrollableFrame._parent_canvas)."""
        start = canvas.yview()[0]
        for i in range(1, steps + 1):
            f = i / steps
            canvas.yview_moveto(start + (to - start) * f * f * (3 - 2 * f))
            yield dur / steps

    def drag_file(self, path: str, onto, on_drop: Callable | None = None,
                  start: tuple[int, int] | None = None) -> Step:
        """Show a file being dragged in from the edge and dropped on *onto*."""
        tx, ty = self._point(onto)
        yield from self.move(start or (self.W - 60, ty - 40), 0.6)
        self.log("drag_file", path=os.path.abspath(path))
        yield from self.move((tx, ty), 1.0)
        self.log("drop")
        if on_drop:
            on_drop()
        yield 0.2

    def until(self, condition: Callable[[], bool], timeout: float = 150, poll: float = 0.3) -> Step:
        """Wait until condition() is true (e.g. a download finished)."""
        t0 = time.time()
        while not condition() and time.time() - t0 < timeout:
            yield poll

    # ── running ─────────────────────────────────────────────────────────
    def run(self, script: Callable[["Director"], Step], warmup: float = 1.5):
        """Start recording, play *script*, write events.json, close the app."""
        if os.path.exists(self._stop):
            os.remove(self._stop)

        def begin():
            self.app.update()
            x, y = self.app.winfo_rootx(), self.app.winfo_rooty()
            hwnd = getattr(self.app, "winfo_id", lambda: 0)()
            self._cap = subprocess.Popen([
                sys.executable, "-m", "demotive.capture", str(x), str(y), str(self.W), str(self.H),
                str(self.fps), os.path.join(self.work, "raw.mp4"), self._stop,
                os.path.join(self.work, "frames.json"), str(hwnd)],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.app.after(1500, play)

        def play():
            gen = script(self)

            def step():
                try:
                    delay = next(gen)
                except StopIteration:
                    finish()
                    return
                self.app.after(max(1, int((delay or 0) * 1000)), step)
            step()

        def finish():
            open(self._stop, "w").close()

            def wait_for_cap():
                if self._cap and self._cap.poll() is None:
                    self.app.after(50, wait_for_cap)
                    return
                with open(os.path.join(self.work, "events.json"), "w", encoding="utf-8") as f:
                    json.dump({"window": [self.W, self.H], "events": self.events}, f, indent=1)
                self.app.destroy()

            wait_for_cap()

        self.app.after(int(warmup * 1000), begin)
        self.app.mainloop()
