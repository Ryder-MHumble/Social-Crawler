# -*- coding: utf-8 -*-
"""Unified SQLite store implementations for crawler platforms."""

from __future__ import annotations

from typing import Any, Dict

from base.base_crawler import AbstractStore
from database.sqlite_store_base import SQLiteUnifiedStoreBase
from database.sqlite_storage import get_sqlite_storage


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return default


class UnifiedXhsSqliteStoreImplement(AbstractStore):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base = SQLiteUnifiedStoreBase("xhs")

    async def store_content(self, content_item: Dict):
        self.base.save_content(
            {
                "content_id": content_item.get("note_id"),
                "content_type": content_item.get("type", "note"),
                "title": content_item.get("title", ""),
                "description": content_item.get("desc", ""),
                "content_url": content_item.get("note_url", ""),
                "cover_url": "",
                "user_id": content_item.get("user_id"),
                "nickname": content_item.get("nickname"),
                "avatar": content_item.get("avatar"),
                "ip_location": content_item.get("ip_location", ""),
                "liked_count": _safe_int(content_item.get("liked_count")),
                "comment_count": _safe_int(content_item.get("comment_count")),
                "share_count": _safe_int(content_item.get("share_count")),
                "collected_count": _safe_int(content_item.get("collected_count")),
                "source_keyword": content_item.get("source_keyword", ""),
                "publish_time": content_item.get("time"),
                "platform_payload_json": {
                    "video_url": content_item.get("video_url", ""),
                    "image_list": content_item.get("image_list", ""),
                    "tag_list": content_item.get("tag_list", ""),
                    "xsec_token": content_item.get("xsec_token", ""),
                    "last_update_time": content_item.get("last_update_time"),
                },
            }
        )

    async def store_comment(self, comment_item: Dict):
        self.base.save_comment(
            {
                "comment_id": comment_item.get("comment_id"),
                "content_id": comment_item.get("note_id"),
                "parent_comment_id": str(comment_item.get("parent_comment_id", "")),
                "content": comment_item.get("content", ""),
                "pictures_json": comment_item.get("pictures", ""),
                "user_id": comment_item.get("user_id"),
                "nickname": comment_item.get("nickname"),
                "avatar": comment_item.get("avatar"),
                "ip_location": comment_item.get("ip_location", ""),
                "like_count": _safe_int(comment_item.get("like_count")),
                "sub_comment_count": _safe_int(comment_item.get("sub_comment_count")),
                "publish_time": comment_item.get("create_time"),
                "platform_payload_json": {},
            }
        )

    async def store_creator(self, creator_item: Dict):
        self.base.save_creator(
            {
                "user_id": creator_item.get("user_id"),
                "nickname": creator_item.get("nickname"),
                "avatar": creator_item.get("avatar"),
                "description": creator_item.get("desc", ""),
                "gender": creator_item.get("gender", ""),
                "ip_location": creator_item.get("ip_location", ""),
                "follows_count": _safe_int(creator_item.get("follows")),
                "fans_count": _safe_int(creator_item.get("fans")),
                "interaction_count": _safe_int(creator_item.get("interaction")),
                "platform_payload_json": {
                    "tag_list": creator_item.get("tag_list", ""),
                },
            }
        )


