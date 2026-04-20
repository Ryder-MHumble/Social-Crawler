from __future__ import annotations

import os
import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    yaml = None

from tasks.common.models import TaskJob, TaskSpec, TaskStage
from tasks.common.template import PresetSeed, TaskDefinition, TaskField, TaskFieldOption, TaskTemplate

_TASK_CONFIG_PATH = Path(__file__).with_name("config.yaml")
_TASK_CONFIG_WARNING_PREFIX = "[creator_outreach.task]"

FALLBACK_DISCOVERY_KEYWORDS = [
    "openclaw教程",
    "openclaw使用",
    "openclaw",
    "小龙虾编程",
]
FALLBACK_INCLUDE_PROFILE_KEYWORDS = [
    "ai",
    "人工智能",
    "agent",
    "mcp",
    "龙虾",
    "openclaw",
]
FALLBACK_INCLUDE_VIDEO_KEYWORDS = [
    "ai",
    "agent",
    "mcp",
    "openclaw",
    "龙虾",
    "claude",
    "cursor",
    "copilot",
]
FALLBACK_EXCLUDE_VIDEO_KEYWORDS = [
    "吃小龙虾",
    "麻辣小龙虾",
    "口味虾",
    "选股",
    "直播切片",
]
FALLBACK_MESSAGE_TEMPLATES = [
    {
        "id": "template_openclaw_invite",
        "name": "OpenClaw 活动邀约",
        "description": "适合首轮触达 AI 创作者、教程作者和工具体验类达人。",
        "message": """hihi你好呀，抱歉打扰啦，我是北京中关村学院的研究员，看到你主页分享了很多OpenClaw的落地应用，想邀请你参加我们举办的龙虾大赛

中关村学院“OpenClaw”比赛分学术 / 生产力 / 生活龙虾三条赛道，全场最佳奖金 20 万 + 100 亿 Token，每条赛道 10 个获奖名额。

报名很简单：上传链接讲清楚你的虾能做什么即可，不用交代码，核心看实际应用效果，结合硬件会加分。

报名：https://claw.lab.bza.edu.cn
详情：https://mp.weixin.qq.com/s/RfqXfunmEP1NLIln-9YUvQ""",
    },
    {
        "id": "template_product_demo",
        "name": "产品体验邀约",
        "description": "适合邀请达人体验产品、反馈功能、录制 demo。",
        "message": """你好，我这边在做一款 AI 编程 / Agent 方向的新产品，看到你平时会持续分享这类工具和实践，想邀请你提前体验一版。

如果你有兴趣，我们可以直接把体验名额、素材包和可公开的信息发给你，也欢迎你给我们提最直接的改进意见。""",
    },
]
FALLBACK_TASK_CONFIG = {
    "defaults": {
        "run_discovery": True,
        "run_filter": True,
        "run_dm": False,
        "discovery_keywords": FALLBACK_DISCOVERY_KEYWORDS,
        "seed_creator_ids": [],
        "max_pages_per_keyword": 3,
        "max_videos_per_creator": 20,
        "creator_whitelist": [],
        "creator_blacklist": [],
        "min_fans_count": 0,
        "max_fans_count": 0,
        "min_total_play_count": 1000,
        "min_total_comment_count": 0,
        "min_total_favorite_count": 0,
        "min_video_count": 1,
        "include_profile_keywords": FALLBACK_INCLUDE_PROFILE_KEYWORDS,
        "exclude_profile_keywords": [],
        "include_video_keywords": FALLBACK_INCLUDE_VIDEO_KEYWORDS,
        "exclude_video_keywords": FALLBACK_EXCLUDE_VIDEO_KEYWORDS,
        "message_template_mode": "template",
        "message_template_id": "template_openclaw_invite",
        "custom_message_template": "",
        "campaign_name": "openclaw_2026",
        "max_dm_targets": 50,
        "concurrent_tabs": 5,
        "batch_delay_seconds": 10,
        "dry_run": True,
    },
    "templates": FALLBACK_MESSAGE_TEMPLATES,
    "presets": [
        {
            "id": "discovery_only",
            "name": "创作者发现-不发私信",
            "params": {
                "run_discovery": True,
                "run_filter": True,
                "run_dm": False,
            },
            "is_default": True,
        },
        {
            "id": "campaign_dry_run",
            "name": "Campaign 干跑检查",
            "params": {
                "run_discovery": False,
                "run_filter": True,
                "run_dm": True,
                "dry_run": True,
            },
            "is_default": False,
        },
    ],
}

