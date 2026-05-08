#!/usr/bin/env python3
"""
Track identification using ShazamIO.
Saves a WAV clip to a temp file and submits to Shazam for identification.
No API key required — unlimited requests.
"""

import asyncio
import logging
import tempfile
import os

log = logging.getLogger(__name__)


class TrackIdentifier:
    def __init__(self):
        from shazamio import Shazam
        self.shazam = Shazam()

    def identify(self, wav_bytes: bytes) -> dict | None:
        """
        Submit audio to Shazam and return a track dict or None.
        Returns: {"artist": ..., "title": ..., "album": ..., "artwork_url": ...} or None
        """
        return asyncio.run(self._identify_async(wav_bytes))

    async def _identify_async(self, wav_bytes: bytes) -> dict | None:
        # Write WAV bytes to a temp file for ShazamIO to read
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            result = await self.shazam.recognize(tmp_path)

            track = result.get("track")
            if not track:
                log.info("Shazam returned no match.")
                return None

            # Extract metadata
            artist = track.get("subtitle", "Unknown Artist")
            title = track.get("title", "Unknown Title")

            # Album is buried in sections metadata
            album = ""
            for section in track.get("sections", []):
                for meta in section.get("metadata", []):
                    if meta.get("title", "").lower() == "album":
                        album = meta.get("text", "")
                        break

            # High res artwork
            artwork_url = track.get("images", {}).get("coverarthq", "")
            if not artwork_url:
                artwork_url = track.get("images", {}).get("coverart", "")

            log.info(f"Identified: {artist} - {title}")

            return {
                "artist": artist,
                "title": title,
                "album": album,
                "artwork_url": artwork_url,
            }

        except Exception as e:
            log.error(f"ShazamIO error: {e}")
            return None

        finally:
            os.unlink(tmp_path)
