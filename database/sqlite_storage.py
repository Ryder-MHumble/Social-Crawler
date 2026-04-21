# -*- coding: utf-8 -*-
"""Unified SQLite storage backend for task console data and cleaned crawler output."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.db_config import sqlite_db_config

SCHEMA_COMPONENT = "task_console_sqlite"
SCHEMA_VERSION = 1

WATCHDOG_DEFAULTS = {
    "job_start_timeout_sec": 120,
    "job_stall_timeout_sec": 600,
    "terminate_grace_sec": 15,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _normalize_json(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "null"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return _json_dumps(value)
        return _json_dumps(parsed)
    return _json_dumps(value)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return 0


@dataclass(frozen=True)
class TableDefinition:
    name: str
    create_sql: str
    indexes: tuple[str, ...]
    order_by: str
    searchable_columns: tuple[str, ...]


TABLE_DEFINITIONS: dict[str, TableDefinition] = {
    "crawl_contents": TableDefinition(
        name="crawl_contents",
        create_sql="""
        CREATE TABLE IF NOT EXISTS crawl_contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            content_id TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            content_url TEXT NOT NULL DEFAULT '',
            cover_url TEXT NOT NULL DEFAULT '',
            user_id TEXT NOT NULL DEFAULT '',
            nickname TEXT NOT NULL DEFAULT '',
            avatar TEXT NOT NULL DEFAULT '',
            ip_location TEXT NOT NULL DEFAULT '',
            liked_count INTEGER NOT NULL DEFAULT 0,
            comment_count INTEGER NOT NULL DEFAULT 0,
            share_count INTEGER NOT NULL DEFAULT 0,
            collected_count INTEGER NOT NULL DEFAULT 0,
            publish_time TEXT,
            platform_payload_json TEXT NOT NULL DEFAULT '{}',
            source_keyword TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE(platform, content_id)
        )
        """,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_crawl_contents_platform ON crawl_contents(platform)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_contents_publish_time ON crawl_contents(publish_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_contents_source_keyword ON crawl_contents(source_keyword)",
        ),
        order_by="last_seen_at DESC, id DESC",
        searchable_columns=("platform", "content_id", "title", "description", "nickname", "source_keyword"),
    ),
    "crawl_comments": TableDefinition(
        name="crawl_comments",
        create_sql="""
        CREATE TABLE IF NOT EXISTS crawl_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            comment_id TEXT NOT NULL,
            content_platform TEXT NOT NULL DEFAULT '',
            content_id TEXT NOT NULL DEFAULT '',
            parent_comment_id TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            pictures_json TEXT NOT NULL DEFAULT '[]',
            user_id TEXT NOT NULL DEFAULT '',
            nickname TEXT NOT NULL DEFAULT '',
            avatar TEXT NOT NULL DEFAULT '',
            ip_location TEXT NOT NULL DEFAULT '',
            like_count INTEGER NOT NULL DEFAULT 0,
            sub_comment_count INTEGER NOT NULL DEFAULT 0,
            publish_time TEXT,
            platform_payload_json TEXT NOT NULL DEFAULT '{}',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE(platform, comment_id)
        )
        """,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_crawl_comments_platform ON crawl_comments(platform)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_comments_content ON crawl_comments(content_platform, content_id)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_comments_publish_time ON crawl_comments(publish_time DESC)",
        ),
        order_by="last_seen_at DESC, id DESC",
        searchable_columns=("platform", "comment_id", "content_id", "content", "nickname"),
    ),
    "crawl_creators": TableDefinition(
        name="crawl_creators",
        create_sql="""
        CREATE TABLE IF NOT EXISTS crawl_creators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            user_id TEXT NOT NULL,
            nickname TEXT NOT NULL DEFAULT '',
            avatar TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            gender TEXT NOT NULL DEFAULT '',
            ip_location TEXT NOT NULL DEFAULT '',
            follows_count INTEGER NOT NULL DEFAULT 0,
            fans_count INTEGER NOT NULL DEFAULT 0,
            interaction_count INTEGER NOT NULL DEFAULT 0,
            platform_payload_json TEXT NOT NULL DEFAULT '{}',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE(platform, user_id)
        )
        """,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_crawl_creators_platform ON crawl_creators(platform)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_creators_fans ON crawl_creators(fans_count DESC)",
        ),
        order_by="last_seen_at DESC, id DESC",
        searchable_columns=("platform", "user_id", "nickname", "description"),
    ),
    "crawl_observations": TableDefinition(
        name="crawl_observations",
        create_sql="""
        CREATE TABLE IF NOT EXISTS crawl_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            task_slug TEXT NOT NULL DEFAULT '',
            stage_key TEXT NOT NULL DEFAULT '',
            job_key TEXT NOT NULL DEFAULT '',
            entity_type TEXT NOT NULL,
            platform TEXT NOT NULL,
            external_id TEXT NOT NULL,
            source_keyword TEXT NOT NULL DEFAULT '',
            clean_status TEXT NOT NULL,
            clean_reason TEXT NOT NULL DEFAULT '',
            rule_key TEXT NOT NULL DEFAULT '',
            dedup_fingerprint TEXT NOT NULL DEFAULT '',
            snapshot_json TEXT NOT NULL DEFAULT '{}',
            observed_at TEXT NOT NULL,
            UNIQUE(run_id, entity_type, platform, external_id, source_keyword)
        )
        """,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_crawl_observations_run ON crawl_observations(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_observations_status ON crawl_observations(clean_status)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_observations_task ON crawl_observations(task_slug)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_observations_platform ON crawl_observations(platform)",
        ),
        order_by="observed_at DESC, id DESC",
        searchable_columns=(
            "run_id",
            "task_slug",
            "stage_key",
            "job_key",
            "entity_type",
            "platform",
            "external_id",
            "source_keyword",
            "clean_status",
            "clean_reason",
            "rule_key",
            "dedup_fingerprint",
            "snapshot_json",
        ),
    ),
    "outreach_candidates": TableDefinition(
        name="outreach_candidates",
        create_sql="""
        CREATE TABLE IF NOT EXISTS outreach_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_name TEXT NOT NULL,
            run_id TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            creator_name TEXT NOT NULL DEFAULT '',
            profile_url TEXT NOT NULL DEFAULT '',
            bio TEXT NOT NULL DEFAULT '',
            fans_count INTEGER NOT NULL DEFAULT 0,
            total_views INTEGER NOT NULL DEFAULT 0,
            average_views INTEGER NOT NULL DEFAULT 0,
            video_count INTEGER NOT NULL DEFAULT 0,
            representative_videos_json TEXT NOT NULL DEFAULT '[]',
            discovery_keyword TEXT NOT NULL DEFAULT '',
            filter_status TEXT NOT NULL DEFAULT 'discovered',
            filter_reason TEXT NOT NULL DEFAULT '',
            raw_row_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            UNIQUE(campaign_name, platform, creator_id)
        )
        """,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_outreach_candidates_campaign ON outreach_candidates(campaign_name)",
            "CREATE INDEX IF NOT EXISTS idx_outreach_candidates_status ON outreach_candidates(filter_status)",
        ),
        order_by="updated_at DESC, id DESC",
        searchable_columns=(
            "campaign_name",
            "platform",
            "creator_id",
            "creator_name",
            "bio",
            "discovery_keyword",
            "filter_status",
            "filter_reason",
        ),
    ),
    "outreach_deliveries": TableDefinition(
        name="outreach_deliveries",
        create_sql="""
        CREATE TABLE IF NOT EXISTS outreach_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_name TEXT NOT NULL,
            run_id TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            creator_name TEXT NOT NULL DEFAULT '',
            message_template_id TEXT NOT NULL DEFAULT '',
            message_body TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            error_message TEXT NOT NULL DEFAULT '',
            attempt_no INTEGER NOT NULL DEFAULT 1,
            sent_at TEXT NOT NULL,
            UNIQUE(campaign_name, platform, creator_id, attempt_no)
        )
        """,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_outreach_deliveries_campaign ON outreach_deliveries(campaign_name)",
            "CREATE INDEX IF NOT EXISTS idx_outreach_deliveries_status ON outreach_deliveries(status)",
        ),
        order_by="sent_at DESC, id DESC",
        searchable_columns=(
            "campaign_name",
            "platform",
            "creator_id",
            "creator_name",
            "message_template_id",
            "status",
            "error_message",
        ),
    ),
    "vibe_content_scores": TableDefinition(
        name="vibe_content_scores",
        create_sql="""
        CREATE TABLE IF NOT EXISTS vibe_content_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            content_id TEXT NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            matched_keywords_json TEXT NOT NULL DEFAULT '[]',
            trend_category TEXT NOT NULL DEFAULT '',
            analysis_status TEXT NOT NULL DEFAULT 'pending',
            top_comments_json TEXT NOT NULL DEFAULT '[]',
            title_fingerprint TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            UNIQUE(run_id, platform, content_id)
        )
        """,
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_vibe_scores_run ON vibe_content_scores(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_vibe_scores_platform ON vibe_content_scores(platform)",
            "CREATE INDEX IF NOT EXISTS idx_vibe_scores_score ON vibe_content_scores(score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_vibe_scores_fingerprint ON vibe_content_scores(title_fingerprint)",
        ),
        order_by="updated_at DESC, id DESC",
        searchable_columns=(
            "run_id",
            "platform",
            "content_id",
            "trend_category",
            "analysis_status",
            "title_fingerprint",
            "matched_keywords_json",
        ),
    ),
}


class SQLiteStorage:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or sqlite_db_config["db_path"]).expanduser()
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def initialize(self) -> dict[str, Any]:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_versions (
                        component TEXT PRIMARY KEY,
                        version INTEGER NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                for definition in TABLE_DEFINITIONS.values():
                    conn.execute(definition.create_sql)
                    for index_sql in definition.indexes:
                        conn.execute(index_sql)
                conn.execute(
                    """
                    INSERT INTO schema_versions(component, version, updated_at)
                    VALUES(?, ?, ?)
                    ON CONFLICT(component) DO UPDATE SET
                        version=excluded.version,
                        updated_at=excluded.updated_at
                    """,
                    (SCHEMA_COMPONENT, SCHEMA_VERSION, _utc_now()),
                )
                conn.commit()
        return self.get_status()

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row is not None

    def is_initialized(self) -> bool:
        if not self.db_path.exists():
            return False
        with self._lock:
            with self._connect() as conn:
                if not self._table_exists(conn, "schema_versions"):
                    return False
                row = conn.execute(
                    "SELECT version FROM schema_versions WHERE component=?",
                    (SCHEMA_COMPONENT,),
                ).fetchone()
                return row is not None

    def get_status(self) -> dict[str, Any]:
        exists = self.db_path.exists()
        initialized = self.is_initialized()
        table_names: list[str] = []
        schema_version: int | None = None
        if exists:
            with self._lock:
                with self._connect() as conn:
                    table_names = [
                        row["name"]
                        for row in conn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                        ).fetchall()
                    ]
                    if self._table_exists(conn, "schema_versions"):
                        row = conn.execute(
                            "SELECT version FROM schema_versions WHERE component=?",
                            (SCHEMA_COMPONENT,),
                        ).fetchone()
                        if row is not None:
                            schema_version = int(row["version"])
        stat = self.db_path.stat() if exists else None
        return {
            "path": str(self.db_path),
            "exists": exists,
            "initialized": initialized,
            "schema_version": schema_version,
            "table_count": len(table_names),
            "table_names": table_names,
            "db_size_bytes": stat.st_size if stat else 0,
            "last_modified_at": (
                datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                if stat
                else None
            ),
            "watchdog": dict(WATCHDOG_DEFAULTS),
        }

    def list_tables(self) -> list[dict[str, Any]]:
        if not self.is_initialized():
            return []
        with self._lock:
            with self._connect() as conn:
                tables: list[dict[str, Any]] = []
                for name, definition in TABLE_DEFINITIONS.items():
                    count = conn.execute(f"SELECT COUNT(*) AS count FROM {name}").fetchone()["count"]
                    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({name})").fetchall()]
                    tables.append(
                        {
                            "name": name,
                            "row_count": int(count),
                            "columns": columns,
                            "order_by": definition.order_by,
                        }
                    )
                return tables

    def _build_filters(
        self,
        table: str,
        *,
        run_id: str | None = None,
        task_slug: str | None = None,
        platform: str | None = None,
        entity_type: str | None = None,
        clean_status: str | None = None,
        q: str | None = None,
    ) -> tuple[list[str], list[Any]]:
        if table not in TABLE_DEFINITIONS:
            raise ValueError(f"Unsupported table: {table}")
        with self._lock:
            with self._connect() as conn:
                columns = {
                    row["name"]
                    for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
                }
        filters: list[tuple[str, str | None]] = [
            ("run_id", run_id),
            ("task_slug", task_slug),
            ("platform", platform),
            ("entity_type", entity_type),
            ("clean_status", clean_status),
        ]
        clauses: list[str] = []
        values: list[Any] = []
        for column, value in filters:
            if value and column in columns:
                clauses.append(f"{column} = ?")
                values.append(value)
        if q:
            search_columns = [col for col in TABLE_DEFINITIONS[table].searchable_columns if col in columns]
            if search_columns:
                clauses.append("(" + " OR ".join(f"{column} LIKE ?" for column in search_columns) + ")")
                values.extend([f"%{q}%"] * len(search_columns))
        return clauses, values

    def query_rows(
        self,
        *,
        table: str,
        run_id: str | None = None,
        task_slug: str | None = None,
        platform: str | None = None,
        entity_type: str | None = None,
        clean_status: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        if not self.is_initialized():
            return {"table": table, "columns": [], "rows": [], "total": 0}
        if table not in TABLE_DEFINITIONS:
            raise ValueError(f"Unsupported table: {table}")
        limit = max(1, min(500, int(limit)))
        offset = max(0, int(offset))
        with self._lock:
            with self._connect() as conn:
                columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
                clauses, values = self._build_filters(
                    table,
                    run_id=run_id,
                    task_slug=task_slug,
                    platform=platform,
                    entity_type=entity_type,
                    clean_status=clean_status,
                    q=q,
                )
                where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
                total = conn.execute(
                    f"SELECT COUNT(*) AS count FROM {table} {where_sql}",
                    values,
                ).fetchone()["count"]
                rows = conn.execute(
                    f"""
                    SELECT * FROM {table}
                    {where_sql}
                    ORDER BY {TABLE_DEFINITIONS[table].order_by}
                    LIMIT ? OFFSET ?
                    """,
                    [*values, limit, offset],
                ).fetchall()
        return {
            "table": table,
            "columns": columns,
            "rows": [dict(row) for row in rows],
            "total": int(total),
        }

    def get_row(self, *, table: str, row_id: int) -> dict[str, Any] | None:
        if not self.is_initialized():
            return None
        if table not in TABLE_DEFINITIONS:
            raise ValueError(f"Unsupported table: {table}")
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE id = ?",
                    (int(row_id),),
                ).fetchone()
        return dict(row) if row else None

    def get_stats(
        self,
        *,
        table: str | None = None,
        run_id: str | None = None,
        task_slug: str | None = None,
        platform: str | None = None,
        entity_type: str | None = None,
        clean_status: str | None = None,
        q: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_initialized():
            return {"table_counts": {}, "observation_status_counts": {}}
        with self._lock:
            with self._connect() as conn:
                table_counts = {
                    name: int(conn.execute(f"SELECT COUNT(*) AS count FROM {name}").fetchone()["count"])
                    for name in TABLE_DEFINITIONS
                    if table is None or name == table
                }
                clauses, values = self._build_filters(
                    "crawl_observations",
                    run_id=run_id,
                    task_slug=task_slug,
                    platform=platform,
                    entity_type=entity_type,
                    clean_status=clean_status,
                    q=q,
                )
                where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
                rows = conn.execute(
                    f"""
                    SELECT clean_status, COUNT(*) AS count
                    FROM crawl_observations
                    {where_sql}
                    GROUP BY clean_status
                    """,
                    values,
                ).fetchall()
        return {
            "table_counts": table_counts,
            "observation_status_counts": {
                row["clean_status"]: int(row["count"])
                for row in rows
            },
        }

    def _get_existing_row(
        self,
        conn: sqlite3.Connection,
        table: str,
        unique_clause: str,
        params: tuple[Any, ...],
    ) -> sqlite3.Row | None:
        return conn.execute(
            f"SELECT * FROM {table} WHERE {unique_clause}",
            params,
        ).fetchone()

    def upsert_content(self, row: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        payload = {
            "platform": _normalize_text(row.get("platform")),
            "content_id": _normalize_text(row.get("content_id")),
            "content_type": _normalize_text(row.get("content_type")),
            "title": _normalize_text(row.get("title")),
            "description": _normalize_text(row.get("description")),
            "content_url": _normalize_text(row.get("content_url")),
            "cover_url": _normalize_text(row.get("cover_url")),
            "user_id": _normalize_text(row.get("user_id")),
            "nickname": _normalize_text(row.get("nickname")),
            "avatar": _normalize_text(row.get("avatar")),
            "ip_location": _normalize_text(row.get("ip_location")),
            "liked_count": _normalize_int(row.get("liked_count")),
            "comment_count": _normalize_int(row.get("comment_count")),
            "share_count": _normalize_int(row.get("share_count")),
            "collected_count": _normalize_int(row.get("collected_count")),
            "publish_time": row.get("publish_time"),
            "platform_payload_json": _normalize_json(row.get("platform_payload_json")),
            "source_keyword": _normalize_text(row.get("source_keyword")),
        }
        with self._lock:
            with self._connect() as conn:
                existing = self._get_existing_row(
                    conn,
                    "crawl_contents",
                    "platform = ? AND content_id = ?",
                    (payload["platform"], payload["content_id"]),
                )
                if existing:
                    conn.execute(
                        """
                        UPDATE crawl_contents
                        SET content_type=?, title=?, description=?, content_url=?, cover_url=?,
                            user_id=?, nickname=?, avatar=?, ip_location=?, liked_count=?,
                            comment_count=?, share_count=?, collected_count=?, publish_time=?,
                            platform_payload_json=?, source_keyword=?, last_seen_at=?
                        WHERE id=?
                        """,
                        (
                            payload["content_type"],
                            payload["title"],
                            payload["description"],
                            payload["content_url"],
                            payload["cover_url"],
                            payload["user_id"],
                            payload["nickname"],
                            payload["avatar"],
                            payload["ip_location"],
                            payload["liked_count"],
                            payload["comment_count"],
                            payload["share_count"],
                            payload["collected_count"],
                            payload["publish_time"],
                            payload["platform_payload_json"],
                            payload["source_keyword"],
                            now,
                            existing["id"],
                        ),
                    )
                    conn.commit()
                    return {"id": int(existing["id"]), "created": False}
                cursor = conn.execute(
                    """
                    INSERT INTO crawl_contents(
                        platform, content_id, content_type, title, description, content_url, cover_url,
                        user_id, nickname, avatar, ip_location, liked_count, comment_count, share_count,
                        collected_count, publish_time, platform_payload_json, source_keyword, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["platform"],
                        payload["content_id"],
                        payload["content_type"],
                        payload["title"],
                        payload["description"],
                        payload["content_url"],
                        payload["cover_url"],
                        payload["user_id"],
                        payload["nickname"],
                        payload["avatar"],
                        payload["ip_location"],
                        payload["liked_count"],
                        payload["comment_count"],
                        payload["share_count"],
                        payload["collected_count"],
                        payload["publish_time"],
                        payload["platform_payload_json"],
                        payload["source_keyword"],
                        now,
                        now,
                    ),
                )
                conn.commit()
                return {"id": int(cursor.lastrowid), "created": True}

    def upsert_comment(self, row: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        payload = {
            "platform": _normalize_text(row.get("platform")),
            "comment_id": _normalize_text(row.get("comment_id")),
            "content_platform": _normalize_text(row.get("content_platform") or row.get("platform")),
            "content_id": _normalize_text(row.get("content_id")),
            "parent_comment_id": _normalize_text(row.get("parent_comment_id")),
            "content": _normalize_text(row.get("content")),
            "pictures_json": _normalize_json(row.get("pictures_json")),
            "user_id": _normalize_text(row.get("user_id")),
            "nickname": _normalize_text(row.get("nickname")),
            "avatar": _normalize_text(row.get("avatar")),
            "ip_location": _normalize_text(row.get("ip_location")),
            "like_count": _normalize_int(row.get("like_count")),
            "sub_comment_count": _normalize_int(row.get("sub_comment_count")),
            "publish_time": row.get("publish_time"),
            "platform_payload_json": _normalize_json(row.get("platform_payload_json")),
        }
        with self._lock:
            with self._connect() as conn:
                existing = self._get_existing_row(
                    conn,
                    "crawl_comments",
                    "platform = ? AND comment_id = ?",
                    (payload["platform"], payload["comment_id"]),
                )
                if existing:
                    conn.execute(
                        """
                        UPDATE crawl_comments
                        SET content_platform=?, content_id=?, parent_comment_id=?, content=?,
                            pictures_json=?, user_id=?, nickname=?, avatar=?, ip_location=?,
                            like_count=?, sub_comment_count=?, publish_time=?, platform_payload_json=?,
                            last_seen_at=?
                        WHERE id=?
                        """,
                        (
                            payload["content_platform"],
                            payload["content_id"],
                            payload["parent_comment_id"],
                            payload["content"],
                            payload["pictures_json"],
                            payload["user_id"],
                            payload["nickname"],
                            payload["avatar"],
                            payload["ip_location"],
                            payload["like_count"],
                            payload["sub_comment_count"],
                            payload["publish_time"],
                            payload["platform_payload_json"],
                            now,
                            existing["id"],
                        ),
                    )
                    conn.commit()
                    return {"id": int(existing["id"]), "created": False}
                cursor = conn.execute(
                    """
                    INSERT INTO crawl_comments(
                        platform, comment_id, content_platform, content_id, parent_comment_id, content,
                        pictures_json, user_id, nickname, avatar, ip_location, like_count,
                        sub_comment_count, publish_time, platform_payload_json, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["platform"],
                        payload["comment_id"],
                        payload["content_platform"],
                        payload["content_id"],
                        payload["parent_comment_id"],
                        payload["content"],
                        payload["pictures_json"],
                        payload["user_id"],
                        payload["nickname"],
                        payload["avatar"],
                        payload["ip_location"],
                        payload["like_count"],
                        payload["sub_comment_count"],
                        payload["publish_time"],
                        payload["platform_payload_json"],
                        now,
                        now,
                    ),
                )
                conn.commit()
                return {"id": int(cursor.lastrowid), "created": True}

    def upsert_creator(self, row: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        payload = {
            "platform": _normalize_text(row.get("platform")),
            "user_id": _normalize_text(row.get("user_id")),
            "nickname": _normalize_text(row.get("nickname")),
            "avatar": _normalize_text(row.get("avatar")),
            "description": _normalize_text(row.get("description")),
            "gender": _normalize_text(row.get("gender")),
            "ip_location": _normalize_text(row.get("ip_location")),
            "follows_count": _normalize_int(row.get("follows_count")),
            "fans_count": _normalize_int(row.get("fans_count")),
            "interaction_count": _normalize_int(row.get("interaction_count")),
            "platform_payload_json": _normalize_json(row.get("platform_payload_json")),
        }
        with self._lock:
            with self._connect() as conn:
                existing = self._get_existing_row(
                    conn,
                    "crawl_creators",
                    "platform = ? AND user_id = ?",
                    (payload["platform"], payload["user_id"]),
                )
                if existing:
                    conn.execute(
                        """
                        UPDATE crawl_creators
                        SET nickname=?, avatar=?, description=?, gender=?, ip_location=?,
                            follows_count=?, fans_count=?, interaction_count=?, platform_payload_json=?, last_seen_at=?
                        WHERE id=?
                        """,
                        (
                            payload["nickname"],
                            payload["avatar"],
                            payload["description"],
                            payload["gender"],
                            payload["ip_location"],
                            payload["follows_count"],
                            payload["fans_count"],
                            payload["interaction_count"],
                            payload["platform_payload_json"],
                            now,
                            existing["id"],
                        ),
                    )
                    conn.commit()
                    return {"id": int(existing["id"]), "created": False}
                cursor = conn.execute(
                    """
                    INSERT INTO crawl_creators(
                        platform, user_id, nickname, avatar, description, gender, ip_location,
                        follows_count, fans_count, interaction_count, platform_payload_json, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["platform"],
                        payload["user_id"],
                        payload["nickname"],
                        payload["avatar"],
                        payload["description"],
                        payload["gender"],
                        payload["ip_location"],
                        payload["follows_count"],
                        payload["fans_count"],
                        payload["interaction_count"],
                        payload["platform_payload_json"],
                        now,
                        now,
                    ),
                )
                conn.commit()
                return {"id": int(cursor.lastrowid), "created": True}

    def record_observation(self, row: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        payload = {
            "run_id": _normalize_text(row.get("run_id")),
            "task_slug": _normalize_text(row.get("task_slug")),
            "stage_key": _normalize_text(row.get("stage_key")),
            "job_key": _normalize_text(row.get("job_key")),
            "entity_type": _normalize_text(row.get("entity_type")),
            "platform": _normalize_text(row.get("platform")),
            "external_id": _normalize_text(row.get("external_id")),
            "source_keyword": _normalize_text(row.get("source_keyword")),
            "clean_status": _normalize_text(row.get("clean_status")),
            "clean_reason": _normalize_text(row.get("clean_reason")),
            "rule_key": _normalize_text(row.get("rule_key")),
            "dedup_fingerprint": _normalize_text(row.get("dedup_fingerprint")),
            "snapshot_json": _normalize_json(row.get("snapshot_json")),
            "observed_at": row.get("observed_at") or now,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO crawl_observations(
                        run_id, task_slug, stage_key, job_key, entity_type, platform, external_id,
                        source_keyword, clean_status, clean_reason, rule_key, dedup_fingerprint,
                        snapshot_json, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, entity_type, platform, external_id, source_keyword) DO UPDATE SET
                        task_slug=excluded.task_slug,
                        stage_key=excluded.stage_key,
                        job_key=excluded.job_key,
                        clean_status=excluded.clean_status,
                        clean_reason=excluded.clean_reason,
                        rule_key=excluded.rule_key,
                        dedup_fingerprint=excluded.dedup_fingerprint,
                        snapshot_json=excluded.snapshot_json,
                        observed_at=excluded.observed_at
                    """,
                    (
                        payload["run_id"],
                        payload["task_slug"],
                        payload["stage_key"],
                        payload["job_key"],
                        payload["entity_type"],
                        payload["platform"],
                        payload["external_id"],
                        payload["source_keyword"],
                        payload["clean_status"],
                        payload["clean_reason"],
                        payload["rule_key"],
                        payload["dedup_fingerprint"],
                        payload["snapshot_json"],
                        payload["observed_at"],
                    ),
                )
                conn.commit()
                row_id = conn.execute(
                    """
                    SELECT id FROM crawl_observations
                    WHERE run_id=? AND entity_type=? AND platform=? AND external_id=? AND source_keyword=?
                    """,
                    (
                        payload["run_id"],
                        payload["entity_type"],
                        payload["platform"],
                        payload["external_id"],
                        payload["source_keyword"],
                    ),
                ).fetchone()
        return {"id": int(row_id["id"]) if row_id else None}

    def upsert_outreach_candidate(self, row: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        payload = {
            "campaign_name": _normalize_text(row.get("campaign_name")),
            "run_id": _normalize_text(row.get("run_id")),
            "platform": _normalize_text(row.get("platform")),
            "creator_id": _normalize_text(row.get("creator_id")),
            "creator_name": _normalize_text(row.get("creator_name")),
            "profile_url": _normalize_text(row.get("profile_url")),
            "bio": _normalize_text(row.get("bio")),
            "fans_count": _normalize_int(row.get("fans_count")),
            "total_views": _normalize_int(row.get("total_views")),
            "average_views": _normalize_int(row.get("average_views")),
            "video_count": _normalize_int(row.get("video_count")),
            "representative_videos_json": _normalize_json(row.get("representative_videos_json")),
            "discovery_keyword": _normalize_text(row.get("discovery_keyword")),
            "filter_status": _normalize_text(row.get("filter_status") or "discovered"),
            "filter_reason": _normalize_text(row.get("filter_reason")),
            "raw_row_json": _normalize_json(row.get("raw_row_json")),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO outreach_candidates(
                        campaign_name, run_id, platform, creator_id, creator_name, profile_url, bio,
                        fans_count, total_views, average_views, video_count, representative_videos_json,
                        discovery_keyword, filter_status, filter_reason, raw_row_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_name, platform, creator_id) DO UPDATE SET
                        run_id=excluded.run_id,
                        creator_name=excluded.creator_name,
                        profile_url=excluded.profile_url,
                        bio=excluded.bio,
                        fans_count=excluded.fans_count,
                        total_views=excluded.total_views,
                        average_views=excluded.average_views,
                        video_count=excluded.video_count,
                        representative_videos_json=excluded.representative_videos_json,
                        discovery_keyword=excluded.discovery_keyword,
                        filter_status=excluded.filter_status,
                        filter_reason=excluded.filter_reason,
                        raw_row_json=excluded.raw_row_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        payload["campaign_name"],
                        payload["run_id"],
                        payload["platform"],
                        payload["creator_id"],
                        payload["creator_name"],
                        payload["profile_url"],
                        payload["bio"],
                        payload["fans_count"],
                        payload["total_views"],
                        payload["average_views"],
                        payload["video_count"],
                        payload["representative_videos_json"],
                        payload["discovery_keyword"],
                        payload["filter_status"],
                        payload["filter_reason"],
                        payload["raw_row_json"],
                        now,
                    ),
                )
                conn.commit()
        return {"updated": True}

    def record_outreach_delivery(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "campaign_name": _normalize_text(row.get("campaign_name")),
            "run_id": _normalize_text(row.get("run_id")),
            "platform": _normalize_text(row.get("platform")),
            "creator_id": _normalize_text(row.get("creator_id")),
            "creator_name": _normalize_text(row.get("creator_name")),
            "message_template_id": _normalize_text(row.get("message_template_id")),
            "message_body": _normalize_text(row.get("message_body")),
            "status": _normalize_text(row.get("status")),
            "error_message": _normalize_text(row.get("error_message")),
            "attempt_no": max(1, _normalize_int(row.get("attempt_no")) or 1),
            "sent_at": row.get("sent_at") or _utc_now(),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO outreach_deliveries(
                        campaign_name, run_id, platform, creator_id, creator_name, message_template_id,
                        message_body, status, error_message, attempt_no, sent_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_name, platform, creator_id, attempt_no) DO UPDATE SET
                        run_id=excluded.run_id,
                        creator_name=excluded.creator_name,
                        message_template_id=excluded.message_template_id,
                        message_body=excluded.message_body,
                        status=excluded.status,
                        error_message=excluded.error_message,
                        sent_at=excluded.sent_at
                    """,
                    (
                        payload["campaign_name"],
                        payload["run_id"],
                        payload["platform"],
                        payload["creator_id"],
                        payload["creator_name"],
                        payload["message_template_id"],
                        payload["message_body"],
                        payload["status"],
                        payload["error_message"],
                        payload["attempt_no"],
                        payload["sent_at"],
                    ),
                )
                conn.commit()
        return {"updated": True}

    def has_successful_delivery(self, *, campaign_name: str, platform: str, creator_id: str) -> bool:
        if not self.is_initialized():
            return False
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM outreach_deliveries
                    WHERE campaign_name = ? AND platform = ? AND creator_id = ? AND status = 'success'
                    LIMIT 1
                    """,
                    (campaign_name, platform, creator_id),
                ).fetchone()
        return row is not None

    def get_next_outreach_attempt(self, *, campaign_name: str, platform: str, creator_id: str) -> int:
        if not self.is_initialized():
            return 1
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT COALESCE(MAX(attempt_no), 0) AS max_attempt
                    FROM outreach_deliveries
                    WHERE campaign_name = ? AND platform = ? AND creator_id = ?
                    """,
                    (campaign_name, platform, creator_id),
                ).fetchone()
        return int(row["max_attempt"]) + 1 if row else 1

    def upsert_vibe_content_score(self, row: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        payload = {
            "run_id": _normalize_text(row.get("run_id")),
            "platform": _normalize_text(row.get("platform")),
            "content_id": _normalize_text(row.get("content_id")),
            "score": _normalize_int(row.get("score")),
            "matched_keywords_json": _normalize_json(row.get("matched_keywords_json")),
            "trend_category": _normalize_text(row.get("trend_category")),
            "analysis_status": _normalize_text(row.get("analysis_status") or "pending"),
            "top_comments_json": _normalize_json(row.get("top_comments_json")),
            "title_fingerprint": _normalize_text(row.get("title_fingerprint")),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO vibe_content_scores(
                        run_id, platform, content_id, score, matched_keywords_json, trend_category,
                        analysis_status, top_comments_json, title_fingerprint, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, platform, content_id) DO UPDATE SET
                        score=excluded.score,
                        matched_keywords_json=excluded.matched_keywords_json,
                        trend_category=excluded.trend_category,
                        analysis_status=excluded.analysis_status,
                        top_comments_json=excluded.top_comments_json,
                        title_fingerprint=excluded.title_fingerprint,
                        updated_at=excluded.updated_at
                    """,
                    (
                        payload["run_id"],
                        payload["platform"],
                        payload["content_id"],
                        payload["score"],
                        payload["matched_keywords_json"],
                        payload["trend_category"],
                        payload["analysis_status"],
                        payload["top_comments_json"],
                        payload["title_fingerprint"],
                        now,
                    ),
                )
                conn.commit()
        return {"updated": True}

    def update_vibe_top_comments(
        self,
        *,
        run_id: str,
        platform: str,
        content_id: str,
        top_comments_json: Any,
    ) -> None:
        if not self.is_initialized():
            return
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE vibe_content_scores
                    SET top_comments_json = ?, updated_at = ?
                    WHERE run_id = ? AND platform = ? AND content_id = ?
                    """,
                    (
                        _normalize_json(top_comments_json),
                        _utc_now(),
                        run_id,
                        platform,
                        content_id,
                    ),
                )
                conn.commit()

    def has_vibe_title_fingerprint(self, title_fingerprint: str) -> bool:
        if not title_fingerprint or not self.is_initialized():
            return False
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT 1 FROM vibe_content_scores
                    WHERE title_fingerprint = ?
                    LIMIT 1
                    """,
                    (title_fingerprint,),
                ).fetchone()
        return row is not None

    def has_content(self, *, platform: str, content_id: str) -> bool:
        if not self.is_initialized():
            return False
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM crawl_contents WHERE platform = ? AND content_id = ? LIMIT 1",
                    (platform, content_id),
                ).fetchone()
        return row is not None

    def has_comment(self, *, platform: str, comment_id: str) -> bool:
        if not self.is_initialized():
            return False
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM crawl_comments WHERE platform = ? AND comment_id = ? LIMIT 1",
                    (platform, comment_id),
                ).fetchone()
        return row is not None

    def has_creator(self, *, platform: str, user_id: str) -> bool:
        if not self.is_initialized():
            return False
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM crawl_creators WHERE platform = ? AND user_id = ? LIMIT 1",
                    (platform, user_id),
                ).fetchone()
        return row is not None

    def get_run_metrics(self, run_id: str) -> dict[str, int]:
        if not run_id or not self.is_initialized():
            return {
                "accepted": 0,
                "filtered": 0,
                "deduped": 0,
                "errors": 0,
            }
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT clean_status, COUNT(*) AS count
                    FROM crawl_observations
                    WHERE run_id = ?
                    GROUP BY clean_status
                    """,
                    (run_id,),
                ).fetchall()
        counts = {row["clean_status"]: int(row["count"]) for row in rows}
        return {
            "accepted": counts.get("accepted", 0),
            "filtered": counts.get("filtered", 0),
            "deduped": counts.get("deduped", 0),
            "errors": counts.get("error", 0),
        }

    def get_run_breakdowns(self, run_id: str) -> dict[str, Any]:
        if not run_id or not self.is_initialized():
            return {
                "status_counts": {},
                "filter_reasons": [],
                "platform_status_counts": [],
                "entity_status_counts": [],
                "source_keyword_counts": [],
            }

        with self._lock:
            with self._connect() as conn:
                status_rows = conn.execute(
                    """
                    SELECT clean_status, COUNT(*) AS count
                    FROM crawl_observations
                    WHERE run_id = ?
                    GROUP BY clean_status
                    """,
                    (run_id,),
                ).fetchall()
                filter_reason_rows = conn.execute(
                    """
                    SELECT clean_reason, COUNT(*) AS count
                    FROM crawl_observations
                    WHERE run_id = ? AND clean_status = 'filtered' AND clean_reason != ''
                    GROUP BY clean_reason
                    ORDER BY count DESC, clean_reason ASC
                    LIMIT 8
                    """,
                    (run_id,),
                ).fetchall()
                platform_rows = conn.execute(
                    """
                    SELECT platform, clean_status, COUNT(*) AS count
                    FROM crawl_observations
                    WHERE run_id = ?
                    GROUP BY platform, clean_status
                    ORDER BY platform ASC, clean_status ASC
                    """,
                    (run_id,),
                ).fetchall()
                entity_rows = conn.execute(
                    """
                    SELECT entity_type, clean_status, COUNT(*) AS count
                    FROM crawl_observations
                    WHERE run_id = ?
                    GROUP BY entity_type, clean_status
                    ORDER BY entity_type ASC, clean_status ASC
                    """,
                    (run_id,),
                ).fetchall()
                keyword_rows = conn.execute(
                    """
                    SELECT source_keyword, COUNT(*) AS count
                    FROM crawl_observations
                    WHERE run_id = ? AND source_keyword != ''
                    GROUP BY source_keyword
                    ORDER BY count DESC, source_keyword ASC
                    LIMIT 12
                    """,
                    (run_id,),
                ).fetchall()

        return {
            "status_counts": {
                row["clean_status"]: int(row["count"])
                for row in status_rows
                if row["clean_status"]
            },
            "filter_reasons": [
                {"reason": row["clean_reason"], "count": int(row["count"])}
                for row in filter_reason_rows
            ],
            "platform_status_counts": self._collapse_status_rows(platform_rows, key_name="platform"),
            "entity_status_counts": self._collapse_status_rows(entity_rows, key_name="entity_type"),
            "source_keyword_counts": [
                {"source_keyword": row["source_keyword"], "count": int(row["count"])}
                for row in keyword_rows
            ],
        }

    @staticmethod
    def _collapse_status_rows(rows: list[Any], *, key_name: str) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row[key_name] or "").strip()
            if not key:
                continue
            payload = grouped.setdefault(key, {key_name: key, "counts": {}, "total": 0})
            status = str(row["clean_status"] or "").strip()
            count = int(row["count"])
            payload["counts"][status] = count
            payload["total"] += count
        return list(grouped.values())


_storage_instance: SQLiteStorage | None = None


def get_sqlite_storage() -> SQLiteStorage:
    global _storage_instance
    if _storage_instance is None or _storage_instance.db_path != Path(sqlite_db_config["db_path"]).expanduser():
        _storage_instance = SQLiteStorage()
    return _storage_instance
