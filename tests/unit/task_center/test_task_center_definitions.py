from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from api.services.task_center import TaskCenterService


def _command_value(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


def _build_service(tmp_path: Path) -> TaskCenterService:
    return TaskCenterService(
        project_root=Path(".").resolve(),
        python_executable=sys.executable,
        state_dir=tmp_path / ".task_center",
    )


def test_xhs_posts_only_preset_resolves_correctly(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={},
        preset_id="preset_sentiment_xhs_posts_only",
    )

    normalized = preview["normalized_params"]
    assert normalized["platforms"] == ["xhs"]
    assert normalized["enable_comments"] is False
    assert normalized["enable_sub_comments"] is False
    assert normalized["max_notes_count"] == 30
    assert "北京中关村学院" in normalized["keywords"]
    assert "中关村学院 投诉" in normalized["keywords"]

    jobs = preview["spec"]["stages"][0]["jobs"]
    assert len(jobs) >= 1
    assert all(_command_value(job["command"], "--platform") == "xhs" for job in jobs)
    assert all(_command_value(job["command"], "--max_notes_count") == "30" for job in jobs)
    assert all(_command_value(job["command"], "--get_comment") == "false" for job in jobs)
    assert all(_command_value(job["command"], "--get_sub_comment") == "false" for job in jobs)


def test_media_daily_report_preset_resolves_correctly(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={},
        preset_id="preset_sentiment_media_daily_report",
    )

    normalized = preview["normalized_params"]
    assert normalized["platforms"] == ["xhs"]
    assert normalized["enable_comments"] is False
    assert normalized["enable_sub_comments"] is False
    assert normalized["max_notes_count"] == 30
    assert normalized["save_option"] == "json"
    assert "北京中关村学院" in normalized["keywords"]
    assert "中关村人工智能研究院" in normalized["keywords"]
    assert "中关村学院 投诉" in normalized["keywords"]
    assert "中关村学院 野鸡" in normalized["keywords"]
    assert "北京中关村学院 怎么样" in normalized["keywords"]

    jobs = preview["spec"]["stages"][0]["jobs"]
    assert len(jobs) >= 1
    assert all(_command_value(job["command"], "--platform") == "xhs" for job in jobs)
    assert all(_command_value(job["command"], "--max_notes_count") == "30" for job in jobs)
    assert all(_command_value(job["command"], "--save_data_option") == "json" for job in jobs)
    assert all(_command_value(job["command"], "--get_comment") == "false" for job in jobs)
    assert all(_command_value(job["command"], "--get_sub_comment") == "false" for job in jobs)
    keyword_payload = ",".join(_command_value(job["command"], "--keywords") for job in jobs)
    assert "北京中关村学院" in keyword_payload
    assert "中关村学院 投诉" in keyword_payload


def test_media_daily_zgca_risk_preset_targets_supported_platforms(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={},
        preset_id="preset_sentiment_media_daily_zgca_risk",
    )

    normalized = preview["normalized_params"]
    assert normalized["platforms"] == ["xhs", "wb", "dy"]
    assert normalized["enable_comments"] is True
    assert normalized["enable_sub_comments"] is False
    assert normalized["save_option"] == "json"
    assert "中关村学院 投诉" in normalized["keywords"]
    assert "中关村学院 黑幕" in normalized["keywords"]

    jobs = preview["spec"]["stages"][0]["jobs"]
    assert len(jobs) == 3
    assert [_command_value(job["command"], "--platform") for job in jobs] == ["xhs", "wb", "dy"]
    for job in jobs:
        command = job["command"]
        assert _command_value(command, "--get_comment") == "true"
        assert _command_value(command, "--get_sub_comment") == "false"
        assert _command_value(command, "--save_data_option") == "json"


def test_media_daily_guozhi_positive_preset_keeps_linkage_keywords(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={},
        preset_id="preset_sentiment_media_daily_guozhi_positive",
    )

    normalized = preview["normalized_params"]
    assert normalized["platforms"] == ["xhs", "wb", "dy"]
    assert normalized["enable_comments"] is False
    assert "中关村人工智能研究院" in normalized["keywords"]
    assert "深圳河套" in normalized["keywords"]
    assert "上海创智" in normalized["keywords"]

    jobs = preview["spec"]["stages"][0]["jobs"]
    assert len(jobs) == 3
    for job in jobs:
        assert _command_value(job["command"], "--keywords").count("中关村人工智能研究院") == 1


def test_media_daily_guozhi_risk_preset_expands_suffix_keywords(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={},
        preset_id="preset_sentiment_media_daily_guozhi_risk",
    )

    normalized = preview["normalized_params"]
    assert normalized["platforms"] == ["xhs", "wb", "dy"]
    assert normalized["enable_comments"] is True
    assert "中关村人工智能研究院 投诉" in normalized["keywords"]
    assert "刘铁岩 黑幕" in normalized["keywords"]
    assert "上海创智 争议" in normalized["keywords"]


def test_sentiment_monitor_defaults_and_default_preset_come_from_yaml(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    template = service.get_template("sentiment_monitor")
    defaults = template["defaults"]
    assert defaults["platforms"] == ["xhs"]
    assert defaults["save_option"] == "json"
    assert defaults["enable_keyword_search"] is True
    assert defaults["enable_account_crawl"] is False
    assert "北京中关村学院" in defaults["keywords"]
    assert "北京中关村学院 怎么样" in defaults["keywords"]

    preview = service.preview_task("sentiment_monitor", params={})
    normalized = preview["normalized_params"]
    assert normalized["platforms"] == ["xhs"]
    assert normalized["enable_comments"] is False
    assert normalized["top_posts_count"] == normalized["max_notes_count"] == 30
    assert normalized["top_comments_count"] == normalized["max_comments_count_singlenotes"] == 20
    assert normalized["save_option"] == "json"
    assert "中关村人工智能研究院" in normalized["keywords"]
    assert "中关村学院 野鸡" in normalized["keywords"]

    command = preview["spec"]["stages"][0]["jobs"][0]["command"]
    assert _command_value(command, "--platform") == "xhs"
    assert _command_value(command, "--save_data_option") == "json"
    assert _command_value(command, "--get_comment") == "false"

    presets = service.list_presets("sentiment_monitor")
    assert presets[0]["id"] == "preset_sentiment_media_daily_report"
    assert presets[0]["is_default"] is True


def test_sentiment_monitor_preview_builds_keyword_and_creator_stages(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={
            "platforms": ["xhs", "wb"],
            "keywords": "alpha,beta",
            "keyword_whitelist": "gamma",
            "keyword_blacklist": "beta",
            "top_posts_count": 12,
            "top_comments_count": 7,
            "enable_comments": True,
            "specified_account_ids": "creator_1,creator_2",
            "account_whitelist": "creator_3",
            "account_blacklist": "creator_2",
            "enable_account_crawl": True,
        },
    )

    normalized = preview["normalized_params"]
    assert normalized["keywords"] == "alpha,gamma"
    assert normalized["specified_account_ids"] == "creator_1,creator_3"
    assert normalized["creator_ids"] == "creator_1,creator_3"
    assert normalized["max_notes_count"] == normalized["top_posts_count"] == 12
    assert normalized["max_comments_count_singlenotes"] == normalized["top_comments_count"] == 7

    stages = preview["spec"]["stages"]
    assert [stage["key"] for stage in stages] == [
        "sentiment_keyword_parallel_crawl",
        "sentiment_creator_parallel_crawl",
    ]
    keyword_command = stages[0]["jobs"][0]["command"]
    assert _command_value(keyword_command, "--type") == "search"
    assert _command_value(keyword_command, "--keywords") == "alpha,gamma"
    creator_command = stages[1]["jobs"][0]["command"]
    assert _command_value(creator_command, "--type") == "creator"
    assert _command_value(creator_command, "--creator_id") == "creator_1,creator_3"


def test_sentiment_monitor_keyword_job_split_expands_platform_keyword_matrix(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={
            "platforms": ["xhs", "wb"],
            "keywords": "alpha,beta",
            "enable_keyword_search": True,
            "enable_account_crawl": False,
            "keyword_job_mode": "single",
            "keyword_job_max_parallel": 4,
            "save_option": "json",
        },
    )

    stage = preview["spec"]["stages"][0]
    assert stage["key"] == "sentiment_keyword_parallel_crawl"
    assert stage["max_parallel"] == 4
    assert len(stage["jobs"]) == 4
    assert len({job["key"] for job in stage["jobs"]}) == 4
    assert [_command_value(job["command"], "--platform") for job in stage["jobs"]] == [
        "xhs",
        "xhs",
        "wb",
        "wb",
    ]
    assert [_command_value(job["command"], "--keywords") for job in stage["jobs"]] == [
        "alpha",
        "beta",
        "alpha",
        "beta",
    ]


def test_sentiment_monitor_browsermint_preview_emits_effective_plan_and_preserves_save_option(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={
            "platforms": ["xhs"],
            "keywords": "alpha,beta,gamma",
            "enable_keyword_search": True,
            "enable_account_crawl": False,
            "browser_provider": "browsermint",
            "browser_session_id": "bm-session-1",
            "keyword_job_mode": "single",
            "keyword_job_max_parallel": 3,
            "save_option": "json",
        },
    )

    normalized = preview["normalized_params"]
    assert normalized["save_option"] == "json"
    assert preview["effective_save_option"] == "json"
    assert preview["runtime_storage_backend"] == "file:json"
    assert preview["effective_plan"]["mode"] == "browsermint_single_session_safe"
    assert preview["plan_warnings"]
    assert any(
        warning.get("code") == "degraded_parallelism"
        for warning in preview["plan_warnings"]
    )

    stage = preview["spec"]["stages"][0]
    assert stage["concurrent"] is False
    assert stage["max_parallel"] == 1
    assert len(stage["jobs"]) == 1
    assert _command_value(stage["jobs"][0]["command"], "--keywords") == "alpha,beta,gamma"


def test_sentiment_monitor_official_accounts_are_task_controlled(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={
            "platforms": ["xhs"],
            "enable_keyword_search": False,
            "enable_account_crawl": False,
            "enable_official_accounts_crawl": True,
            "official_account_targets": "https://www.xiaohongshu.com/user/profile/abc123",
            "save_option": "json",
        },
    )

    stages = preview["spec"]["stages"]
    assert [stage["key"] for stage in stages] == ["sentiment_official_account_crawl"]
    assert stages[0]["jobs"][0]["metadata"]["crawl_type"] == "official_accounts"


def test_sentiment_monitor_creator_job_chunking_splits_account_targets(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={
            "platforms": ["xhs"],
            "enable_keyword_search": False,
            "enable_account_crawl": True,
            "specified_account_ids": "creator_1,creator_2,creator_3",
            "creator_job_mode": "chunked",
            "creator_job_chunk_size": 2,
            "creator_job_max_parallel": 2,
            "save_option": "json",
        },
    )

    stage = preview["spec"]["stages"][0]
    assert stage["key"] == "sentiment_creator_parallel_crawl"
    assert stage["max_parallel"] == 2
    assert len(stage["jobs"]) == 2
    assert len({job["key"] for job in stage["jobs"]}) == 2
    assert [_command_value(job["command"], "--creator_id") for job in stage["jobs"]] == [
        "creator_1,creator_2",
        "creator_3",
    ]


def test_sentiment_monitor_qrcode_login_forces_headful_browser(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={
            "platforms": ["xhs"],
            "keywords": "北京中关村学院",
            "enable_keyword_search": True,
            "enable_account_crawl": False,
            "login_type": "qrcode",
            "headless": True,
            "save_option": "json",
        },
    )

    normalized = preview["normalized_params"]
    assert normalized["login_type"] == "qrcode"
    assert normalized["headless"] is False

    command = preview["spec"]["stages"][0]["jobs"][0]["command"]
    assert _command_value(command, "--lt") == "qrcode"
    assert _command_value(command, "--headless") == "false"


def test_sentiment_monitor_cookie_login_uses_inline_cookie(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "sentiment_monitor",
        params={
            "platforms": ["xhs"],
            "keywords": "北京中关村学院",
            "enable_keyword_search": True,
            "enable_account_crawl": False,
            "login_type": "cookie",
            "cookies": "a=1; b=2",
            "save_option": "json",
            "headless": True,
        },
    )

    normalized = preview["normalized_params"]
    assert normalized["login_type"] == "cookie"
    assert normalized["cookies"] == "a=1; b=2"

    command = preview["spec"]["stages"][0]["jobs"][0]["command"]
    assert _command_value(command, "--lt") == "cookie"
    assert _command_value(command, "--cookies") == "a=1; b=2"


def test_sentiment_monitor_cookie_login_requires_cookie_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_service(tmp_path)
    fake_cookie_module = types.ModuleType("cookies_config")
    fake_cookie_module.get_cookie = lambda _platform: ""
    monkeypatch.setitem(sys.modules, "cookies_config", fake_cookie_module)

    with pytest.raises(ValueError, match="已选择 Cookie 登录"):
        service.preview_task(
            "sentiment_monitor",
            params={
                "platforms": ["xhs"],
                "keywords": "北京中关村学院",
                "enable_keyword_search": True,
                "enable_account_crawl": False,
                "login_type": "cookie",
                "cookies": "",
                "save_option": "json",
                "headless": True,
            },
        )


def test_creator_outreach_defaults_and_dm_preset_are_yaml_backed(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    template = service.get_template("creator_outreach")
    defaults = template["defaults"]
    assert defaults["run_discovery"] is True
    assert defaults["run_filter"] is True
    assert defaults["run_dm"] is False
    assert defaults["message_template_id"] == "template_openclaw_invite"

    preview = service.preview_task(
        "creator_outreach",
        params={},
        preset_id="preset_creator_campaign_dry_run",
    )
    normalized = preview["normalized_params"]
    assert normalized["run_dm"] is True
    assert normalized["dry_run"] is True
    assert normalized["campaign_name"] == "openclaw_dryrun"
    assert normalized["max_dm_targets"] == 50
    assert normalized["message_template_id"] == "template_openclaw_invite"

    stages = preview["spec"]["stages"]
    assert [stage["key"] for stage in stages] == ["prepare_creator_list", "dm_campaign"]
    filter_command = stages[0]["jobs"][0]["command"]
    assert "--campaign-name" in filter_command
    assert "--include-profile-keywords" in filter_command
    dm_command = stages[1]["jobs"][0]["command"]
    assert _command_value(dm_command, "--campaign-id") == normalized["campaign_name"]
    assert "--dry-run" in dm_command
    assert _command_value(dm_command, "--max-targets") == "50"
    assert _command_value(dm_command, "--batch-delay-seconds") == "10"


def test_vibe_coding_defaults_and_creator_preset(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    template = service.get_template("vibe_coding")
    defaults = template["defaults"]
    assert defaults["enable_keyword_search"] is True
    assert defaults["enable_account_crawl"] is False
    assert defaults["save_option"] == "json"
    assert "vibe coding" in defaults["scenario_words"]
    save_option_field = next(field for field in template["fields"] if field["key"] == "save_option")
    assert {option["value"] for option in save_option_field["options"]} >= {"json", "sqlite"}

    preview = service.preview_task(
        "vibe_coding",
        params={},
        preset_id="preset_vibe_creator_targets",
    )
    normalized = preview["normalized_params"]
    assert normalized["enable_keyword_search"] is False
    assert normalized["enable_account_crawl"] is True
    assert normalized["save_option"] == "json"
    assert normalized["specified_account_ids"]

    stages = preview["spec"]["stages"]
    assert [stage["key"] for stage in stages] == ["vibe_creator_parallel_crawl"]
    command = stages[0]["jobs"][0]["command"]
    assert _command_value(command, "--type") == "creator"
    assert _command_value(command, "--creator_id") == normalized["specified_account_ids"]
    assert _command_value(command, "--save_data_option") == "json"


def test_vibe_coding_save_option_normalization_and_command_passthrough(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "vibe_coding",
        params={
            "platforms": ["xhs"],
            "keywords": "cursor ai编程",
            "enable_keyword_search": True,
            "enable_account_crawl": True,
            "specified_account_ids": "208259",
            "save_option": "invalid_option",
        },
    )

    normalized = preview["normalized_params"]
    assert normalized["save_option"] == "json"

    stages = {stage["key"]: stage for stage in preview["spec"]["stages"]}
    keyword_command = stages["vibe_keyword_parallel_crawl"]["jobs"][0]["command"]
    creator_command = stages["vibe_creator_parallel_crawl"]["jobs"][0]["command"]

    assert _command_value(keyword_command, "--save-data-option") == "json"
    assert _command_value(creator_command, "--save_data_option") == "json"


def test_vibe_coding_keyword_job_chunking_expands_keyword_jobs(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    preview = service.preview_task(
        "vibe_coding",
        params={
            "platforms": ["xhs"],
            "keywords": "cursor,bolt,v0",
            "keyword_whitelist": "",
            "keyword_blacklist": "",
            "scenario_words": "",
            "enable_keyword_search": True,
            "enable_account_crawl": False,
            "keyword_job_mode": "chunked",
            "keyword_job_chunk_size": 2,
            "keyword_job_max_parallel": 2,
        },
    )

    stage = preview["spec"]["stages"][0]
    assert stage["key"] == "vibe_keyword_parallel_crawl"
    assert stage["max_parallel"] == 2
    assert len(stage["jobs"]) == 2
    assert len({job["key"] for job in stage["jobs"]}) == 2
    assert [_command_value(job["command"], "--search-keywords") for job in stage["jobs"]] == [
        "cursor,bolt",
        "v0",
    ]


def test_alias_params_override_preset_values(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    sentiment_preview = service.preview_task(
        "sentiment_monitor",
        preset_id="preset_sentiment_media_daily_report",
        params={
            "top_posts_count": 8,
            "top_comments_count": 5,
            "creator_ids": "creator_a,creator_b",
            "account_blacklist": "creator_b",
        },
    )
    sentiment_params = sentiment_preview["normalized_params"]
    assert sentiment_params["max_notes_count"] == sentiment_params["top_posts_count"] == 8
    assert sentiment_params["max_comments_count_singlenotes"] == sentiment_params["top_comments_count"] == 5
    assert sentiment_params["specified_account_ids"] == "creator_a"

    vibe_preview = service.preview_task(
        "vibe_coding",
        preset_id="preset_vibe_creator_targets",
        params={
            "search_keywords": "cursor ai编程,bolt.new做网站",
            "max_notes_per_keyword": 9,
            "top_comments_count": 4,
        },
    )
    vibe_params = vibe_preview["normalized_params"]
    assert vibe_params["keywords"] == "cursor ai编程,bolt.new做网站,vibe coding,ai编程实战,用ai做独立产品"
    assert vibe_params["max_notes_count"] == vibe_params["max_notes_per_keyword"] == 9
    assert vibe_params["max_comments_count_singlenotes"] == vibe_params["top_comments_count"] == 4


def test_seed_presets_cannot_be_updated(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    with pytest.raises(ValueError, match="Seed presets are managed by code/config"):
        service.update_preset(
            "preset_sentiment_media_daily_report",
            name="媒体监测日报-改名",
            params={
                "platforms": ["xhs"],
                "keywords": "测试关键词",
                "max_notes_count": 12,
                "enable_comments": False,
                "enable_sub_comments": False,
                "max_comments_count_singlenotes": 20,
                "login_type": "qrcode",
                "save_option": "json",
                "headless": False,
            },
            is_default=True,
        )


def test_seed_presets_cannot_be_deleted(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    with pytest.raises(ValueError, match="Seed presets are managed by code/config"):
        service.delete_preset("preset_sentiment_media_daily_report")


def test_stale_seed_presets_are_pruned_without_touching_user_presets(tmp_path: Path) -> None:
    state_dir = tmp_path / ".task_center"
    state_dir.mkdir(parents=True, exist_ok=True)
    presets_path = state_dir / "presets.json"
    presets_path.write_text(
        json.dumps(
            [
                {
                    "id": "preset_creator_dm_dry_run",
                    "task_slug": "creator_outreach",
                    "name": "旧私信预设",
                    "params": {"run_dm": True},
                    "is_default": False,
                    "is_seed": True,
                    "updated_at": "2026-04-17T00:00:00",
                },
                {
                    "id": "preset_creator_user_saved",
                    "task_slug": "creator_outreach",
                    "name": "用户自定义预设",
                    "params": {"run_dm": False},
                    "is_default": False,
                    "is_seed": False,
                    "updated_at": "2026-04-17T00:00:00",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = _build_service(tmp_path)
    preset_ids = [preset["id"] for preset in service.list_presets("creator_outreach")]

    assert "preset_creator_dm_dry_run" not in preset_ids
    assert "preset_creator_campaign_dry_run" in preset_ids
    assert "preset_creator_user_saved" in preset_ids
