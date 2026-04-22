#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from tasks.common.crawl_planner import CrawlJobSlice, plan_platform_value_jobs
from tasks.xhs_business_seed.keyword_config import build_keyword_pool
from tools import runtime_paths
from tools.utils import str2bool

SUPPORTED_PLATFORMS = ("xhs", "dy", "bili")
PLATFORM_LABELS = {
    "xhs": "Xiaohongshu",
    "dy": "Douyin",
    "bili": "Bilibili",
}
PROFILE_LOCK_PATTERNS = (
    "Singleton*",
    "LOCK",
    "lockfile",
    ".org.chromium.Chromium.*",
    "chrome_debug.log",
    "CrashpadMetrics-active.pma",
)


@dataclass
class LaunchJob:
    key: str
    platform: str
    keywords: list[str]
    group_index: int
    group_total: int
    command: list[str]
    stdout_path: Path
    stderr_path: Path
    browser_data_root: Path
    clone_shared_profile: bool
    shared_profile_exists: bool
    process: subprocess.Popen[bytes] | None = None
    pid: int | None = None
    status: str = "pending"
    returncode: int | None = None
    started_at: float | None = None
    finished_at: float | None = None

    def to_manifest(self) -> dict[str, object]:
        return {
            "key": self.key,
            "platform": self.platform,
            "platform_label": PLATFORM_LABELS.get(self.platform, self.platform),
            "keywords": list(self.keywords),
            "group_index": self.group_index,
            "group_total": self.group_total,
            "command": list(self.command),
            "stdout": str(self.stdout_path),
            "stderr": str(self.stderr_path),
            "browser_data_root": str(self.browser_data_root),
            "shared_profile_exists": self.shared_profile_exists,
            "pid": self.pid,
            "status": self.status,
            "returncode": self.returncode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run business-seed crawling across Xiaohongshu, Douyin, and Bilibili "
            "with platform-level and keyword-batch concurrency."
        ),
    )
    parser.add_argument(
        "--platforms",
        default="xhs,dy,bili",
        help="Comma-separated platforms. Supported: xhs, dy, bili.",
    )
    parser.add_argument(
        "--max-notes-per-keyword",
        type=int,
        default=30,
        help="Maximum number of posts/videos to fetch per keyword on each platform.",
    )
    parser.add_argument(
        "--save-option",
        default="supabase",
        help="Storage backend passed to main.py, default is supabase.",
    )
    parser.add_argument(
        "--login-type",
        default="qrcode",
        choices=["qrcode", "cookie", "phone"],
        help="Login type for each platform.",
    )
    parser.add_argument(
        "--headless",
        default="false",
        choices=["true", "false"],
        help="Whether to run browsers in headless mode.",
    )
    parser.add_argument(
        "--include-risk-keywords",
        action="store_true",
        help="Include the risk keyword bucket in addition to core + scene terms.",
    )
    parser.add_argument(
        "--keywords",
        default="",
        help="Optional explicit comma-separated keywords. When set, this overrides the built-in keyword pool.",
    )
    parser.add_argument(
        "--keyword-limit",
        type=int,
        default=0,
        help="Optional limit applied after keyword resolution. 0 means no limit.",
    )
    parser.add_argument(
        "--keyword-job-mode",
        default="chunked",
        choices=["auto", "bundle", "single", "chunked"],
        help="How to split keywords into jobs before multiplying by platform.",
    )
    parser.add_argument(
        "--keyword-job-chunk-size",
        type=int,
        default=3,
        help="Keywords per job when --keyword-job-mode=chunked.",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=6,
        help="Maximum number of platform-keyword jobs to run at the same time.",
    )
    parser.add_argument(
        "--per-process-concurrency",
        type=int,
        default=1,
        help="Value passed to main.py --max_concurrency_num inside each subprocess.",
    )
    parser.add_argument(
        "--clone-shared-profile",
        default="true",
        choices=["true", "false"],
        help="Clone the shared platform browser profile into an isolated job profile.",
    )
    parser.add_argument(
        "--launch-delay-sec",
        type=float,
        default=1.0,
        help="Delay between launching jobs to reduce simultaneous browser contention.",
    )
    parser.add_argument(
        "--poll-interval-sec",
        type=float,
        default=2.0,
        help="Polling interval used while waiting for running jobs to finish.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved execution plan without launching jobs.",
    )
    return parser.parse_args()


