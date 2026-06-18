from __future__ import annotations

import logging
import re
import secrets
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Channel, Recording, Playlist, PlaylistItem
from ..config import AppConfig

LOGGER = logging.getLogger("recorder")
SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]{3,80}$")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]", "_", value.strip())
    value = re.sub(r"_+", "_", value)
    return value[:64] or "stream"


def generate_token() -> str:
    return secrets.token_urlsafe(16)


def validate_slug(slug: str) -> bool:
    return bool(SLUG_RE.match(slug))


@dataclass
class RecordingTask:
    channel_id: int
    recording_id: int
    output_path: Path
    streamlink_proc: subprocess.Popen
    ffmpeg_proc: subprocess.Popen
    started_at: datetime

    def is_running(self) -> bool:
        return self.streamlink_proc.poll() is None and self.ffmpeg_proc.poll() is None

    def stop(self):
        for proc in (self.streamlink_proc, self.ffmpeg_proc):
            if proc.poll() is None:
                proc.terminate()
        for proc in (self.streamlink_proc, self.ffmpeg_proc):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)


class RecordingManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self._tasks: Dict[int, RecordingTask] = {}
        self._lock = threading.Lock()
        self.config.data_dir.mkdir(parents=True, exist_ok=True)

    def is_recording(self, channel_id: int) -> bool:
        with self._lock:
            task = self._tasks.get(channel_id)
            return bool(task and task.is_running())

    def _build_output_path(self, channel: Channel, stream_title: Optional[str]) -> Path:
        folder = self.config.data_dir / "recordings" / channel.twitch_username
        folder.mkdir(parents=True, exist_ok=True)
        title = sanitize_filename((stream_title or "live")).replace(" ", "_")
        timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
        filename = f"{channel.twitch_username}_{timestamp}_{title}.mp4"
        return folder / filename

    def start(self, session: Session, channel: Channel, stream_id: Optional[str], stream_title: Optional[str]) -> Optional[Recording]:
        with self._lock:
            if channel.id in self._tasks:
                return None
            output_path = self._build_output_path(channel, stream_title)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            title = stream_title or f"live_{now_utc().strftime('%Y%m%d_%H%M%S')}"
            recording = Recording(
                channel_id=channel.id,
                twitch_stream_id=stream_id,
                title_original=title,
                title_display=title,
                started_at=now_utc(),
                file_path=str(output_path),
                status="recording",
            )
            session.add(recording)
            session.flush()

            streamlink_cmd = [
                "streamlink",
                "--twitch-disable-ads",
                f"https://www.twitch.tv/{channel.twitch_username}",
                self.config.streamlink_quality,
                "--stdout",
            ]
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-fflags",
                "+genpts",
                "-i",
                "pipe:0",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(output_path),
            ]
            streamlink_proc = subprocess.Popen(
                streamlink_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=streamlink_proc.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            self._tasks[channel.id] = RecordingTask(
                channel_id=channel.id,
                recording_id=recording.id,
                output_path=output_path,
                streamlink_proc=streamlink_proc,
                ffmpeg_proc=ffmpeg_proc,
                started_at=recording.started_at,
            )
            channel.status = "recording"
            session.add(channel)
            session.commit()
            LOGGER.info("Started recording channel=%s into %s", channel.twitch_username, output_path)
            return recording

    def _auto_add_playlist(self, session: Session, channel: Channel, recording: Recording):
        if not channel.auto_add_to_playlist or not channel.auto_playlist_id:
            return
        playlist = session.get(Playlist, channel.auto_playlist_id)
        if not playlist:
            LOGGER.warning("Auto playlist %s for channel %s no longer exists", channel.auto_playlist_id, channel.twitch_username)
            return
        existing = (
            session.query(PlaylistItem)
            .filter(PlaylistItem.playlist_id == playlist.id, PlaylistItem.recording_id == recording.id)
            .first()
        )
        if existing:
            return
        max_pos = session.query(func.max(PlaylistItem.position)).filter(PlaylistItem.playlist_id == playlist.id).scalar()
        if max_pos is None:
            max_pos = 0
        session.add(
            PlaylistItem(
                playlist_id=playlist.id,
                recording_id=recording.id,
                position=max_pos + 1,
            )
        )

    def stop(self, session: Session, channel: Channel, reason: str = "manual") -> Optional[Recording]:
        with self._lock:
            task = self._tasks.pop(channel.id, None)
            if not task:
                return None
        task.stop()
        recording = session.get(Recording, task.recording_id)
        if not recording:
            return None
        if recording.status != "recording":
            return recording
        if task.output_path.exists() and task.output_path.stat().st_size > 0:
            status = "completed"
        else:
            status = "failed"
        recording.status = status
        recording.ended_at = now_utc()
        recording.duration_sec = int((recording.ended_at - recording.started_at).total_seconds())
        channel.status = "offline" if reason == "offline" else "stopped"
        channel.is_live = False
        channel.last_checked_at = now_utc()
        session.add(recording)
        session.add(channel)
        self._auto_add_playlist(session, channel, recording)
        LOGGER.info("Stopped recording channel=%s id=%s reason=%s status=%s", channel.twitch_username, recording.id, reason, status)
        return recording

    def cleanup_dead_tasks(self, session: Session):
        dead_channels = []
        with self._lock:
            for channel_id, task in list(self._tasks.items()):
                if not task.is_running():
                    dead_channels.append(channel_id)
        for channel_id in dead_channels:
            channel = session.get(Channel, channel_id)
            if channel:
                self.stop(session, channel, reason="unexpected")

    def stop_all(self, session: Session):
        with self._lock:
            channel_ids = list(self._tasks.keys())
        for channel_id in channel_ids:
            channel = session.get(Channel, channel_id)
            if channel:
                self.stop(session, channel, reason="shutdown")
