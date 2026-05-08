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

# How often to poll RMS when no record is playing (seconds) — fast so needle drop feels instant
SLEEP_POLL_INTERVAL = 3

# How often to poll RMS when watching for side end (seconds)
SIDE_END_POLL_INTERVAL = 15

# How many seconds of audio to capture per identification attempt
CAPTURE_SECONDS = 10

# How long to wait after signal detected before capturing — lets music settle past intro/crackle
SETTLE_SECONDS = 3

# How many identification attempts before giving up on a side
MAX_ID_ATTEMPTS = 3

# How long to wait between identification retries (seconds)
RETRY_INTERVAL = 8

# RMS threshold for "no record playing" (digital source = near zero noise floor)
SILENCE_THRESHOLD = 200

# RMS threshold for "side has ended" — higher to account for crackle and run-out groove
SIDE_END_THRESHOLD = 600

# How many consecutive low-RMS readings before we declare the side finished
SIDE_END_CONSECUTIVE = 4


def identify_with_retries(listener, identifier, max_attempts, retry_interval):
    """
    Attempt identification up to max_attempts times.
    Waits retry_interval seconds between attempts.
    Returns a track dict on success, or None if all attempts fail.
    """
    for attempt in range(1, max_attempts + 1):
        log.info(f"Identification attempt {attempt}/{max_attempts}...")
        audio_data = listener.capture()
        track = identifier.identify(audio_data)
        if track:
            return track
        if attempt < max_attempts:
            log.info(f"No match — retrying in {retry_interval}s...")
            time.sleep(retry_interval)
    log.info("All identification attempts failed — will retry next wake cycle.")
    return None


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
            # ---------------------------------------------------------- #
            # MODE 1: Watching for side end after a successful ID         #
            # ---------------------------------------------------------- #
            if watching_for_side_end:
                time.sleep(SIDE_END_POLL_INTERVAL)
                audio_data = listener.capture()
                rms = listener.get_rms(audio_data)
                log.info(f"RMS level: {rms:.1f}")

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
                continue

            # ---------------------------------------------------------- #
            # MODE 2: Sleep phase — fast RMS polling, no API calls        #
            # ---------------------------------------------------------- #
            audio_data = listener.capture()
            rms = listener.get_rms(audio_data)

            if rms < SILENCE_THRESHOLD:
                log.debug(f"Silence — RMS: {rms:.1f}")
                time.sleep(SLEEP_POLL_INTERVAL)
                continue

            # Signal detected


            # ---------------------------------------------------------- #
            # MODE 3: Signal detected — settle then identify              #
            # ---------------------------------------------------------- #
            log.info(f"Signal detected — RMS: {rms:.1f}. Settling for {SETTLE_SECONDS}s...")
            time.sleep(SETTLE_SECONDS)

            track = identify_with_retries(listener, identifier, MAX_ID_ATTEMPTS, RETRY_INTERVAL)

            if track is None:
                log.info("Could not identify track — returning to sleep.")
                time.sleep(SLEEP_POLL_INTERVAL)

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
                watching_for_side_end = True

        except Exception as e:
            log.error(f"Error in main loop: {e}", exc_info=True)
            display.show_error()
            time.sleep(SLEEP_POLL_INTERVAL)


if __name__ == "__main__":
    main()

