#!/usr/bin/env python3
"""
Diagnostic test screen for 64x64 LED matrix.
Divides the screen into coloured zones to identify any dead areas.
"""

import time
from rgbmatrix import RGBMatrix, RGBMatrixOptions

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
canvas = matrix.CreateFrameCanvas()

# Draw coloured zones
for y in range(64):
    for x in range(64):
        # Quadrants
        if x < 32 and y < 32:
            canvas.SetPixel(x, y, 255, 0, 0)      # Top left — Red
        elif x >= 32 and y < 32:
            canvas.SetPixel(x, y, 0, 255, 0)      # Top right — Green
        elif x < 32 and y >= 32:
            canvas.SetPixel(x, y, 0, 0, 255)      # Bottom left — Blue
        else:
            canvas.SetPixel(x, y, 255, 255, 0)    # Bottom right — Yellow

# Draw white border
for x in range(64):
    canvas.SetPixel(x, 0, 255, 255, 255)
    canvas.SetPixel(x, 63, 255, 255, 255)
for y in range(64):
    canvas.SetPixel(0, y, 255, 255, 255)
    canvas.SetPixel(63, y, 255, 255, 255)

# Draw white cross in centre
for x in range(64):
    canvas.SetPixel(x, 32, 255, 255, 255)
for y in range(64):
    canvas.SetPixel(32, y, 255, 255, 255)

canvas = matrix.SwapOnVSync(canvas)

print("Test screen displayed. Press Ctrl+C to exit.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
