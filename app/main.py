from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import load_config
from .database import create_engine_and_session, get_db
from .models import Channel, Playlist, PlaylistItem, Recording, Share
from .schemas import (
    ChannelCreateRequest,
    ChannelPatchRequest,
    LoginRequest,
    PlaylistCreateRequest,
    PlaylistItemCreateRequest,
    PlaylistPatchRequest,
    RecordingUpdateRequest,
    ShareCreateRequest,
)
from .services.poller import Poller
from .services.recorder import RecordingManager, generate_token, validate_slug, now_utc
from .services.twitch_client import TwitchClient


app = FastAPI(title="Twitch Recorder")
config = load_config()
engine, SessionLocal = create_engine_and_session(config)

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.add_middleware(SessionMiddleware, secret_key=config.app_secret, same_site="lax")

twitch = TwitchClient(config)
recorder = RecordingManager(config)
poller = Poller(twitch, recorder)
scheduler = BackgroundScheduler()


def get_db_session() -> Generator[Session, None, None]:
    yield from get_db(SessionLocal)


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_range_header(range_header: str, file_size: int) -> Optional[tuple[int, int]]:
    if not range_header.startswith("bytes="):
        return None
    span = range_header.replace("bytes=", "", 1).strip()
    if "-" not in span:
        return None
    start_str, end_str = span.split("-", 1)
    if start_str == "":
        return None
    try:
        start = int(start_str)
    except ValueError:
        return None
    try:
        end = int(end_str) if end_str else file_size - 1
    except ValueError:
        return None
    if start >= file_size:
        return None
    end = min(end, file_size - 1)
    if end < start:
        return None
    return start, end


def iter_file_range(path: Path, start: int, end: int, chunk: int = 1024 * 1024):
    with open(path, "rb") as f:
        f.seek(start)
        left = end - start + 1
        while left > 0:
            size = min(chunk, left)
            data = f.read(size)
            if not data:
                break
            left -= len(data)
            yield data


def require_admin(request: Request) -> None:
    if request.session.get("authenticated") is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")


def normalize_username(username: str) -> str:
    return username.strip().lstrip("@").lower()


def channel_payload(channel: Channel):
    return {
        "id": channel.id,
        "twitch_username": channel.twitch_username,
        "display_name": channel.display_name,
        "enabled": channel.enabled,
        "status": channel.status,
        "is_live": channel.is_live,
        "auto_add_to_playlist": channel.auto_add_to_playlist,
        "auto_playlist_id": channel.auto_playlist_id,
        "last_checked_at": channel.last_checked_at.isoformat() if channel.last_checked_at else None,
        "last_stream_title": channel.last_stream_title,
    }


def recording_payload(recording: Recording):
    share = recording.share
    share_key = None
    if share and share.enabled:
        share_key = share.slug or share.token
    return {
        "id": recording.id,
        "channel_id": recording.channel_id,
        "channel": recording.channel.twitch_username if recording.channel else None,
        "twitch_stream_id": recording.twitch_stream_id,
        "title_original": recording.title_original,
        "title_display": recording.title_display,
        "started_at": recording.started_at.isoformat() if recording.started_at else None,
        "ended_at": recording.ended_at.isoformat() if recording.ended_at else None,
        "duration_sec": recording.duration_sec,
        "status": recording.status,
        "file_path": recording.file_path,
        "share_key": share_key,
        "share_enabled": share.enabled if share else False,
        "share_slug": share.slug if share else None,
        "share_token": share.token if share else None,
        "share_expires_at": share.expires_at.isoformat() if share and share.expires_at else None,
    }


def playlist_payload(playlist: Playlist):
    return {
        "id": playlist.id,
        "name": playlist.name,
        "items": [
            {
                "recording_id": item.recording_id,
                "position": item.position,
                "recording_title": item.recording.title_display if item.recording else None,
                "recording_status": item.recording.status if item.recording else None,
                "channel": item.recording.channel.twitch_username if item.recording and item.recording.channel else None,
            }
            for item in sorted(playlist.items, key=lambda i: i.position)
        ],
    }


def get_share_for_key(session: Session, key: str) -> Optional[Share]:
    # Priority: custom slug first, token fallback
    share = session.query(Share).filter(Share.slug == key, Share.enabled.is_(True)).first()
    if share:
        if share.expires_at and share.expires_at < now():
            return None
        return share
    share = session.query(Share).filter(Share.token == key, Share.enabled.is_(True)).first()
    if share:
        if share.expires_at and share.expires_at < now():
            return None
        return share
    return None


def stream_video(request: Request, path: str) -> StreamingResponse:
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Replay file not found")
    file_size = os.path.getsize(path)
    if file_size == 0:
        raise HTTPException(status_code=404, detail="Replay is empty")
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(path, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})
    parsed = parse_range_header(range_header, file_size)
    if not parsed:
        headers = {
            "Content-Range": f"bytes */{file_size}",
            "Accept-Ranges": "bytes",
        }
        raise HTTPException(status_code=416, detail="Invalid range", headers=headers)
    start, end = parsed
    content_length = end - start + 1
    return StreamingResponse(
        iter_file_range(Path(path), start, end),
        status_code=206,
        media_type="video/mp4",
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        },
    )


