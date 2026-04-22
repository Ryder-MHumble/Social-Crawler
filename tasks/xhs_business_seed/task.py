from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import config
from tasks.common.models import TaskJob, TaskSpec, TaskStage
from tasks.common.template import (
    PresetSeed,
    TaskDefinition,
    TaskField,
    TaskFieldOption,
    TaskTemplate,
)

from .keyword_config import (
    DEFAULT_RELEVANCE_EXCLUDE,
    DEFAULT_RELEVANCE_MUST_CONTAIN,
    build_keyword_pool,
    parse_keyword_buckets,
    split_keywords_into_batches,
)

KEYWORD_BUCKET_OPTIONS = [
    TaskFieldOption(value="core", label="Core Terms"),
    TaskFieldOption(value="scene", label="Scene Terms"),
    TaskFieldOption(value="risk", label="Risk Terms"),
]
LOGIN_OPTIONS = [
    TaskFieldOption(value="qrcode", label="QR Code"),
    TaskFieldOption(value="cookie", label="Cookie"),
    TaskFieldOption(value="phone", label="Phone"),
]
DEFAULT_PARAMS = {
    "keyword_buckets": ["core", "scene"],
    "include_risk_keywords": False,
    "parallel_jobs": 4,
    "max_notes_per_keyword": 30,
    "enable_comments": False,
    "enable_sub_comments": False,
    "max_comments_per_note": getattr(config, "CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES", 20),
    "login_type": getattr(config, "LOGIN_TYPE", "qrcode"),
    "headless": getattr(config, "HEADLESS", False),
}


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_cookie(platform: str) -> str:
    try:
        import cookies_config  # type: ignore
    except ImportError:
        return ""

    get_cookie = getattr(cookies_config, "get_cookie", None)
    if callable(get_cookie):
        cookie = get_cookie(platform)
        if isinstance(cookie, str):
            return cookie.strip()
    return ""


def get_template() -> TaskTemplate:
    return TaskTemplate(
        slug="xhs_business_seed",
        title="XHS Business Seed Crawl",
        description="Parallel Xiaohongshu crawl for the business keyword pool, defaulting to Supabase storage.",
        defaults=dict(DEFAULT_PARAMS),
        capabilities=[
            "Business-ready keyword pool seeded from the monitoring brief",
            "Parallel XiaoHongShu keyword batching",
            "Supabase-first storage with existing dedup filters",
        ],
        fields=[
            TaskField(
                key="keyword_buckets",
                component="multiselect",
                label="Keyword Buckets",
                default=list(DEFAULT_PARAMS["keyword_buckets"]),
                group="Scope",
                required=True,
                options=KEYWORD_BUCKET_OPTIONS,
                validation={"min_items": 1},
            ),
            TaskField(
                key="include_risk_keywords",
                component="switch",
                label="Include Risk Terms",
                default=DEFAULT_PARAMS["include_risk_keywords"],
                group="Scope",
            ),
            TaskField(
                key="parallel_jobs",
                component="number",
                label="Parallel Jobs",
                default=DEFAULT_PARAMS["parallel_jobs"],
                group="Runtime",
                validation={"min": 1, "max": 8},
            ),
            TaskField(
                key="max_notes_per_keyword",
                component="number",
                label="Max Notes / Keyword",
                default=DEFAULT_PARAMS["max_notes_per_keyword"],
                group="Runtime",
                validation={"min": 1, "max": 100},
            ),
            TaskField(
                key="enable_comments",
                component="switch",
                label="Enable Comments",
                default=DEFAULT_PARAMS["enable_comments"],
                group="Runtime",
            ),
            TaskField(
                key="enable_sub_comments",
                component="switch",
                label="Enable Sub-comments",
                default=DEFAULT_PARAMS["enable_sub_comments"],
                group="Runtime",
                visible_when={"enable_comments": True},
            ),
            TaskField(
                key="max_comments_per_note",
                component="number",
                label="Max Comments / Note",
                default=DEFAULT_PARAMS["max_comments_per_note"],
                group="Runtime",
                visible_when={"enable_comments": True},
                validation={"min": 1, "max": 100},
            ),
            TaskField(
                key="login_type",
                component="select",
                label="Login Type",
                default=DEFAULT_PARAMS["login_type"],
                group="Runtime",
                options=LOGIN_OPTIONS,
            ),
            TaskField(
                key="headless",
                component="switch",
                label="Headless",
                default=DEFAULT_PARAMS["headless"],
                group="Runtime",
            ),
        ],
    )