class UnifiedDouyinSqliteStoreImplement(AbstractStore):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base = SQLiteUnifiedStoreBase("dy")

    async def store_content(self, content_item: Dict):
        self.base.save_content(
            {
                "content_id": content_item.get("aweme_id"),
                "content_type": content_item.get("aweme_type", "video"),
                "title": content_item.get("title", ""),
                "description": content_item.get("desc", ""),
                "content_url": content_item.get("aweme_url", ""),
                "cover_url": content_item.get("cover_url", ""),
                "user_id": content_item.get("user_id"),
                "nickname": content_item.get("nickname"),
                "avatar": content_item.get("avatar"),
                "ip_location": content_item.get("ip_location", ""),
                "liked_count": _safe_int(content_item.get("liked_count")),
                "comment_count": _safe_int(content_item.get("comment_count")),
                "share_count": _safe_int(content_item.get("share_count")),
                "collected_count": _safe_int(content_item.get("collected_count")),
                "source_keyword": content_item.get("source_keyword", ""),
                "publish_time": content_item.get("create_time"),
                "platform_payload_json": {
                    "aweme_type": content_item.get("aweme_type", ""),
                    "sec_uid": content_item.get("sec_uid", ""),
                    "short_user_id": content_item.get("short_user_id", ""),
                    "user_unique_id": content_item.get("user_unique_id", ""),
                    "user_signature": content_item.get("user_signature", ""),
                    "video_download_url": content_item.get("video_download_url", ""),
                    "music_download_url": content_item.get("music_download_url", ""),
                    "note_download_url": content_item.get("note_download_url", ""),
                },
            }
        )

    async def store_comment(self, comment_item: Dict):
        self.base.save_comment(
            {
                "comment_id": comment_item.get("comment_id"),
                "content_id": comment_item.get("aweme_id"),
                "parent_comment_id": str(comment_item.get("parent_comment_id", "")),
                "content": comment_item.get("content", ""),
                "pictures_json": comment_item.get("pictures", ""),
                "user_id": comment_item.get("user_id"),
                "nickname": comment_item.get("nickname"),
                "avatar": comment_item.get("avatar"),
                "ip_location": comment_item.get("ip_location", ""),
                "like_count": _safe_int(comment_item.get("like_count")),
                "sub_comment_count": _safe_int(comment_item.get("sub_comment_count")),
                "publish_time": comment_item.get("create_time"),
                "platform_payload_json": {
                    "sec_uid": comment_item.get("sec_uid", ""),
                    "short_user_id": comment_item.get("short_user_id", ""),
                    "user_unique_id": comment_item.get("user_unique_id", ""),
                    "user_signature": comment_item.get("user_signature", ""),
                },
            }
        )

    async def store_creator(self, creator_item: Dict):
        self.base.save_creator(
            {
                "user_id": creator_item.get("user_id"),
                "nickname": creator_item.get("nickname"),
                "avatar": creator_item.get("avatar"),
                "description": creator_item.get("desc", ""),
                "gender": creator_item.get("gender", ""),
                "ip_location": creator_item.get("ip_location", ""),
                "follows_count": _safe_int(creator_item.get("follows")),
                "fans_count": _safe_int(creator_item.get("fans")),
                "interaction_count": _safe_int(creator_item.get("interaction")),
                "platform_payload_json": {
                    "videos_count": _safe_int(creator_item.get("videos_count")),
                },
            }
        )


