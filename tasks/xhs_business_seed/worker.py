from __future__ import annotations

import argparse
import re
import shutil
from typing import Optional

import config
from database import db
from database.supabase_store_base import SupabaseStoreBase
from media_platform.xhs import XiaoHongShuCrawler
from tools.app_runner import run
from tools import runtime_paths
from tools.utils import str2bool

from .keyword_config import DEFAULT_RELEVANCE_MUST_CONTAIN

crawler: Optional[XiaoHongShuCrawler] = None


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one Xiaohongshu business keyword batch and store into Supabase.",
    )
    parser.add_argument("--keywords", required=True, help="Comma-separated keyword batch.")
    parser.add_argument("--job-label", default="", help="Optional label shown in logs.")
    parser.add_argument("--max-notes-per-keyword", type=int, default=30)
    parser.add_argument("--enable-comments", default="true")
    parser.add_argument("--enable-sub-comments", default="false")
    parser.add_argument("--max-comments-per-note", type=int, default=20)
    parser.add_argument(
        "--login-type",
        choices=["qrcode", "cookie", "phone"],
        default=getattr(config, "LOGIN_TYPE", "qrcode"),
    )
    parser.add_argument("--cookies", default=getattr(config, "COOKIES", ""))
    parser.add_argument("--headless", default=str(getattr(config, "HEADLESS", False)).lower())
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--sleep-sec", type=float, default=float(getattr(config, "CRAWLER_MAX_SLEEP_SEC", 5)))
    parser.add_argument(
        "--save-option",
        choices=["json", "csv", "excel", "sqlite", "db", "mongodb", "supabase"],
        default="supabase",
    )
    parser.add_argument("--enable-ip-proxy", default=str(getattr(config, "ENABLE_IP_PROXY", False)).lower())
    parser.add_argument("--enable-official-accounts", default="false")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument(
        "--profile-mode",
        choices=["shared", "clone"],
        default="shared",
        help="shared: use the base XHS browser profile; clone: copy base profile to an isolated worker profile.",
    )
    parser.add_argument(
        "--profile-key",
        default="",
        help="Worker-specific profile suffix when profile-mode=clone.",
    )
    parser.add_argument(
        "--relevance-must-contain",
        default=",".join(DEFAULT_RELEVANCE_MUST_CONTAIN),
        help="Comma-separated relevance gate terms.",
    )
    parser.add_argument("--relevance-exclude", default="")
    parser.add_argument("--min-content-engagement", type=int, default=int(getattr(config, "MIN_CONTENT_ENGAGEMENT", 0)))
    parser.add_argument("--min-comment-length", type=int, default=int(getattr(config, "MIN_COMMENT_LENGTH", 5)))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_-]+", "_", value or "").strip("_")
    return normalized or "worker"


def _remove_profile_lock_files(profile_dir) -> None:
    for pattern in ("Singleton*", "LOCK", "lockfile"):
        for path in profile_dir.glob(pattern):
            if path.is_file():
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass


def prepare_browser_profile(args: argparse.Namespace) -> None:
    runtime_paths.ensure_runtime_layout()
    base_pattern = getattr(config, "USER_DATA_DIR", "%s_user_data_dir")
    shared_profile_dir = runtime_paths.get_browser_user_data_dir("xhs", base_pattern)

    if args.profile_mode != "clone":
        return

    profile_key = _slugify(args.profile_key or args.job_label or "worker")
    cloned_pattern = f"xhs_business_seed_{profile_key}_%s_user_data_dir"
    cloned_profile_dir = runtime_paths.get_browser_user_data_dir("xhs", cloned_pattern)

    if cloned_profile_dir.exists():
        shutil.rmtree(cloned_profile_dir)

    if shared_profile_dir.exists():
        ignore = shutil.ignore_patterns(
            "Singleton*",
            "LOCK",
            "lockfile",
            "chrome_debug.log",
            "CrashpadMetrics-active.pma",
        )
        shutil.copytree(shared_profile_dir, cloned_profile_dir, ignore=ignore)
        _remove_profile_lock_files(cloned_profile_dir)

    config.USER_DATA_DIR = cloned_pattern


