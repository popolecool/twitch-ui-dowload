from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class ChannelCreateRequest(BaseModel):
    twitch_username: str = Field(..., min_length=1)
    auto_add_to_playlist: bool = False
    auto_playlist_id: Optional[int] = None


class ChannelPatchRequest(BaseModel):
    auto_add_to_playlist: Optional[bool] = None
    auto_playlist_id: Optional[int] = None
    enabled: Optional[bool] = None


class RecordingUpdateRequest(BaseModel):
    title_display: str = Field(..., min_length=1)


class PlaylistCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)


class PlaylistPatchRequest(BaseModel):
    name: str = Field(..., min_length=1)


class PlaylistItemCreateRequest(BaseModel):
    recording_id: int
    position: Optional[int] = None


class ShareCreateRequest(BaseModel):
    share_slug: Optional[str] = None
    share_enabled: bool = True
    expires_at: Optional[datetime] = None
    regenerate_token: bool = False
