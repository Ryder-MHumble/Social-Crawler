from __future__ import annotations

from math import ceil
from typing import Iterable

CORE_ENTITY_KEYWORDS = [
    "北京中关村学院",
    "中关村学院",
    "北京中关村学院招生",
    "北京中关村学院夏令营",
    "北京中关村学院博士生",
    "中关村人工智能研究院",
    "刘铁岩",
    "邵斌",
]

SCENE_KEYWORDS = [
    "北京中关村学院 怎么样",
    "中关村学院 值得去吗",
    "中关村学院 博士",
    "中关村学院 博士生",
    "中关村学院 直博",
    "中关村学院 夏令营",
    "中关村学院 招生",
    "中关村学院 宣讲",
    "中关村学院 面试",
    "中关村学院 考核",
    "中关村学院 毕业去向",
    "中关村学院 就业",
    "中关村学院 孵化",
    "中关村学院 创业",
    "中关村学院 融资",
    "中关村学院 对比",
    "中关村学院 vs",
    "中关村学院 不如",
    "中关村学院 野鸡",
    "中关村学院 骗子",
]

RISK_KEYWORDS = [
    "北京中关村学院 避雷",
    "中关村学院 坑",
    "中关村学院 骗",
    "中关村学院 水",
    "中关村学院 垃圾",
    "中关村学院 投诉",
    "中关村学院 举报",
    "中关村学院 维权",
    "中关村学院 内定",
    "中关村学院 不公平",
    "中关村学院 黑幕",
    "中关村学院 退学",
    "中关村学院 劝退",
    "中关村学院 毕业",
    "中关村学院 师资差",
    "中关村学院 导师不负责",
    "中关村学院 招生黑幕",
    "中关村学院 夏令营 不公平",
]

DEFAULT_BUCKETS = ("core", "scene")
SUPPORTED_BUCKETS = ("core", "scene", "risk")
DEFAULT_RELEVANCE_MUST_CONTAIN = [
    "北京中关村学院",
    "中关村学院",
    "中关村人工智能研究院",
    "刘铁岩",
    "邵斌",
]
DEFAULT_RELEVANCE_EXCLUDE: list[str] = []


def dedupe_keywords(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        keyword = " ".join(str(raw or "").split()).strip()
        if not keyword or keyword in seen:
            continue
        seen.add(keyword)
        result.append(keyword)
    return result


def parse_keyword_buckets(raw: str | Iterable[str] | None) -> list[str]:
    if raw is None:
        return list(DEFAULT_BUCKETS)
    if isinstance(raw, str):
        values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    else:
        values = [str(item).strip().lower() for item in raw if str(item).strip()]
    buckets = [item for item in values if item in SUPPORTED_BUCKETS]
    return dedupe_keywords(buckets) or list(DEFAULT_BUCKETS)


def build_keyword_pool(
    *,
    include_core: bool = True,
    include_scene: bool = True,
    include_risk: bool = False,
    extra_keywords: Iterable[str] | None = None,
) -> list[str]:
    keywords: list[str] = []
    if include_core:
        keywords.extend(CORE_ENTITY_KEYWORDS)
    if include_scene:
        keywords.extend(SCENE_KEYWORDS)
    if include_risk:
        keywords.extend(RISK_KEYWORDS)
    if extra_keywords:
        keywords.extend(extra_keywords)
    return dedupe_keywords(keywords)


def split_keywords_into_batches(
    keywords: Iterable[str],
    *,
    parallel_jobs: int,
) -> list[list[str]]:
    deduped = dedupe_keywords(keywords)
    if not deduped:
        return []
    safe_parallel_jobs = max(1, parallel_jobs)
    batch_size = max(1, ceil(len(deduped) / safe_parallel_jobs))
    return [
        deduped[index:index + batch_size]
        for index in range(0, len(deduped), batch_size)
    ]

