#!/usr/bin/env python3
"""
LED matrix display driver.
Wraps rpi-rgb-led-matrix to show album art and status screens.
Supports live brightness updates from the web UI.
"""

import logging
import time
import base64
import io
import threading
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from config import BRIGHTNESS, GPIO_SLOWDOWN, HARDWARE_MAPPING

log = logging.getLogger(__name__)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DIM   = (40, 40, 40)

_TURNTABLE_GREY  = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAId0lEQVR4nO1ZWU8bSxqt7na723YvxsYsRuaaxcQEQmQwFiEiUZQICSWKIuUH5KflKY95jSAokQhBIewQwhKBWQ02GC9t9+Zeah5q6GFgEgzh3jsz8nnwQ1d11TnfVl+XAaigggoqqKCCCiqooILfBIZhfzeFm8D/ngwMwxBpr9d7zRVulM81EYvFamtrdV2fmJgoFAoQwr90+7N+xzAMP4Vl3V/A4XD09fU9ffoUANDa2jowMAAAwHG8/N1t1+L8L2AYBiFkWRbDMEmSdF3/j/ZDetCQNcFms0WjUV3XNU2LRqMOh2NjY+PshD9dAI7jpmn29vZ6PB5RFCGEaG/TNBVFyefzhUJBFEVZlk3TvPh6b29ve3v76Ojo7Oxsf39/fX39+Pi4zWYzDMNS+ycKQOz7+voMwxgZGXE6ncFg0O/3ezwehmEIghBFUdd1m81GUZTdbi8Wi/F4PJPJQAhVVRUEwefzff/+HQAwNDREEMTOzg4AQNd1tH6ZGq6ZxJbtNU07ODjo6uoyTTOVSh0eHmaz2XMbOxyOurq6UChUW1sry/LGxgZBEC6Xy+fzFYtFQRDW19cfPHiA43g8HlcURRRFURQzmUw5TK4jALGPxWIYhsmy7PV6l5aWTk5Oynm3tbU1EAjMzs4KgtDT09Pd3T07OwsAePny5evXr0ulEsuyNE17PB7TND98+ID2ukkBlu1xHNc0TdO0b9++gdOKjjbz+Xxut5sgCFmWk8mkqqpnRzmOu3///u7ubn9/fyKRUBSF5/mVlRWe5+fn5zVNAwDcu3evubn5zZs3lwq4Wg6g5bq7uyGE29vbzc3Nc3NzBEGYponChqKoWCymadrR0ZGqqjzPt7a2bmxsoPgGABAEIQjC6Ojoq1evMpnM8vLy7u4uGhoYGPB6valUqra21u12r62tgTIq0hUEIPaRSMTpdH7+/Pn58+cfP37EMMwwDGu0o6Njf39/a2srFApFIpG3b98CAJ48eXJwcGAYBoQQTXa73fF4nOO4pqammpoaDMNYlj06OkqlUhDCrq6uycnJcDhcDqtyBZxjT5Jkc3Pzu3fvrAnIVMfHx8FgMJ/PJ5PJQqFA03QgEJAkyTAM0zTtdjvLsm63u76+vrGxcW5u7sePH1VVVaZp5vN5VVUBAO3t7clkMpvNkiR5YwLOsp+YmEDnqyAI4XB4eXkZx3F0AmAYtre3Z5rm7du3IYSaprW1tQmCMD09DSEMBAKBQKCmpoZhmGQy6fV6JUlSVTWZTFq7kCQZDAZHRkZstnIte/m8c+ytrFpfX+d5/s6dOyiJwWkeJxKJRCJBEARBEKVSCT2vra198eLF8PBwqVQaHBw8OTn59OkTGkX6UYr39PSsrq6aphkMBmVZBmWcBpd0HWjdSCTCMMzExARBEBBCVH8kSTo5OTFNc3BwsKmpCQmzKoZhGIgfAABCWCwWd3d3h4aGAoHA4uLi4uIiy7KHh4dWaTJNs7q6mqbp7e1tu93e0tKytLRkjf4Cv/IAUh8Oh2maHh8fR7QQIRzHl5aWHj58mE6n5+bmGhsbW1paZFnO5XK5XA41RQAAm83mdDp5nuc4DkK4sLAwNTXl8/k6OzsnJyd1XUfRiDaKRCLT09MAALfbnc1mVVVFzrnExL8YIwjCMIxnz54ZhoFoCYIgCEKxWEQJBwAIh8M+n29nZyebzVIUxfM8wzB2ux1xghCWSqVCoYBe93g84XC4VCpNTU1pmobmoN9QKMTz/MzMDI7jXq83EAjMzc1deghc4gGkXhCEtbU1CCHP8zzP+/1+xE/TNFmW0+n0wcFBY2NjKBTK5/MnJyf7+/ulUgl5yW63OxwOlmXr6+udTqcgCPPz87lcDvx7cJMkGQqF3r9/b8VhmSXoEgEIqE8uFovHx8fWQ5IkXS4Xy7I8z9M0jdxdV1fX0tKC47iqqpIkFQoFWZaLxWImk9nc3LSchhLJWhydjOvr67qu4zgejUZ9Ph8qDOU0c+WWUYIgSJJUFAU90TQNhfve3p5FhaIomqYZhmEYxuVy2e12iqJQcXQ4HJIkiaJYLBZRIiFACN1uN8dxX79+BQB0dnYSBDE2NiZJ0o0JQBbt6uqKRCK5XE5RlO3t7dXVVYs32glCqCiKoigoQhAoimIYhuM4lmXr6upomsZxXNd15B+UTn19fVNTUxiGORwOv98/PDwMyu6lyxKA0mhlZUUQBLfbXV1dzXEcOPX+uW2sqoJUqaqqqurZRhU10hzHoXRqaGhYWFhAnXMkEkGfB+Xk7hUEAACCweDm5ubm5ubZh4i69eF79nPxrKpzkgzDQKVsf38fcU0kEhiGeTwemqb39vauxP4SAWihmZmZSCQSjUaTySSEEBVTVBZFUdQ07aKv0Vf5zySB029/CCHKE1EU7969Oz8/f3HmbwlAEEVxamrKMIwvX744HA6Xy1VVVfX48eN4PE7TtGmapVJJkqR8Pi8IQqFQUFX1ogmtiwZ4Civ8ZFluaGhQFCWTyVzV/GUJQN53uVxdXV2o8WJZdmFhAVU6iqJYluU4juM4v99PURQAAElCoVIoFCRJukgLOwVBEK2trdPT0+U0DtcRgE7TsbGxlpaWP/74A0KYyWS2traQtVCaptNpaz5JkgzDoPbB5/OhSmoYhiiKqPJks1nrnkJRFDSK6uY1cAM3c+fS9GIQEwSBiinP8y6Xq66uDgCQzWYlSWpra0skEqZpTkxMXMP8V8PZK7dfz0Sx8bPJt27dam9vJwjC6/XW1NSQJPno0aNrX+te4ZOyfAv9rPIgHB0dxWIxiqJyuRxBEB0dHel02urqyufzz2Wv+sKNgCTJQCDgdDoNw0ilUmVeAf234GK0/M7fAn/b9frZI/yvvk+voIIKKqigggoqqKCCCv4/8A8KPSj3kP3R1gAAAABJRU5ErkJggg=="
_TURNTABLE_WHITE = "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"

