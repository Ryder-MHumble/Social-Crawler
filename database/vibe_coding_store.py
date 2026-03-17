# -*- coding: utf-8 -*-
"""
Vibe Coding Data Store

Handles storage of vibe coding related content to the vibe_coding_raw_data table.
This store is optimized for trend analysis and idea extraction workflows.
"""

from typing import Dict, List, Optional
import hashlib

import config
from database.supabase_client import get_supabase
from database.supabase_store_base import SupabaseStoreBase
from tools import utils
from tools.time_util import get_current_timestamp


class VibeCodingStore(SupabaseStoreBase):
    """
    Store for vibe coding raw data collection.

    This store extends the base store with vibe coding specific logic:
    - Keyword matching and categorization
    - Top comments collection
    - Innovation scoring (when AI analysis is enabled)
    - Session tracking for batch processing
    """

    def __init__(self, platform: str):
        super().__init__(platform)
        self.session_id = getattr(config, "CURRENT_CRAWL_SESSION_ID", None)
        self._vibe_coding_keywords = getattr(config, "VIBE_CODING_KEYWORDS", [])

    async def _ensure_preloaded(self):
        """
        Override parent method to preload from vibe_coding_raw_data table.
        Loads existing content IDs for cross-session deduplication.
        """
        if self.platform in self._preloaded_platforms:
            return

        self._preloaded_platforms.add(self.platform)
        try:
            sb = get_supabase()
            result = sb.table("vibe_coding_raw_data").select("content_id").eq("platform", self.platform).execute()
            rows = result.data or []
            existing_ids = {str(row["content_id"]) for row in rows if row.get("content_id")}
            self._seen_content_ids.update(existing_ids)
            utils.logger.info(
                f"[VibeCodingStore] Preloaded {len(existing_ids)} existing {self.platform} content IDs "
                f"(cross-session dedup)"
            )
        except Exception as e:
            utils.logger.warning(
                f"[VibeCodingStore] Failed to preload existing IDs for {self.platform}: {e}. "
                f"Dedup for this session may be incomplete."
            )

    def _matches_vibe_coding_keywords(self, title: str, description: str) -> List[str]:
        """
        Check if content matches vibe coding keywords.
        Returns list of matched keywords.
        """
        text = f"{title or ''} {description or ''}".lower()
        matched = []

        for keyword in self._vibe_coding_keywords:
            if keyword.lower() in text:
                matched.append(keyword)

        return matched

    def _categorize_content(self, title: str, description: str, keywords: List[str]) -> str:
        """
        Categorize content based on matched keywords and content.
        Returns a trend category from VIBE_CODING_TREND_CATEGORIES.
        """
        text = f"{title or ''} {description or ''}".lower()

        # Simple rule-based categorization (can be enhanced with AI later)
        if any(k in text for k in ["cursor", "copilot", "claude", "ai编程", "ai写代码"]):
            return "AI-assisted coding"
        elif any(k in text for k in ["零代码", "低代码", "no code", "low code", "v0", "bolt"]):
            return "no-code tools"
        elif any(k in text for k in ["副业", "兼职", "独立开发", "一人公司", "solopreneur"]):
            return "indie hacking"
        elif any(k in text for k in ["快速开发", "mvp", "10分钟", "一天做"]):
            return "rapid prototyping"
        elif any(k in text for k in ["工具流", "工具链", "workflow"]):
            return "workflow automation"
        elif any(k in text for k in ["教程", "学习", "入门"]):
            return "learning resources"
        elif any(k in text for k in ["实战", "案例", "项目"]):
            return "case studies"
        else:
            return "other"

    @staticmethod
    def _parse_count(val) -> int:
        """Parse count value, handling Chinese number formats like '1.7万'."""
        if not val:
            return 0
        s = str(val).strip()
        if '万' in s:
            try:
                return int(float(s.replace('万', '')) * 10000)
            except Exception:
                return 0
        try:
            return int(float(s))
        except Exception:
            return 0

    async def save_vibe_coding_content(
        self,
        content_item: Dict,
        top_comments: Optional[List[Dict]] = None
    ):
        """
        Save content to vibe_coding_raw_data table.

        Args:
            content_item: Content data dict (same format as sentiment_contents)
            top_comments: Optional list of top comment dicts for idea mining
        """
        # Support both 'content_id' and platform-specific IDs (e.g. 'note_id' for XHS)
        content_id = (
            content_item.get("content_id")
            or content_item.get("note_id")
            or content_item.get("aweme_id")
            or content_item.get("video_id")
            or content_item.get("weibo_id")
        )
        if not content_id:
            return

        content_id = str(content_id)

        # Pre-load existing IDs for dedup
        await self._ensure_preloaded()

        # Check if already processed
        if content_id in self._seen_content_ids:
            utils.logger.debug(
                f"[VibeCodingStore] SKIP (already processed) {self.platform}/{content_id}"
            )
            return

        title = content_item.get("title", "") or ""
        # Support both 'description' and 'desc' field names
        description = content_item.get("description") or content_item.get("desc", "") or ""

        # Check vibe coding keyword match
        matched_keywords = self._matches_vibe_coding_keywords(title, description)
        if not matched_keywords:
            utils.logger.debug(
                f"[VibeCodingStore] SKIP (no vibe coding keywords) {self.platform}/{content_id}"
            )
            return

        # Engagement filter (higher threshold for quality)
        min_engagement = getattr(config, "VIBE_CODING_MIN_ENGAGEMENT", 10)
        liked = self._parse_count(content_item.get("liked_count", 0))
        comments = self._parse_count(content_item.get("comment_count", 0))
        if liked + comments < min_engagement:
            utils.logger.debug(
                f"[VibeCodingStore] SKIP (low engagement: {liked}👍 {comments}💬) "
                f"{self.platform}/{content_id}"
            )
            return

        # Categorize content
        trend_category = self._categorize_content(title, description, matched_keywords)

        # Mark as seen
        self._seen_content_ids.add(content_id)

        sb = get_supabase()
        now_ts = int(get_current_timestamp())

        # Generate unique ID
        hash_input = f"{self.platform}:{content_id}".encode('utf-8')
        hash_value = int(hashlib.sha256(hash_input).hexdigest()[:15], 16)

        # Prepare top comments for storage
        top_comments_json = None
        if top_comments:
            # Store top N comments with essential fields
            max_comments = getattr(config, "VIBE_CODING_TOP_COMMENTS_COUNT", 20)
            top_comments_json = [
                {
                    "comment_id": c.get("comment_id"),
                    "content": c.get("content", ""),
                    "nickname": c.get("nickname", ""),
                    "like_count": c.get("like_count", 0),
                    "publish_time": c.get("publish_time"),
                }
                for c in top_comments[:max_comments]
            ]

        # Normalize platform-specific field names
        content_url = (
            content_item.get("content_url")
            or content_item.get("note_url")
            or content_item.get("aweme_url")
            or ""
        )
        cover_url = (
            content_item.get("cover_url")
            or content_item.get("image_list", "").split(",")[0] if isinstance(content_item.get("image_list"), str) else ""
            or ""
        )
        publish_time = content_item.get("publish_time") or content_item.get("time")

        row = {
            "id": hash_value,
            "platform": self.platform,
            "content_id": content_id,
            "content_type": content_item.get("content_type") or content_item.get("type", ""),
            "title": title,
            "description": description,
            "content_url": content_url,
            "cover_url": cover_url,
            "user_id": str(content_item.get("user_id", "")),
            "nickname": content_item.get("nickname", ""),
            "avatar": content_item.get("avatar", ""),
            "ip_location": content_item.get("ip_location", ""),
            "liked_count": liked,
            "comment_count": comments,
            "share_count": self._parse_count(content_item.get("share_count", 0)),
            "collected_count": self._parse_count(content_item.get("collected_count", 0)),
            "publish_time": publish_time,
            "vibe_coding_keywords": matched_keywords,
            "trend_category": trend_category,
            "top_comments": top_comments_json,
            "platform_data": content_item.get("platform_data", {}),
            "source_keyword": content_item.get("source_keyword", ""),
            "crawl_session_id": self.session_id,
            "analysis_status": "pending",
            "last_modify_ts": now_ts,
        }

        try:
            result = (
                sb.table("vibe_coding_raw_data")
                .upsert(row)
                .execute()
            )
            utils.logger.info(
                f"[VibeCodingStore] ✅ Saved {self.platform}/{content_id} "
                f"[{trend_category}] keywords: {', '.join(matched_keywords[:3])}"
            )
            return result
        except Exception as e:
            utils.logger.error(
                f"[VibeCodingStore] ❌ Failed to save {self.platform}/{content_id}: {e}"
            )
            raise

    async def update_analysis_result(
        self,
        content_id: str,
        innovation_score: float,
        extracted_ideas: Dict,
        trend_category: Optional[str] = None
    ):
        """
        Update AI analysis results for a content item.

        Args:
            content_id: Content ID to update
            innovation_score: AI-generated innovation score (0-1)
            extracted_ideas: Structured ideas extracted by AI
            trend_category: Optional updated category based on AI analysis
        """
        sb = get_supabase()
        now_ts = int(get_current_timestamp())

        update_data = {
            "innovation_score": innovation_score,
            "extracted_ideas": extracted_ideas,
            "analysis_status": "analyzed",
            "analyzed_at": now_ts,
            "last_modify_ts": now_ts,
        }

        if trend_category:
            update_data["trend_category"] = trend_category

        try:
            result = (
                sb.table("vibe_coding_raw_data")
                .update(update_data)
                .eq("platform", self.platform)
                .eq("content_id", str(content_id))
                .execute()
            )
            utils.logger.info(
                f"[VibeCodingStore] Updated analysis for {self.platform}/{content_id} "
                f"(score: {innovation_score:.2f})"
            )
            return result
        except Exception as e:
            utils.logger.error(
                f"[VibeCodingStore] Failed to update analysis for {self.platform}/{content_id}: {e}"
            )
            raise

    async def mark_design_generated(self, content_id: str, design_proposal_id: str):
        """Mark content as having a design proposal generated."""
        sb = get_supabase()
        now_ts = int(get_current_timestamp())

        try:
            result = (
                sb.table("vibe_coding_raw_data")
                .update({
                    "analysis_status": "design_generated",
                    "design_proposal_id": design_proposal_id,
                    "last_modify_ts": now_ts,
                })
                .eq("platform", self.platform)
                .eq("content_id", str(content_id))
                .execute()
            )
            utils.logger.info(
                f"[VibeCodingStore] Marked design generated for {self.platform}/{content_id}"
            )
            return result
        except Exception as e:
            utils.logger.error(
                f"[VibeCodingStore] Failed to mark design generated: {e}"
            )
            raise

    @classmethod
    def get_pending_analysis_content(cls, platform: Optional[str] = None, limit: int = 100):
        """
        Fetch content pending AI analysis.

        Args:
            platform: Optional platform filter
            limit: Max number of items to fetch

        Returns:
            List of content items with analysis_status='pending'
        """
        sb = get_supabase()

        query = sb.table("vibe_coding_raw_data").select("*").eq("analysis_status", "pending")

        if platform:
            query = query.eq("platform", platform)

        query = query.order("publish_time", desc=True).limit(limit)

        try:
            result = query.execute()
            return result.data or []
        except Exception as e:
            utils.logger.error(f"[VibeCodingStore] Failed to fetch pending content: {e}")
            return []

    @classmethod
    def get_top_innovative_content(cls, limit: int = 50, min_score: float = 0.7):
        """
        Fetch top innovative content by innovation score.

        Args:
            limit: Max number of items to fetch
            min_score: Minimum innovation score threshold

        Returns:
            List of high-scoring content items
        """
        sb = get_supabase()

        try:
            result = (
                sb.table("vibe_coding_raw_data")
                .select("*")
                .gte("innovation_score", min_score)
                .order("innovation_score", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            utils.logger.error(f"[VibeCodingStore] Failed to fetch top content: {e}")
            return []
