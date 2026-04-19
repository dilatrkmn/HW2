from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class Storage:
    """SQLite-backed persistence for crawls and search."""

    def __init__(self, db_path: str = "data/crawler.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS crawl_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin_url TEXT NOT NULL,
                    max_depth INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    pages_discovered INTEGER NOT NULL DEFAULT 0,
                    pages_fetched INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT,
                    body TEXT,
                    fetched_at REAL,
                    fetch_status TEXT NOT NULL,
                    last_error TEXT
                );

                CREATE TABLE IF NOT EXISTS discoveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    page_id INTEGER NOT NULL,
                    depth INTEGER NOT NULL,
                    discovered_from TEXT,
                    UNIQUE(job_id, page_id),
                    FOREIGN KEY(job_id) REFERENCES crawl_jobs(id),
                    FOREIGN KEY(page_id) REFERENCES pages(id)
                );

                CREATE INDEX IF NOT EXISTS idx_discoveries_job_depth ON discoveries(job_id, depth);
                CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
                """
            )

    def create_job(self, origin_url: str, max_depth: int) -> int:
        now = time.time()
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO crawl_jobs(origin_url, max_depth, status, created_at, updated_at)
                VALUES(?, ?, 'running', ?, ?)
                """,
                (origin_url, max_depth, now, now),
            )
            return int(cursor.lastrowid)

    def set_job_status(self, job_id: int, status: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE crawl_jobs SET status=?, updated_at=? WHERE id=?",
                (status, time.time(), job_id),
            )

    def upsert_page_shell(self, url: str) -> int:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO pages(url, fetch_status) VALUES(?, 'pending')",
                (url,),
            )
            row = self._conn.execute("SELECT id FROM pages WHERE url=?", (url,)).fetchone()
            return int(row["id"])

    def save_discovery(self, job_id: int, page_id: int, depth: int, discovered_from: str | None) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO discoveries(job_id, page_id, depth, discovered_from)
                VALUES(?, ?, ?, ?)
                """,
                (job_id, page_id, depth, discovered_from),
            )
            created = cur.rowcount > 0
            if created:
                self._conn.execute(
                    "UPDATE crawl_jobs SET pages_discovered = pages_discovered + 1, updated_at=? WHERE id=?",
                    (time.time(), job_id),
                )
            return created

    def mark_page_fetched(self, page_id: int, title: str, body: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE pages
                SET title=?, body=?, fetched_at=?, fetch_status='ok', last_error=NULL
                WHERE id=?
                """,
                (title, body, time.time(), page_id),
            )

    def mark_page_error(self, page_id: int, error: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE pages
                SET fetched_at=?, fetch_status='error', last_error=?
                WHERE id=?
                """,
                (time.time(), error[:500], page_id),
            )

    def increment_job_fetched(self, job_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE crawl_jobs SET pages_fetched = pages_fetched + 1, updated_at=? WHERE id=?",
                (time.time(), job_id),
            )

    def search(self, query: str, limit: int = 200) -> list[dict[str, Any]]:
        like = f"%{query.lower()}%"
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT p.url AS relevant_url, j.origin_url, d.depth,
                       p.title, p.fetch_status
                FROM pages p
                JOIN discoveries d ON d.page_id = p.id
                JOIN crawl_jobs j ON j.id = d.job_id
                WHERE p.fetch_status='ok'
                AND (LOWER(COALESCE(p.title, '')) LIKE ? OR LOWER(COALESCE(p.body, '')) LIKE ?)
                ORDER BY d.depth ASC, p.fetched_at DESC
                LIMIT ?
                """,
                (like, like, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, origin_url, max_depth, status, created_at, updated_at,
                       pages_discovered, pages_fetched
                FROM crawl_jobs
                ORDER BY id DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def count_pages_by_status(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT fetch_status, COUNT(*) as c FROM pages GROUP BY fetch_status"
            ).fetchall()
        result = {"ok": 0, "pending": 0, "error": 0}
        for row in rows:
            result[row["fetch_status"]] = int(row["c"])
        return result

    def reset_all(self) -> None:
        """Delete all crawl jobs/pages/discoveries to start clean."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM discoveries")
            self._conn.execute("DELETE FROM pages")
            self._conn.execute("DELETE FROM crawl_jobs")
