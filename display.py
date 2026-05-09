#!/usr/bin/env python3
"""
LED matrix display driver.
Wraps rpi-rgb-led-matrix to show album art and status screens.
"""

import logging
import time
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

# Matrix hardware config — adjust to match your panel wiring
MATRIX_OPTIONS = {
    "rows": 64,
    "cols": 64,
    "chain_length": 1,
    "parallel": 1,
    "hardware_mapping": "adafruit-hat",
    "brightness": 50,  # lower brightness looks better for album art
    "gpio_slowdown": 4,  # Pi 3B sweet spot
    "drop_privileges": False,
}

# Colours
BLACK  = (0, 0, 0)
WHITE  = (255, 255, 255)
DIM    = (40, 40, 40)
ACCENT = (180, 60, 60)  # deep red for status screens


def _make_matrix():
    """Initialise and return the RGB matrix object."""
    try:
        from rgbmatrix import RGBMatrix, RGBMatrixOptions
        opts = RGBMatrixOptions()
        for k, v in MATRIX_OPTIONS.items():
            setattr(opts, k, v)
        return RGBMatrix(options=opts)
    except ImportError:
        log.warning("rgbmatrix not available — running in preview mode (no display output)")
        return None


class MatrixDisplay:
    def __init__(self):
        self.matrix = _make_matrix()
        self.canvas = self.matrix.CreateFrameCanvas() if self.matrix else None

    # ------------------------------------------------------------------ #
    # Public methods                                                       #
    # ------------------------------------------------------------------ #

    def show_album_art(self, image: Image.Image):
        """Display a 64x64 PIL image on the matrix with a smooth fade."""
        self._fade_to(image)

    def show_startup(self):
        """Splash screen on boot."""
        img = self._solid(BLACK)
        draw = ImageDraw.Draw(img)
        draw.rectangle([28, 20, 36, 44], fill=ACCENT)   # simple vinyl icon
        draw.ellipse([26, 28, 38, 36], fill=BLACK)
        draw.ellipse([30, 30, 34, 34], fill=ACCENT)
        self._push(img)

    def show_idle(self):
        """Shown when no track is detected."""
        img = self._solid(BLACK)
        draw = ImageDraw.Draw(img)
        # Animated dots drawn as static here; main loop can call this repeatedly
        for i, x in enumerate([26, 31, 36]):
            brightness = 60 + i * 30
            draw.ellipse([x, 30, x+4, 34], fill=(brightness, brightness, brightness))
        self._push(img)

    def show_track_text(self, track: dict):
        """Fallback: show artist name as text if no art is found."""
        img = self._solid(BLACK)
        draw = ImageDraw.Draw(img)
        artist = track.get("artist", "")[:10]
        title  = track.get("title", "")[:10]
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 8)
        except OSError:
            font = ImageFont.load_default()
        draw.text((2, 20), artist, font=font, fill=WHITE)
        draw.text((2, 34), title,  font=font, fill=DIM)
        self._push(img)

    def show_error(self):
        """Brief red flash on error."""
        img = self._solid((60, 0, 0))
        self._push(img)
        time.sleep(1)
        self._push(self._solid(BLACK))

    def clear(self):
        self._push(self._solid(BLACK))

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _push(self, image: Image.Image):
        """Send a PIL image to the matrix."""
        if self.matrix and self.canvas:
            self.canvas.SetImage(image.convert("RGB"))
            self.canvas = self.matrix.SwapOnVSync(self.canvas)
        else:
            log.debug("Preview mode: image would be displayed here")

    def _fade_to(self, target: Image.Image, steps=12, delay=0.04):
        """Crossfade from the current display to a new image."""
        # Capture current state as a black image (we don't read back from matrix)
        current = self._solid(BLACK)
        for i in range(1, steps + 1):
            alpha = i / steps
            blended = Image.blend(current, target, alpha)
            self._push(blended)
            time.sleep(delay)

    @staticmethod
    def _solid(colour: tuple) -> Image.Image:
        img = Image.new("RGB", (64, 64), colour)
        return img