def _load(b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")


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
        self._turntable_grey  = _load(_TURNTABLE_GREY)
        self._turntable_white = _load(_TURNTABLE_WHITE)
        self._pulse_thread = None
        self._pulsing = False

    def matrix_brightness(self) -> int:
        return self._brightness

    def set_brightness(self, value: int):
        value = max(0, min(100, int(value)))
        if self.matrix:
            self.matrix.brightness = value
        self._brightness = value
        log.info(f"Brightness set to {value}")

    def show_album_art(self, image: Image.Image):
        self._stop_pulse()
        self._fade_to(image)

    def show_startup(self):
        self._stop_pulse()
        self._push(self._turntable_grey)

    def show_idle(self):
        """Sleeping — turntable dimmed."""
        self._stop_pulse()
        self._push(ImageEnhance.Brightness(self._turntable_grey).enhance(0.35))

    def show_listening(self):
        """Listening — white turntable pulsing."""
        self._start_pulse()

    def show_track_text(self, track: dict):
        self._stop_pulse()
        img = self._solid(BLACK)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 8)
        except OSError:
            font = ImageFont.load_default()
        draw.text((2, 20), track.get("artist", "")[:10], font=font, fill=WHITE)
        draw.text((2, 34), track.get("title", "")[:10],  font=font, fill=DIM)
        self._push(img)

    def show_error(self):
        self._stop_pulse()
        self._push(self._solid((60, 0, 0)))
        time.sleep(1)
        self._push(self._solid(BLACK))

    def clear(self):
        self._stop_pulse()
        self._push(self._solid(BLACK))

    def _start_pulse(self):
        if self._pulsing:
            return
        self._pulsing = True
        self._pulse_thread = threading.Thread(target=self._pulse_loop, daemon=True)
        self._pulse_thread.start()

    def _stop_pulse(self):
        self._pulsing = False
        if self._pulse_thread:
            self._pulse_thread.join(timeout=1)
            self._pulse_thread = None

    def _pulse_loop(self):
        """Smoothly pulse the white turntable while _pulsing is True."""
        import math
        step = 0
        while self._pulsing:
            # Sine wave 0.2 -> 1.0 brightness
            factor = 0.2 + 0.8 * (0.5 + 0.5 * math.sin(step * 0.15))
            img = ImageEnhance.Brightness(self._turntable_white).enhance(factor)
            self._push(img)
            time.sleep(0.05)
            step += 1

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