class UnifiedBiliSqliteStoreImplement(AbstractStore):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base = SQLiteUnifiedStoreBase("bili")
        self.storage = get_sqlite_storage()

    async def store_content(self, content_item: Dict):
        self.base.save_content(
            {
                "content_id": content_item.get("video_id"),
                "content_type": content_item.get("video_type", "video"),
                "title": content_item.get("title", ""),
                "description": content_item.get("desc", ""),
                "content_url": content_item.get("video_url", ""),
                "cover_url": content_item.get("video_cover_url", ""),
                "user_id": content_item.get("user_id"),
                "nickname": content_item.get("nickname"),
                "avatar": content_item.get("avatar"),
                "ip_location": "",
                "liked_count": _safe_int(content_item.get("liked_count")),
                "comment_count": _safe_int(content_item.get("video_comment")),
                "share_count": _safe_int(content_item.get("video_share_count")),
                "collected_count": _safe_int(content_item.get("video_favorite_count")),
                "source_keyword": content_item.get("source_keyword", ""),
                "publish_time": content_item.get("create_time"),
                "platform_payload_json": {
                    "video_play_count": _safe_int(content_item.get("video_play_count")),
                    "video_coin_count": _safe_int(content_item.get("video_coin_count")),
                    "video_danmaku": _safe_int(content_item.get("video_danmaku")),
                    "disliked_count": _safe_int(content_item.get("disliked_count")),
                },
            }
        )

    async def store_comment(self, comment_item: Dict):
        self.base.save_comment(
            {
                "comment_id": comment_item.get("comment_id"),
                "content_id": comment_item.get("video_id"),
                "parent_comment_id": str(comment_item.get("parent_comment_id", "")),
                "content": comment_item.get("content", ""),
                "pictures_json": [],
                "user_id": comment_item.get("user_id"),
                "nickname": comment_item.get("nickname"),
                "avatar": comment_item.get("avatar"),
                "ip_location": "",
                "like_count": _safe_int(comment_item.get("like_count")),
                "sub_comment_count": _safe_int(comment_item.get("sub_comment_count")),
                "publish_time": comment_item.get("create_time"),
                "platform_payload_json": {
                    "sex": comment_item.get("sex", ""),
                    "sign": comment_item.get("sign", ""),
                },
            }
        )

    async def store_creator(self, creator: Dict):
        self.base.save_creator(
            {
                "user_id": creator.get("user_id"),
                "nickname": creator.get("nickname"),
                "avatar": creator.get("avatar"),
                "description": creator.get("sign", ""),
                "gender": creator.get("sex", ""),
                "ip_location": "",
                "follows_count": 0,
                "fans_count": _safe_int(creator.get("total_fans")),
                "interaction_count": _safe_int(creator.get("total_liked")),
                "platform_payload_json": {
                    "user_rank": _safe_int(creator.get("user_rank")),
                    "is_official": _safe_int(creator.get("is_official")),
                },
            }
        )

    async def store_contact(self, contact_item: Dict):
        self.storage.record_observation(
            {
                "run_id": "",
                "task_slug": "",
                "stage_key": "",
                "job_key": "",
                "entity_type": "bili_contact",
                "platform": "bili",
                "external_id": f"{contact_item.get('up_id', '')}:{contact_item.get('fan_id', '')}",
                "source_keyword": "",
                "clean_status": "accepted",
                "clean_reason": "Bilibili contact snapshot observed.",
                "rule_key": "bili_contact",
                "dedup_fingerprint": f"bili-contact:{contact_item.get('up_id', '')}:{contact_item.get('fan_id', '')}",
                "snapshot_json": contact_item,
            }
        )

    async def store_dynamic(self, dynamic_item: Dict):
        self.storage.record_observation(
            {
                "run_id": "",
                "task_slug": "",
                "stage_key": "",
                "job_key": "",
                "entity_type": "bili_dynamic",
                "platform": "bili",
                "external_id": str(dynamic_item.get("dynamic_id", "") or ""),
                "source_keyword": "",
                "clean_status": "accepted",
                "clean_reason": "Bilibili dynamic snapshot observed.",
                "rule_key": "bili_dynamic",
                "dedup_fingerprint": f"bili-dynamic:{dynamic_item.get('dynamic_id', '')}",
                "snapshot_json": dynamic_item,
            }
        )


class UnifiedWeiboSqliteStoreImplement(AbstractStore):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base = SQLiteUnifiedStoreBase("wb")

    async def store_content(self, content_item: Dict):
        self.base.save_content(
            {
                "content_id": content_item.get("note_id"),
                "content_type": "post",
                "title": "",
                "description": content_item.get("content", ""),
                "content_url": content_item.get("note_url", ""),
                "cover_url": "",
                "user_id": content_item.get("user_id"),
                "nickname": content_item.get("nickname"),
                "avatar": content_item.get("avatar"),
                "ip_location": content_item.get("ip_location", ""),
                "liked_count": _safe_int(content_item.get("attitudes_count")),
                "comment_count": _safe_int(content_item.get("comments_count")),
                "share_count": _safe_int(content_item.get("reposts_count")),
                "collected_count": 0,
                "source_keyword": content_item.get("source_keyword", ""),
                "publish_time": content_item.get("create_time"),
                "platform_payload_json": {
                    "note_id_str": content_item.get("note_id"),
                    "comment_id": content_item.get("comment_id", ""),
                },
            }
        )

    async def store_comment(self, comment_item: Dict):
        self.base.save_comment(
            {
                "comment_id": comment_item.get("comment_id"),
                "content_id": comment_item.get("note_id"),
                "parent_comment_id": str(comment_item.get("parent_comment_id", "")),
                "content": comment_item.get("content", ""),
                "pictures_json": [],
                "user_id": comment_item.get("user_id"),
                "nickname": comment_item.get("nickname"),
                "avatar": comment_item.get("avatar"),
                "ip_location": comment_item.get("ip_location", ""),
                "like_count": _safe_int(comment_item.get("comment_like_count")),
                "sub_comment_count": _safe_int(comment_item.get("sub_comment_count")),
                "publish_time": comment_item.get("create_time"),
                "platform_payload_json": {},
            }
        )

    async def store_creator(self, creator: Dict):
        self.base.save_creator(
            {
                "user_id": creator.get("user_id"),
                "nickname": creator.get("nickname"),
                "avatar": creator.get("avatar"),
                "description": creator.get("desc", ""),
                "gender": creator.get("gender", ""),
                "ip_location": creator.get("ip_location", ""),
                "follows_count": _safe_int(creator.get("follows")),
                "fans_count": _safe_int(creator.get("fans")),
                "interaction_count": _safe_int(creator.get("interaction")),
                "platform_payload_json": {},
            }
        )


