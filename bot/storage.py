import asyncio
import os
import sqlite3
import threading

DEFAULT_RULES = "Запрещены спам, реклама, оскорбления, разжигание ненависти и флуд."


class Storage:
    """SQLite-backed per-chat settings and warning counters.

    Blocking sqlite3 calls run in a thread pool via asyncio.to_thread; a
    threading.Lock serializes access since the connection is shared across
    those worker threads.
    """

    def __init__(self, db_path: str):
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def init_db(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    connected INTEGER NOT NULL DEFAULT 0,
                    automod_enabled INTEGER NOT NULL DEFAULT 0,
                    rules TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS warnings (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (chat_id, user_id)
                )
                """
            )

    async def get_chat(self, chat_id: int) -> dict:
        return await asyncio.to_thread(self._get_chat_sync, chat_id)

    def _get_chat_sync(self, chat_id: int) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM chats WHERE chat_id = ?", (chat_id,)
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO chats (chat_id, title, connected, automod_enabled, rules) "
                    "VALUES (?, '', 0, 0, ?)",
                    (chat_id, DEFAULT_RULES),
                )
                self._conn.commit()
                row = self._conn.execute(
                    "SELECT * FROM chats WHERE chat_id = ?", (chat_id,)
                ).fetchone()
            return dict(row)

    async def set_connected(self, chat_id: int, title: str, connected: bool) -> None:
        await self.get_chat(chat_id)
        await asyncio.to_thread(self._set_connected_sync, chat_id, title, connected)

    def _set_connected_sync(self, chat_id: int, title: str, connected: bool) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE chats SET title = ?, connected = ?, automod_enabled = ? WHERE chat_id = ?",
                (title, int(connected), int(connected), chat_id),
            )

    async def set_automod(self, chat_id: int, enabled: bool) -> None:
        await self.get_chat(chat_id)
        await asyncio.to_thread(
            self._exec, "UPDATE chats SET automod_enabled = ? WHERE chat_id = ?", (int(enabled), chat_id)
        )

    async def set_rules(self, chat_id: int, rules: str) -> None:
        await self.get_chat(chat_id)
        await asyncio.to_thread(
            self._exec, "UPDATE chats SET rules = ? WHERE chat_id = ?", (rules, chat_id)
        )

    def _exec(self, query: str, params: tuple) -> None:
        with self._lock, self._conn:
            self._conn.execute(query, params)

    async def add_warning(self, chat_id: int, user_id: int) -> int:
        return await asyncio.to_thread(self._add_warning_sync, chat_id, user_id)

    def _add_warning_sync(self, chat_id: int, user_id: int) -> int:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO warnings (chat_id, user_id, count) VALUES (?, ?, 1) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET count = count + 1",
                (chat_id, user_id),
            )
            row = self._conn.execute(
                "SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            ).fetchone()
            return row["count"]

    async def get_warnings(self, chat_id: int, user_id: int) -> int:
        return await asyncio.to_thread(self._get_warnings_sync, chat_id, user_id)

    def _get_warnings_sync(self, chat_id: int, user_id: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            ).fetchone()
            return row["count"] if row else 0

    async def reset_warnings(self, chat_id: int, user_id: int) -> None:
        await asyncio.to_thread(
            self._exec,
            "DELETE FROM warnings WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
