from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    twitch_username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="offline", nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_stream_id: Mapped[Optional[str]] = mapped_column(String(64))
    last_stream_title: Mapped[Optional[str]] = mapped_column(Text)
    auto_add_to_playlist: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_playlist_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    default_playlist: Mapped[Optional["Playlist"]] = relationship(
        "Playlist", back_populates="channels", foreign_keys=[auto_playlist_id]
    )
    recordings: Mapped[List["Recording"]] = relationship("Recording", back_populates="channel", cascade="all, delete-orphan")


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    channels: Mapped[List["Channel"]] = relationship("Channel", back_populates="default_playlist")
    items: Mapped[List["PlaylistItem"]] = relationship(
        "PlaylistItem", back_populates="playlist", cascade="all, delete-orphan", order_by="PlaylistItem.position"
    )


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    twitch_stream_id: Mapped[Optional[str]] = mapped_column(String(64))
    title_original: Mapped[str] = mapped_column(Text, nullable=False)
    title_display: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="recording", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    channel: Mapped["Channel"] = relationship("Channel", back_populates="recordings")
    share: Mapped[Optional["Share"]] = relationship("Share", back_populates="recording", uselist=False, cascade="all, delete-orphan")
    playlist_items: Mapped[List["PlaylistItem"]] = relationship("PlaylistItem", back_populates="recording", cascade="all, delete-orphan")


class PlaylistItem(Base):
    __tablename__ = "playlist_items"
    __table_args__ = (UniqueConstraint("playlist_id", "recording_id", name="uq_playlist_recording"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    playlist_id: Mapped[int] = mapped_column(Integer, ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False)
    recording_id: Mapped[int] = mapped_column(Integer, ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    playlist: Mapped["Playlist"] = relationship("Playlist", back_populates="items")
    recording: Mapped["Recording"] = relationship("Recording", back_populates="playlist_items")


class Share(Base):
    __tablename__ = "shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recording_id: Mapped[int] = mapped_column(Integer, ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, unique=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(80), unique=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    recording: Mapped["Recording"] = relationship("Recording", back_populates="share")