class UnifiedKuaishouSqliteStoreImplement(AbstractStore):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base = SQLiteUnifiedStoreBase("ks")

    async def store_content(self, content_item: Dict):
        self.base.save_content(
            {
                "content_id": content_item.get("video_id"),
                "content_type": content_item.get("video_type", "video"),
                "title": content_item.get("title", ""),
                "description": content_item.get("desc", ""),
                "content_url": content_item.get("video_url", ""),
                "cover_url": content_item.get("video_cover_url", ""),
                "user_id": content_item.get("user_id"),
                "nickname": content_item.get("nickname"),
                "avatar": content_item.get("avatar"),
                "ip_location": "",
                "liked_count": _safe_int(content_item.get("liked_count")),
                "comment_count": 0,
                "share_count": 0,
                "collected_count": 0,
                "source_keyword": content_item.get("source_keyword", ""),
                "publish_time": content_item.get("create_time"),
                "platform_payload_json": {
                    "viewd_count": _safe_int(content_item.get("viewd_count")),
                    "video_play_url": content_item.get("video_play_url", ""),
                },
            }
        )

    async def store_comment(self, comment_item: Dict):
        self.base.save_comment(
            {
                "comment_id": comment_item.get("comment_id"),
                "content_id": comment_item.get("video_id"),
                "parent_comment_id": "",
                "content": comment_item.get("content", ""),
                "pictures_json": [],
                "user_id": comment_item.get("user_id"),
                "nickname": comment_item.get("nickname"),
                "avatar": comment_item.get("avatar"),
                "ip_location": "",
                "like_count": 0,
                "sub_comment_count": _safe_int(comment_item.get("sub_comment_count")),
                "publish_time": comment_item.get("create_time"),
                "platform_payload_json": {},
            }
        )

    async def store_creator(self, creator_item: Dict):
        self.base.save_creator(
            {
                "user_id": creator_item.get("user_id"),
                "nickname": creator_item.get("nickname"),
                "avatar": creator_item.get("avatar"),
                "description": creator_item.get("desc", ""),
                "gender": creator_item.get("gender", ""),
                "ip_location": creator_item.get("ip_location", ""),
                "follows_count": _safe_int(creator_item.get("follows")),
                "fans_count": _safe_int(creator_item.get("fans")),
                "interaction_count": _safe_int(creator_item.get("interaction")),
                "platform_payload_json": {},
            }
        )


class UnifiedTiebaSqliteStoreImplement(AbstractStore):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base = SQLiteUnifiedStoreBase("tieba")

    async def store_content(self, content_item: Dict):
        self.base.save_content(
            {
                "content_id": content_item.get("note_id"),
                "content_type": "thread",
                "title": content_item.get("title", ""),
                "description": content_item.get("desc", ""),
                "content_url": content_item.get("note_url", ""),
                "cover_url": "",
                "user_id": "",
                "nickname": content_item.get("user_nickname", ""),
                "avatar": content_item.get("user_avatar", ""),
                "ip_location": content_item.get("ip_location", ""),
                "liked_count": 0,
                "comment_count": _safe_int(content_item.get("total_replay_num")),
                "share_count": 0,
                "collected_count": 0,
                "source_keyword": content_item.get("source_keyword", ""),
                "publish_time": content_item.get("publish_time"),
                "platform_payload_json": {
                    "tieba_id": content_item.get("tieba_id", ""),
                    "tieba_name": content_item.get("tieba_name", ""),
                    "tieba_link": content_item.get("tieba_link", ""),
                    "total_replay_page": _safe_int(content_item.get("total_replay_page")),
                    "user_link": content_item.get("user_link", ""),
                },
            }
        )

    async def store_comment(self, comment_item: Dict):
        self.base.save_comment(
            {
                "comment_id": comment_item.get("comment_id"),
                "content_id": comment_item.get("note_id"),
                "parent_comment_id": str(comment_item.get("parent_comment_id", "")),
                "content": comment_item.get("content", ""),
                "pictures_json": [],
                "user_id": "",
                "nickname": comment_item.get("user_nickname", ""),
                "avatar": comment_item.get("user_avatar", ""),
                "ip_location": comment_item.get("ip_location", ""),
                "like_count": 0,
                "sub_comment_count": _safe_int(comment_item.get("sub_comment_count")),
                "publish_time": comment_item.get("publish_time"),
                "platform_payload_json": {
                    "tieba_id": comment_item.get("tieba_id", ""),
                    "tieba_name": comment_item.get("tieba_name", ""),
                    "tieba_link": comment_item.get("tieba_link", ""),
                    "note_url": comment_item.get("note_url", ""),
                    "user_link": comment_item.get("user_link", ""),
                },
            }
        )

    async def store_creator(self, creator_item: Dict):
        self.base.save_creator(
            {
                "user_id": creator_item.get("user_id"),
                "nickname": creator_item.get("nickname"),
                "avatar": creator_item.get("avatar"),
                "description": "",
                "gender": creator_item.get("gender", ""),
                "ip_location": creator_item.get("ip_location", ""),
                "follows_count": _safe_int(creator_item.get("follows")),
                "fans_count": _safe_int(creator_item.get("fans")),
                "interaction_count": 0,
                "platform_payload_json": {
                    "user_name": creator_item.get("user_name", ""),
                    "registration_duration": creator_item.get("registration_duration", ""),
                },
            }
        )


