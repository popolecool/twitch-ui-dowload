from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import AppConfig
from .models import Base


def create_engine_and_session(config: AppConfig):
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{Path(config.db_path).resolve()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    return engine, SessionLocal


def get_db(SessionLocal) -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