def normalize_platforms(raw: str) -> list[str]:
    platforms = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not platforms:
        return list(SUPPORTED_PLATFORMS)
    invalid = [item for item in platforms if item not in SUPPORTED_PLATFORMS]
    if invalid:
        raise ValueError(f"Unsupported platforms: {', '.join(invalid)}")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in platforms:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def split_csv(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def build_keywords(
    *,
    include_risk_keywords: bool,
    explicit_keywords: str = "",
    keyword_limit: int = 0,
) -> list[str]:
    keywords = split_csv(explicit_keywords) or build_keyword_pool(
        include_core=True,
        include_scene=True,
        include_risk=include_risk_keywords,
    )
    if keyword_limit > 0:
        keywords = keywords[:keyword_limit]
    return keywords


def make_run_dir() -> Path:
    runtime_paths.ensure_runtime_layout()
    root = runtime_paths.get_logs_dir() / "manual_runs"
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = root / f"business_seed_multi_platform_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def slugify(value: str) -> str:
    result = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in (value or ""))
    result = result.strip("_")
    return result or "job"


def order_job_slices(slices: list[CrawlJobSlice], platforms: list[str]) -> list[CrawlJobSlice]:
    platform_rank = {platform: index for index, platform in enumerate(platforms)}
    return sorted(
        slices,
        key=lambda item: (
            item.group_index,
            platform_rank.get(item.platform, len(platform_rank)),
            item.values[0].lower() if item.values else "",
        ),
    )


def build_command(
    *,
    python_executable: str,
    platform: str,
    keywords_csv: str,
    max_notes_per_keyword: int,
    save_option: str,
    login_type: str,
    headless: str,
    per_process_concurrency: int,
) -> list[str]:
    return [
        python_executable,
        "-X",
        "utf8",
        "-u",
        "main.py",
        "--platform",
        platform,
        "--lt",
        login_type,
        "--type",
        "search",
        "--keywords",
        keywords_csv,
        "--save_data_option",
        save_option,
        "--max_notes_count",
        str(max_notes_per_keyword),
        "--get_comment",
        "false",
        "--get_sub_comment",
        "false",
        "--max_comments_count_singlenotes",
        "1",
        "--max_concurrency_num",
        str(max(1, per_process_concurrency)),
        "--headless",
        headless,
    ]


def get_shared_profile_dir(platform: str) -> Path:
    return runtime_paths.get_browser_user_data_dir(
        platform,
        getattr(config, "USER_DATA_DIR", "%s_user_data_dir"),
    )


def remove_profile_lock_files(profile_dir: Path) -> None:
    for pattern in PROFILE_LOCK_PATTERNS:
        for path in profile_dir.glob(pattern):
            if path.is_file():
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass


def get_job_browser_data_root(*, run_dir: Path, job_key: str) -> Path:
    base_root = runtime_paths.get_browser_data_dir()
    return base_root / "business_seed_jobs" / run_dir.name / job_key


def materialize_browser_data_root(job: LaunchJob) -> None:
    job_root = job.browser_data_root
    if job_root.exists():
        shutil.rmtree(job_root)
    job_root.mkdir(parents=True, exist_ok=True)

    shared_profile_dir = get_shared_profile_dir(job.platform)
    if not job.clone_shared_profile or not shared_profile_dir.exists():
        return

    target_profile_dir = job_root / shared_profile_dir.name
    ignore = shutil.ignore_patterns(*PROFILE_LOCK_PATTERNS)
    shutil.copytree(shared_profile_dir, target_profile_dir, ignore=ignore)
    remove_profile_lock_files(target_profile_dir)


def inspect_shared_profile(platform: str) -> bool:
    shared_profile_dir = get_shared_profile_dir(platform)
    return shared_profile_dir.exists()


