from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from replaypos.database.models import Base, SettingsDB


def get_db_path() -> Path:
    db_dir = Path.home() / ".replaypos"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "replaypos.db"


def create_engine_from_path(db_path: Path | str) -> Engine:
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


class DatabaseService:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else get_db_path()
        self.engine = create_engine_from_path(self.db_path)
        self._session_factory = sessionmaker(bind=self.engine)
        logger.info("Database initialized at {}", self.db_path)

    def init_db(self):
        Base.metadata.create_all(self.engine)
        logger.info("Database schema created/verified")

    def create_session(self) -> Session:
        return self._session_factory()

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.create_session() as session:
            row = session.query(SettingsDB).filter(SettingsDB.key == key).first()
            if row is None:
                return default
            try:
                return json.loads(row.value)
            except (json.JSONDecodeError, TypeError):
                return row.value

    def set_setting(self, key: str, value: Any):
        with self.create_session() as session:
            row = session.query(SettingsDB).filter(SettingsDB.key == key).first()
            if row:
                row.value = json.dumps(value) if not isinstance(value, str) else value
            else:
                serialized = json.dumps(value) if not isinstance(value, str) else value
                session.add(SettingsDB(key=key, value=serialized))
            session.commit()

    def close(self):
        self.engine.dispose()
        logger.info("Database connection closed")


_db_service: DatabaseService | None = None


def get_database() -> DatabaseService:
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
        _db_service.init_db()
    return _db_service