@app.on_event("startup")
def startup_event():
    if not scheduler.get_job("twitch-poller"):
        def _run_job():
            with SessionLocal() as session:
                poller.run_once(session)

        scheduler.add_job(
            _run_job,
            "interval",
            seconds=config.poll_interval_seconds,
            id="twitch-poller",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
    scheduler.start()


@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown(wait=False)
    with SessionLocal() as session:
        recorder.stop_all(session)
        session.commit()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login")
async def login(payload: LoginRequest, request: Request):
    if payload.username != config.admin_username or payload.password != config.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    request.session["authenticated"] = True
    request.session["username"] = payload.username
    return {"ok": True}


@app.post("/api/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/auth/me")
async def whoami(request: Request):
    if request.session.get("authenticated") is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {"authenticated": True, "username": request.session.get("username")}


@app.get("/api/channels")
def list_channels(request: Request, db: Session = Depends(get_db_session)):
    require_admin(request)
    channels = db.query(Channel).order_by(Channel.created_at.desc()).all()
    return [channel_payload(c) for c in channels]


@app.post("/api/channels")
def create_channel(payload: ChannelCreateRequest, request: Request, db: Session = Depends(get_db_session)):
    require_admin(request)
    username = normalize_username(payload.twitch_username)
    if not username:
        raise HTTPException(status_code=400, detail="twitch_username required")
    existing = db.query(Channel).filter(Channel.twitch_username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Channel already exists")
    if payload.auto_playlist_id:
        playlist = db.get(Playlist, payload.auto_playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")
    display_name = twitch.resolve_display_name(username)
    channel = Channel(
        twitch_username=username,
        display_name=display_name,
        auto_add_to_playlist=payload.auto_add_to_playlist,
        auto_playlist_id=payload.auto_playlist_id,
    )
    db.add(channel)
    db.commit()
    return channel_payload(channel)


@app.patch("/api/channels/{channel_id}")
def update_channel(
    channel_id: int,
    payload: ChannelPatchRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    require_admin(request)
    channel = db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if payload.enabled is not None:
        channel.enabled = payload.enabled
    if payload.auto_add_to_playlist is not None:
        channel.auto_add_to_playlist = payload.auto_add_to_playlist
    if payload.auto_playlist_id is not None:
        if payload.auto_playlist_id:
            playlist = db.get(Playlist, payload.auto_playlist_id)
            if not playlist:
                raise HTTPException(status_code=404, detail="Playlist not found")
        channel.auto_playlist_id = payload.auto_playlist_id
    db.add(channel)
    db.commit()
    return channel_payload(channel)


@app.delete("/api/channels/{channel_id}")
def delete_channel(channel_id: int, request: Request, db: Session = Depends(get_db_session)):
    require_admin(request)
    channel = db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if recorder.is_recording(channel.id):
        recorder.stop(db, channel, reason="deleted")
    db.delete(channel)
    db.commit()
    return {"ok": True}


@app.get("/api/recordings")
def list_recordings(
    request: Request,
    db: Session = Depends(get_db_session),
    channel_id: Optional[int] = None,
):
    require_admin(request)
    query = db.query(Recording)
    if channel_id:
        query = query.filter(Recording.channel_id == channel_id)
    return [recording_payload(r) for r in query.order_by(Recording.started_at.desc()).all()]


@app.patch("/api/recordings/{recording_id}")
def update_recording_title(
    recording_id: int,
    payload: RecordingUpdateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    require_admin(request)
    recording = db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    recording.title_display = payload.title_display.strip()
    db.add(recording)
    db.commit()
    return recording_payload(recording)


@app.post("/api/recordings/{recording_id}/share")
def configure_share(
    recording_id: int,
    payload: ShareCreateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    require_admin(request)
    recording = db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    share = recording.share
    now = now()
    if payload.share_enabled is False:
        if not share:
            raise HTTPException(status_code=404, detail="Share not configured")
        share.enabled = False
        share.expires_at = now
        db.add(share)
        db.commit()
        return {
            "recording_id": recording.id,
            "enabled": False,
            "share_slug": None,
            "share_token": None,
        }

    if not share:
        share = Share(recording_id=recording.id, token=generate_token(), enabled=True)
    elif payload.regenerate_token:
        share.token = generate_token()

    if payload.share_slug:
        slug = payload.share_slug.strip()
        if not validate_slug(slug):
            raise HTTPException(
                status_code=400,
                detail="share_slug must match ^[a-zA-Z0-9_-]{3,80}$",
            )
        existing = (
            db.query(Share)
            .filter(Share.slug == slug, Share.recording_id != recording.id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Slug already exists")
        share.slug = slug
    elif payload.share_slug is not None and payload.share_slug.strip() == "":
        share.slug = None

    share.enabled = True
    share.expires_at = payload.expires_at
    db.add(share)
    db.commit()

    share_key = share.slug or share.token
    return {
        "recording_id": recording.id,
        "enabled": True,
        "share_slug": share.slug,
        "share_token": share.token,
        "share_url": f"/share/{share_key}",
        "expires_at": share.expires_at.isoformat() if share.expires_at else None,
    }


@app.delete("/api/recordings/{recording_id}/share")
def revoke_share(recording_id: int, request: Request, db: Session = Depends(get_db_session)):
    require_admin(request)
    recording = db.get(Recording, recording_id)
    if not recording or not recording.share:
        raise HTTPException(status_code=404, detail="Share not found")
    recording.share.enabled = False
    db.add(recording.share)
    db.commit()
    return {"ok": True}


@app.get("/api/playlists")
def list_playlists(request: Request, db: Session = Depends(get_db_session)):
    require_admin(request)
    playlists = db.query(Playlist).order_by(Playlist.name.asc()).all()
    return [playlist_payload(p) for p in playlists]


@app.post("/api/playlists")
def create_playlist(payload: PlaylistCreateRequest, request: Request, db: Session = Depends(get_db_session)):
    require_admin(request)
    name = payload.name.strip()
    if db.query(Playlist).filter(Playlist.name == name).first():
        raise HTTPException(status_code=409, detail="Playlist already exists")
    playlist = Playlist(name=name)
    db.add(playlist)
    db.commit()
    return playlist_payload(playlist)


@app.patch("/api/playlists/{playlist_id}")
def rename_playlist(
    playlist_id: int,
    payload: PlaylistPatchRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    require_admin(request)
    playlist = db.get(Playlist, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    name = payload.name.strip()
    if db.query(Playlist).filter(Playlist.name == name, Playlist.id != playlist_id).first():
        raise HTTPException(status_code=409, detail="Playlist name already exists")
    playlist.name = name
    db.add(playlist)
    db.commit()
    return playlist_payload(playlist)


@app.delete("/api/playlists/{playlist_id}")
def delete_playlist(playlist_id: int, request: Request, db: Session = Depends(get_db_session)):
    require_admin(request)
    playlist = db.get(Playlist, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    db.delete(playlist)
    db.commit()
    return {"ok": True}


@app.post("/api/playlists/{playlist_id}/items")
def add_to_playlist(
    playlist_id: int,
    payload: PlaylistItemCreateRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    require_admin(request)
    playlist = db.get(Playlist, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    recording = db.get(Recording, payload.recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    exists = (
        db.query(PlaylistItem)
        .filter(PlaylistItem.playlist_id == playlist_id, PlaylistItem.recording_id == payload.recording_id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Recording already in playlist")

    max_pos = db.query(func.max(PlaylistItem.position)).filter(PlaylistItem.playlist_id == playlist_id).scalar() or 0
    position = payload.position or (max_pos + 1)
    if position < 1:
        position = 1
    if position > max_pos + 1:
        position = max_pos + 1
    if payload.position is not None:
        db.query(PlaylistItem).filter(
            PlaylistItem.playlist_id == playlist_id,
            PlaylistItem.position >= position,
        ).update({PlaylistItem.position: PlaylistItem.position + 1}, synchronize_session=False)
    db.add(PlaylistItem(playlist_id=playlist_id, recording_id=payload.recording_id, position=position))
    db.commit()
    return {"ok": True, "playlist_id": playlist_id, "recording_id": payload.recording_id, "position": position}


@app.delete("/api/playlists/{playlist_id}/items/{recording_id}")
def remove_from_playlist(
    playlist_id: int,
    recording_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
):
    require_admin(request)
    item = (
        db.query(PlaylistItem)
        .filter(PlaylistItem.playlist_id == playlist_id, PlaylistItem.recording_id == recording_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Playlist item not found")
    db.delete(item)
    db.query(PlaylistItem).filter(
        PlaylistItem.playlist_id == playlist_id, PlaylistItem.position > item.position
    ).update({PlaylistItem.position: PlaylistItem.position - 1}, synchronize_session=False)
    db.commit()
    return {"ok": True}


@app.get("/api/watch/{recording_id}")
def watch_admin(recording_id: int, request: Request, db: Session = Depends(get_db_session)):
    require_admin(request)
    recording = db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    return recording_payload(recording)


@app.get("/api/media/{recording_id}")
def media_admin(recording_id: int, request: Request, db: Session = Depends(get_db_session)):
    require_admin(request)
    recording = db.get(Recording, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    return stream_video(request, recording.file_path)


@app.get("/share/{key}", response_class=HTMLResponse)
def share_page(request: Request, key: str, db: Session = Depends(get_db_session)):
    share = get_share_for_key(db, key)
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    recording = share.recording
    return templates.TemplateResponse(
        "share.html",
        {
            "request": request,
            "title": recording.title_display,
            "channel": recording.channel.twitch_username if recording.channel else "unknown",
            "key": key,
            "share": share,
        },
    )


@app.get("/share/{key}/media")
def share_media(key: str, request: Request, db: Session = Depends(get_db_session)):
    share = get_share_for_key(db, key)
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    recording = share.recording
    return stream_video(request, recording.file_path)
