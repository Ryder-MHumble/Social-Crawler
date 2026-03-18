# -*- coding: utf-8 -*-
"""
Vibe Coding Store Wrapper

Intercepts platform store calls and redirects to VibeCodingStore.
- content → vibe_coding_raw_data (with scoring filter)
- comments → accumulated in memory, flushed as top_comments JSONB
- creators → skipped (creator info already in content row)
"""

from typing import Dict

import vibe_coding.config as vc_cfg
from vibe_coding.store import VibeCodingStore
from tools import utils


class VibeCodingStoreWrapper:

    def __init__(self, platform: str, original_store):
        self.platform = platform
        self.original_store = original_store
        self.vibe_store = VibeCodingStore(platform)
        # content_ids that were actually saved to vibe_coding_raw_data this session
        self._saved_ids: set = set()
        # content_id -> sorted list of top-N comments
        self._top_comments: dict = {}

    async def store_content(self, content_item: Dict):
        if not vc_cfg.ENABLE_VIBE_CODING_COLLECTION:
            await self.original_store.store_content(content_item)
            return

        try:
            result = await self.vibe_store.save_vibe_coding_content(content_item)
            if result is not None:
                content_id = str(
                    content_item.get("content_id")
                    or content_item.get("note_id")
                    or content_item.get("aweme_id")
                    or content_item.get("video_id")
                    or ""
                )
                if content_id:
                    self._saved_ids.add(content_id)
        except Exception as e:
            utils.logger.warning(f"[VibeCodingWrapper] store_content error: {e}")

    async def store_comment(self, comment_item: Dict):
        if not vc_cfg.ENABLE_VIBE_CODING_COLLECTION:
            await self.original_store.store_comment(comment_item)
            return

        content_id = str(
            comment_item.get("content_id")
            or comment_item.get("note_id")
            or ""
        )
        if not content_id or content_id not in self._saved_ids:
            return

        # Skip very short comments
        body = (comment_item.get("content") or "").strip()
        if len(body) < vc_cfg.VIBE_CODING_MIN_COMMENT_LENGTH:
            return

        max_n = vc_cfg.VIBE_CODING_TOP_COMMENTS_COUNT
        bucket = self._top_comments.setdefault(content_id, [])
        bucket.append(comment_item)
        bucket.sort(key=lambda c: int(c.get("like_count", 0) or 0), reverse=True)
        self._top_comments[content_id] = bucket[:max_n]

        # Incremental flush to DB
        try:
            from database.supabase_client import get_supabase
            from tools.time_util import get_current_timestamp
            sb = get_supabase()
            serialized = [
                {
                    "comment_id": c.get("comment_id"),
                    "content": c.get("content", ""),
                    "nickname": c.get("nickname", ""),
                    "like_count": int(c.get("like_count", 0) or 0),
                    "publish_time": c.get("publish_time"),
                }
                for c in self._top_comments[content_id]
            ]
            sb.table("vibe_coding_raw_data").update({
                "top_comments": serialized,
                "last_modify_ts": int(get_current_timestamp()),
            }).eq("platform", self.platform).eq("content_id", content_id).execute()
        except Exception as e:
            utils.logger.debug(f"[VibeCodingWrapper] flush top_comments failed: {e}")

    async def store_creator(self, creator_item: Dict):
        if not vc_cfg.ENABLE_VIBE_CODING_COLLECTION:
            await self.original_store.store_creator(creator_item)

    def __getattr__(self, name):
        return getattr(self.original_store, name)
