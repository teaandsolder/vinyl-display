#!/usr/bin/env python3
"""
Fetch album art and resize to 64x64 for the LED matrix.
Uses the artwork URL supplied by ShazamIO (Apple Music),
with a MusicBrainz Cover Art Archive fallback.
"""

import logging
import requests
from PIL import Image
import io

log = logging.getLogger(__name__)

MATRIX_SIZE = (64, 64)
CAA_SEARCH = "https://musicbrainz.org/ws/2/release"
CAA_IMAGE  = "https://coverartarchive.org/release/{mbid}/front-500"


class AlbumArtFetcher:

    def fetch_by_mbid(self, mbid: str, fallback_track: dict = None) -> Image.Image | None:
        """Fetch artwork from Cover Art Archive, falling back to track artwork if 404."""
        url = CAA_IMAGE.format(mbid=mbid)
        image = self._download_image(url)
        if image:
            return self._resize(image)
        log.warning(f"Cover Art Archive returned no image for {mbid} — falling back to track artwork")
        if fallback_track:
            return self.fetch(fallback_track)
        return None

    def fetch(self, track: dict) -> Image.Image | None:
        """Return a 64x64 PIL Image for the given track, or None on failure."""
        url = track.get("artwork_url")
        if url:
            image = self._download_image(url)
            if image:
                return self._resize(image)

        log.info("Falling back to Cover Art Archive...")
        mbid = self._lookup_mbid(track)
        if mbid:
            caa_url = CAA_IMAGE.format(mbid=mbid)
            image = self._download_image(caa_url)
            if image:
                return self._resize(image)

        log.warning(f"No album art found for: {track.get('artist')} - {track.get('album')}")
        return None

    def _download_image(self, url: str) -> Image.Image | None:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            image = Image.open(io.BytesIO(resp.content)).convert("RGB")
            log.info(f"Artwork downloaded from {url}")
            return image
        except Exception as e:
            log.warning(f"Image download failed ({url}): {e}")
            return None

    def _lookup_mbid(self, track: dict) -> str | None:
        """Query MusicBrainz for a release MBID to use with Cover Art Archive."""
        try:
            params = {
                "query": f'artist:"{track.get("artist", "")}" release:"{track.get("album", track.get("title", ""))}"',
                "fmt": "json",
                "limit": 1,
            }
            resp = requests.get(CAA_SEARCH, params=params, timeout=10,
                                headers={"User-Agent": "VinylDisplay/1.0"})
            resp.raise_for_status()
            releases = resp.json().get("releases", [])
            if releases:
                return releases[0].get("id")
        except Exception as e:
            log.warning(f"MusicBrainz lookup failed: {e}")
        return None

    def _resize(self, image: Image.Image) -> Image.Image:
        """Resize to 64x64 using high quality Lanczos resampling."""
        from PIL import ImageEnhance
        image = image.resize(MATRIX_SIZE, Image.LANCZOS)
        image = ImageEnhance.Color(image).enhance(0.8)  # 80% saturation
        return image
