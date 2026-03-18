# -*- coding: utf-8 -*-
"""
Vibe Coding Data Store

Handles all persistence for vibe_coding_raw_data table.

Key improvements over v1:
- Keyword scoring (Tier A/B/C) replaces simple boolean match
- Blacklist rejection before scoring
- Title fingerprint dedup to catch reposts across platforms
- Score stored in platform_data for auditability
"""

import hashlib
import re
from typing import Dict, List, Optional

from database.supabase_client import get_supabase
from database.supabase_store_base import SupabaseStoreBase
from tools import utils
from tools.time_util import get_current_timestamp
import vibe_coding.config as vc_cfg


class VibeCodingStore(SupabaseStoreBase):
    """
    Store for vibe_coding_raw_data table.

    Dedup layers (in order):
    1. In-memory _seen_content_ids (content_id per platform) — inherited from base
    2. In-memory _seen_title_fps (title fingerprint) — catches cross-platform reposts
    3. DB preload on first call per platform — cross-session dedup
    """

    # Class-level title fingerprint set (shared across instances, per session)
    _seen_title_fps: set = set()

    def __init__(self, platform: str):
        super().__init__(platform)
        self.session_id = vc_cfg.CURRENT_CRAWL_SESSION_ID
        self._tier_a = [kw.lower() for kw in vc_cfg.KEYWORDS_TIER_A]
        self._tier_b = [kw.lower() for kw in vc_cfg.KEYWORDS_TIER_B]
        self._tier_c = [kw.lower() for kw in vc_cfg.KEYWORDS_TIER_C]
        self._blacklist = [kw.lower() for kw in vc_cfg.KEYWORDS_BLACKLIST]

    # ------------------------------------------------------------------
    # Preload (cross-session dedup)
    # ------------------------------------------------------------------

    async def _ensure_preloaded(self):
        if self.platform in self._preloaded_platforms:
            return
        self._preloaded_platforms.add(self.platform)
        try:
            sb = get_supabase()
            result = (
                sb.table("vibe_coding_raw_data")
                .select("content_id, title")
                .eq("platform", self.platform)
                .execute()
            )
            rows = result.data or []
            for row in rows:
                cid = row.get("content_id")
                if cid:
                    self._seen_content_ids.add(str(cid))
                title = row.get("title") or ""
                fp = self._title_fingerprint(title)
                if fp:
                    VibeCodingStore._seen_title_fps.add(fp)
            utils.logger.info(
                f"[VibeCodingStore] Preloaded {len(rows)} existing {self.platform} records"
            )
        except Exception as e:
            utils.logger.warning(f"[VibeCodingStore] Preload failed for {self.platform}: {e}")

    # ------------------------------------------------------------------
    # Scoring & filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Lowercase + collapse whitespace."""
        return re.sub(r"\s+", " ", (text or "").lower().strip())

    @staticmethod
    def _title_fingerprint(title: str) -> str:
        """Hash of normalised title (no spaces/punct) for repost detection."""
        cleaned = re.sub(r"[^\w\u4e00-\u9fff]", "", (title or "").lower())
        if len(cleaned) < 5:
            return ""
        return hashlib.md5(cleaned.encode()).hexdigest()

    def _score_content(self, title: str, description: str) -> tuple[int, List[str]]:
        """
        Returns (total_score, matched_keywords).
        Score = sum of tier weights for each distinct keyword found.
        Returns (-1, []) if blacklisted.
        """
        text = self._normalize_text(f"{title} {description}")

        # Blacklist check first
        for bw in self._blacklist:
            if bw in text:
                return -1, []

        matched: List[str] = []
        score = 0

        for kw in self._tier_a:
            if kw in text:
                matched.append(kw)
                score += 4

        for kw in self._tier_b:
            if kw in text:
                matched.append(kw)
                score += 2

        for kw in self._tier_c:
            if kw in text:
                matched.append(kw)
                score += 1

        return score, matched

    def _categorize(self, title: str, description: str) -> str:
        text = self._normalize_text(f"{title} {description}")
        for category, triggers in vc_cfg.CATEGORY_RULES.items():
            if any(t in text for t in triggers):
                return category
        return "other"

    # ------------------------------------------------------------------
    # Parse helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_count(val) -> int:
        if not val:
            return 0
        s = str(val).strip()
        if "万" in s:
            try:
                return int(float(s.replace("万", "")) * 10000)
            except Exception:
                return 0
        try:
            return int(float(s))
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Main save method
    # ------------------------------------------------------------------

    async def save_vibe_coding_content(
        self,
        content_item: Dict,
        top_comments: Optional[List[Dict]] = None,
    ):
        """
        Evaluate content against keyword scoring rules and persist if it passes.
        Returns the upsert result, or None if skipped.
        """
        content_id = str(
            content_item.get("content_id")
            or content_item.get("note_id")
            or content_item.get("aweme_id")
            or content_item.get("video_id")
            or content_item.get("weibo_id")
            or ""
        )
        if not content_id:
            return None

        # Layer 1: in-memory content_id dedup
        await self._ensure_preloaded()
        if content_id in self._seen_content_ids:
            utils.logger.debug(f"[VibeCodingStore] SKIP dup content_id {self.platform}/{content_id}")
            return None

        title = content_item.get("title", "") or ""
        description = content_item.get("description") or content_item.get("desc", "") or ""

        # Layer 2: title fingerprint dedup
        if vc_cfg.ENABLE_TITLE_FINGERPRINT_DEDUP:
            fp = self._title_fingerprint(title)
            if fp and fp in VibeCodingStore._seen_title_fps:
                utils.logger.debug(
                    f"[VibeCodingStore] SKIP dup title fingerprint {self.platform}/{content_id}: {title[:30]}"
                )
                return None

        # Layer 3: keyword scoring
        score, matched_keywords = self._score_content(title, description)
        threshold = vc_cfg.KEYWORD_SCORE_THRESHOLD

        if score < 0:
            utils.logger.debug(f"[VibeCodingStore] SKIP blacklisted {self.platform}/{content_id}")
            return None
        if score < threshold:
            utils.logger.debug(
                f"[VibeCodingStore] SKIP low score ({score}<{threshold}) {self.platform}/{content_id}"
            )
            return None

        # Layer 4: engagement filter
        liked = self._parse_count(content_item.get("liked_count", 0))
        comments_cnt = self._parse_count(content_item.get("comment_count", 0))
        min_eng = vc_cfg.VIBE_CODING_MIN_ENGAGEMENT
        if liked + comments_cnt < min_eng:
            utils.logger.debug(
                f"[VibeCodingStore] SKIP low engagement ({liked}+{comments_cnt}<{min_eng}) "
                f"{self.platform}/{content_id}"
            )
            return None

        # Passed all filters — mark seen
        self._seen_content_ids.add(content_id)
        fp = self._title_fingerprint(title)
        if fp:
            VibeCodingStore._seen_title_fps.add(fp)

        trend_category = self._categorize(title, description)

        # Normalize platform-specific fields
        content_url = (
            content_item.get("content_url")
            or content_item.get("note_url")
            or content_item.get("aweme_url")
            or ""
        )
        image_list = content_item.get("image_list", "")
        cover_url = (
            content_item.get("cover_url")
            or (image_list.split(",")[0] if isinstance(image_list, str) and image_list else "")
            or ""
        )
        publish_time = content_item.get("publish_time") or content_item.get("time")

        # Prepare top_comments JSONB
        top_comments_json = None
        if top_comments:
            max_n = vc_cfg.VIBE_CODING_TOP_COMMENTS_COUNT
            top_comments_json = [
                {
                    "comment_id": c.get("comment_id"),
                    "content": c.get("content", ""),
                    "nickname": c.get("nickname", ""),
                    "like_count": self._parse_count(c.get("like_count", 0)),
                    "publish_time": c.get("publish_time"),
                }
                for c in top_comments[:max_n]
            ]

        now_ts = int(get_current_timestamp())
        hash_input = f"{self.platform}:{content_id}".encode()
        row_id = int(hashlib.sha256(hash_input).hexdigest()[:15], 16)

        row = {
            "id": row_id,
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
            "comment_count": comments_cnt,
            "share_count": self._parse_count(content_item.get("share_count", 0)),
            "collected_count": self._parse_count(content_item.get("collected_count", 0)),
            "publish_time": publish_time,
            "vibe_coding_keywords": matched_keywords,
            "trend_category": trend_category,
            "top_comments": top_comments_json,
            "platform_data": {
                **(content_item.get("platform_data") or {}),
                "_keyword_score": score,
            },
            "source_keyword": content_item.get("source_keyword", ""),
            "crawl_session_id": self.session_id,
            "analysis_status": "pending",
            "last_modify_ts": now_ts,
        }

        sb = get_supabase()
        try:
            result = sb.table("vibe_coding_raw_data").upsert(row).execute()
            utils.logger.info(
                f"[VibeCodingStore] SAVED {self.platform}/{content_id} "
                f"score={score} [{trend_category}] kw={matched_keywords[:3]}"
            )
            return result
        except Exception as e:
            utils.logger.error(f"[VibeCodingStore] Save failed {self.platform}/{content_id}: {e}")
            raise

    # ------------------------------------------------------------------
    # Analysis helpers (called by OpenClaw pipeline)
    # ------------------------------------------------------------------

    async def update_analysis_result(
        self,
        content_id: str,
        innovation_score: float,
        extracted_ideas: Dict,
        trend_category: Optional[str] = None,
    ):
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
        sb.table("vibe_coding_raw_data").update(update_data).eq("platform", self.platform).eq(
            "content_id", str(content_id)
        ).execute()

    async def mark_design_generated(self, content_id: str, design_proposal_id: str):
        sb = get_supabase()
        sb.table("vibe_coding_raw_data").update({
            "analysis_status": "design_generated",
            "design_proposal_id": design_proposal_id,
            "last_modify_ts": int(get_current_timestamp()),
        }).eq("platform", self.platform).eq("content_id", str(content_id)).execute()

    @classmethod
    def get_pending_analysis(cls, platform: Optional[str] = None, limit: int = 100) -> List[Dict]:
        sb = get_supabase()
        q = sb.table("vibe_coding_raw_data").select("*").eq("analysis_status", "pending")
        if platform:
            q = q.eq("platform", platform)
        result = q.order("publish_time", desc=True).limit(limit).execute()
        return result.data or []

    @classmethod
    def get_top_by_score(cls, limit: int = 50, min_score: float = 0.7) -> List[Dict]:
        sb = get_supabase()
        result = (
            sb.table("vibe_coding_raw_data")
            .select("*")
            .gte("innovation_score", min_score)
            .order("innovation_score", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
