from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from apps.crawler.run_business_seed_platforms import (
    build_keywords,
    build_launch_jobs,
    materialize_browser_data_root,
    order_job_slices,
)
from tasks.common.crawl_planner import plan_platform_value_jobs


def _build_args(**overrides) -> SimpleNamespace:
    params = {
        "keyword_job_mode": "single",
        "keyword_job_chunk_size": 2,
        "max_parallel": 6,
        "max_notes_per_keyword": 30,
        "save_option": "supabase",
        "login_type": "qrcode",
        "headless": "false",
        "per_process_concurrency": 1,
        "clone_shared_profile": "true",
    }
    params.update(overrides)
    return SimpleNamespace(**params)


def test_order_job_slices_round_robins_platforms() -> None:
    slices, _ = plan_platform_value_jobs(
        ["xhs", "dy", "bili"],
        ["alpha", "beta", "gamma"],
        split_mode="single",
        chunk_size=1,
        max_parallel=6,
    )

    ordered = order_job_slices(slices, ["xhs", "dy", "bili"])

    assert [(item.platform, item.values[0]) for item in ordered[:6]] == [
        ("xhs", "alpha"),
        ("dy", "alpha"),
        ("bili", "alpha"),
        ("xhs", "beta"),
        ("dy", "beta"),
        ("bili", "beta"),
    ]


def test_build_keywords_supports_override_and_limit() -> None:
    assert build_keywords(
        include_risk_keywords=False,
        explicit_keywords="alpha,beta,gamma",
        keyword_limit=2,
    ) == ["alpha", "beta"]


def test_build_launch_jobs_clones_shared_profiles(tmp_path: Path, monkeypatch) -> None:
    browser_data_root = tmp_path / "browser_data"
    monkeypatch.setenv("SOCIAL_CRAWLER_BROWSER_DATA_DIR", str(browser_data_root))

    for platform in ("xhs", "dy"):
        shared_profile = browser_data_root / f"{platform}_user_data_dir"
        shared_profile.mkdir(parents=True, exist_ok=True)
        (shared_profile / "Cookies").write_text("ok", encoding="utf-8")
        (shared_profile / "SingletonLock").write_text("lock", encoding="utf-8")

    jobs, stage_max_parallel = build_launch_jobs(
        python_executable="python",
        run_dir=tmp_path / "run",
        platforms=["xhs", "dy"],
        keywords=["alpha", "beta", "gamma", "delta"],
        args=_build_args(keyword_job_mode="chunked", keyword_job_chunk_size=2, max_parallel=4),
    )

    assert stage_max_parallel == 4
    assert len(jobs) == 4

    xhs_jobs = [job for job in jobs if job.platform == "xhs"]
    assert xhs_jobs

    materialize_browser_data_root(xhs_jobs[0])
    cloned_profile = xhs_jobs[0].browser_data_root / "xhs_user_data_dir"
    assert cloned_profile.exists()
    assert (cloned_profile / "Cookies").exists()
    assert not any(cloned_profile.glob("Singleton*"))
