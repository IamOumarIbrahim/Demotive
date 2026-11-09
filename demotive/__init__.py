"""Demotive: scripted, polished demo videos of desktop apps.

1. Write a short script that drives your app (Director).
2. Demotive records the window while it runs.
3. compose turns the raw take into a video with zooms, a smooth cursor,
   click ripples, step captions, fast-forward and title cards.
"""

from .director import Director

__all__ = ["Director"]
__version__ = "0.1.0"
