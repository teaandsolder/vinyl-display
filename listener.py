#!/usr/bin/env python3
"""
Audio capture from Rega Fono Mini A2D USB interface.
Captures mono at 16kHz — matches ShazamIO's internal format,
minimising DMA load and reducing matrix PWM interference.
"""

import io
import wave
import logging
import sounddevice as sd
import numpy as np

log = logging.getLogger(__name__)

DEVICE_NAME = "CODEC"   # partial match; set None to use system default
SAMPLE_RATE = 16000     # ShazamIO downmixes to 16kHz internally anyway
CHANNELS    = 1         # mono — halves DMA bandwidth vs stereo


def find_device(name):
    """Find a sounddevice input device by partial name match."""
    for i, dev in enumerate(sd.query_devices()):
        if name.lower() in dev["name"].lower() and dev["max_input_channels"] > 0:
            log.info(f"Found audio device [{i}]: {dev['name']}")
            return i
    return None


class AudioListener:
    def __init__(self, capture_seconds=10):
        self.capture_seconds = capture_seconds
        if DEVICE_NAME:
            self.device = find_device(DEVICE_NAME)
            if self.device is None:
                log.error(
                    f"Audio device '{DEVICE_NAME}' not found. "
                    f"Is the Rega plugged in? Run 'arecord -l' to list devices."
                )
                raise SystemExit(1)
        else:
            self.device = None

    def capture(self) -> bytes:
        """Record audio and return WAV bytes for identification."""
        frames = int(SAMPLE_RATE * self.capture_seconds)
        log.info(f"Recording {self.capture_seconds}s from device: {self.device or 'default'}")
        audio = sd.rec(frames, samplerate=SAMPLE_RATE, channels=CHANNELS,
                       dtype="int16", device=self.device, blocking=True)
        return self._to_wav_bytes(audio)

    def quick_rms(self) -> float:
        """Record 1 second and return RMS — lightweight signal check."""
        audio = sd.rec(SAMPLE_RATE, samplerate=SAMPLE_RATE, channels=CHANNELS,
                       dtype="int16", device=self.device, blocking=True)
        return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))

    def _to_wav_bytes(self, audio: np.ndarray) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        buf.seek(0)
        return buf.read()