class UnifiedZhihuSqliteStoreImplement(AbstractStore):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base = SQLiteUnifiedStoreBase("zhihu")

    async def store_content(self, content_item: Dict):
        self.base.save_content(
            {
                "content_id": content_item.get("content_id"),
                "content_type": content_item.get("content_type", ""),
                "title": content_item.get("title", ""),
                "description": content_item.get("desc", ""),
                "content_url": content_item.get("content_url", ""),
                "cover_url": "",
                "user_id": content_item.get("user_id"),
                "nickname": content_item.get("user_nickname", ""),
                "avatar": content_item.get("user_avatar", ""),
                "ip_location": "",
                "liked_count": _safe_int(content_item.get("voteup_count")),
                "comment_count": _safe_int(content_item.get("comment_count")),
                "share_count": 0,
                "collected_count": 0,
                "source_keyword": content_item.get("source_keyword", ""),
                "publish_time": content_item.get("created_time"),
                "platform_payload_json": {
                    "content_text": content_item.get("content_text", ""),
                    "question_id": content_item.get("question_id", ""),
                    "updated_time": content_item.get("updated_time"),
                    "user_link": content_item.get("user_link", ""),
                    "user_url_token": content_item.get("user_url_token", ""),
                },
            }
        )

    async def store_comment(self, comment_item: Dict):
        self.base.save_comment(
            {
                "comment_id": comment_item.get("comment_id"),
                "content_id": comment_item.get("content_id"),
                "parent_comment_id": str(comment_item.get("parent_comment_id", "")),
                "content": comment_item.get("content", ""),
                "pictures_json": [],
                "user_id": comment_item.get("user_id"),
                "nickname": comment_item.get("user_nickname", ""),
                "avatar": comment_item.get("user_avatar", ""),
                "ip_location": comment_item.get("ip_location", ""),
                "like_count": _safe_int(comment_item.get("like_count")),
                "sub_comment_count": _safe_int(comment_item.get("sub_comment_count")),
                "publish_time": comment_item.get("publish_time"),
                "platform_payload_json": {
                    "dislike_count": _safe_int(comment_item.get("dislike_count")),
                    "content_type": comment_item.get("content_type", ""),
                    "user_link": comment_item.get("user_link", ""),
                },
            }
        )

    async def store_creator(self, creator_item: Dict):
        self.base.save_creator(
            {
                "user_id": creator_item.get("user_id"),
                "nickname": creator_item.get("user_nickname", ""),
                "avatar": creator_item.get("user_avatar", ""),
                "description": "",
                "gender": creator_item.get("gender", ""),
                "ip_location": creator_item.get("ip_location", ""),
                "follows_count": _safe_int(creator_item.get("follows_count")),
                "fans_count": _safe_int(creator_item.get("fans_count")),
                "interaction_count": _safe_int(creator_item.get("interaction_count")),
                "platform_payload_json": {
                    "headline": creator_item.get("headline", ""),
                },
            }
        )