def normalize_params(raw_params: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(raw_params or {})
    params = {
        "keyword_buckets": parse_keyword_buckets(raw.get("keyword_buckets")),
        "include_risk_keywords": _coerce_bool(
            raw.get("include_risk_keywords"),
            DEFAULT_PARAMS["include_risk_keywords"],
        ),
        "parallel_jobs": int(raw.get("parallel_jobs", DEFAULT_PARAMS["parallel_jobs"])),
        "max_notes_per_keyword": int(
            raw.get("max_notes_per_keyword", DEFAULT_PARAMS["max_notes_per_keyword"])
        ),
        "enable_comments": _coerce_bool(
            raw.get("enable_comments"),
            DEFAULT_PARAMS["enable_comments"],
        ),
        "enable_sub_comments": _coerce_bool(
            raw.get("enable_sub_comments"),
            DEFAULT_PARAMS["enable_sub_comments"],
        ),
        "max_comments_per_note": int(
            raw.get("max_comments_per_note", DEFAULT_PARAMS["max_comments_per_note"])
        ),
        "login_type": str(raw.get("login_type", DEFAULT_PARAMS["login_type"])).strip() or "qrcode",
        "headless": _coerce_bool(raw.get("headless"), DEFAULT_PARAMS["headless"]),
    }
    if params["parallel_jobs"] < 1:
        raise ValueError("parallel_jobs must be greater than 0.")
    if params["max_notes_per_keyword"] < 1:
        raise ValueError("max_notes_per_keyword must be greater than 0.")
    if params["max_comments_per_note"] < 1:
        raise ValueError("max_comments_per_note must be greater than 0.")
    if not params["enable_comments"]:
        params["enable_sub_comments"] = False

    keywords = build_keyword_pool(
        include_core="core" in params["keyword_buckets"],
        include_scene="scene" in params["keyword_buckets"],
        include_risk=params["include_risk_keywords"] or "risk" in params["keyword_buckets"],
    )
    if not keywords:
        raise ValueError("At least one keyword bucket must yield keywords.")
    return params


def build_task(
    project_root: Path,
    python_executable: str,
    params: Mapping[str, Any] | None = None,
) -> TaskSpec:
    normalized = normalize_params(params or DEFAULT_PARAMS)
    keywords = build_keyword_pool(
        include_core="core" in normalized["keyword_buckets"],
        include_scene="scene" in normalized["keyword_buckets"],
        include_risk=normalized["include_risk_keywords"] or "risk" in normalized["keyword_buckets"],
    )
    batches = split_keywords_into_batches(
        keywords,
        parallel_jobs=normalized["parallel_jobs"],
    )
    bootstrap_command = [
        python_executable,
        "-m",
        "tasks.xhs_business_seed.worker",
        "--keywords",
        keywords[0],
        "--job-label",
        "bootstrap",
        "--max-notes-per-keyword",
        "1",
        "--enable-comments",
        "false",
        "--enable-sub-comments",
        "false",
        "--max-comments-per-note",
        "1",
        "--login-type",
        normalized["login_type"],
        "--headless",
        "false",
        "--max-concurrency",
        "1",
        "--sleep-sec",
        str(getattr(config, "CRAWLER_MAX_SLEEP_SEC", 5)),
        "--save-option",
        "supabase",
        "--enable-official-accounts",
        "false",
        "--profile-mode",
        "shared",
        "--profile-key",
        "bootstrap",
        "--relevance-must-contain",
        ",".join(DEFAULT_RELEVANCE_MUST_CONTAIN),
        "--relevance-exclude",
        ",".join(DEFAULT_RELEVANCE_EXCLUDE),
        "--min-content-engagement",
        str(getattr(config, "MIN_CONTENT_ENGAGEMENT", 0)),
        "--min-comment-length",
        str(getattr(config, "MIN_COMMENT_LENGTH", 5)),
    ]
    bootstrap_cookie = _load_cookie("xhs") if normalized["login_type"] == "cookie" else ""
    if bootstrap_cookie:
        bootstrap_command.extend(["--cookies", bootstrap_cookie])

    jobs: list[TaskJob] = []
    for index, batch in enumerate(batches, start=1):
        command = [
            python_executable,
            "-m",
            "tasks.xhs_business_seed.worker",
            "--keywords",
            ",".join(batch),
            "--job-label",
            f"batch-{index:02d}",
            "--max-notes-per-keyword",
            str(normalized["max_notes_per_keyword"]),
            "--enable-comments",
            "true" if normalized["enable_comments"] else "false",
            "--enable-sub-comments",
            "true" if normalized["enable_sub_comments"] else "false",
            "--max-comments-per-note",
            str(normalized["max_comments_per_note"]),
            "--login-type",
            normalized["login_type"],
            "--headless",
            "true" if normalized["headless"] else "false",
            "--max-concurrency",
            "1",
            "--sleep-sec",
            str(getattr(config, "CRAWLER_MAX_SLEEP_SEC", 5)),
            "--save-option",
            "supabase",
            "--enable-official-accounts",
            "false",
            "--profile-mode",
            "clone",
            "--profile-key",
            f"batch_{index:02d}",
            "--relevance-must-contain",
            ",".join(DEFAULT_RELEVANCE_MUST_CONTAIN),
            "--relevance-exclude",
            ",".join(DEFAULT_RELEVANCE_EXCLUDE),
            "--min-content-engagement",
            str(getattr(config, "MIN_CONTENT_ENGAGEMENT", 0)),
            "--min-comment-length",
            str(getattr(config, "MIN_COMMENT_LENGTH", 5)),
        ]
        cookie = _load_cookie("xhs") if normalized["login_type"] == "cookie" else ""
        if cookie:
            command.extend(["--cookies", cookie])
        title = batch[0] if len(batch) == 1 else f"{batch[0]} +{len(batch) - 1}"
        jobs.append(
            TaskJob(
                key=f"batch_{index:02d}",
                name=f"XHS batch {index:02d} | {title}",
                command=command,
                cwd=project_root,
            )
        )

    welcome_lines = [
        "Mission: expand Xiaohongshu coverage with the business keyword pool.",
        f"Keyword buckets: {', '.join(normalized['keyword_buckets'])}",
        f"Total keywords: {len(keywords)}",
        f"Parallel jobs: {len(jobs)}",
        f"Comments: {'enabled' if normalized['enable_comments'] else 'disabled'}",
        "Storage: supabase",
    ]
    stage = TaskStage(
        key="xhs_business_seed_parallel_crawl",
        name="XHS business seed parallel crawl",
        jobs=jobs,
        concurrent=True,
        abort_on_failure=False,
    )
    bootstrap_stage = TaskStage(
        key="xhs_business_seed_login_bootstrap",
        name="XHS login bootstrap",
        jobs=[
            TaskJob(
                key="bootstrap",
                name="Bootstrap XHS login state",
                command=bootstrap_command,
                cwd=project_root,
            )
        ],
        concurrent=False,
        abort_on_failure=True,
    )
    return TaskSpec(
        slug="xhs_business_seed",
        title="XHS Business Seed Crawl",
        short_desc="Parallel Xiaohongshu crawl for business monitoring keywords",
        capabilities=[
            "Core-term and scene-term keyword pool",
            "Bootstrap login stage before parallel crawl",
            "Parallel keyword batching for XiaoHongShu",
            "Supabase-first persistence with dedup-ready storage",
        ],
        welcome_lines=welcome_lines,
        stages=[bootstrap_stage, stage],
        aliases=["xhs_seed", "business_seed"],
    )


def build_definition() -> TaskDefinition:
    return TaskDefinition(
        template=get_template(),
        normalize_params=normalize_params,
        build_task_spec=build_task,
        preset_seeds=[
            PresetSeed(
                id="preset_xhs_business_seed_default",
                task_slug="xhs_business_seed",
                name="XHS Business Seed Default",
                params=dict(DEFAULT_PARAMS),
                is_default=False,
            )
        ],
    )