def configure_runtime(args: argparse.Namespace) -> list[str]:
    keywords = _split_csv(args.keywords)
    if not keywords:
        raise ValueError("At least one keyword is required.")

    config.PLATFORM = "xhs"
    config.CRAWLER_TYPE = "search"
    config.KEYWORDS = ",".join(keywords)
    config.LOGIN_TYPE = args.login_type
    config.COOKIES = args.cookies
    config.START_PAGE = max(1, args.start_page)
    config.SAVE_DATA_OPTION = args.save_option
    config.CRAWLER_MAX_NOTES_COUNT = max(1, args.max_notes_per_keyword)
    config.ENABLE_GET_COMMENTS = str2bool(args.enable_comments)
    config.ENABLE_GET_SUB_COMMENTS = str2bool(args.enable_sub_comments)
    if not config.ENABLE_GET_COMMENTS:
        config.ENABLE_GET_SUB_COMMENTS = False
    config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = max(1, args.max_comments_per_note)
    config.HEADLESS = str2bool(args.headless)
    config.CDP_HEADLESS = config.HEADLESS
    config.MAX_CONCURRENCY_NUM = max(1, args.max_concurrency)
    config.CRAWLER_MAX_SLEEP_SEC = max(0.0, args.sleep_sec)
    config.ENABLE_IP_PROXY = str2bool(args.enable_ip_proxy)
    config.ENABLE_OFFICIAL_ACCOUNTS_CRAWL = str2bool(args.enable_official_accounts)
    config.ENABLE_GET_MEIDAS = False
    config.ENABLE_RELEVANCE_FILTER = True
    config.RELEVANCE_MUST_CONTAIN = _split_csv(args.relevance_must_contain)
    config.RELEVANCE_EXCLUDE_KEYWORDS = _split_csv(args.relevance_exclude)
    config.MIN_CONTENT_ENGAGEMENT = max(0, args.min_content_engagement)
    config.MIN_COMMENT_LENGTH = max(0, args.min_comment_length)
    prepare_browser_profile(args)
    return keywords


def print_runtime_plan(args: argparse.Namespace, keywords: list[str]) -> None:
    print("=" * 80)
    print("[XHS Business Seed Batch]")
    print("=" * 80)
    print(f"Job label               : {args.job_label or '-'}")
    print(f"Keywords ({len(keywords)})          : {', '.join(keywords)}")
    print(f"Save option             : {args.save_option}")
    print(f"Login type              : {args.login_type}")
    print(f"Headless                : {config.HEADLESS}")
    print(f"Comments enabled        : {config.ENABLE_GET_COMMENTS}")
    print(f"Sub-comments enabled    : {config.ENABLE_GET_SUB_COMMENTS}")
    print(f"Max notes / keyword     : {config.CRAWLER_MAX_NOTES_COUNT}")
    print(f"Max comments / note     : {config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES}")
    print(f"Per-process concurrency : {config.MAX_CONCURRENCY_NUM}")
    print(f"Sleep seconds           : {config.CRAWLER_MAX_SLEEP_SEC}")
    print(f"Profile mode            : {args.profile_mode}")
    print(f"Profile key             : {args.profile_key or '-'}")
    print(f"Relevance gate          : {', '.join(config.RELEVANCE_MUST_CONTAIN) or '-'}")
    print("=" * 80)


async def _run_batch() -> None:
    global crawler
    crawler = XiaoHongShuCrawler()
    await crawler.start()
    if config.SAVE_DATA_OPTION == "supabase":
        SupabaseStoreBase.print_session_summary("xhs")


async def _cleanup() -> None:
    global crawler
    if crawler:
        if getattr(crawler, "cdp_manager", None):
            try:
                await crawler.cdp_manager.cleanup(force=True)
            except Exception as exc:
                error_message = str(exc).lower()
                if "closed" not in error_message and "disconnected" not in error_message:
                    print(f"[XHS Batch] Error cleaning CDP browser: {exc}")
        elif getattr(crawler, "browser_context", None):
            try:
                await crawler.browser_context.close()
            except Exception as exc:
                error_message = str(exc).lower()
                if "closed" not in error_message and "disconnected" not in error_message:
                    print(f"[XHS Batch] Error closing browser context: {exc}")

    if config.SAVE_DATA_OPTION in ("db", "sqlite"):
        await db.close()


def _force_stop() -> None:
    current_crawler = crawler
    if not current_crawler:
        return
    cdp_manager = getattr(current_crawler, "cdp_manager", None)
    launcher = getattr(cdp_manager, "launcher", None)
    if not launcher:
        return
    try:
        launcher.cleanup()
    except Exception:
        pass


def main() -> None:
    args = parse_args()
    keywords = configure_runtime(args)
    print_runtime_plan(args, keywords)
    if args.dry_run:
        return
    run(_run_batch, _cleanup, cleanup_timeout_seconds=15.0, on_first_interrupt=_force_stop)


if __name__ == "__main__":
    main()
