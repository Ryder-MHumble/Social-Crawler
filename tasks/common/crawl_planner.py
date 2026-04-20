from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

ALLOWED_SPLIT_MODES = {"auto", "bundle", "single", "chunked"}


@dataclass(frozen=True)
class CrawlJobSlice:
    platform: str
    values: tuple[str, ...]
    group_index: int
    group_total: int

    @property
    def csv_value(self) -> str:
        return ",".join(self.values)


def normalize_split_mode(value: Any, default: str = "auto") -> str:
    candidate = str(value).strip().lower() if value is not None else default
    return candidate if candidate in ALLOWED_SPLIT_MODES else default


def normalize_chunk_size(value: Any, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return max(1, default)
    return max(1, parsed)


def normalize_parallel_limit(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return max(0, default)
    return max(0, parsed)


def resolve_parallel_limit(
    *,
    platform_count: int,
    value_count: int,
    requested_parallel: int,
) -> int:
    if platform_count <= 0 or value_count <= 0:
        return 0

    total_jobs = platform_count * value_count
    if requested_parallel > 0:
        return min(requested_parallel, total_jobs)

    if value_count <= 1:
        return platform_count
    if platform_count <= 1:
        return min(2, value_count)
    return platform_count


def _chunk_values(values: Sequence[str], chunk_size: int) -> list[tuple[str, ...]]:
    return [
        tuple(values[index : index + chunk_size])
        for index in range(0, len(values), chunk_size)
    ]


def _resolve_groups(
    values: Sequence[str],
    *,
    split_mode: str,
    chunk_size: int,
    per_platform_parallel: int,
) -> list[tuple[str, ...]]:
    if not values:
        return []

    normalized_mode = normalize_split_mode(split_mode)
    if normalized_mode == "bundle":
        return [tuple(values)]
    if normalized_mode == "single":
        return [(value,) for value in values]
    if normalized_mode == "chunked":
        return _chunk_values(values, normalize_chunk_size(chunk_size))

    if len(values) == 1 or per_platform_parallel <= 1:
        return [tuple(values)]

    auto_chunk_size = max(1, math.ceil(len(values) / per_platform_parallel))
    return _chunk_values(values, auto_chunk_size)


def plan_platform_value_jobs(
    platforms: Sequence[str],
    values: Sequence[str],
    *,
    split_mode: str = "auto",
    chunk_size: int = 1,
    max_parallel: int = 0,
) -> tuple[list[CrawlJobSlice], int]:
    normalized_platforms = [str(platform).strip() for platform in platforms if str(platform).strip()]
    normalized_values = [str(value).strip() for value in values if str(value).strip()]
    if not normalized_platforms or not normalized_values:
        return [], 0

    resolved_parallel = resolve_parallel_limit(
        platform_count=len(normalized_platforms),
        value_count=len(normalized_values),
        requested_parallel=normalize_parallel_limit(max_parallel),
    )
    per_platform_parallel = max(1, resolved_parallel // len(normalized_platforms))
    groups = _resolve_groups(
        normalized_values,
        split_mode=split_mode,
        chunk_size=chunk_size,
        per_platform_parallel=per_platform_parallel,
    )
    if not groups:
        return [], 0

    jobs: list[CrawlJobSlice] = []
    for platform in normalized_platforms:
        for group_index, group in enumerate(groups, start=1):
            jobs.append(
                CrawlJobSlice(
                    platform=platform,
                    values=group,
                    group_index=group_index,
                    group_total=len(groups),
                )
            )

    return jobs, min(max(1, resolved_parallel), len(jobs))
