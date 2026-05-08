#!/usr/bin/env python3
"""
Track identification using the AudD API.
Send a WAV clip, get back artist/title/album metadata.
Sign up for a free API key at: https://dashboard.audd.io/
"""

import logging
import requests
import config

log = logging.getLogger(__name__)

AUDD_ENDPOINT = "https://api.audd.io/"


class TrackIdentifier:
    def __init__(self):
        if not config.AUDD_API_KEY:
            raise ValueError("AUDD_API_KEY is not set in config.py")

    def identify(self, wav_bytes: bytes) -> dict | None:
        """
        Submit audio to AudD and return a track dict or None.
        Returns: {"artist": ..., "title": ..., "album": ...} or None
        """
        try:
            response = requests.post(
                AUDD_ENDPOINT,
                data={
                    "api_token": config.AUDD_API_KEY,
                    "return": "apple_music,spotify",
                },
                files={"file": ("clip.wav", wav_bytes, "audio/wav")},
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success" or not data.get("result"):
                log.info(f"AudD response: {data.get('status')} - no match")
                return None

            result = data["result"]
            track = {
                "artist": result.get("artist", "Unknown Artist"),
                "title": result.get("title", "Unknown Title"),
                "album": result.get("album", ""),
            }

            # Try to extract a high-res artwork URL from Spotify metadata if present
            spotify = result.get("spotify")
            if spotify:
                images = spotify.get("album", {}).get("images", [])
                if images:
                    # Spotify returns images sorted largest first
                    track["artwork_url"] = images[0]["url"]

            # Fall back to Apple Music artwork if available
            if "artwork_url" not in track:
                apple = result.get("apple_music")
                if apple:
                    raw_url = apple.get("artwork", {}).get("url", "")
                    if raw_url:
                        # Replace Apple's template dimensions with a large size
                        track["artwork_url"] = raw_url.replace("{w}x{h}", "512x512")

            log.info(f"Identified: {track['artist']} - {track['title']}")
            return track

        except requests.RequestException as e:
            log.error(f"AudD request failed: {e}")
            return None
