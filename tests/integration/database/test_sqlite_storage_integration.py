from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pytest

import config
from bilibili_dm_sender.dm_record_store import DMRecordStore
from config.db_config import sqlite_db_config
from database import sqlite_storage as sqlite_storage_module
from database.sqlite_store_base import SQLiteUnifiedStoreBase
from database.sqlite_storage import SQLiteStorage
from tasks.creator_outreach.filter_creators import filter_creators
from vibe_coding.store import VibeCodingStore
import vibe_coding.config as vc_cfg

pytestmark = pytest.mark.integration


@pytest.fixture
def sqlite_env(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "crawler.sqlite3"
    monkeypatch.setitem(sqlite_db_config, "db_path", str(db_path))
    monkeypatch.setattr(sqlite_storage_module, "_storage_instance", None)
    storage = sqlite_storage_module.get_sqlite_storage()
    storage.initialize()
    yield storage
    monkeypatch.setattr(sqlite_storage_module, "_storage_instance", None)


def _set_runtime_context(monkeypatch, *, run_id: str) -> None:
    monkeypatch.setenv("SOCIAL_CRAWLER_RUN_ID", run_id)
    monkeypatch.setenv("SOCIAL_CRAWLER_TASK_SLUG", "sentiment_monitor")
    monkeypatch.setenv("SOCIAL_CRAWLER_STAGE_KEY", "stage_a")
    monkeypatch.setenv("SOCIAL_CRAWLER_JOB_KEY", "job_a")


def test_sqlite_initialize_is_idempotent(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "init.sqlite3")
    assert storage.get_status()["initialized"] is False

    first = storage.initialize()
    second = storage.initialize()

    assert first["initialized"] is True
    assert second["initialized"] is True
    assert "crawl_contents" in second["table_names"]
    assert second["schema_version"] == 1


def test_unified_store_dedups_content_and_filters_comments(
    sqlite_env,
    monkeypatch,
) -> None:
    monkeypatch.setattr(config, "ENABLE_RELEVANCE_FILTER", False, raising=False)
    monkeypatch.setattr(config, "MIN_CONTENT_ENGAGEMENT", 0, raising=False)
    monkeypatch.setattr(config, "MIN_COMMENT_LENGTH", 10, raising=False)
    base = SQLiteUnifiedStoreBase("xhs")

    _set_runtime_context(monkeypatch, run_id="run_dedup_1")
    base.save_content(
        {
            "content_id": "note-1",
            "title": "OpenClaw note",
            "description": "first pass",
            "liked_count": 12,
            "comment_count": 3,
            "source_keyword": "openclaw",
        }
    )

    _set_runtime_context(monkeypatch, run_id="run_dedup_2")
    base.save_content(
        {
            "content_id": "note-1",
            "title": "OpenClaw note",
            "description": "second pass",
            "liked_count": 15,
            "comment_count": 4,
            "source_keyword": "openclaw",
        }
    )
    base.save_comment(
        {
            "comment_id": "comment-short",
            "content_id": "note-1",
            "content": "短评",
            "nickname": "tester",
        }
    )

    content_rows = sqlite_env.query_rows(table="crawl_contents")
    assert content_rows["total"] == 1
    assert content_rows["rows"][0]["liked_count"] == 15

    observations = sqlite_env.query_rows(
        table="crawl_observations",
        entity_type="content",
        limit=10,
    )
    statuses = {row["run_id"]: row["clean_status"] for row in observations["rows"]}
    assert statuses["run_dedup_1"] == "accepted"
    assert statuses["run_dedup_2"] == "deduped"

    comment_obs = sqlite_env.query_rows(
        table="crawl_observations",
        entity_type="comment",
        limit=10,
    )
    assert comment_obs["rows"][0]["clean_status"] == "filtered"
    assert "below 10" in comment_obs["rows"][0]["clean_reason"]


@pytest.mark.asyncio
async def test_vibe_sqlite_blacklist_records_filtered_observation(
    sqlite_env,
    monkeypatch,
) -> None:
    _set_runtime_context(monkeypatch, run_id="run_vibe_blacklist")
    monkeypatch.setattr(config, "SAVE_DATA_OPTION", "sqlite", raising=False)
    monkeypatch.setattr(vc_cfg, "KEYWORDS_BLACKLIST", ["forbidden"], raising=False)
    monkeypatch.setattr(vc_cfg, "KEYWORDS_TIER_A", ["openclaw"], raising=False)
    monkeypatch.setattr(vc_cfg, "KEYWORDS_TIER_B", [], raising=False)
    monkeypatch.setattr(vc_cfg, "KEYWORDS_TIER_C", [], raising=False)
    monkeypatch.setattr(vc_cfg, "KEYWORD_SCORE_THRESHOLD", 1, raising=False)
    monkeypatch.setattr(vc_cfg, "VIBE_CODING_MIN_ENGAGEMENT", 0, raising=False)

    store = VibeCodingStore("xhs")
    result = await store.save_vibe_coding_content(
        {
            "content_id": "vibe-1",
            "title": "forbidden title",
            "description": "openclaw mention",
            "liked_count": 10,
            "comment_count": 2,
            "source_keyword": "openclaw",
        }
    )

    assert result is None
    observations = sqlite_env.query_rows(
        table="crawl_observations",
        run_id="run_vibe_blacklist",
        limit=10,
    )
    assert observations["total"] == 1
    assert observations["rows"][0]["clean_status"] == "filtered"
    assert observations["rows"][0]["rule_key"] == "vibe_blacklist"


def test_creator_outreach_filter_and_dm_records_write_sqlite(
    sqlite_env,
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setenv("SOCIAL_CRAWLER_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("SOCIAL_CRAWLER_RUN_ID", "run_creator_outreach")
    monkeypatch.setenv("SOCIAL_CRAWLER_TASK_SLUG", "creator_outreach")
    monkeypatch.setenv("SOCIAL_CRAWLER_STAGE_KEY", "prepare_creator_list")
    monkeypatch.setenv("SOCIAL_CRAWLER_JOB_KEY", "prepare_csv")

    csv_path = runtime_dir / "input" / "openclaw_creators.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "博主ID",
                "博主名称",
                "主页链接",
                "粉丝数",
                "简介",
                "代表视频1",
                "代表视频2",
                "代表视频3",
                "总播放量",
                "总评论量",
                "总收藏量",
                "平均播放量",
                "视频数量",
                "发现关键词",
                "视频列表(标题|URL|播放量|发布日期)",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "博主ID": "1001",
                "博主名称": "AI Creator",
                "主页链接": "https://space.bilibili.com/1001",
                "粉丝数": "1200",
                "简介": "分享 AI Agent 工作流",
                "代表视频1": "OpenClaw 教程",
                "代表视频2": "AI 工作流实战",
                "代表视频3": "",
                "总播放量": "50000",
                "总评论量": "300",
                "总收藏量": "180",
                "平均播放量": "25000",
                "视频数量": "2",
                "发现关键词": "openclaw教程",
                "视频列表(标题|URL|播放量|发布日期)": "OpenClaw 教程|https://example.com|播放50000|2026-04-01",
            }
        )
        writer.writerow(
            {
                "博主ID": "385941246",
                "博主名称": "Noise Creator",
                "主页链接": "https://space.bilibili.com/385941246",
                "粉丝数": "3000",
                "简介": "杂项账号",
                "代表视频1": "吃小龙虾",
                "代表视频2": "",
                "代表视频3": "",
                "总播放量": "1000",
                "总评论量": "10",
                "总收藏量": "5",
                "平均播放量": "1000",
                "视频数量": "1",
                "发现关键词": "seed",
                "视频列表(标题|URL|播放量|发布日期)": "吃小龙虾|https://example.com|播放1000|2026-04-01",
            }
        )

    filter_creators(
        argparse.Namespace(
            input_file=str(csv_path),
            min_follower_count=100,
            max_fans_count=0,
            min_total_views=100,
            min_average_views=100,
            min_total_comment_count=0,
            min_total_favorite_count=0,
            min_video_count=1,
            include_keywords="openclaw,agent",
            exclude_keywords="",
            creator_whitelist_ids="",
            creator_blacklist_ids="",
            campaign_name="campaign_test",
        )
    )

    candidates = sqlite_env.query_rows(table="outreach_candidates", limit=10)
    status_by_creator = {row["creator_id"]: row["filter_status"] for row in candidates["rows"]}
    assert status_by_creator["1001"] == "accepted"
    assert status_by_creator["385941246"] == "filtered"

    creators = sqlite_env.query_rows(table="crawl_creators", limit=10)
    assert creators["total"] == 1
    assert creators["rows"][0]["user_id"] == "1001"

    observations = sqlite_env.query_rows(
        table="crawl_observations",
        run_id="run_creator_outreach",
        entity_type="creator",
        limit=10,
    )
    assert observations["total"] == 2

    dm_store = DMRecordStore()
    assert dm_store.is_already_sent("1001", campaign="campaign_test") is False
    assert dm_store.save_dm_record(
        "1001",
        "AI Creator",
        "hello",
        "success",
        campaign="campaign_test",
        message_template_id="template_openclaw_invite",
    )
    assert dm_store.is_already_sent("1001", campaign="campaign_test") is True
    assert dm_store.get_sent_count("campaign_test") == 1
