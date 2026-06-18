from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from ..config import AppConfig

LOGGER = logging.getLogger("twitch-client")


@dataclass
class TwitchStreamState:
    is_live: bool
    stream_id: Optional[str]
    title: Optional[str]
    user_name: Optional[str]


class TwitchClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self._token: Optional[str] = None
        self._token_expire_at: Optional[datetime] = None
        self._http = httpx.Client(timeout=20.0)

    def _has_credentials(self) -> bool:
        return bool(self.config.twitch_client_id and self.config.twitch_client_secret)

    def _ensure_token(self) -> Optional[str]:
        if not self._has_credentials():
            LOGGER.warning("Twitch credentials not configured. Live polling is disabled.")
            return None

        if self._token and self._token_expire_at and datetime.now(timezone.utc) < self._token_expire_at:
            return self._token

        response = self._http.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": self.config.twitch_client_id,
                "client_secret": self.config.twitch_client_secret,
                "grant_type": "client_credentials",
            },
        )
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not access_token:
            raise RuntimeError("No access token in Twitch response")
        self._token = access_token
        self._token_expire_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60))
        return self._token

    def resolve_display_name(self, username: str) -> str:
        normalized = username.strip().lstrip("@").lower()
        if not self._has_credentials():
            return normalized
        token = self._ensure_token()
        if not token:
            return normalized
        resp = self._http.get(
            "https://api.twitch.tv/helix/users",
            params={"login": normalized},
            headers={"Client-Id": self.config.twitch_client_id, "Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            return normalized
        data = resp.json().get("data") or []
        if not data:
            return normalized
        return data[0].get("display_name", normalized) or normalized

    def get_stream_state(self, username: str) -> TwitchStreamState:
        normalized = username.strip().lstrip("@").lower()
        if not self._has_credentials():
            return TwitchStreamState(False, None, None, normalized)
        token = self._ensure_token()
        if not token:
            return TwitchStreamState(False, None, None, normalized)

        response = self._http.get(
            "https://api.twitch.tv/helix/streams",
            params={"user_login": normalized},
            headers={"Client-Id": self.config.twitch_client_id, "Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            response.raise_for_status()
            return TwitchStreamState(False, None, None, normalized)
        data = response.json().get("data") or []
        if not data:
            return TwitchStreamState(False, None, None, normalized)

        live = data[0]
        return TwitchStreamState(
            is_live=True,
            stream_id=str(live.get("id")),
            title=live.get("title"),
            user_name=live.get("user_name"),
        )