def build_launch_jobs(
    *,
    python_executable: str,
    run_dir: Path,
    platforms: list[str],
    keywords: list[str],
    args: argparse.Namespace,
) -> tuple[list[LaunchJob], int]:
    slices, stage_max_parallel = plan_platform_value_jobs(
        platforms,
        keywords,
        split_mode=args.keyword_job_mode,
        chunk_size=max(1, args.keyword_job_chunk_size),
        max_parallel=max(1, args.max_parallel),
    )
    ordered_slices = order_job_slices(slices, platforms)
    clone_shared_profile = str2bool(args.clone_shared_profile)
    jobs: list[LaunchJob] = []
    for slice_item in ordered_slices:
        first_keyword = slice_item.values[0] if slice_item.values else slice_item.platform
        job_key = (
            f"{slice_item.platform}_g{slice_item.group_index:02d}"
            f"_of_{slice_item.group_total:02d}_{slugify(first_keyword)[:24]}"
        )
        browser_data_root = get_job_browser_data_root(run_dir=run_dir, job_key=job_key)
        shared_profile_exists = inspect_shared_profile(slice_item.platform)
        command = build_command(
            python_executable=python_executable,
            platform=slice_item.platform,
            keywords_csv=",".join(slice_item.values),
            max_notes_per_keyword=args.max_notes_per_keyword,
            save_option=args.save_option,
            login_type=args.login_type,
            headless=args.headless,
            per_process_concurrency=args.per_process_concurrency,
        )
        jobs.append(
            LaunchJob(
                key=job_key,
                platform=slice_item.platform,
                keywords=list(slice_item.values),
                group_index=slice_item.group_index,
                group_total=slice_item.group_total,
                command=command,
                stdout_path=run_dir / f"{job_key}.stdout.log",
                stderr_path=run_dir / f"{job_key}.stderr.log",
                browser_data_root=browser_data_root,
                clone_shared_profile=clone_shared_profile,
                shared_profile_exists=shared_profile_exists,
            )
        )
    return jobs, max(1, stage_max_parallel or 1)


