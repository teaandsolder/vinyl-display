#!/usr/bin/env python3
"""
Album resolver — collects identified tracks during a side and queries
MusicBrainz to find the most likely album.
Uses release type weighting and track sequence to score releases.
"""

import logging
import requests
from collections import Counter

log = logging.getLogger(__name__)

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/recording"
HEADERS = {"User-Agent": "VinylDisplay/1.0 (teaandsolder)"}

# Release type base scores — studio albums preferred over compilations and live
RELEASE_TYPE_SCORES = {
    "Album":       3,  # studio album
    "Compilation": 2,
    "Live":        1,
    "Single":      1,
    "EP":          1,
}
DEFAULT_TYPE_SCORE = 1


class AlbumResolver:
    def __init__(self):
        self.reset()

    def reset(self):
        self.tracks = []
        self.release_votes = Counter()
        self.release_info = {}
        self._position_cache = {}  # track title → {release_id: track_number}

    def add_track(self, artist: str, title: str) -> dict | None:
        if (artist, title) in self.tracks:
            log.info(f"Album resolver: already seen '{title}' — skipping query")
            return self._current_best()

        self.tracks.append((artist, title))
        log.info(f"Album resolver: {len(self.tracks)} track(s) identified this side")

        releases = self._query_releases(artist, title)

        # Cache track numbers by normalised release title for sequence matching
        self._position_cache[title] = {}
        for r in releases:
            t = r["title"].lower().strip()
            if t not in self._position_cache[title] or r["track_number"] is not None:
                self._position_cache[title][t] = {
                    "id": r["id"],
                    "track_number": r["track_number"],
                    "title": r["title"]
                }

        prev_positions = {}
        if len(self.tracks) >= 2:
            prev_title = self.tracks[-2][1]
            prev_positions = {
                t: info["track_number"]
                for t, info in self._position_cache.get(prev_title, {}).items()
            }

        for r in releases:
            rid = r["id"]
            rtitle_norm = r["title"].lower().strip()
            type_score = r["type_score"]
            sequence_bonus = 0

            if prev_positions and rtitle_norm in prev_positions:
                prev_num = prev_positions[rtitle_norm]
                curr_num = r["track_number"]
                if prev_num is not None and curr_num is not None:
                    if curr_num == prev_num + 1:
                        sequence_bonus = 2
                        log.info(f"Album resolver: consecutive match on '{r['title']}' (tracks {prev_num}→{curr_num})")
                        log.info(f"Album resolver: consecutive match on '{rtitle}' (tracks {prev_num}→{curr_num})")

            self.release_votes[rid] += type_score + sequence_bonus
            self.release_info[rid] = r

        return self._current_best()

    def _current_best(self) -> dict | None:
        if not self.release_votes:
            return None

        best_id = self.release_votes.most_common(1)[0][0]
        top_votes = self.release_votes[best_id]
        total_tracks = len(self.tracks)

        if total_tracks >= 2:
            info = self.release_info.get(best_id, {})
            log.info(f"Album resolver: '{info.get('title')}' ({top_votes} pts from {total_tracks} tracks)")
            return {
                "title": info.get("title", ""),
                "mbid": best_id,
                "confidence": min(top_votes / (total_tracks * 5), 1.0)
            }
        return None

    def _query_releases(self, artist: str, title: str) -> list:
        try:
            params = {
                "query": f'recording:"{title}" AND artist:"{artist}"',
                "fmt": "json",
                "limit": 10,
            }
            resp = requests.get(MUSICBRAINZ_URL, params=params,
                                headers=HEADERS, timeout=10)
            resp.raise_for_status()
            recordings = resp.json().get("recordings", [])

            releases = []
            for recording in recordings:
                for release in recording.get("releases", []):
                    # Get release type
                    rg = release.get("release-group", {})
                    primary_type = rg.get("primary-type", "")
                    secondary_types = rg.get("secondary-types", [])

                    # Score: secondary types (Compilation, Live) override primary
                    if "Live" in secondary_types:
                        type_score = RELEASE_TYPE_SCORES["Live"]
                        release_type = "Live"
                    elif "Compilation" in secondary_types:
                        type_score = RELEASE_TYPE_SCORES["Compilation"]
                        release_type = "Compilation"
                    else:
                        release_type = primary_type
                        type_score = RELEASE_TYPE_SCORES.get(primary_type, DEFAULT_TYPE_SCORE)

                    # Get track number from media
                    track_number = None
                    for medium in release.get("media", []):
                        for track in medium.get("track", []):
                            num = track.get("number")
                            if num is not None:
                                try:
                                    track_number = int(str(num).strip())
                                except (ValueError, TypeError):
                                    pass

                    releases.append({
                        "title": release.get("title", ""),
                        "id": release.get("id", ""),
                        "type": release_type,
                        "type_score": type_score,
                        "track_number": track_number,
                    })

            log.info(f"Album resolver: '{title}' found on {len(releases)} releases")
            return releases

        except Exception as e:
            log.warning(f"MusicBrainz query failed: {e}")
            return []
