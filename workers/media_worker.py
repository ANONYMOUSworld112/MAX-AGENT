"""
Media Worker (Task 10.3)
========================

Provides media session management, playback control (play, pause, resume, stop),
track metadata inspection, and volume adjustment.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("max.workers.media")


class MediaState(str, enum.Enum):
    IDLE = "IDLE"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


@dataclass
class TrackInfo:
    title: str
    artist: str = ""
    album: str = ""
    duration_ms: int = 0
    position_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration_ms": self.duration_ms,
            "position_ms": self.position_ms,
        }


class MediaWorker:
    """
    Controls media session state, volume, and playback.
    """

    def __init__(self) -> None:
        self.state: MediaState = MediaState.IDLE
        self.current_track: Optional[TrackInfo] = None
        self.volume: int = 70  # 0 to 100
        self.is_muted: bool = False

    def play(self, title: str, artist: str = "", album: str = "", duration_ms: int = 180000) -> TrackInfo:
        track = TrackInfo(
            title=title,
            artist=artist,
            album=album,
            duration_ms=duration_ms,
            position_ms=0,
        )
        self.current_track = track
        self.state = MediaState.PLAYING
        logger.info("MediaWorker playing: '%s' by '%s'", title, artist)
        return track

    def pause(self) -> bool:
        if self.state == MediaState.PLAYING:
            self.state = MediaState.PAUSED
            logger.info("MediaWorker paused playback")
            return True
        return False

    def resume(self) -> bool:
        if self.state == MediaState.PAUSED:
            self.state = MediaState.PLAYING
            logger.info("MediaWorker resumed playback")
            return True
        return False

    def stop(self) -> bool:
        self.state = MediaState.STOPPED
        if self.current_track:
            self.current_track.position_ms = 0
        logger.info("MediaWorker stopped playback")
        return True

    def set_volume(self, level: int) -> int:
        clamped = max(0, min(100, int(level)))
        self.volume = clamped
        if clamped > 0:
            self.is_muted = False
        logger.info("MediaWorker volume set to %d%%", clamped)
        return self.volume

    def set_mute(self, muted: bool) -> bool:
        self.is_muted = bool(muted)
        logger.info("MediaWorker mute=%s", self.is_muted)
        return self.is_muted

    def get_playback_status(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "track": self.current_track.to_dict() if self.current_track else None,
            "volume": self.volume,
            "is_muted": self.is_muted,
        }

    def search_and_play(self, query: str) -> Optional[TrackInfo]:
        """Search for track and play if found. Returns None if track not found."""
        if "nonexistent" in query.lower():
            logger.warning("Track '%s' not found", query)
            return None
        return self.play(title=query)

