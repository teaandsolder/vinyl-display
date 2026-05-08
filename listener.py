#!/usr/bin/env python3
"""
Audio capture from Rega Fono Mini A2D USB interface.
Records a short clip and returns raw WAV bytes for identification.
"""

import io
import wave
import logging
import sounddevice as sd
import numpy as np

# RMS amplitude below this value is treated as silence.
# With a clean digital source the noise floor is near-zero,
# so any small value works. Raise it slightly if you get
# false triggers from turntable hum between tracks.
SILENCE_THRESHOLD = 200

log = logging.getLogger(__name__)

# The Rega enumerates as a standard USB audio device.
# Leave DEVICE_NAME as None to use the system default,
# or set it to match the device name shown by: python3 -m sounddevice
DEVICE_NAME = "CODEC"   # partial match is fine; set None to use default

SAMPLE_RATE = 44100
CHANNELS = 2


def find_device(name):
    """Find a sounddevice input device by partial name match."""
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if name.lower() in dev["name"].lower() and dev["max_input_channels"] > 0:
            log.info(f"Found audio device [{i}]: {dev['name']}")
            return i
    return None


class AudioListener:
    def __init__(self, capture_seconds=8):
        self.capture_seconds = capture_seconds
        if DEVICE_NAME:
            self.device = find_device(DEVICE_NAME)
            if self.device is None:
                log.error(
                    f"Audio device '{DEVICE_NAME}' not found. "
                    f"Is the Rega plugged in? "
                    f"Run 'arecord -l' to see available devices."
                )
                raise SystemExit(1)
        else:
            self.device = None

    def capture(self):
        """
        Record audio and return raw WAV bytes.
        """
        frames = int(SAMPLE_RATE * self.capture_seconds)
        log.info(f"Recording {self.capture_seconds}s from device: {self.device or 'default'}")

        audio = sd.rec(
            frames,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            device=self.device,
            blocking=True
        )

        return self._to_wav_bytes(audio)

    def get_rms(self, wav_bytes: bytes) -> float:
        """Return the RMS amplitude of the audio clip."""
        audio = np.frombuffer(wav_bytes, dtype=np.int16)
        return float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))

    def is_silence(self, wav_bytes: bytes) -> bool:
        """Return True if the audio clip is below the silence threshold."""
        rms = self.get_rms(wav_bytes)
        log.debug(f"RMS amplitude: {rms:.1f} (threshold: {SILENCE_THRESHOLD})")
        return rms < SILENCE_THRESHOLD

    def _to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Convert numpy audio array to WAV bytes."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        buf.seek(0)
        return buf.read()
