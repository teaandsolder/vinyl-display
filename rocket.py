#!/usr/bin/env python3
"""
Rocket launch animation for 64x64 LED matrix.
Uses SetPixel to avoid Pillow compatibility issues.
"""

import time
import math
import random
from PIL import Image, ImageDraw
from rgbmatrix import RGBMatrix, RGBMatrixOptions

# Matrix config
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'adafruit-hat'
options.gpio_slowdown = 2
options.brightness = 80
options.drop_privileges = False

matrix = RGBMatrix(options=options)

# Colours
BLACK      = (0, 0, 0)
WHITE      = (255, 255, 255)
RED        = (255, 30, 0)
ORANGE     = (255, 120, 0)
YELLOW     = (255, 220, 0)
LIGHT_BLUE = (100, 180, 255)
GREY       = (160, 160, 160)
DARK_GREY  = (80, 80, 80)
STAR       = (200, 200, 255)


def push_pixels(canvas, img):
    """Push a PIL image to the matrix pixel by pixel."""
    pixels = img.load()
    for y in range(64):
        for x in range(64):
            r, g, b = pixels[x, y]
            canvas.SetPixel(x, y, r, g, b)


def make_frame(rocket_y, frame, stars):
    img = Image.new("RGB", (64, 64), BLACK)
    draw = ImageDraw.Draw(img)

    # Stars
    for sx, sy in stars:
        draw.point((sx, sy), fill=STAR)

    rx = 29
    ry = rocket_y

    # Nose cone
    draw.polygon([(rx + 2, ry), (rx, ry + 4), (rx + 4, ry + 4)], fill=WHITE)

    # Body
    draw.rectangle([rx, ry + 4, rx + 4, ry + 11], fill=GREY)

    # Window
    draw.ellipse([rx + 1, ry + 5, rx + 3, ry + 7], fill=LIGHT_BLUE)

    # Fins
    draw.polygon([(rx, ry + 9), (rx - 3, ry + 13), (rx, ry + 12)], fill=DARK_GREY)
    draw.polygon([(rx + 4, ry + 9), (rx + 7, ry + 13), (rx + 4, ry + 12)], fill=DARK_GREY)

    # Flame
    if frame % 3 == 0:
        flame_col, flame_h = YELLOW, 6
    elif frame % 3 == 1:
        flame_col, flame_h = ORANGE, 8
    else:
        flame_col, flame_h = RED, 5

    draw.polygon([(rx + 1, ry + 12), (rx + 3, ry + 12), (rx + 2, ry + 12 + flame_h)], fill=flame_col)

    return img


def make_explosion(cx, cy, radius):
    img = Image.new("RGB", (64, 64), BLACK)
    draw = ImageDraw.Draw(img)
    colours = [RED, ORANGE, YELLOW, WHITE]
    for i, col in enumerate(colours):
        r = radius - i * 3
        if r > 0:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col)
    random.seed(radius)
    for _ in range(20):
        angle = random.uniform(0, 6.28)
        dist = random.uniform(0, radius + 5)
        sx = int(cx + dist * math.cos(angle))
        sy = int(cy + dist * math.sin(angle))
        if 0 <= sx < 64 and 0 <= sy < 64:
            draw.point((sx, sy), fill=YELLOW)
    return img


def run():
    stars = [(random.randint(0, 63), random.randint(0, 63)) for _ in range(40)]
    canvas = matrix.CreateFrameCanvas()

    # Phase 1: Rocket on launchpad
    for f in range(20):
        img = make_frame(45, f, stars)
        draw = ImageDraw.Draw(img)
        draw.rectangle([24, 58, 39, 60], fill=DARK_GREY)
        draw.rectangle([20, 60, 43, 62], fill=GREY)
        push_pixels(canvas, img)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(0.05)

    # Countdown flash
    for _ in range(3):
        img = Image.new("RGB", (64, 64), (30, 0, 0))
        push_pixels(canvas, img)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(0.1)
        img = Image.new("RGB", (64, 64), BLACK)
        push_pixels(canvas, img)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(0.1)

    # Phase 2: Liftoff
    for frame in range(60):
        rocket_y = 45 - frame
        if rocket_y < -15:
            break
        img = make_frame(rocket_y, frame, stars)
        push_pixels(canvas, img)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(0.04)

    # Phase 3: Explosion
    for radius in range(2, 30, 2):
        img = make_explosion(31, 10, radius)
        push_pixels(canvas, img)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(0.05)

    # Fade out
    for brightness in range(100, 0, -5):
        img = make_explosion(31, 10, 28)
        img = img.point(lambda p: int(p * brightness / 100))
        push_pixels(canvas, img)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(0.03)

    # Clear
    push_pixels(canvas, Image.new("RGB", (64, 64), BLACK))
    canvas = matrix.SwapOnVSync(canvas)


if __name__ == "__main__":
    while True:
        run()
