import sqlite3
from contextlib import contextmanager
from typing import Optional


class Database:
    def __init__(self, path: str = "bot.sqlite3"):
        self.path = path
        self._init()

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _table_columns(self, con: sqlite3.Connection, table: str) -> set[str]:
        cur = con.execute(f"PRAGMA table_info({table})")
        return {row["name"] for row in cur.fetchall()}

    def _init(self):
        with self.connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    step INTEGER NOT NULL DEFAULT 0,
                    nickname TEXT,
                    inviter_id INTEGER,
                    referral_count INTEGER NOT NULL DEFAULT 0,
                    applied INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'В обработке'
                )
            """)

            con.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    invited_id INTEGER PRIMARY KEY,
                    inviter_id INTEGER NOT NULL,
                    notified INTEGER NOT NULL DEFAULT 0,
                    invited_nickname TEXT,
                    created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_ref_inviter ON referrals(inviter_id)")

            # Таблица кликов по каналам (для закрытых каналов и как защита от “не нажал кнопку”)
            con.execute("""
                CREATE TABLE IF NOT EXISTS channel_clicks (
                    user_id INTEGER NOT NULL,
                    channel_key TEXT NOT NULL,
                    created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                    PRIMARY KEY(user_id, channel_key)
                )
            """)

            # --- Миграция если ты раньше делал channel_id и словил "no such column"
            cols = self._table_columns(con, "channel_clicks")
            if "channel_id" in cols and "channel_key" not in cols:
                # создаём новую таблицу правильную и копируем
                con.execute("""
                    CREATE TABLE IF NOT EXISTS channel_clicks_new (
                        user_id INTEGER NOT NULL,
                        channel_key TEXT NOT NULL,
                        created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                        PRIMARY KEY(user_id, channel_key)
                    )
                """)
                try:
                    con.execute("""
                        INSERT OR IGNORE INTO channel_clicks_new(user_id, channel_key, created_at)
                        SELECT user_id, channel_id, created_at FROM channel_clicks
                    """)
                except Exception:
                    # если created_at не было
                    con.execute("""
                        INSERT OR IGNORE INTO channel_clicks_new(user_id, channel_key)
                        SELECT user_id, channel_id FROM channel_clicks
                    """)

                con.execute("DROP TABLE channel_clicks")
                con.execute("ALTER TABLE channel_clicks_new RENAME TO channel_clicks")

    # --- users ---
    def ensure_user(self, user_id: int) -> None:
        with self.connect() as con:
            con.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))

    def get_user(self, user_id: int) -> Optional[sqlite3.Row]:
        with self.connect() as con:
            cur = con.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            return cur.fetchone()

    def set_step(self, user_id: int, step: int) -> None:
        with self.connect() as con:
            con.execute("UPDATE users SET step=? WHERE user_id=?", (step, user_id))

    def set_nickname(self, user_id: int, nickname: str | None) -> None:
        with self.connect() as con:
            con.execute("UPDATE users SET nickname=? WHERE user_id=?", (nickname, user_id))

    def set_applied(self, user_id: int, applied: int) -> None:
        with self.connect() as con:
            con.execute("UPDATE users SET applied=? WHERE user_id=?", (applied, user_id))

    def set_status(self, user_id: int, status: str) -> None:
        with self.connect() as con:
            con.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))

    def set_inviter(self, user_id: int, inviter_id: int) -> None:
        with self.connect() as con:
            con.execute("UPDATE users SET inviter_id=? WHERE user_id=?", (inviter_id, user_id))

    def get_referral_count(self, user_id: int) -> int:
        with self.connect() as con:
            cur = con.execute("SELECT referral_count FROM users WHERE user_id=?", (user_id,))
            row = cur.fetchone()
            return int(row["referral_count"]) if row else 0

    # --- referrals ---
    def add_referral_once(self, invited_id: int, inviter_id: int) -> bool:
        with self.connect() as con:
            cur = con.execute("SELECT 1 FROM referrals WHERE invited_id=? LIMIT 1", (invited_id,))
            if cur.fetchone():
                return False

            con.execute(
                "INSERT INTO referrals(invited_id, inviter_id) VALUES (?, ?)",
                (invited_id, inviter_id),
            )
            con.execute(
                "UPDATE users SET referral_count = referral_count + 1 WHERE user_id=?",
                (inviter_id,),
            )
            return True

    def mark_referral_notified(self, invited_id: int, nickname: str) -> None:
        with self.connect() as con:
            con.execute(
                "UPDATE referrals SET notified=1, invited_nickname=? WHERE invited_id=?",
                (nickname, invited_id),
            )

    def get_referral_inviter(self, invited_id: int) -> Optional[int]:
        with self.connect() as con:
            cur = con.execute("SELECT inviter_id FROM referrals WHERE invited_id=? LIMIT 1", (invited_id,))
            row = cur.fetchone()
            return int(row["inviter_id"]) if row else None

    def is_referral_notified(self, invited_id: int) -> bool:
        with self.connect() as con:
            cur = con.execute("SELECT notified FROM referrals WHERE invited_id=? LIMIT 1", (invited_id,))
            row = cur.fetchone()
            return bool(row and int(row["notified"]) == 1)

    # --- channel clicks ---
    def mark_channel_clicked(self, user_id: int, channel_key: str) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO channel_clicks(user_id, channel_key) VALUES (?, ?)",
                (user_id, channel_key),
            )

    def has_clicked_channel(self, user_id: int, channel_key: str) -> bool:
        with self.connect() as con:
            cur = con.execute(
                "SELECT 1 FROM channel_clicks WHERE user_id=? AND channel_key=? LIMIT 1",
                (user_id, channel_key),
            )
            return cur.fetchone() is not None

    def reset_channel_clicks(self, user_id: int) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM channel_clicks WHERE user_id=?", (user_id,))