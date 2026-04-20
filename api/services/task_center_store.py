from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class TaskCenterFileStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.presets_path = self.root_dir / "presets.json"
        self.runs_path = self.root_dir / "runs.json"
        self._lock = threading.Lock()

    def load_presets(self) -> list[dict[str, Any]]:
        return self._load_json_list(self.presets_path)

    def save_presets(self, presets: list[dict[str, Any]]) -> None:
        self._write_json_list(self.presets_path, presets)

    def ensure_seed_presets(self, seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._lock:
            seed_ids = {seed["id"] for seed in seeds}
            original_presets = self._load_json_list(self.presets_path)
            presets = [
                preset
                for preset in original_presets
                if not (preset.get("is_seed") is True and preset.get("id") not in seed_ids)
            ]
            existing_ids = {preset["id"] for preset in presets}
            changed = len(presets) != len(original_presets)
            for seed in seeds:
                if seed["id"] not in existing_ids:
                    presets.append(seed)
                    changed = True
            if changed or not self.presets_path.exists():
                self._write_json_list(self.presets_path, presets)
            return presets

    def load_runs(self) -> list[dict[str, Any]]:
        return self._load_json_list(self.runs_path)

    def upsert_run(self, run: dict[str, Any]) -> None:
        with self._lock:
            runs = self._load_json_list(self.runs_path)
            updated = False
            for index, current in enumerate(runs):
                if current.get("id") == run.get("id"):
                    runs[index] = run
                    updated = True
                    break
            if not updated:
                runs.append(run)
            runs.sort(key=lambda item: item.get("started_at") or "", reverse=True)
            self._write_json_list(self.runs_path, runs)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        for run in self.load_runs():
            if run.get("id") == run_id:
                return run
        return None

    def _load_json_list(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data if isinstance(data, list) else []

    def _write_json_list(self, path: Path, items: list[dict[str, Any]]) -> None:
        path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
