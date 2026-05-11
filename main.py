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
from display import MatrixDisplay
from listener import AudioListener
from identifier import TrackIdentifier
from art import AlbumArtFetcher
from server import start_server
from state import state
from config import (
    CAPTURE_SECONDS, SETTLE_SECONDS,
    SIGNAL_THRESHOLD, SIDE_END_CONSECUTIVE,
    SLEEP_POLL_INTERVAL, PLAYING_POLL_INTERVAL,
    BRIGHTNESS, SATURATION
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
    """Save a PIL image to the covers folder. Returns the local file path or None."""
    if image is None:
        return None
    _ensure_dirs()
    url_hash = hashlib.md5(source_url.encode()).hexdigest()[:12]
    path = os.path.join(COVERS_DIR, f"{url_hash}.jpg")
    if not os.path.exists(path):
        image.save(path, "JPEG", quality=95)
        log.info(f"Saved cover: {path}")
    return path


def identify(listener, identifier):
    log.info("Identifying...")
    return identifier.identify(listener.capture())


def main():
    display     = MatrixDisplay()
    listener    = AudioListener(capture_seconds=CAPTURE_SECONDS)
    identifier  = TrackIdentifier()
    art_fetcher = AlbumArtFetcher()

    state.update(brightness=BRIGHTNESS, saturation=SATURATION)
    start_server()

    current_track   = None
    current_artwork = None
    low_count       = 0
    playing         = False
    last_saturation = SATURATION

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
            # Apply live brightness and saturation from web UI
            s = state.get()
            if s.brightness != display.matrix_brightness():
                display.set_brightness(s.brightness)
            if s.saturation != last_saturation and current_artwork:
                from PIL import ImageEnhance
                img = ImageEnhance.Color(current_artwork).enhance(s.saturation)
                display.show_album_art(img)
                last_saturation = s.saturation

            # ---------------------------------------------------------- #
            # PLAYING                                                      #
            # ---------------------------------------------------------- #
            if playing:
                # Sleep in 1s chunks to catch web UI artwork selections quickly
                for _ in range(PLAYING_POLL_INTERVAL):
                    time.sleep(1)
                    s = state.get()
                    if s.preferred_artwork_url and s.preferred_artwork_url != s.current_artwork_url:
                        selected_url = s.preferred_artwork_url
                        log.info("Web UI artwork selection — updating display")
                        if selected_url.startswith("/covers/"):
                            filename = selected_url.replace("/covers/", "")
                            local_path = os.path.join(COVERS_DIR, filename)
                            from PIL import Image as PILImage
                            if os.path.exists(local_path):
                                full_img = PILImage.open(local_path).convert("RGB")
                                matrix_img = art_fetcher._for_matrix(full_img)
                            else:
                                matrix_img = None
                                local_path = None
                        else:
                            matrix_img, full_img = art_fetcher.fetch_url(selected_url)
                            local_path = _save_cover(full_img, selected_url) if full_img else None
                            if local_path:
                                selected_url = f"/covers/{os.path.basename(local_path)}"
                        if matrix_img:
                            current_artwork = matrix_img
                            display.show_album_art(matrix_img)
                        state.update(current_artwork_url=selected_url, preferred_artwork_url="")
                        if current_track and local_path:
                            _save_pref(current_track["artist"], current_track["title"], local_path)
                        break

                rms = listener.quick_rms()
                log.info(f"RMS: {rms:.1f}")

                if rms < SIGNAL_THRESHOLD:
                    low_count += 1
                    log.info(f"Low signal {low_count}/3")

                    if low_count == 1:
                        # Short wait — between-track gap or quiet passage
                        time.sleep(5)
                        rms2 = listener.quick_rms()
                        log.info(f"RMS recheck: {rms2:.1f}")
                        if rms2 >= SIGNAL_THRESHOLD:
                            log.info("Signal recovered — resetting count")
                            low_count = 0
                            continue

                    elif low_count == 2:
                        # Medium wait — more sustained quiet
                        time.sleep(20)
                        rms2 = listener.quick_rms()
                        log.info(f"RMS recheck: {rms2:.1f}")
                        if rms2 >= SIGNAL_THRESHOLD:
                            log.info("Signal recovered — resetting count")
                            low_count = 0
                            continue

                    elif low_count >= 3:
                        # Long wait — almost certainly end of side
                        time.sleep(30)
                        rms2 = listener.quick_rms()
                        log.info(f"RMS recheck: {rms2:.1f}")
                        if rms2 >= SIGNAL_THRESHOLD:
                            log.info("Signal recovered — resetting count")
                            low_count = 0
                            continue
                        log.info("Side ended — resetting.")
                        playing = False
                        low_count = 0
                        current_track = None
                        current_artwork = None
                        state.update(playing=False, artist="", title="", album="",
                                     current_artwork_url="", preferred_artwork_url="")
                        state.clear_candidates()
                        display.show_idle()
                    continue

                low_count = 0

                track = identify(listener, identifier)
                if not track:
                    continue

                # Check for web UI selection after identification
                s = state.get()
                if s.preferred_artwork_url and s.preferred_artwork_url != s.current_artwork_url:
                    selected_url = s.preferred_artwork_url
                    log.info("Web UI artwork selection — updating display")
                    matrix_img, full_img = art_fetcher.fetch_url(selected_url)
                    if matrix_img and full_img:
                        local_path = _save_cover(full_img, selected_url)
                        local_url = f"/covers/{os.path.basename(local_path)}"
                        current_artwork = matrix_img
                        display.show_album_art(matrix_img)
                        state.update(current_artwork_url=local_url, preferred_artwork_url="")
                        if current_track:
                            _save_pref(current_track["artist"], current_track["title"], local_path)
                    else:
                        state.update(preferred_artwork_url="")
                    continue

                if track != current_track:
                    log.info(f"Track: {track['artist']} - {track['title']}")
                    current_track = track
                    state.update(
                        artist=track["artist"],
                        title=track["title"],
                        album=track.get("album", ""),
                        preferred_artwork_url=""  # clear any stale selection
                    )
                    # Add ShazamIO artwork as candidate
                    if track.get("artwork_url"):
                        state.add_artwork_candidate(
                            track["artwork_url"], "shazam", "Shazam"
                        )
                    # Check for saved preference first
                    pref_path = _get_pref(track["artist"], track["title"])
                    if pref_path and os.path.exists(pref_path):
                        from PIL import Image as PILImage
                        log.info(f"Using preferred artwork for: {track['artist']} - {track['title']}")
                        full_img = PILImage.open(pref_path).convert("RGB")
                        matrix_img = art_fetcher._for_matrix(full_img)
                        local_url = f"/covers/{os.path.basename(pref_path)}"
                        state.update(current_artwork_url=local_url)
                        current_artwork = matrix_img
                        display.show_album_art(matrix_img)
                        continue
                    image = art_fetcher.fetch(track, shared_state=state)
                    if image:
                        matrix_img, full_img = image
                        # Save full res to covers folder
                        source_url = state.get().current_artwork_url
                        local_path = _save_cover(full_img, source_url or track.get("artwork_url", track["title"]))
                        if local_path:
                            local_url = f"/covers/{os.path.basename(local_path)}"
                            state.update(current_artwork_url=local_url)
                            state.add_artwork_candidate(local_url, "local", "Current")
                        # Only update display if artwork changed
                        if matrix_img != current_artwork:
                            current_artwork = matrix_img
                            display.show_album_art(matrix_img)
                    else:
                        display.show_track_text(track)
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
            state.clear_candidates()
            state.update(
                playing=True,
                artist=track["artist"],
                title=track["title"],
                album=track.get("album", ""),
                current_artwork_url="",
                preferred_artwork_url=""
            )

            if track.get("artwork_url"):
                state.add_artwork_candidate(track["artwork_url"], "shazam", "Shazam")

            # Check for saved preference
            pref_path = _get_pref(track["artist"], track["title"])
            if pref_path and os.path.exists(pref_path):
                from PIL import Image as PILImage
                log.info(f"Using preferred artwork for: {track['artist']} - {track['title']}")
                matrix_img = art_fetcher._for_matrix(PILImage.open(pref_path).convert("RGB"))
                local_url = f"/covers/{os.path.basename(pref_path)}"
                state.update(current_artwork_url=local_url)
                state.add_artwork_candidate(local_url, "local", "Your Pick ✓")
                current_artwork = matrix_img
                display.show_album_art(matrix_img)
            else:
                matrix_img, full_img = art_fetcher.fetch(track, shared_state=state)
                if matrix_img and full_img:
                    source_url = state.get().current_artwork_url
                    local_path = _save_cover(full_img, source_url or track.get("artwork_url", track["title"]))
                    if local_path:
                        local_url = f"/covers/{os.path.basename(local_path)}"
                        state.update(current_artwork_url=local_url)
                        state.add_artwork_candidate(local_url, "local", "Current")
                    current_artwork = matrix_img
                    display.show_album_art(matrix_img)
                else:
                    display.show_track_text(track)

        except Exception as e:
            log.error(f"Error: {e}", exc_info=True)
            display.show_error()
            time.sleep(SLEEP_POLL_INTERVAL)


if __name__ == "__main__":
    main()
