#!/usr/bin/env python3
"""
Vinyl Display — Album art on a 64x64 LED matrix.
Listens via Rega Fono Mini A2D USB, identifies via ShazamIO,
displays via rpi-rgb-led-matrix.
Web interface at http://raspberrypi3b.local:5000
"""

import time
import logging
import signal
import sys
import json
import os
import hashlib
from PIL import Image as PILImage
from display import MatrixDisplay
from listener import AudioListener
from identifier import TrackIdentifier
from art import AlbumArtFetcher
from server import start_server
from state import state
import stats as vstats
from config import (
    CAPTURE_SECONDS, SETTLE_SECONDS,
    SIGNAL_THRESHOLD,
    SLEEP_POLL_INTERVAL, PLAYING_POLL_INTERVAL,
    BRIGHTNESS, SATURATION, GAMMA
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

PREF_FILE  = os.path.expanduser("~/.vinyl-display/preferences.json")
COVERS_DIR = os.path.expanduser("~/vinyl-display-covers")


def _ensure_dirs():
    os.makedirs(os.path.dirname(PREF_FILE), exist_ok=True)
    os.makedirs(COVERS_DIR, exist_ok=True)


def _load_prefs() -> dict:
    _ensure_dirs()
    if os.path.exists(PREF_FILE):
        try:
            with open(PREF_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_pref(artist: str, title: str, local_path: str):
    if not local_path:
        log.warning(f"Attempted to save empty path for: {artist} - {title}")
        return
    prefs = _load_prefs()
    key = f"{artist.lower().strip()}|{title.lower().strip()}"
    prefs[key] = local_path
    with open(PREF_FILE, "w") as f:
        json.dump(prefs, f, indent=2)
    log.info(f"Saved preference for: {artist} - {title}")


def _get_pref(artist: str, title: str) -> str | None:
    key = f"{artist.lower().strip()}|{title.lower().strip()}"
    return _load_prefs().get(key)


def _save_cover(image, source_url: str) -> str | None:
    """Save a PIL image to the covers folder. Returns local path or None."""
    if image is None:
        return None
    _ensure_dirs()
    url_hash = hashlib.md5(source_url.encode()).hexdigest()[:12]
    path = os.path.join(COVERS_DIR, f"{url_hash}.jpg")
    if not os.path.exists(path):
        image.save(path, "JPEG", quality=95)
        log.info(f"Saved cover: {path}")
    return path


def _apply_selection(selected_url, art_fetcher):
    """
    Load and process a selected artwork URL (local /covers/ or remote).
    Returns (matrix_img, full_img, local_path, resolved_url).
    """
    if selected_url.startswith("/covers/"):
        filename = selected_url.replace("/covers/", "")
        local_path = os.path.join(COVERS_DIR, filename)
        if os.path.exists(local_path):
            full_img = PILImage.open(local_path).convert("RGB")
            matrix_img = art_fetcher._for_matrix(full_img)
            return matrix_img, full_img, local_path, selected_url
        return None, None, None, selected_url
    else:
        matrix_img, full_img = art_fetcher.fetch_url(selected_url)
        local_path = _save_cover(full_img, selected_url) if full_img else None
        resolved_url = f"/covers/{os.path.basename(local_path)}" if local_path else selected_url
        return matrix_img, full_img, local_path, resolved_url


def identify(listener, identifier):
    log.info("Identifying...")
    return identifier.identify(listener.capture())


def main():
    display     = MatrixDisplay()
    listener    = AudioListener(capture_seconds=CAPTURE_SECONDS)
    identifier  = TrackIdentifier()
    art_fetcher = AlbumArtFetcher()

    state.update(brightness=BRIGHTNESS, saturation=SATURATION, gamma=GAMMA)
    start_server()

    current_track        = None
    current_artwork      = None
    current_artwork_full = None
    playing              = False
    last_saturation      = SATURATION
    last_gamma           = GAMMA
    side_start_time      = None
    last_artist          = None

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
            s = state.get()

            # Live brightness update
            if s.brightness != display.matrix_brightness():
                display.set_brightness(s.brightness)

            # Live saturation/gamma update — reprocess from full res source
            if current_artwork_full and (s.saturation != last_saturation or s.gamma != last_gamma):
                display.show_album_art(art_fetcher._for_matrix(current_artwork_full))
                last_saturation = s.saturation
                last_gamma = s.gamma

            # ---------------------------------------------------------- #
            # PLAYING                                                      #
            # ---------------------------------------------------------- #
            if playing:
                # Sleep in 1s chunks to catch web UI artwork selections quickly
                for i in range(PLAYING_POLL_INTERVAL):
                    time.sleep(1)
                    state.update(next_identify_in=PLAYING_POLL_INTERVAL - i)
                    s = state.get()
                    if s.preferred_artwork_url and s.preferred_artwork_url != s.current_artwork_url:
                        matrix_img, full_img, local_path, resolved_url = _apply_selection(
                            s.preferred_artwork_url, art_fetcher
                        )
                        if matrix_img:
                            current_artwork = matrix_img
                            current_artwork_full = full_img
                            display.show_album_art(matrix_img)
                        state.update(current_artwork_url=resolved_url, preferred_artwork_url="")
                        if current_track and local_path:
                            _save_pref(current_track["artist"], current_track["title"], local_path)
                        break

                rms = listener.quick_rms()
                log.info(f"RMS: {rms:.1f}")

                if rms < SIGNAL_THRESHOLD:
                    log.info(f"Low signal — RMS: {rms:.1f}")
                    time.sleep(5)
                    rms2 = listener.quick_rms()
                    log.info(f"Recheck 1 — RMS: {rms2:.1f}")

                    if rms2 >= SIGNAL_THRESHOLD:
                        log.info("Signal recovered")
                        continue

                    if rms2 >= 50:
                        # Run-out groove — wait longer to confirm
                        time.sleep(25)
                        rms3 = listener.quick_rms()
                        log.info(f"Recheck 2 — RMS: {rms3:.1f}")
                        if rms3 >= SIGNAL_THRESHOLD:
                            log.info("Signal recovered")
                            continue

                    log.info("Side ended — resetting.")
                    if side_start_time:
                        vstats.record_side_duration(time.time() - side_start_time)
                    playing = False
                    side_start_time = None
                    last_artist = None
                    current_track = None
                    current_artwork = None
                    current_artwork_full = None
                    state.update(playing=False, artist="", title="", album="",
                                current_artwork_url="", preferred_artwork_url="")
                    state.clear_candidates()
                    display.show_idle()
                    continue

                track = identify(listener, identifier)
                if not track:
                    continue

                # Web UI selection made during identification
                s = state.get()
                if s.preferred_artwork_url and s.preferred_artwork_url != s.current_artwork_url:
                    matrix_img, full_img, local_path, resolved_url = _apply_selection(
                        s.preferred_artwork_url, art_fetcher
                    )
                    if matrix_img:
                        current_artwork = matrix_img
                        current_artwork_full = full_img
                        display.show_album_art(matrix_img)
                    state.update(current_artwork_url=resolved_url, preferred_artwork_url="")
                    if current_track and local_path:
                        _save_pref(current_track["artist"], current_track["title"], local_path)
                    continue

                if track != current_track:
                    log.info(f"Track: {track['artist']} - {track['title']}")
                    current_track = track
                    state.update(
                        artist=track["artist"],
                        title=track["title"],
                        album=track.get("album", ""),
                        preferred_artwork_url=""
                    )

                    # Record artist change in history
                    if track["artist"] != last_artist:
                        last_artist = track["artist"]
                        vstats.record_artist_change(
                            track["artist"], track["title"],
                            state.get().current_artwork_url
                        )

                    # Same artist = same record = keep current artwork
                    if current_artwork and track["artist"] == last_artist:
                        log.info(f"Same artist — keeping artwork for: {track['title']}")
                        continue

                    _fetch_and_show(track, art_fetcher, display,
                                    current_artwork, current_artwork_full)
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
            side_start_time = time.time()
            vstats.record_needle_drop()
            state.clear_candidates()
            state.update(
                playing=True,
                artist=track["artist"],
                title=track["title"],
                album=track.get("album", ""),
                current_artwork_url="",
                preferred_artwork_url=""
            )

            current_artwork, current_artwork_full = _fetch_and_show(
                track, art_fetcher, display, None, None
            )

        except Exception as e:
            log.error(f"Error: {e}", exc_info=True)
            display.show_error()
            time.sleep(SLEEP_POLL_INTERVAL)


def _fetch_and_show(track, art_fetcher, display, current_artwork, current_artwork_full):
    """Fetch artwork for a track (checking preferences first) and display it."""
    if track.get("artwork_url"):
        state.add_artwork_candidate(track["artwork_url"], "shazam", "Shazam")

    pref_path = _get_pref(track["artist"], track["title"])
    if pref_path and os.path.exists(pref_path):
        log.info(f"Using preferred artwork for: {track['artist']} - {track['title']}")
        full_img = PILImage.open(pref_path).convert("RGB")
        matrix_img = art_fetcher._for_matrix(full_img)
        local_url = f"/covers/{os.path.basename(pref_path)}"
        state.update(current_artwork_url=local_url)
        state.add_artwork_candidate(local_url, "local", "Your Pick ✓")
        display.show_album_art(matrix_img)
        return matrix_img, full_img

    matrix_img, full_img = art_fetcher.fetch(track, shared_state=state)
    if matrix_img and full_img:
        source_url = state.get().current_artwork_url
        local_path = _save_cover(full_img, source_url or track.get("artwork_url", track["title"]))
        if local_path:
            local_url = f"/covers/{os.path.basename(local_path)}"
            state.update(current_artwork_url=local_url)
            state.add_artwork_candidate(local_url, "local", "Current")
        if matrix_img != current_artwork:
            display.show_album_art(matrix_img)
            vstats.record_cover_play(state.get().current_artwork_url)
        return matrix_img, full_img

    display.show_track_text(track)
    return current_artwork, current_artwork_full


if __name__ == "__main__":
    main()
