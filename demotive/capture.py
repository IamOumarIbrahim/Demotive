"""Grab a screen rectangle at a fixed frame rate into a near-lossless MP4.

usage: python capture.py X Y W H FPS OUT.mp4 STOPFILE TIMESFILE [HWND]
Runs until STOPFILE exists. Writes the wall-clock time of every frame to
TIMESFILE (JSON) so the composer can line frames up with the driver's events.
"""

import ctypes
import json
import os
import subprocess
import sys
import time

import imageio_ffmpeg
from PIL import Image, ImageGrab


class _WinCapture:
    def __init__(self, hwnd, w, h):
        self.hwnd = hwnd
        self.w, self.h = w, h
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.hdcScreen = self.user32.GetDC(hwnd)
        self.hdcMem = self.gdi32.CreateCompatibleDC(self.hdcScreen)
        self.hbm = self.gdi32.CreateCompatibleBitmap(self.hdcScreen, w, h)
        self.gdi32.SelectObject(self.hdcMem, self.hbm)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', ctypes.c_uint32),
                ('biWidth', ctypes.c_int32),
                ('biHeight', ctypes.c_int32),
                ('biPlanes', ctypes.c_uint16),
                ('biBitCount', ctypes.c_uint16),
                ('biCompression', ctypes.c_uint32),
                ('biSizeImage', ctypes.c_uint32),
                ('biXPelsPerMeter', ctypes.c_int32),
                ('biYPelsPerMeter', ctypes.c_int32),
                ('biClrUsed', ctypes.c_uint32),
                ('biClrImportant', ctypes.c_uint32),
            ]
        self.bmi = BITMAPINFOHEADER()
        self.bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self.bmi.biWidth = w
        self.bmi.biHeight = -h
        self.bmi.biPlanes = 1
        self.bmi.biBitCount = 24
        self.bmi.biCompression = 0
        self.buf = (ctypes.c_char * (w * h * 3))()

    def grab(self):
        res = self.user32.PrintWindow(self.hwnd, self.hdcMem, 2)
        if not res:
            self.user32.PrintWindow(self.hwnd, self.hdcMem, 0)
        self.gdi32.GetDIBits(self.hdcMem, self.hbm, 0, self.h, self.buf, ctypes.byref(self.bmi), 0)
        return Image.frombuffer('RGB', (self.w, self.h), bytes(self.buf), 'raw', 'BGR', 0, 1).tobytes()

    def close(self):
        self.gdi32.DeleteObject(self.hbm)
        self.gdi32.DeleteDC(self.hdcMem)
        self.user32.ReleaseDC(self.hwnd, self.hdcScreen)


def main():
    x, y, w, h, fps = map(int, sys.argv[1:6])
    out, stopfile, timesfile = sys.argv[6:9]
    hwnd = int(sys.argv[9]) if len(sys.argv) > 9 else 0
    w -= w % 2
    h -= h % 2
    ff = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "ultrafast",
         "-tune", "zerolatency", "-crf", "8", "-pix_fmt", "yuv444p", out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    times = []
    step = 1 / fps
    nxt = time.perf_counter()
    t0_wall = time.time() - time.perf_counter()

    win_cap = None
    use_win_cap = False
    if sys.platform == "win32" and hwnd:
        try:
            # test if ImageGrab works
            ImageGrab.grab((x, y, x + w, y + h), all_screens=True)
        except Exception:
            use_win_cap = True
            win_cap = _WinCapture(hwnd, w, h)

    while not os.path.exists(stopfile):
        if use_win_cap and win_cap:
            frame = win_cap.grab()
        else:
            try:
                frame = ImageGrab.grab((x, y, x + w, y + h), all_screens=True).convert("RGB").tobytes()
            except Exception:
                if sys.platform == "win32" and hwnd and not win_cap:
                    win_cap = _WinCapture(hwnd, w, h)
                    use_win_cap = True
                    frame = win_cap.grab()
                else:
                    raise
        now = time.perf_counter()
        # keep a constant frame rate: repeat the frame if we fell behind
        while nxt <= now:
            ff.stdin.write(frame)
            times.append(t0_wall + nxt)
            nxt += step
        time.sleep(max(0, nxt - time.perf_counter() - 0.002))
    ff.stdin.close()
    ff.wait()
    if win_cap:
        win_cap.close()
    with open(timesfile, "w") as f:
        json.dump(times, f)


if __name__ == "__main__":
    main()
