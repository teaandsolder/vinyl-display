#!/usr/bin/env python3
"""
Shared state between the main vinyl display loop and the Flask web server.
Thread-safe access via a simple lock.

Three playback states:
  sleeping  — no signal, idle screen
  listening — signal detected, trying to identify, no match yet
  playing   — identified, artwork showing
"""

import threading
from dataclasses import dataclass, field

LOG_BUFFER_SIZE = 150


@dataclass
class VinylState:
    playing: bool = False
    listening: bool = False
    artist: str = ""
    title: str = ""
    album: str = ""
    current_artwork_url: str = ""
    preferred_artwork_url: str = ""
    artwork_candidates: list = field(default_factory=list)
    brightness: int = 50
    saturation: float = 0.8
    gamma: float = 1.0
    next_identify_in: int = 30
    log_buffer: list = field(default_factory=list)


class SharedState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = VinylState()

    def get(self) -> VinylState:
        with self._lock:
            return self._state

    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self._state, k, v)

    def add_artwork_candidate(self, url: str, source: str, label: str):
        with self._lock:
            urls = [c["url"] for c in self._state.artwork_candidates]
            if url not in urls:
                self._state.artwork_candidates.append({
                    "url": url, "source": source, "label": label
                })

    def clear_candidates(self):
        with self._lock:
            self._state.artwork_candidates = []

    def append_log(self, level: str, message: str, timestamp: str):
        with self._lock:
            self._state.log_buffer.append({
                "level": level,
                "message": message,
                "ts": timestamp,
            })
            if len(self._state.log_buffer) > LOG_BUFFER_SIZE:
                self._state.log_buffer = self._state.log_buffer[-LOG_BUFFER_SIZE:]


state = SharedState()
