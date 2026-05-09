#!/usr/bin/env python3
"""
Vinyl Display — Album art on a 64x64 LED matrix.
Listens via Rega Fono Mini A2D USB, identifies via ShazamIO,
resolves album via MusicBrainz, displays via rpi-rgb-led-matrix.
"""

import time
import logging
import signal
import sys
from display import MatrixDisplay
from listener import AudioListener
from identifier import TrackIdentifier
from art import AlbumArtFetcher
from album_resolver import AlbumResolver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

SLEEP_POLL_INTERVAL  = 3    # seconds between RMS checks when idle
PLAYING_POLL_INTERVAL = 30  # seconds between re-identification when playing
CAPTURE_SECONDS      = 10   # seconds of audio to capture
SETTLE_SECONDS       = 3    # seconds to wait after signal detected
SIGNAL_THRESHOLD     = 150  # RMS below this = no signal
SIDE_END_CONSECUTIVE = 2    # consecutive low readings before side-end reset


def identify(listener, identifier):
    """Single identification attempt. Returns track dict or None."""
    log.info("Identifying...")
    return identifier.identify(listener.capture())


def reset_side(resolver, display):
    """Reset all side state."""
    resolver.reset()
    display.show_idle()
    return None, None, None  # current_track, current_artwork, current_mbid


def main():
    display   = MatrixDisplay()
    listener  = AudioListener(capture_seconds=CAPTURE_SECONDS)
    identifier = TrackIdentifier()
    art_fetcher = AlbumArtFetcher()
    resolver  = AlbumResolver()

    current_track   = None
    current_artwork = None
    current_mbid    = None   # last MBID used for artwork — skip re-download if unchanged
    low_count       = 0
    playing         = False

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
            # PLAYING                                                      #
            # ---------------------------------------------------------- #
            if playing:
                time.sleep(PLAYING_POLL_INTERVAL)
                rms = listener.quick_rms()
                log.info(f"RMS: {rms:.1f}")

                if rms < SIGNAL_THRESHOLD:
                    low_count += 1
                    log.info(f"Low signal {low_count}/{SIDE_END_CONSECUTIVE}")
                    if low_count >= SIDE_END_CONSECUTIVE:
                        log.info("Side ended — resetting.")
                        playing = False
                        low_count = 0
                        current_track, current_artwork, current_mbid = reset_side(resolver, display)
                    continue

                low_count = 0

                track = identify(listener, identifier)
                if not track:
                    continue

                # New artist = new record, reset resolver
                if current_track and track["artist"] != current_track["artist"]:
                    log.info(f"New artist: {track['artist']} — resetting resolver")
                    resolver.reset()
                    current_mbid = None

                best_album = resolver.add_track(track["artist"], track["title"])

                if track != current_track:
                    log.info(f"Track: {track['artist']} - {track['title']}")
                    current_track = track
                    # Fetch artwork — use resolver if confident, else ShazamIO URL
                    if best_album and best_album.get("mbid") and best_album["mbid"] != current_mbid:
                        log.info(f"Resolver: {best_album['title']} ({best_album['confidence']:.0%})")
                        image = art_fetcher.fetch_by_mbid(best_album["mbid"], fallback_track=track)
                        if image:
                            current_artwork = image
                            current_mbid = best_album["mbid"]
                            display.show_album_art(image)
                    else:
                        image = art_fetcher.fetch(track)
                        if image:
                            current_artwork = image
                            display.show_album_art(image)
                    if not current_artwork:
                        display.show_track_text(track)

                elif best_album and best_album.get("mbid") and best_album["mbid"] != current_mbid:
                    # Same track but resolver now confident with a different album — update artwork
                    log.info(f"Resolver updated: {best_album['title']} ({best_album['confidence']:.0%})")
                    image = art_fetcher.fetch_by_mbid(best_album["mbid"], fallback_track=current_track)
                    if image:
                        current_artwork = image
                        current_mbid = best_album["mbid"]
                        display.show_album_art(image)
                else:
                    log.info(f"Same track: {current_track['title']}")

                continue

            # ---------------------------------------------------------- #
            # SLEEPING                                                     #
            # ---------------------------------------------------------- #
            rms = listener.quick_rms()

            if rms < SIGNAL_THRESHOLD:
                log.debug(f"Silence — RMS: {rms:.1f}")
                time.sleep(SLEEP_POLL_INTERVAL)
                continue

            log.info(f"Signal detected — RMS: {rms:.1f}. Settling {SETTLE_SECONDS}s...")
            time.sleep(SETTLE_SECONDS)

            track = identify(listener, identifier)
            if not track:
                log.info("No match — back to sleep.")
                continue

            log.info(f"New track: {track['artist']} - {track['title']}")
            current_track = track
            playing = True
            low_count = 0
            current_mbid = None
            resolver.reset()
            resolver.add_track(track["artist"], track["title"])

            image = art_fetcher.fetch(track)
            if image:
                current_artwork = image
                display.show_album_art(image)
            else:
                display.show_track_text(track)

        except Exception as e:
            log.error(f"Error: {e}", exc_info=True)
            display.show_error()
            time.sleep(SLEEP_POLL_INTERVAL)


if __name__ == "__main__":
    main()
