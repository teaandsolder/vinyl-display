#!/usr/bin/env python3
"""
Local artwork cache.
Stores preferred artwork per album as local image files.
Next time the same album is identified, the cached image is used immediately.
"""

import json
import logging
import os
from PIL import Image

log = logging.getLogger(__name__)

CACHE_DIR   = os.path.expanduser("~/.vinyl-display/cache")
CACHE_INDEX = os.path.expanduser("~/.vinyl-display/cache_index.json")


def _ensure_dirs():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _load_index() -> dict:
    if os.path.exists(CACHE_INDEX):
        try:
            with open(CACHE_INDEX) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_index(index: dict):
    _ensure_dirs()
    with open(CACHE_INDEX, "w") as f:
        json.dump(index, f, indent=2)


def _album_key(artist: str, album: str) -> str:
    return f"{artist.lower().strip()}|{album.lower().strip()}"


def get(artist: str, album: str) -> Image.Image | None:
    key = _album_key(artist, album)
    index = _load_index()
    if key not in index:
        return None
    path = index[key]["path"]
    if not os.path.exists(path):
        return None
    try:
        log.info(f"Cache hit: {artist} - {album}")
        return Image.open(path).convert("RGB")
    except Exception as e:
        log.warning(f"Cache read failed: {e}")
        return None


def save(artist: str, album: str, image_url: str, image: Image.Image):
    _ensure_dirs()
    key = _album_key(artist, album)
    filename = f"{key.replace('|', '_').replace(' ', '_')[:80]}.jpg"
    path = os.path.join(CACHE_DIR, filename)
    try:
        image.save(path, "JPEG", quality=95)
        index = _load_index()
        index[key] = {"artist": artist, "album": album, "path": path, "source_url": image_url}
        _save_index(index)
        log.info(f"Cached artwork for: {artist} - {album}")
    except Exception as e:
        log.error(f"Cache save failed: {e}")


def clear(artist: str, album: str):
    key = _album_key(artist, album)
    index = _load_index()
    if key in index:
        path = index[key].get("path")
        if path and os.path.exists(path):
            os.remove(path)
        del index[key]
        _save_index(index)
        log.info(f"Cache cleared for: {artist} - {album}")


def list_all() -> list:
    return list(_load_index().values())
