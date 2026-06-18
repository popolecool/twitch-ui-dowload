from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def env_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    app_secret: str
    admin_username: str
    admin_password: str
    data_dir: Path
    db_path: Path
    poll_interval_seconds: int
    twitch_client_id: str | None = None
    twitch_client_secret: str | None = None
    streamlink_quality: str = "best"


def load_config() -> AppConfig:
    data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
    db_path = Path(os.getenv("DB_PATH", "./db/app.db")).resolve()
    return AppConfig(
        app_secret=os.getenv("APP_SECRET", "dev-secret-change-me"),
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", "admin123"),
        data_dir=data_dir,
        db_path=db_path,
        poll_interval_seconds=env_int(os.getenv("POLL_INTERVAL_SECONDS"), 60),
        twitch_client_id=os.getenv("TWITCH_CLIENT_ID"),
        twitch_client_secret=os.getenv("TWITCH_CLIENT_SECRET"),
        streamlink_quality=os.getenv("STREAMLINK_QUALITY", "best"),
    )
