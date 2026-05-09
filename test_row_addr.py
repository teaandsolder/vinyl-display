#!/usr/bin/env python3
"""
Cycles through row_address_type values 0-4
showing a solid red screen for 4 seconds each.
Watch which one has no banding.
"""

import time
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image

for row_addr in range(5):
    print(f"Testing row_address_type = {row_addr}")

    options = RGBMatrixOptions()
    options.rows = 64
    options.cols = 64
    options.hardware_mapping = 'adafruit-hat'
    options.gpio_slowdown = 2
    options.row_address_type = row_addr
    options.drop_privileges = False

    try:
        matrix = RGBMatrix(options=options)
        img = Image.new('RGB', (64, 64), (255, 0, 0))
        canvas = matrix.CreateFrameCanvas()
        canvas.SetImage(img)
        matrix.SwapOnVSync(canvas)
        time.sleep(4)
        del matrix
    except Exception as e:
        print(f"  Error: {e}")

print("Done — which value had no banding?")
