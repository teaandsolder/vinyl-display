#!/usr/bin/env python3
"""
Fetch album art for the LED matrix and web UI.
Returns full resolution for saving/display in web UI,
and 64x64 processed version for the matrix.
"""

import logging
import requests
import numpy as np
from PIL import Image, ImageEnhance
import io
from config import SATURATION

log = logging.getLogger(__name__)

MATRIX_SIZE  = (64, 64)
PREVIEW_SIZE = (800, 800)   # saved to covers folder for web UI — high DPI
CAA_IMAGE    = "https://coverartarchive.org/release/{mbid}/front-500"
MB_SEARCH    = "https://musicbrainz.org/ws/2/release"
MB_HEADERS   = {"User-Agent": "VinylDisplay/1.0 (teaandsolder)"}


class AlbumArtFetcher:

    def fetch(self, track: dict, shared_state=None):
        """
        Fetch best available artwork.
        Returns (matrix_image, full_image) tuple or (None, None).
        """
        candidates = []
        shazam_url = track.get("artwork_url")
        if shazam_url:
            candidates.append({"url": shazam_url, "source": "shazam", "label": "Shazam"})

        mbid = self._lookup_mbid(track)
        if mbid:
            caa_url = CAA_IMAGE.format(mbid=mbid)
            candidates.append({"url": caa_url, "source": "caa", "label": "Cover Art Archive"})

        if shared_state:
            for c in candidates:
                shared_state.add_artwork_candidate(c["url"], c["source"], c["label"])

        for candidate in candidates:
            full_image = self._download(candidate["url"])
            if full_image:
                if shared_state:
                    shared_state.update(current_artwork_url=candidate["url"])
                return self._for_matrix(full_image), self._for_preview(full_image)

        log.warning(f"No artwork found for: {track.get('artist')} - {track.get('album')}")
        return None, None

    def fetch_url(self, url: str):
        """Fetch from specific URL. Returns (matrix_image, full_image) or (None, None)."""
        full_image = self._download(url)
        if full_image:
            return self._for_matrix(full_image), self._for_preview(full_image)
        return None, None

    def _download(self, url: str) -> Image.Image | None:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            log.info(f"Artwork downloaded from {url}")
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception as e:
            log.warning(f"Download failed ({url}): {e}")
            return None

    def _lookup_mbid(self, track: dict) -> str | None:
        try:
            params = {
                "query": f'artist:"{track.get("artist","")}" release:"{track.get("album", track.get("title",""))}"',
                "fmt": "json",
                "limit": 1,
            }
            resp = requests.get(MB_SEARCH, params=params, headers=MB_HEADERS, timeout=10)
            resp.raise_for_status()
            releases = resp.json().get("releases", [])
            if releases:
                return releases[0].get("id")
        except Exception as e:
            log.warning(f"MusicBrainz lookup failed: {e}")
        return None

    def _for_matrix(self, image: Image.Image) -> Image.Image:
        """Resize to 64x64 with saturation and gamma for LED matrix."""
        from state import state
        s = state.get()
        img = image.resize(MATRIX_SIZE, Image.LANCZOS)
        img = ImageEnhance.Color(img).enhance(s.saturation)
        # Gamma: 1.0 = linear, <1.0 = darker, >1.0 = brighter midtones
        if s.gamma != 1.0:
            arr = np.array(img).astype(np.float32) / 255.0
            arr = np.power(arr, 1.0 / s.gamma)
            img = Image.fromarray((arr * 255).astype(np.uint8))
        return img

    def _for_preview(self, image: Image.Image) -> Image.Image:
        """Resize to preview size for web UI — high quality, no saturation adjustment."""
        return image.resize(PREVIEW_SIZE, Image.LANCZOS)
