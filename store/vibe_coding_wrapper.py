# -*- coding: utf-8 -*-
"""
Vibe Coding Store Wrapper

Replaces platform stores to save vibe coding content ONLY to vibe_coding_raw_data table.
Does NOT save to sentiment_contents or sentiment_comments tables.

When ENABLE_VIBE_CODING_COLLECTION is True:
- Content → vibe_coding_raw_data table (with keyword filtering)
- Comments → Collected in memory and saved as JSONB in top_comments field
- Creators → Skipped (creator info already in content)

When ENABLE_VIBE_CODING_COLLECTION is False:
- Falls back to original store behavior
"""

from typing import Dict, List
import config
from database.vibe_coding_store import VibeCodingStore
from tools import utils


class VibeCodingStoreWrapper:
    """
    Wrapper that intercepts store calls and saves ONLY to vibe_coding_raw_data table.

    This wrapper completely replaces the original store when vibe coding collection
    is enabled, preventing duplicate saves to sentiment_contents/comments tables.
    """

    def __init__(self, platform: str, original_store):
        self.platform = platform
        self.original_store = original_store
        self.vibe_store = VibeCodingStore(platform)
        # Set of content_ids saved to vibe_coding_raw_data (for comment filtering)
        self._vibe_saved_ids: set = set()
        # content_id -> sorted top-N comments (accumulated as comments arrive)
        self._top_comments: dict = {}

    async def store_content(self, content_item: Dict):
        """
        Store content ONLY to vibe_coding_raw_data table (skip original store).
        Comments haven't arrived yet, so top_comments starts empty and is updated later.
        """
        if not getattr(config, "ENABLE_VIBE_CODING_COLLECTION", False):
            await self.original_store.store_content(content_item)
            return

        try:
            saved = await self.vibe_store.save_vibe_coding_content(content_item)
            if saved is not None:
                # Track that this content was saved so comments can be flushed later
                content_id = str(content_item.get("content_id", ""))
                if content_id:
                    self._vibe_saved_ids.add(content_id)
        except Exception as e:
            utils.logger.warning(f"[VibeCodingWrapper] Failed to save content: {e}")

    async def store_comment(self, comment_item: Dict):
        """
        Collect top-N comments in memory for each vibe-relevant content,
        then flush to vibe_coding_raw_data.top_comments after each batch.
        Does NOT write to sentiment_comments.
        """
        if not getattr(config, "ENABLE_VIBE_CODING_COLLECTION", False):
            await self.original_store.store_comment(comment_item)
            return

        content_id = str(comment_item.get("content_id", ""))
        if not content_id or content_id not in self._vibe_saved_ids:
            return

        max_n = getattr(config, "VIBE_CODING_TOP_COMMENTS_COUNT", 20)
        bucket = self._top_comments.setdefault(content_id, [])
        bucket.append(comment_item)
        bucket.sort(key=lambda x: int(x.get("like_count", 0) or 0), reverse=True)
        self._top_comments[content_id] = bucket[:max_n]

        # Flush top_comments to DB after every comment (incremental update)
        try:
            from database.supabase_client import get_supabase
            from tools.time_util import get_current_timestamp
            sb = get_supabase()
            top = [
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
                "top_comments": top,
                "last_modify_ts": int(get_current_timestamp()),
            }).eq("platform", self.platform).eq("content_id", content_id).execute()
        except Exception as e:
            utils.logger.debug(f"[VibeCodingWrapper] Failed to flush top_comments: {e}")

    async def store_creator(self, creator_item: Dict):
        """
        Skip creator storage for vibe coding (not needed).
        """
        # Check if vibe coding collection is enabled
        if not getattr(config, "ENABLE_VIBE_CODING_COLLECTION", False):
            # If vibe coding is disabled, fall back to original store
            await self.original_store.store_creator(creator_item)
            return

        # For vibe coding mode, we don't need to store creators separately
        # Creator info is already included in content_item
        pass

    # Delegate other methods to original store
    def __getattr__(self, name):
        return getattr(self.original_store, name)
