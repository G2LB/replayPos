from __future__ import annotations

from typing import Any

from loguru import logger

from replaypos.database.database import get_database


class SettingsManager:
    def __init__(self):
        self._db = get_database()

    def get(self, key: str, default: Any = None) -> Any:
        return self._db.get_setting(key, default)

    def set(self, key: str, value: Any):
        logger.debug("Setting {} = {}", key, value)
        self._db.set_setting(key, value)

    def get_all(self) -> dict[str, Any]:
        with self._db.create_session() as session:
            from replaypos.database.models import SettingsDB

            rows = session.query(SettingsDB).all()
            return {row.key: row.value for row in rows}

    def delete(self, key: str):
        with self._db.create_session() as session:
            from replaypos.database.models import SettingsDB

            row = session.query(SettingsDB).filter(SettingsDB.key == key).first()
            if row:
                session.delete(row)
                session.commit()
