from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .recorder import RecordingManager
from .twitch_client import TwitchClient
from .recorder import now_utc
from ..models import Channel

LOGGER = logging.getLogger("poller")


class Poller:
    def __init__(self, twitch_client: TwitchClient, recorder: RecordingManager):
        self.twitch_client = twitch_client
        self.recorder = recorder

    def run_once(self, db: Session):
        channels = db.query(Channel).filter(Channel.enabled.is_(True)).all()
        self.recorder.cleanup_dead_tasks(db)
        for channel in channels:
            try:
                state = self.twitch_client.get_stream_state(channel.twitch_username)
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("Error fetching twitch state for %s: %s", channel.twitch_username, exc)
                continue

            channel.last_checked_at = now_utc()
            if state.user_name:
                channel.display_name = state.user_name
            if state.title:
                channel.last_stream_title = state.title

            if state.is_live:
                channel.is_live = True
                channel.status = "live"
                channel.last_stream_id = state.stream_id
                if not self.recorder.is_recording(channel.id):
                    try:
                        self.recorder.start(db, channel, state.stream_id, state.title)
                    except Exception as exc:
                        channel.status = "error"
                        LOGGER.exception("Failed to start recording for %s: %s", channel.twitch_username, exc)
            else:
                channel.is_live = False
                if self.recorder.is_recording(channel.id):
                    self.recorder.stop(db, channel, reason="offline")
                else:
                    channel.status = "offline"
            db.add(channel)
        db.commit()
