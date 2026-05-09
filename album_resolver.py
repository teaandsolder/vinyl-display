#!/usr/bin/env python3
"""
Album resolver — collects identified track names during a side
and queries MusicBrainz to find the most likely album.
Gets smarter as more tracks are identified.
"""

import logging
import requests
from collections import Counter

log = logging.getLogger(__name__)

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/recording"
HEADERS = {"User-Agent": "VinylDisplay/1.0 (teaandsolder)"}


class AlbumResolver:
    def __init__(self):
        self.reset()

    def reset(self):
        """Call at the start of each side."""
        self.tracks = []        # list of (artist, title) tuples identified this side
        self.release_votes = Counter()  # release title → vote count
        self.best_release = None
        self.best_mbid = None

    def add_track(self, artist: str, title: str) -> dict | None:
        """
        Add a newly identified track and re-query MusicBrainz.
        Returns a release dict {title, mbid, artwork_url} if confidence is high enough,
        or None if still gathering data.
        """
        # Avoid duplicates
        if (artist, title) in self.tracks:
            log.info(f"Album resolver: already seen '{title}' — skipping query")
            return self._current_best()

        self.tracks.append((artist, title))
        log.info(f"Album resolver: {len(self.tracks)} track(s) identified this side")

        # Query MusicBrainz for this track
        releases = self._query_releases(artist, title)
        for release in releases:
            self.release_votes[release["title"]] += 1
            # Store MBID of the most voted release
            if self.release_votes[release["title"]] >= self.release_votes.get(self.best_release, 0):
                self.best_release = release["title"]
                self.best_mbid = release.get("id")

        return self._current_best()

    def _current_best(self) -> dict | None:
        """Return the current best album guess if we have enough confidence."""
        if not self.best_release:
            return None

        top_votes = self.release_votes[self.best_release]
        total_tracks = len(self.tracks)

        # Need at least 2 tracks and 66% agreement to show a result
        if total_tracks >= 2 and top_votes >= total_tracks * 0.66:
            log.info(f"Album resolver: '{self.best_release}' ({top_votes}/{total_tracks} votes)")
            return {
                "title": self.best_release,
                "mbid": self.best_mbid,
                "confidence": top_votes / total_tracks
            }
        return None

    def _query_releases(self, artist: str, title: str) -> list:
        """Query MusicBrainz for releases containing this track."""
        try:
            params = {
                "query": f'recording:"{title}" AND artist:"{artist}"',
                "fmt": "json",
                "limit": 5,
            }
            resp = requests.get(MUSICBRAINZ_URL, params=params,
                                headers=HEADERS, timeout=10)
            resp.raise_for_status()
            recordings = resp.json().get("recordings", [])

            releases = []
            for recording in recordings:
                for release in recording.get("releases", []):
                    releases.append({
                        "title": release.get("title", ""),
                        "id": release.get("id", ""),
                    })
            return releases

        except Exception as e:
            log.warning(f"MusicBrainz query failed: {e}")
            return []
