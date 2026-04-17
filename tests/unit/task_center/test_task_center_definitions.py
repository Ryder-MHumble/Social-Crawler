from __future__ import annotations

import sys
from pathlib import Path

from api.services.task_center import TaskCenterService


def test_xhs_posts_only_preset_resolves_correctly(tmp_path: Path) -> None:
    service = TaskCenterService(
        project_root=Path(".").resolve(),
        python_executable=sys.executable,
        state_dir=tmp_path / ".task_center",
    )

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

    jobs = preview["spec"]["stages"][0]["jobs"]
    assert len(jobs) == 1
    command = jobs[0]["command"]
    assert "--platform" in command and command[command.index("--platform") + 1] == "xhs"
    assert "--max_notes_count" in command and command[command.index("--max_notes_count") + 1] == "30"
    assert "--get_comment" in command and command[command.index("--get_comment") + 1] == "false"
    assert "--get_sub_comment" in command and command[command.index("--get_sub_comment") + 1] == "false"