def write_manifest(
    run_dir: Path,
    *,
    args: argparse.Namespace,
    platforms: list[str],
    keywords: list[str],
    max_parallel: int,
    jobs: list[LaunchJob],
) -> None:
    payload = {
        "run_dir": str(run_dir),
        "platforms": platforms,
        "keyword_count": len(keywords),
        "keywords": keywords,
        "split_mode": args.keyword_job_mode,
        "keyword_job_chunk_size": args.keyword_job_chunk_size,
        "max_parallel": max_parallel,
        "per_process_concurrency": args.per_process_concurrency,
        "clone_shared_profile": str2bool(args.clone_shared_profile),
        "jobs": [job.to_manifest() for job in jobs],
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def print_plan(
    *,
    run_dir: Path,
    platforms: list[str],
    keywords: list[str],
    jobs: list[LaunchJob],
    max_parallel: int,
    args: argparse.Namespace,
) -> None:
    jobs_per_platform = Counter(job.platform for job in jobs)
    print("=" * 96)
    print("Business Seed Multi-Platform Crawl")
    print("=" * 96)
    print(f"Platforms               : {', '.join(PLATFORM_LABELS[p] for p in platforms)}")
    print(f"Keyword count           : {len(keywords)}")
    print(f"Keyword split mode      : {args.keyword_job_mode}")
    print(f"Keyword chunk size      : {args.keyword_job_chunk_size}")
    print(f"Planned jobs            : {len(jobs)}")
    print(f"Stage max parallel      : {max_parallel}")
    print(f"Per-process concurrency : {max(1, args.per_process_concurrency)}")
    print(f"Max notes / keyword     : {args.max_notes_per_keyword}")
    print("Comments                : disabled")
    print(f"Save option             : {args.save_option}")
    print(f"Login type              : {args.login_type}")
    print(f"Headless                : {args.headless}")
    print(f"Clone shared profile    : {str2bool(args.clone_shared_profile)}")
    print(f"Run dir                 : {run_dir}")
    print("=" * 96)
    for platform in platforms:
        print(
            f"[plan] {PLATFORM_LABELS[platform]:<12} "
            f"jobs={jobs_per_platform.get(platform, 0)}"
        )
    missing_profile_platforms = [
        PLATFORM_LABELS.get(platform, platform)
        for platform in platforms
        if any(job.platform == platform and not job.shared_profile_exists for job in jobs)
    ]
    if missing_profile_platforms:
        print(
            "[warn] Shared browser profile not found for: "
            + ", ".join(missing_profile_platforms)
            + ". These jobs will start with empty browser data roots."
        )
    print("=" * 96)


def launch_job(job: LaunchJob) -> None:
    materialize_browser_data_root(job)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["SOCIAL_CRAWLER_BROWSER_DATA_DIR"] = str(job.browser_data_root)
    stdout_handle = job.stdout_path.open("wb")
    stderr_handle = job.stderr_path.open("wb")
    try:
        process = subprocess.Popen(
            job.command,
            cwd=PROJECT_ROOT,
            stdout=stdout_handle,
            stderr=stderr_handle,
            env=env,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()
    job.process = process
    job.pid = process.pid
    job.started_at = time.time()
    job.status = "running"


def terminate_running_jobs(jobs: list[LaunchJob]) -> None:
    for job in jobs:
        process = job.process
        if not process or process.poll() is not None:
            continue
        try:
            process.terminate()
        except Exception:
            pass


def run_jobs(
    *,
    jobs: list[LaunchJob],
    max_parallel: int,
    launch_delay_sec: float,
    poll_interval_sec: float,
    run_dir: Path,
    args: argparse.Namespace,
    platforms: list[str],
    keywords: list[str],
) -> int:
    pending: deque[LaunchJob] = deque(jobs)
    running: list[LaunchJob] = []
    completed: list[LaunchJob] = []

    try:
        while pending or running:
            while pending and len(running) < max_parallel:
                job = pending.popleft()
                launch_job(job)
                running.append(job)
                print(
                    f"[launch] {job.key} pid={job.pid} "
                    f"platform={job.platform} keywords={','.join(job.keywords)}"
                )
                write_manifest(
                    run_dir,
                    args=args,
                    platforms=platforms,
                    keywords=keywords,
                    max_parallel=max_parallel,
                    jobs=jobs,
                )
                if launch_delay_sec > 0:
                    time.sleep(launch_delay_sec)

            still_running: list[LaunchJob] = []
            for job in running:
                process = job.process
                if not process:
                    continue
                returncode = process.poll()
                if returncode is None:
                    still_running.append(job)
                    continue
                job.returncode = returncode
                job.finished_at = time.time()
                job.status = "success" if returncode == 0 else "failed"
                completed.append(job)
                print(
                    f"[finish] {job.key} status={job.status} returncode={returncode} "
                    f"stdout={job.stdout_path.name} stderr={job.stderr_path.name}"
                )
                write_manifest(
                    run_dir,
                    args=args,
                    platforms=platforms,
                    keywords=keywords,
                    max_parallel=max_parallel,
                    jobs=jobs,
                )
            running = still_running

            if running:
                time.sleep(max(0.5, poll_interval_sec))
    except KeyboardInterrupt:
        print("[interrupt] Stopping running jobs...")
        terminate_running_jobs(running)
        for job in running:
            job.status = "stopped"
            job.finished_at = time.time()
        write_manifest(
            run_dir,
            args=args,
            platforms=platforms,
            keywords=keywords,
            max_parallel=max_parallel,
            jobs=jobs,
        )
        return 130

    failed_jobs = [job for job in completed if job.returncode not in (0, None)]
    print("=" * 96)
    print("Execution summary")
    print("=" * 96)
    print(f"Completed jobs          : {len(completed)} / {len(jobs)}")
    print(f"Successful jobs         : {len(completed) - len(failed_jobs)}")
    print(f"Failed jobs             : {len(failed_jobs)}")
    if failed_jobs:
        for job in failed_jobs:
            print(f"[failed] {job.key} rc={job.returncode} stderr={job.stderr_path.name}")
    print("=" * 96)
    return 0 if not failed_jobs else 1


def main() -> int:
    args = parse_args()
    platforms = normalize_platforms(args.platforms)
    if args.max_notes_per_keyword < 1:
        raise ValueError("--max-notes-per-keyword must be greater than 0.")
    if args.per_process_concurrency < 1:
        raise ValueError("--per-process-concurrency must be greater than 0.")
    if args.max_parallel < 1:
        raise ValueError("--max-parallel must be greater than 0.")

    keywords = build_keywords(
        include_risk_keywords=args.include_risk_keywords,
        explicit_keywords=args.keywords,
        keyword_limit=args.keyword_limit,
    )
    if not keywords:
        raise ValueError("No keywords were generated from the configured business seed pool.")

    run_dir = make_run_dir()
    jobs, stage_max_parallel = build_launch_jobs(
        python_executable=sys.executable,
        run_dir=run_dir,
        platforms=platforms,
        keywords=keywords,
        args=args,
    )
    if not jobs:
        raise ValueError("No launch jobs were generated.")

    write_manifest(
        run_dir,
        args=args,
        platforms=platforms,
        keywords=keywords,
        max_parallel=stage_max_parallel,
        jobs=jobs,
    )
    print_plan(
        run_dir=run_dir,
        platforms=platforms,
        keywords=keywords,
        jobs=jobs,
        max_parallel=stage_max_parallel,
        args=args,
    )

    if args.dry_run:
        for job in jobs:
            print(f"[dry-run] {job.key}: {' '.join(job.command)}")
            print(f"          browser_data_root={job.browser_data_root}")
        return 0

    return run_jobs(
        jobs=jobs,
        max_parallel=stage_max_parallel,
        launch_delay_sec=max(0.0, args.launch_delay_sec),
        poll_interval_sec=max(0.5, args.poll_interval_sec),
        run_dir=run_dir,
        args=args,
        platforms=platforms,
        keywords=keywords,
    )


if __name__ == "__main__":
    raise SystemExit(main())
