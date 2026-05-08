#!/usr/bin/env python3
"""
Vinyl Display - Album art on a 64x64 LED matrix
Listens via Rega Fono Mini A2D USB, identifies via AudD, displays via rpi-rgb-led-matrix
"""

import time
import logging
import signal
import sys
from display import MatrixDisplay
from listener import AudioListener
from identifier import TrackIdentifier
from art import AlbumArtFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# How often to poll (seconds)
POLL_INTERVAL = 30

# How many seconds of audio to capture per attempt
CAPTURE_SECONDS = 8

# RMS threshold for "no record playing" (digital source = near zero noise floor)
SILENCE_THRESHOLD = 200

# RMS threshold for "side has ended" — higher to account for crackle and run-out groove
SIDE_END_THRESHOLD = 800

# How many consecutive low-RMS readings before we declare the side finished
SIDE_END_CONSECUTIVE = 3


def main():
    display = MatrixDisplay()
    listener = AudioListener(capture_seconds=CAPTURE_SECONDS)
    identifier = TrackIdentifier()
    art_fetcher = AlbumArtFetcher()

    current_track = None
    side_end_counter = 0
    watching_for_side_end = False

    def shutdown(sig, frame):
        log.info("Shutting down...")
        display.clear()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    display.show_startup()
    log.info("Vinyl Display started. Listening...")

    while True:
        try:
            log.info("Capturing audio...")
            audio_data = listener.capture()
            rms = listener.get_rms(audio_data)
            log.info(f"RMS level: {rms:.1f}")

            # ---------------------------------------------------------- #
            # MODE 1: Watching for side end after a successful ID         #
            # ---------------------------------------------------------- #
            if watching_for_side_end:
                if rms < SIDE_END_THRESHOLD:
                    side_end_counter += 1
                    log.info(f"Low signal — side end counter: {side_end_counter}/{SIDE_END_CONSECUTIVE}")
                    if side_end_counter >= SIDE_END_CONSECUTIVE:
                        log.info("Side ended — resetting, ready for next record.")
                        current_track = None
                        watching_for_side_end = False
                        side_end_counter = 0
                        display.show_idle()
                else:
                    if side_end_counter > 0:
                        log.info("Signal recovered — resetting side end counter.")
                    side_end_counter = 0

                time.sleep(POLL_INTERVAL)
                continue

            # ---------------------------------------------------------- #
            # MODE 2: Listening for a new record                          #
            # ---------------------------------------------------------- #
            if rms < SILENCE_THRESHOLD:
                log.info("Silence detected — no record playing.")
                if current_track is not None:
                    current_track = None
                    display.show_idle()
                time.sleep(POLL_INTERVAL)
                continue

            log.info("Identifying track...")
            track = identifier.identify(audio_data)

            if track is None:
                log.info("No track identified — will retry next poll.")
                display.show_idle()

            elif track != current_track:
                log.info(f"New track: {track['artist']} - {track['title']} ({track['album']})")
                current_track = track
                watching_for_side_end = True
                side_end_counter = 0
                image = art_fetcher.fetch(track)
                if image:
                    display.show_album_art(image)
                else:
                    display.show_track_text(track)

            else:
                log.info(f"Same track still playing: {track['title']}")

        except Exception as e:
            log.error(f"Error in main loop: {e}", exc_info=True)
            display.show_error()

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
