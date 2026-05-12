#!/usr/bin/env python3
"""
Stats tracking for Vinyl Display.
All stats are controlled via config.py — set STATS_ENABLED = False to disable all.
"""

import json
import os
import logging
from datetime import datetime
from config import (
    STATS_ENABLED,
    STAT_NEEDLE_DROPS, STAT_LISTENING_HISTORY,
    STAT_COVER_PLAYS, STAT_SIDE_DURATION,
    STATS_HISTORY_LIMIT, STATS_SIDE_DURATION_LIMIT,
    STATS_TOP_COVERS_COUNT, STATS_HISTORY_DAYS
)

log = logging.getLogger(__name__)

STATS_FILE = os.path.expanduser("~/.vinyl-display/stats.json")


def _load() -> dict:
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "needle_drops": 0,
        "history": [],
        "cover_plays": {},
        "side_durations": [],
    }


def _save(data: dict):
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    with open(STATS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_needle_drop():
    if not STATS_ENABLED or not STAT_NEEDLE_DROPS:
        return
    data = _load()
    data["needle_drops"] += 1
    _save(data)
    log.info(f"Needle drop #{data['needle_drops']}")


def record_artist_change(artist: str, title: str, artwork_url: str):
    if not STATS_ENABLED or not STAT_LISTENING_HISTORY:
        return
    data = _load()
    data["history"].append({
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "artist": artist,
        "title": title,
        "artwork_url": artwork_url,
    })
    data["history"] = data["history"][-STATS_HISTORY_LIMIT:]
    _save(data)


def record_cover_play(artwork_url: str):
    if not STATS_ENABLED or not STAT_COVER_PLAYS or not artwork_url:
        return
    data = _load()
    data["cover_plays"][artwork_url] = data["cover_plays"].get(artwork_url, 0) + 1
    _save(data)


def record_side_duration(seconds: float):
    if not STATS_ENABLED or not STAT_SIDE_DURATION or seconds < 60:
        return
    data = _load()
    data["side_durations"].append(int(seconds))
    data["side_durations"] = data["side_durations"][-STATS_SIDE_DURATION_LIMIT:]
    _save(data)


def get_stats(covers_dir: str) -> dict:
    """Return compiled stats for the web UI."""
    data = _load()

    durations = data.get("side_durations", [])
    avg_side = sum(durations) / len(durations) if durations else 0
    avg_mins = int(avg_side // 60)
    avg_secs = int(avg_side % 60)

    cover_plays = data.get("cover_plays", {})
    # Filter out covers that no longer exist
    valid_covers = {}
    for url, count in cover_plays.items():
        if url.startswith("/covers/"):
            path = os.path.join(covers_dir, url.replace("/covers/", ""))
            if os.path.exists(path):
                valid_covers[url] = count
        # Skip external URLs in most played — they may have changed or expired
    top_covers = sorted(valid_covers.items(), key=lambda x: x[1], reverse=True)[:STATS_TOP_COVERS_COUNT]

    # Unique artists from history
    unique_artists = len(set(e["artist"] for e in data.get("history", [])))

    unique_covers = 0
    if os.path.exists(covers_dir):
        unique_covers = len([f for f in os.listdir(covers_dir) if f.endswith(".jpg")])

    history = data.get("history", [])
    days = {}
    for entry in reversed(history):
        day = entry["ts"][:10]
        if day not in days:
            days[day] = []
        days[day].append(entry)
    history_by_day = [
        {"date": day, "entries": entries}
        for day, entries in sorted(days.items(), reverse=True)
    ][:STATS_HISTORY_DAYS]

    return {
        "needle_drops": data.get("needle_drops", 0),
        "unique_covers": unique_covers,
        "unique_artists": unique_artists,
        "avg_side": f"{avg_mins}m {avg_secs:02d}s" if avg_side > 0 else "—",
        "top_covers": [{"url": url, "count": count} for url, count in top_covers],
        "history_by_day": history_by_day,
        "enabled": STATS_ENABLED,
    }
