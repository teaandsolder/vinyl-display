#!/usr/bin/env python3
"""
LED matrix display driver.
Wraps rpi-rgb-led-matrix to show album art and status screens.
Supports live brightness updates from the web UI.
"""

import logging
import time
from PIL import Image, ImageDraw, ImageFont
from config import BRIGHTNESS, GPIO_SLOWDOWN, HARDWARE_MAPPING

log = logging.getLogger(__name__)

BLACK  = (0, 0, 0)
WHITE  = (255, 255, 255)
DIM    = (40, 40, 40)
ACCENT = (180, 60, 60)


def _make_matrix():
    try:
        from rgbmatrix import RGBMatrix, RGBMatrixOptions
        opts = RGBMatrixOptions()
        opts.rows = 64
        opts.cols = 64
        opts.chain_length = 1
        opts.parallel = 1
        opts.hardware_mapping = HARDWARE_MAPPING
        opts.brightness = BRIGHTNESS
        opts.gpio_slowdown = GPIO_SLOWDOWN
        opts.drop_privileges = False
        return RGBMatrix(options=opts)
    except ImportError:
        log.warning("rgbmatrix not available — running in preview mode")
        return None


class MatrixDisplay:
    def __init__(self):
        self.matrix = _make_matrix()
        self.canvas = self.matrix.CreateFrameCanvas() if self.matrix else None
        self._brightness = BRIGHTNESS

    def matrix_brightness(self) -> int:
        return self._brightness

    def set_brightness(self, value: int):
        value = max(0, min(100, int(value)))
        if self.matrix:
            self.matrix.brightness = value
        self._brightness = value
        log.info(f"Brightness set to {value}")

    def show_album_art(self, image: Image.Image):
        self._fade_to(image)

    def show_startup(self):
        img = self._solid(BLACK)
        draw = ImageDraw.Draw(img)
        draw.rectangle([28, 20, 36, 44], fill=ACCENT)
        draw.ellipse([26, 28, 38, 36], fill=BLACK)
        draw.ellipse([30, 30, 34, 34], fill=ACCENT)
        self._push(img)

    def show_idle(self):
        img = self._solid(BLACK)
        draw = ImageDraw.Draw(img)
        for i, x in enumerate([26, 31, 36]):
            brightness = 60 + i * 30
            draw.ellipse([x, 30, x+4, 34], fill=(brightness, brightness, brightness))
        self._push(img)

    def show_track_text(self, track: dict):
        img = self._solid(BLACK)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 8)
        except OSError:
            font = ImageFont.load_default()
        draw.text((2, 20), track.get("artist", "")[:10], font=font, fill=WHITE)
        draw.text((2, 34), track.get("title", "")[:10], font=font, fill=DIM)
        self._push(img)

    def show_error(self):
        self._push(self._solid((60, 0, 0)))
        time.sleep(1)
        self._push(self._solid(BLACK))

    def clear(self):
        self._push(self._solid(BLACK))

    def _push(self, image: Image.Image):
        if self.matrix and self.canvas:
            self.canvas.SetImage(image.convert("RGB"))
            self.canvas = self.matrix.SwapOnVSync(self.canvas)
        else:
            log.debug("Preview mode: image would be displayed here")

    def _fade_to(self, target: Image.Image, steps=12, delay=0.04):
        current = self._solid(BLACK)
        for i in range(1, steps + 1):
            self._push(Image.blend(current, target, i / steps))
            time.sleep(delay)

    @staticmethod
    def _solid(colour: tuple) -> Image.Image:
        return Image.new("RGB", (64, 64), colour)