MESSAGE_MODE_OPTIONS = [
    TaskFieldOption(value="template", label="使用预设模板"),
    TaskFieldOption(value="custom", label="自定义文案"),
]


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sanitize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace("\n", ",").split(",")
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        raw_items = [str(item) for item in value]
    else:
        return []
    deduped: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        item = str(raw_item).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _csv_text(value: Any) -> str:
    return ",".join(_sanitize_string_list(value))


def _normalize_external_task_config(raw: Mapping[str, Any]) -> dict[str, Any]:
    defaults_raw = raw.get("defaults", {})
    templates_raw = raw.get("templates", [])
    presets_raw = raw.get("presets", [])
    fallback_defaults = FALLBACK_TASK_CONFIG["defaults"]

    defaults = {
        "run_discovery": _coerce_bool(
            defaults_raw.get("run_discovery"),
            bool(fallback_defaults["run_discovery"]),
        )
        if isinstance(defaults_raw, Mapping)
        else bool(fallback_defaults["run_discovery"]),
        "run_filter": _coerce_bool(
            defaults_raw.get("run_filter"),
            bool(fallback_defaults["run_filter"]),
        )
        if isinstance(defaults_raw, Mapping)
        else bool(fallback_defaults["run_filter"]),
        "run_dm": _coerce_bool(
            defaults_raw.get("run_dm"),
            bool(fallback_defaults["run_dm"]),
        )
        if isinstance(defaults_raw, Mapping)
        else bool(fallback_defaults["run_dm"]),
        "discovery_keywords": _sanitize_string_list(defaults_raw.get("discovery_keywords"))
        if isinstance(defaults_raw, Mapping)
        else list(fallback_defaults["discovery_keywords"]),
        "seed_creator_ids": _sanitize_string_list(defaults_raw.get("seed_creator_ids"))
        if isinstance(defaults_raw, Mapping)
        else list(fallback_defaults["seed_creator_ids"]),
        "max_pages_per_keyword": _coerce_int(
            defaults_raw.get("max_pages_per_keyword"),
            int(fallback_defaults["max_pages_per_keyword"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["max_pages_per_keyword"]),
        "max_videos_per_creator": _coerce_int(
            defaults_raw.get("max_videos_per_creator"),
            int(fallback_defaults["max_videos_per_creator"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["max_videos_per_creator"]),
        "creator_whitelist": _sanitize_string_list(defaults_raw.get("creator_whitelist"))
        if isinstance(defaults_raw, Mapping)
        else list(fallback_defaults["creator_whitelist"]),
        "creator_blacklist": _sanitize_string_list(defaults_raw.get("creator_blacklist"))
        if isinstance(defaults_raw, Mapping)
        else list(fallback_defaults["creator_blacklist"]),
        "min_fans_count": _coerce_int(
            defaults_raw.get("min_fans_count"),
            int(fallback_defaults["min_fans_count"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["min_fans_count"]),
        "max_fans_count": _coerce_int(
            defaults_raw.get("max_fans_count"),
            int(fallback_defaults["max_fans_count"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["max_fans_count"]),
        "min_total_play_count": _coerce_int(
            defaults_raw.get("min_total_play_count"),
            int(fallback_defaults["min_total_play_count"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["min_total_play_count"]),
        "min_total_comment_count": _coerce_int(
            defaults_raw.get("min_total_comment_count"),
            int(fallback_defaults["min_total_comment_count"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["min_total_comment_count"]),
        "min_total_favorite_count": _coerce_int(
            defaults_raw.get("min_total_favorite_count"),
            int(fallback_defaults["min_total_favorite_count"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["min_total_favorite_count"]),
        "min_video_count": _coerce_int(
            defaults_raw.get("min_video_count"),
            int(fallback_defaults["min_video_count"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["min_video_count"]),
        "include_profile_keywords": _sanitize_string_list(defaults_raw.get("include_profile_keywords"))
        if isinstance(defaults_raw, Mapping)
        else list(fallback_defaults["include_profile_keywords"]),
        "exclude_profile_keywords": _sanitize_string_list(defaults_raw.get("exclude_profile_keywords"))
        if isinstance(defaults_raw, Mapping)
        else list(fallback_defaults["exclude_profile_keywords"]),
        "include_video_keywords": _sanitize_string_list(defaults_raw.get("include_video_keywords"))
        if isinstance(defaults_raw, Mapping)
        else list(fallback_defaults["include_video_keywords"]),
        "exclude_video_keywords": _sanitize_string_list(defaults_raw.get("exclude_video_keywords"))
        if isinstance(defaults_raw, Mapping)
        else list(fallback_defaults["exclude_video_keywords"]),
        "message_template_mode": str(
            defaults_raw.get("message_template_mode", fallback_defaults["message_template_mode"])
        ).strip()
        if isinstance(defaults_raw, Mapping)
        else str(fallback_defaults["message_template_mode"]),
        "message_template_id": str(
            defaults_raw.get("message_template_id", fallback_defaults["message_template_id"])
        ).strip()
        if isinstance(defaults_raw, Mapping)
        else str(fallback_defaults["message_template_id"]),
        "custom_message_template": str(
            defaults_raw.get("custom_message_template", fallback_defaults["custom_message_template"])
        ).strip()
        if isinstance(defaults_raw, Mapping)
        else str(fallback_defaults["custom_message_template"]),
        "campaign_name": str(defaults_raw.get("campaign_name", fallback_defaults["campaign_name"])).strip()
        if isinstance(defaults_raw, Mapping)
        else str(fallback_defaults["campaign_name"]),
        "max_dm_targets": _coerce_int(
            defaults_raw.get("max_dm_targets"),
            int(fallback_defaults["max_dm_targets"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["max_dm_targets"]),
        "concurrent_tabs": _coerce_int(
            defaults_raw.get("concurrent_tabs"),
            int(fallback_defaults["concurrent_tabs"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["concurrent_tabs"]),
        "batch_delay_seconds": _coerce_int(
            defaults_raw.get("batch_delay_seconds"),
            int(fallback_defaults["batch_delay_seconds"]),
        )
        if isinstance(defaults_raw, Mapping)
        else int(fallback_defaults["batch_delay_seconds"]),
        "dry_run": _coerce_bool(
            defaults_raw.get("dry_run"),
            bool(fallback_defaults["dry_run"]),
        )
        if isinstance(defaults_raw, Mapping)
        else bool(fallback_defaults["dry_run"]),
    }

    templates: list[dict[str, str]] = []
    if isinstance(templates_raw, Sequence) and not isinstance(templates_raw, (bytes, bytearray, str)):
        for raw_template in templates_raw:
            if not isinstance(raw_template, Mapping):
                continue
            template_id = str(raw_template.get("id", "")).strip()
            name = str(raw_template.get("name", "")).strip()
            message = str(raw_template.get("message", "")).strip()
            if not template_id or not name or not message:
                continue
            templates.append(
                {
                    "id": template_id,
                    "name": name,
                    "description": str(raw_template.get("description", "")).strip(),
                    "message": message,
                }
            )

    presets: list[dict[str, Any]] = []
    if isinstance(presets_raw, Sequence) and not isinstance(presets_raw, (bytes, bytearray, str)):
        for raw_preset in presets_raw:
            if not isinstance(raw_preset, Mapping):
                continue
            preset_id = str(raw_preset.get("id", "")).strip()
            name = str(raw_preset.get("name", "")).strip()
            params = raw_preset.get("params", {})
            if not preset_id or not name or not isinstance(params, Mapping):
                continue
            presets.append(
                {
                    "id": preset_id,
                    "name": name,
                    "params": dict(params),
                    "is_default": _coerce_bool(raw_preset.get("is_default"), False),
                }
            )

    return {
        "defaults": defaults,
        "templates": templates or list(FALLBACK_MESSAGE_TEMPLATES),
        "presets": presets or list(FALLBACK_TASK_CONFIG["presets"]),
    }


def _load_task_config() -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    if yaml is None and _TASK_CONFIG_PATH.exists():
        warnings.warn(
            f"{_TASK_CONFIG_WARNING_PREFIX} PyYAML is unavailable; falling back to hardcoded defaults.",
            stacklevel=2,
        )
    elif yaml is not None and _TASK_CONFIG_PATH.exists():
        try:
            raw = yaml.safe_load(_TASK_CONFIG_PATH.read_text(encoding="utf-8")) or {}
            if isinstance(raw, Mapping):
                loaded = _normalize_external_task_config(raw)
        except Exception as exc:
            warnings.warn(
                f"{_TASK_CONFIG_WARNING_PREFIX} Failed to load {_TASK_CONFIG_PATH.name}: {exc}. "
                "Falling back to hardcoded defaults.",
                stacklevel=2,
            )
            loaded = {}
    return loaded or dict(FALLBACK_TASK_CONFIG)


TASK_CONFIG = _load_task_config()
DEFAULTS = dict(TASK_CONFIG["defaults"])
MESSAGE_TEMPLATES = list(TASK_CONFIG["templates"])
MESSAGE_TEMPLATE_OPTIONS = [
    TaskFieldOption(
        value=template["id"],
        label=template["name"],
        description=template.get("description", ""),
    )
    for template in MESSAGE_TEMPLATES
]
MESSAGE_TEMPLATE_MAP = {template["id"]: template for template in MESSAGE_TEMPLATES}
DEFAULT_PARAMS = {
    **DEFAULTS,
    "discovery_keywords": _csv_text(DEFAULTS["discovery_keywords"]),
    "seed_creator_ids": _csv_text(DEFAULTS["seed_creator_ids"]),
    "creator_whitelist": _csv_text(DEFAULTS["creator_whitelist"]),
    "creator_blacklist": _csv_text(DEFAULTS["creator_blacklist"]),
    "include_profile_keywords": _csv_text(DEFAULTS["include_profile_keywords"]),
    "exclude_profile_keywords": _csv_text(DEFAULTS["exclude_profile_keywords"]),
    "include_video_keywords": _csv_text(DEFAULTS["include_video_keywords"]),
    "exclude_video_keywords": _csv_text(DEFAULTS["exclude_video_keywords"]),
}


def _get_template_message(template_id: str) -> str:
    return MESSAGE_TEMPLATE_MAP.get(template_id, {}).get("message", "")


def _resolve_message(params: Mapping[str, Any]) -> str:
    if params["message_template_mode"] == "custom":
        return str(params["custom_message_template"]).strip()
    return _get_template_message(str(params["message_template_id"]))


def _discovery_command(python_executable: str) -> list[str]:
    return [python_executable, "-m", "tasks.creator_outreach.discover_bilibili_creators"]


def _prepare_csv_command(python_executable: str, params: Mapping[str, Any]) -> list[str]:
    command = [
        python_executable,
        "-m",
        "tasks.creator_outreach.prepare_creator_csv",
        "--filter",
        "1" if params["run_filter"] else "0",
    ]
    for flag, value in (
        ("--creator-whitelist", params["creator_whitelist"]),
        ("--creator-blacklist", params["creator_blacklist"]),
        ("--include-profile-keywords", params["include_profile_keywords"]),
        ("--exclude-profile-keywords", params["exclude_profile_keywords"]),
        ("--include-video-keywords", params["include_video_keywords"]),
        ("--exclude-video-keywords", params["exclude_video_keywords"]),
        ("--campaign-name", params["campaign_name"]),
    ):
        if value:
            command.extend([flag, str(value)])
    for flag, value in (
        ("--min-fans-count", params["min_fans_count"]),
        ("--max-fans-count", params["max_fans_count"]),
        ("--min-total-play-count", params["min_total_play_count"]),
        ("--min-total-comment-count", params["min_total_comment_count"]),
        ("--min-total-favorite-count", params["min_total_favorite_count"]),
        ("--min-video-count", params["min_video_count"]),
        ("--max-targets", params["max_dm_targets"]),
    ):
        if int(value) > 0:
            command.extend([flag, str(value)])
    return command


def get_template() -> TaskTemplate:
    return TaskTemplate(
        slug="creator_outreach",
        title="创作者触达",
        description="围绕达人发现、规则筛选、话术模板和投放节奏统一建模的 Bilibili 触达任务。",
        defaults=dict(DEFAULT_PARAMS),
        capabilities=[
            "发现 / 筛选 / 触达三段式流程",
            "达人白名单、黑名单与筛选规则建模",
            "预设话术模板与自定义文案",
            "批量 campaign 干跑与节奏控制",
        ],
        fields=[
            TaskField(
                key="run_discovery",
                component="switch",
                label="执行发现阶段",
                default=DEFAULT_PARAMS["run_discovery"],
                group="阶段控制",
                badge="Discovery",
            ),
            TaskField(
                key="run_filter",
                component="switch",
                label="执行筛选阶段",
                default=DEFAULT_PARAMS["run_filter"],
                group="阶段控制",
                badge="Filter",
            ),
            TaskField(
                key="run_dm",
                component="switch",
                label="执行触达阶段",
                default=DEFAULT_PARAMS["run_dm"],
                description="默认关闭，避免误发；可结合 dry-run 先演练。",
                group="阶段控制",
                badge="DM",
            ),
            TaskField(
                key="discovery_keywords",
                component="textarea",
                label="发现关键词",
                default=DEFAULT_PARAMS["discovery_keywords"],
                description="多个关键词用英文逗号或换行分隔。",
                placeholder="例如：openclaw教程, agent 工作流, ai 编程",
                rows=6,
                layout="full",
                group="发现来源",
                visible_when={"run_discovery": True},
            ),
            TaskField(
                key="seed_creator_ids",
                component="textarea",
                label="种子达人 ID / URL",
                default=DEFAULT_PARAMS["seed_creator_ids"],
                description="可直接补充指定达人主页 URL 或 UID，无需完全依赖关键词发现。",
                placeholder="例如：https://space.bilibili.com/4401694, 385670211",
                rows=4,
                layout="full",
                group="发现来源",
                visible_when={"run_discovery": True},
            ),
            TaskField(
                key="max_pages_per_keyword",
                component="number",
                label="每个关键词抓取页数",
                default=DEFAULT_PARAMS["max_pages_per_keyword"],
                group="发现来源",
                visible_when={"run_discovery": True},
                validation={"min": 1, "max": 20},
            ),
            TaskField(
                key="max_videos_per_creator",
                component="number",
                label="每个达人采样视频数",
                default=DEFAULT_PARAMS["max_videos_per_creator"],
                group="发现来源",
                visible_when={"run_discovery": True},
                validation={"min": 1, "max": 100},
            ),
            TaskField(
                key="creator_whitelist",
                component="textarea",
                label="达人白名单",
                default=DEFAULT_PARAMS["creator_whitelist"],
                description="最终候选人必须命中白名单时使用。",
                rows=3,
                layout="full",
                group="筛选规则",
            ),
            TaskField(
                key="creator_blacklist",
                component="textarea",
                label="达人黑名单",
                default=DEFAULT_PARAMS["creator_blacklist"],
                description="会从候选池中直接剔除。",
                rows=3,
                layout="full",
                group="筛选规则",
            ),
            TaskField(
                key="min_fans_count",
                component="number",
                label="最小粉丝数",
                default=DEFAULT_PARAMS["min_fans_count"],
                group="筛选规则",
                validation={"min": 0, "max": 100000000},
            ),
            TaskField(
                key="max_fans_count",
                component="number",
                label="最大粉丝数",
                default=DEFAULT_PARAMS["max_fans_count"],
                group="筛选规则",
                helper_text="填 0 表示不设上限。",
                validation={"min": 0, "max": 100000000},
            ),
            TaskField(
                key="min_total_play_count",
                component="number",
                label="最小总播放量",
                default=DEFAULT_PARAMS["min_total_play_count"],
                group="筛选规则",
                validation={"min": 0, "max": 1000000000},
            ),
            TaskField(
                key="min_total_comment_count",
                component="number",
                label="最小总评论数",
                default=DEFAULT_PARAMS["min_total_comment_count"],
                group="筛选规则",
                validation={"min": 0, "max": 100000000},
            ),
            TaskField(
                key="min_total_favorite_count",
                component="number",
                label="最小总收藏数",
                default=DEFAULT_PARAMS["min_total_favorite_count"],
                group="筛选规则",
                validation={"min": 0, "max": 100000000},
            ),
            TaskField(
                key="min_video_count",
                component="number",
                label="最小视频数量",
                default=DEFAULT_PARAMS["min_video_count"],
                group="筛选规则",
                validation={"min": 1, "max": 1000},
            ),
            TaskField(
                key="include_profile_keywords",
                component="textarea",
                label="简介命中词",
                default=DEFAULT_PARAMS["include_profile_keywords"],
                description="至少命中其一时保留。",
                rows=4,
                layout="full",
                group="筛选规则",
            ),
            TaskField(
                key="exclude_profile_keywords",
                component="textarea",
                label="简介排除词",
                default=DEFAULT_PARAMS["exclude_profile_keywords"],
                description="命中任一即剔除。",
                rows=4,
                layout="full",
                group="筛选规则",
            ),
            TaskField(
                key="include_video_keywords",
                component="textarea",
                label="视频命中词",
                default=DEFAULT_PARAMS["include_video_keywords"],
                description="代表视频中至少命中其一时保留。",
                rows=4,
                layout="full",
                group="筛选规则",
            ),
            TaskField(
                key="exclude_video_keywords",
                component="textarea",
                label="视频排除词",
                default=DEFAULT_PARAMS["exclude_video_keywords"],
                description="代表视频命中任一即剔除。",
                rows=4,
                layout="full",
                group="筛选规则",
            ),
            TaskField(
                key="message_template_mode",
                component="select",
                label="话术来源",
                default=DEFAULT_PARAMS["message_template_mode"],
                group="话术与 Campaign",
                options=MESSAGE_MODE_OPTIONS,
                visible_when={"run_dm": True},
            ),
            TaskField(
                key="message_template_id",
                component="select",
                label="预设话术模板",
                default=DEFAULT_PARAMS["message_template_id"],
                group="话术与 Campaign",
                options=MESSAGE_TEMPLATE_OPTIONS,
                visible_when={"run_dm": True, "message_template_mode": "template"},
            ),
            TaskField(
                key="custom_message_template",
                component="textarea",
                label="自定义触达文案",
                default=DEFAULT_PARAMS["custom_message_template"],
                placeholder="输入完整触达文案，运行时会直接发送给达人。",
                rows=8,
                layout="full",
                group="话术与 Campaign",
                visible_when={"run_dm": True, "message_template_mode": "custom"},
            ),
            TaskField(
                key="campaign_name",
                component="text",
                label="Campaign 名称",
                default=DEFAULT_PARAMS["campaign_name"],
                description="用于运行记录和防重复发送。",
                group="话术与 Campaign",
                visible_when={"run_dm": True},
            ),
            TaskField(
                key="max_dm_targets",
                component="number",
                label="本次最多触达人数",
                default=DEFAULT_PARAMS["max_dm_targets"],
                group="执行节奏",
                visible_when={"run_dm": True},
                validation={"min": 1, "max": 10000},
            ),
            TaskField(
                key="concurrent_tabs",
                component="number",
                label="并发标签页数",
                default=DEFAULT_PARAMS["concurrent_tabs"],
                group="执行节奏",
                visible_when={"run_dm": True},
                validation={"min": 1, "max": 20},
            ),
            TaskField(
                key="batch_delay_seconds",
                component="number",
                label="批次间隔秒数",
                default=DEFAULT_PARAMS["batch_delay_seconds"],
                group="执行节奏",
                visible_when={"run_dm": True},
                validation={"min": 0, "max": 3600},
            ),
            TaskField(
                key="dry_run",
                component="switch",
                label="Dry-run 演练",
                default=DEFAULT_PARAMS["dry_run"],
                description="开启后只演练触达名单和节奏，不真正发送私信。",
                group="执行节奏",
                visible_when={"run_dm": True},
            ),
        ],
    )


def normalize_params(raw_params: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(raw_params or {})
    params = {
        "run_discovery": _coerce_bool(raw.get("run_discovery"), DEFAULT_PARAMS["run_discovery"]),
        "run_filter": _coerce_bool(raw.get("run_filter"), DEFAULT_PARAMS["run_filter"]),
        "run_dm": _coerce_bool(raw.get("run_dm"), DEFAULT_PARAMS["run_dm"]),
        "discovery_keywords": _csv_text(
            raw.get("discovery_keywords", DEFAULT_PARAMS["discovery_keywords"])
        ),
        "seed_creator_ids": _csv_text(raw.get("seed_creator_ids", DEFAULT_PARAMS["seed_creator_ids"])),
        "max_pages_per_keyword": _coerce_int(
            raw.get("max_pages_per_keyword"),
            DEFAULT_PARAMS["max_pages_per_keyword"],
        ),
        "max_videos_per_creator": _coerce_int(
            raw.get("max_videos_per_creator"),
            DEFAULT_PARAMS["max_videos_per_creator"],
        ),
        "creator_whitelist": _csv_text(raw.get("creator_whitelist", DEFAULT_PARAMS["creator_whitelist"])),
        "creator_blacklist": _csv_text(raw.get("creator_blacklist", DEFAULT_PARAMS["creator_blacklist"])),
        "min_fans_count": max(0, _coerce_int(raw.get("min_fans_count"), DEFAULT_PARAMS["min_fans_count"])),
        "max_fans_count": max(0, _coerce_int(raw.get("max_fans_count"), DEFAULT_PARAMS["max_fans_count"])),
        "min_total_play_count": max(
            0,
            _coerce_int(raw.get("min_total_play_count"), DEFAULT_PARAMS["min_total_play_count"]),
        ),
        "min_total_comment_count": max(
            0,
            _coerce_int(raw.get("min_total_comment_count"), DEFAULT_PARAMS["min_total_comment_count"]),
        ),
        "min_total_favorite_count": max(
            0,
            _coerce_int(raw.get("min_total_favorite_count"), DEFAULT_PARAMS["min_total_favorite_count"]),
        ),
        "min_video_count": max(1, _coerce_int(raw.get("min_video_count"), DEFAULT_PARAMS["min_video_count"])),
        "include_profile_keywords": _csv_text(
            raw.get("include_profile_keywords", DEFAULT_PARAMS["include_profile_keywords"])
        ),
        "exclude_profile_keywords": _csv_text(
            raw.get("exclude_profile_keywords", DEFAULT_PARAMS["exclude_profile_keywords"])
        ),
        "include_video_keywords": _csv_text(
            raw.get("include_video_keywords", DEFAULT_PARAMS["include_video_keywords"])
        ),
        "exclude_video_keywords": _csv_text(
            raw.get("exclude_video_keywords", DEFAULT_PARAMS["exclude_video_keywords"])
        ),
        "message_template_mode": str(
            raw.get("message_template_mode", DEFAULT_PARAMS["message_template_mode"])
        ).strip()
        or DEFAULT_PARAMS["message_template_mode"],
        "message_template_id": str(
            raw.get("message_template_id", DEFAULT_PARAMS["message_template_id"])
        ).strip()
        or DEFAULT_PARAMS["message_template_id"],
        "custom_message_template": str(
            raw.get("custom_message_template", DEFAULT_PARAMS["custom_message_template"])
        ).strip(),
        "campaign_name": str(raw.get("campaign_name", DEFAULT_PARAMS["campaign_name"])).strip()
        or DEFAULT_PARAMS["campaign_name"],
        "max_dm_targets": max(1, _coerce_int(raw.get("max_dm_targets"), DEFAULT_PARAMS["max_dm_targets"])),
        "concurrent_tabs": max(1, _coerce_int(raw.get("concurrent_tabs"), DEFAULT_PARAMS["concurrent_tabs"])),
        "batch_delay_seconds": max(
            0,
            _coerce_int(raw.get("batch_delay_seconds"), DEFAULT_PARAMS["batch_delay_seconds"]),
        ),
        "dry_run": _coerce_bool(raw.get("dry_run"), DEFAULT_PARAMS["dry_run"]),
    }
    if not (params["run_discovery"] or params["run_filter"] or params["run_dm"]):
        raise ValueError("At least one stage must be enabled.")
    if params["run_discovery"] and not params["discovery_keywords"] and not params["seed_creator_ids"]:
        raise ValueError("Provide discovery_keywords or seed_creator_ids when discovery is enabled.")
    if params["max_pages_per_keyword"] < 1:
        raise ValueError("max_pages_per_keyword must be greater than 0.")
    if params["max_videos_per_creator"] < 1:
        raise ValueError("max_videos_per_creator must be greater than 0.")
    if params["max_fans_count"] and params["max_fans_count"] < params["min_fans_count"]:
        raise ValueError("max_fans_count must be greater than or equal to min_fans_count.")
    if params["message_template_mode"] not in {"template", "custom"}:
        raise ValueError("message_template_mode must be template or custom.")
    if params["message_template_mode"] == "template" and params["message_template_id"] not in MESSAGE_TEMPLATE_MAP:
        raise ValueError("message_template_id is not defined in config.yaml.")
    resolved_message = _resolve_message(params)
    if params["run_dm"] and not resolved_message:
        raise ValueError("Message template cannot be empty when DM stage is enabled.")
    params["resolved_message_template"] = resolved_message
    return params


def build_task(
    project_root: Path,
    python_executable: str,
    params: Mapping[str, Any] | None = None,
) -> TaskSpec:
    normalized = normalize_params(params or DEFAULT_PARAMS)
    stages: list[TaskStage] = []

    if normalized["run_discovery"]:
        command = [
            *_discovery_command(python_executable),
            "--keywords",
            normalized["discovery_keywords"],
            "--max-pages-per-keyword",
            str(normalized["max_pages_per_keyword"]),
            "--max-videos-per-creator",
            str(normalized["max_videos_per_creator"]),
        ]
        if normalized["seed_creator_ids"]:
            command.extend(["--seed-creator-ids", normalized["seed_creator_ids"]])
        stages.append(
            TaskStage(
                key="discover_creators",
                name="Discover creators by keyword",
                jobs=[
                    TaskJob(
                        key="discover",
                        name="Creator discovery",
                        command=command,
                        cwd=project_root,
                    )
                ],
                concurrent=False,
                abort_on_failure=True,
            )
        )

    if normalized["run_discovery"] or normalized["run_filter"] or normalized["run_dm"]:
        stages.append(
            TaskStage(
                key="prepare_creator_list",
                name="Prepare outreach creator list",
                jobs=[
                    TaskJob(
                        key="prepare_csv",
                        name="Prepare creator CSV",
                        command=_prepare_csv_command(python_executable, normalized),
                        cwd=project_root,
                    )
                ],
                concurrent=False,
                abort_on_failure=True,
            )
        )

    if normalized["run_dm"]:
        dm_command = [
            python_executable,
            "send_bilibili_dm_manual.py",
            "--campaign-id",
            normalized["campaign_name"],
            "--concurrent-tabs",
            str(normalized["concurrent_tabs"]),
            "--batch-delay-seconds",
            str(normalized["batch_delay_seconds"]),
            "--max-targets",
            str(normalized["max_dm_targets"]),
        ]
        if normalized["dry_run"]:
            dm_command.append("--dry-run")
        stages.append(
            TaskStage(
                key="dm_campaign",
                name="Send outreach DM campaign",
                jobs=[
                    TaskJob(
                        key="send_dm",
                        name="Bilibili DM sender",
                        command=dm_command,
                        cwd=project_root / "bilibili_dm_sender",
                        env={
                            "BILI_DM_MESSAGE": normalized["resolved_message_template"],
                            "BILI_DM_MESSAGE_TEMPLATE_ID": (
                                normalized["message_template_id"]
                                if normalized["message_template_mode"] == "template"
                                else "custom"
                            ),
                        },
                    )
                ],
                concurrent=False,
                abort_on_failure=False,
            )
        )

    return TaskSpec(
        slug="creator_outreach",
        title="Creator Outreach",
        short_desc="Discover creators, filter them, and run configurable outreach campaigns",
        capabilities=[
            "Bilibili creator discovery with keyword and seed-account inputs",
            "Rule-based filtering with whitelist, blacklist, and threshold modeling",
            "Template-driven or custom outreach copy",
            "Campaign-level cadence control and dry-run support",
        ],
        welcome_lines=[
            "Mission: run a modeled creator outreach workflow.",
            f"Discovery: {'on' if normalized['run_discovery'] else 'off'}",
            f"Filter: {'on' if normalized['run_filter'] else 'off'}",
            f"DM: {'on' if normalized['run_dm'] else 'off'}",
            f"Campaign: {normalized['campaign_name']}",
            f"Dry-run: {'on' if normalized['dry_run'] else 'off'}",
        ],
        stages=stages,
        aliases=["outreach", "dm_campaign"],
    )


def build_definition() -> TaskDefinition:
    return TaskDefinition(
        template=get_template(),
        normalize_params=normalize_params,
        build_task_spec=build_task,
        preset_seeds=[
            PresetSeed(
                id=f"preset_creator_{preset['id']}",
                task_slug="creator_outreach",
                name=str(preset["name"]),
                params=normalize_params({**DEFAULT_PARAMS, **dict(preset["params"])}),
                is_default=bool(preset["is_default"]),
            )
            for preset in TASK_CONFIG["presets"]
        ],
    )
