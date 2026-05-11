# config.py — User settings for Vinyl Display
# Edit this file to configure the system for your setup.

# ------------------------------------------------------------------ #
# Audio                                                               #
# ------------------------------------------------------------------ #

# Partial name of your USB audio device.
# Run 'arecord -l' to see available devices.
# Set to None to use the system default input.
DEVICE_NAME = "CODEC"

# Seconds of audio to capture for each identification attempt.
# ShazamIO works best with 10 seconds.
CAPTURE_SECONDS = 10

# Seconds to wait after signal is detected before capturing.
# Lets the music settle past quiet intros and needle crackle.
SETTLE_SECONDS = 3


# ------------------------------------------------------------------ #
# Signal threshold                                                    #
# ------------------------------------------------------------------ #

# RMS below this = no signal (needle lifted or run-out groove).
# Run-out groove reads 65-130. Music reads 200+.
# 150 sits cleanly between the two.
SIGNAL_THRESHOLD = 150

# How many consecutive low readings before declaring the side ended.
# 2 = ~60 seconds of sustained quiet.
SIDE_END_CONSECUTIVE = 2

# Seconds between RMS checks when no record is playing.
SLEEP_POLL_INTERVAL = 3

# Seconds between re-identification polls when a record is playing.
PLAYING_POLL_INTERVAL = 30


# ------------------------------------------------------------------ #
# Display                                                             #
# ------------------------------------------------------------------ #

# LED matrix brightness (0-100).
BRIGHTNESS = 50

# GPIO slowdown for the Pi.
# Pi 3B with adafruit-hat-pwm: 2
# Pi 4: try 4
GPIO_SLOWDOWN = 2

# Hardware mapping for your bonnet.
# Adafruit RGB Matrix Bonnet with PWM quality mod: "adafruit-hat-pwm"
# Adafruit RGB Matrix Bonnet without PWM mod: "adafruit-hat"
HARDWARE_MAPPING = "adafruit-hat-pwm"

# Saturation adjustment (1.0 = unchanged, 0.8 = slightly muted).
SATURATION = 0.8
