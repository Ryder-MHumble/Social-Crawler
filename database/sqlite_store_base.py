# -*- coding: utf-8 -*-
"""Unified cleaned SQLite write helpers for crawler storage implementations."""

from __future__ import annotations

import os
from typing import Any

import config

from .sqlite_storage import get_sqlite_storage


class SQLiteUnifiedStoreBase:
    def __init__(self, platform: str):
        self.platform = platform
        self.storage = get_sqlite_storage()
        self.storage.initialize()

    @staticmethod
    def _to_int(value: Any) -> int:
        if value is None or value == "":
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            try:
                return int(float(str(value)))
            except (TypeError, ValueError):
                return 0

    @staticmethod
    def _source_keyword(content_item: dict[str, Any]) -> str:
        return str(content_item.get("source_keyword", "") or "")

    @staticmethod
    def _context() -> dict[str, str]:
        return {
            "run_id": os.getenv("SOCIAL_CRAWLER_RUN_ID", "").strip(),
            "task_slug": os.getenv("SOCIAL_CRAWLER_TASK_SLUG", "").strip(),
            "stage_key": os.getenv("SOCIAL_CRAWLER_STAGE_KEY", "").strip(),
            "job_key": os.getenv("SOCIAL_CRAWLER_JOB_KEY", "").strip(),
        }

    def _observe(
        self,
        *,
        entity_type: str,
        external_id: str,
        source_keyword: str,
        clean_status: str,
        clean_reason: str,
        rule_key: str,
        dedup_fingerprint: str,
        snapshot: dict[str, Any],
    ) -> None:
        context = self._context()
        if not external_id:
            return
        self.storage.record_observation(
            {
                **context,
                "entity_type": entity_type,
                "platform": self.platform,
                "external_id": external_id,
                "source_keyword": source_keyword or "",
                "clean_status": clean_status,
                "clean_reason": clean_reason,
                "rule_key": rule_key,
                "dedup_fingerprint": dedup_fingerprint,
                "snapshot_json": snapshot,
            }
        )

    @staticmethod
    def _is_content_relevant(title: str, description: str) -> bool:
        if not getattr(config, "ENABLE_RELEVANCE_FILTER", False):
            return True
        text = f"{title or ''} {description or ''}".lower()
        for keyword in getattr(config, "RELEVANCE_EXCLUDE_KEYWORDS", []):
            if str(keyword).lower() in text:
                return False
        must_contain = getattr(config, "RELEVANCE_MUST_CONTAIN", [])
        if not must_contain:
            return True
        return any(str(keyword).lower() in text for keyword in must_contain)

    def save_content(self, content_item: dict[str, Any]) -> None:
        content_id = str(content_item.get("content_id", "") or "")
        if not content_id:
            return
        source_keyword = self._source_keyword(content_item)
        title = str(content_item.get("title", "") or "")
        description = str(content_item.get("description", "") or "")
        is_official = source_keyword.startswith("@")
        dedup_fingerprint = f"{self.platform}:{content_id}"

        if not is_official and not self._is_content_relevant(title, description):
            self._observe(
                entity_type="content",
                external_id=content_id,
                source_keyword=source_keyword,
                clean_status="filtered",
                clean_reason="Content failed relevance filter.",
                rule_key="relevance_filter",
                dedup_fingerprint=dedup_fingerprint,
                snapshot=content_item,
            )
            return

        min_engagement = int(getattr(config, "MIN_CONTENT_ENGAGEMENT", 0) or 0)
        engagement = self._to_int(content_item.get("liked_count")) + self._to_int(
            content_item.get("comment_count")
        )
        if not is_official and min_engagement > 0 and engagement < min_engagement:
            self._observe(
                entity_type="content",
                external_id=content_id,
                source_keyword=source_keyword,
                clean_status="filtered",
                clean_reason=f"Content engagement {engagement} is below {min_engagement}.",
                rule_key="engagement_filter",
                dedup_fingerprint=dedup_fingerprint,
                snapshot=content_item,
            )
            return

        existed = self.storage.has_content(platform=self.platform, content_id=content_id)
        self.storage.upsert_content({"platform": self.platform, **content_item})
        self._observe(
            entity_type="content",
            external_id=content_id,
            source_keyword=source_keyword,
            clean_status="deduped" if existed else "accepted",
            clean_reason="Existing content updated." if existed else "Content stored.",
            rule_key="content_id_dedup" if existed else "accepted_content",
            dedup_fingerprint=dedup_fingerprint,
            snapshot=content_item,
        )

    def save_comment(self, comment_item: dict[str, Any]) -> None:
        comment_id = str(comment_item.get("comment_id", "") or "")
        if not comment_id:
            return
        source_keyword = self._source_keyword(comment_item)
        parent_content_id = str(comment_item.get("content_id", "") or "")
        dedup_fingerprint = f"{self.platform}:{comment_id}"

        if getattr(config, "ENABLE_RELEVANCE_FILTER", False) and parent_content_id:
            if not self.storage.has_content(platform=self.platform, content_id=parent_content_id):
                self._observe(
                    entity_type="comment",
                    external_id=comment_id,
                    source_keyword=source_keyword,
                    clean_status="filtered",
                    clean_reason="Parent content was not accepted into the cleaned dataset.",
                    rule_key="parent_content_filter",
                    dedup_fingerprint=dedup_fingerprint,
                    snapshot=comment_item,
                )
                return

        min_comment_length = int(getattr(config, "MIN_COMMENT_LENGTH", 0) or 0)
        content = str(comment_item.get("content", "") or "").strip()
        if min_comment_length > 0 and len(content) < min_comment_length:
            self._observe(
                entity_type="comment",
                external_id=comment_id,
                source_keyword=source_keyword,
                clean_status="filtered",
                clean_reason=f"Comment length {len(content)} is below {min_comment_length}.",
                rule_key="comment_length_filter",
                dedup_fingerprint=dedup_fingerprint,
                snapshot=comment_item,
            )
            return

        existed = self.storage.has_comment(platform=self.platform, comment_id=comment_id)
        self.storage.upsert_comment({"platform": self.platform, **comment_item})
        self._observe(
            entity_type="comment",
            external_id=comment_id,
            source_keyword=source_keyword,
            clean_status="deduped" if existed else "accepted",
            clean_reason="Existing comment updated." if existed else "Comment stored.",
            rule_key="comment_id_dedup" if existed else "accepted_comment",
            dedup_fingerprint=dedup_fingerprint,
            snapshot=comment_item,
        )

    def save_creator(self, creator_item: dict[str, Any]) -> None:
        user_id = str(creator_item.get("user_id", "") or "")
        if not user_id:
            return
        dedup_fingerprint = f"{self.platform}:{user_id}"
        existed = self.storage.has_creator(platform=self.platform, user_id=user_id)
        self.storage.upsert_creator({"platform": self.platform, **creator_item})
        self._observe(
            entity_type="creator",
            external_id=user_id,
            source_keyword="",
            clean_status="deduped" if existed else "accepted",
            clean_reason="Existing creator updated." if existed else "Creator stored.",
            rule_key="creator_id_dedup" if existed else "accepted_creator",
            dedup_fingerprint=dedup_fingerprint,
            snapshot=creator_item,
        )
