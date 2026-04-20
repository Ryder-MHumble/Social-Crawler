#!/usr/bin/env python3
"""Bilibili DM delivery records backed by the unified SQLite storage."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.sqlite_storage import get_sqlite_storage


class DMRecordStore:
    """Persist outreach delivery attempts into SQLite."""

    def __init__(self) -> None:
        self.storage = get_sqlite_storage()
        self.storage.initialize()

    @staticmethod
    def _current_run_id() -> str:
        return os.getenv("SOCIAL_CRAWLER_RUN_ID", "").strip()

    def _count_deliveries(self, campaign: str, status: str) -> int:
        with self.storage._lock:
            with self.storage._connect() as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM outreach_deliveries
                    WHERE campaign_name = ? AND platform = 'bili' AND status = ?
                    """,
                    (campaign, status),
                ).fetchone()
        return int(row["count"]) if row else 0

    def _list_deliveries(self, campaign: str, status: str) -> list[dict]:
        with self.storage._lock:
            with self.storage._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT creator_id, creator_name, error_message
                    FROM outreach_deliveries
                    WHERE campaign_name = ? AND platform = 'bili' AND status = ?
                    ORDER BY sent_at DESC
                    """,
                    (campaign, status),
                ).fetchall()
        return [
            {
                "user_id": row["creator_id"],
                "username": row["creator_name"],
                "error_msg": row["error_message"],
            }
            for row in rows
        ]

    def save_dm_record(
        self,
        user_id: str,
        username: str,
        message: str,
        status: str,
        error_msg: Optional[str] = None,
        campaign: str = "openclaw_2026",
        message_template_id: str = "",
        run_id: Optional[str] = None,
        attempt_no: Optional[int] = None,
    ) -> bool:
        try:
            resolved_attempt = attempt_no or self.storage.get_next_outreach_attempt(
                campaign_name=campaign,
                platform="bili",
                creator_id=user_id,
            )
            self.storage.record_outreach_delivery(
                {
                    "campaign_name": campaign,
                    "run_id": run_id or self._current_run_id(),
                    "platform": "bili",
                    "creator_id": user_id,
                    "creator_name": username,
                    "message_template_id": message_template_id,
                    "message_body": message,
                    "status": status,
                    "error_message": error_msg or "",
                    "attempt_no": resolved_attempt,
                    "sent_at": datetime.now().isoformat(),
                }
            )
            print(f"已记录到 SQLite: {username} - {status}")
            return True
        except Exception as exc:
            print(f"数据库错误: {exc}")
            return False

    def get_sent_count(self, campaign: str = "openclaw_2026") -> int:
        try:
            return self._count_deliveries(campaign, "success")
        except Exception as exc:
            print(f"查询错误: {exc}")
            return 0

    def get_failed_users(self, campaign: str = "openclaw_2026") -> list:
        try:
            return self._list_deliveries(campaign, "failed")
        except Exception as exc:
            print(f"查询错误: {exc}")
            return []

    def is_already_sent(self, user_id: str, campaign: str = "openclaw_2026") -> bool:
        try:
            return self.storage.has_successful_delivery(
                campaign_name=campaign,
                platform="bili",
                creator_id=user_id,
            )
        except Exception as exc:
            print(f"查询错误: {exc}")
            return False


if __name__ == "__main__":
    store = DMRecordStore()
    print(f"已成功发送: {store.get_sent_count()} 条")
    failed = store.get_failed_users()
    if failed:
        print(f"\n发送失败: {len(failed)} 个用户")
        for user in failed[:5]:
            print(f"  - {user['username']}: {user['error_msg']}")
