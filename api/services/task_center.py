from __future__ import annotations

import subprocess
import sys
from dataclasses import asdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from tasks.common.template import PresetSeed, TaskDefinition, TaskField, TaskFieldOption
from tasks.runner.registry import load_task_definitions
from tools import runtime_paths

from tasks.common.runtime import RunSetupError

from .browsermint_integration import (
    BrowsermintIntegrationClient,
    BrowsermintProbeFailed,
    BrowsermintUserActionRequired,
    probe_browsermint_login,
)
from .task_center_store import TaskCenterFileStore
from .task_run_manager import TaskRunManager

_PARAM_ALIAS_GROUPS = (
    ("keywords", ("search_keywords",)),
    ("max_notes_count", ("top_posts_count", "max_notes_per_keyword")),
    ("max_comments_count_singlenotes", ("top_comments_count",)),
    ("specified_account_ids", ("creator_ids",)),
)


def _serialize_option(option: TaskFieldOption) -> dict[str, Any]:
    return {
        "value": option.value,
        "label": option.label,
        "description": option.description,
    }


def _serialize_field(field: TaskField) -> dict[str, Any]:
    return {
        "key": field.key,
        "component": field.component,
        "label": field.label,
        "default": field.default,
        "description": field.description,
        "group": field.group,
        "required": field.required,
        "options": [_serialize_option(option) for option in field.options],
        "placeholder": field.placeholder,
        "rows": field.rows,
        "layout": field.layout,
        "helper_text": field.helper_text,
        "badge": field.badge,
        "visible_when": field.visible_when,
        "disabled_when": field.disabled_when,
        "validation": field.validation,
    }


def _serialize_template(definition: TaskDefinition) -> dict[str, Any]:
    template = definition.template
    return {
        "slug": template.slug,
        "title": template.title,
        "description": template.description,
        "defaults": template.defaults,
        "capabilities": template.capabilities,
        "fields": [_serialize_field(field) for field in template.fields],
    }


def _serialize_task_spec(task_spec) -> dict[str, Any]:
    return {
        "slug": task_spec.slug,
        "title": task_spec.title,
        "stages": [
            {
                "key": stage.key,
                "name": stage.name,
                "concurrent": stage.concurrent,
                "max_parallel": stage.max_parallel,
                "abort_on_failure": stage.abort_on_failure,
                "jobs": [
                    {
                        "key": job.key,
                        "name": job.name,
                        "cwd": str(job.cwd),
                        "command": list(job.command),
                        "display_command": subprocess.list2cmdline(job.command),
                        "metadata": dict(job.metadata or {}),
                    }
                    for job in stage.jobs
                ],
            }
            for stage in task_spec.stages
        ],
    }


def _task_runtime_metadata(task_spec, normalized_params: dict[str, Any]) -> dict[str, Any]:
    effective_save_option = str(
        task_spec.metadata.get("effective_save_option")
        or normalized_params.get("save_option")
        or ""
    )
    runtime_storage_backend = str(
        task_spec.metadata.get("runtime_storage_backend")
        or effective_save_option
    )
    return {
        "effective_plan": dict(task_spec.metadata.get("effective_plan") or {}),
        "plan_warnings": [dict(item) for item in task_spec.metadata.get("plan_warnings") or []],
        "warnings": [dict(item) for item in task_spec.metadata.get("warnings") or []],
        "effective_save_option": effective_save_option,
        "runtime_storage_backend": runtime_storage_backend,
    }


class TaskCenterService:
    def __init__(
        self,
        *,
        project_root: Path,
        python_executable: str,
        definitions: list[TaskDefinition] | None = None,
        state_dir: Path | None = None,
    ) -> None:
        self.project_root = project_root
        self.python_executable = python_executable
        definition_list = definitions or load_task_definitions()
        self.definitions = {
            definition.template.slug: definition for definition in definition_list
        }
        self.seed_preset_ids = {
            seed.id
            for definition in definition_list
            for seed in definition.preset_seeds
        }
        runtime_paths.ensure_runtime_layout()
        self.store = TaskCenterFileStore(state_dir or runtime_paths.get_task_center_state_dir())
        self.run_manager = TaskRunManager(project_root=project_root, store=self.store)
        self.browsermint_client = BrowsermintIntegrationClient()
        self._ensure_seed_presets()

    def list_templates(self) -> list[dict[str, Any]]:
        return [_serialize_template(definition) for definition in self.definitions.values()]

    def get_template(self, slug: str) -> dict[str, Any]:
        definition = self._get_definition(slug)
        return _serialize_template(definition)

    def preview_task(
        self,
        slug: str,
        *,
        params: dict[str, Any] | None = None,
        preset_id: str | None = None,
    ) -> dict[str, Any]:
        definition = self._get_definition(slug)
        normalized = self._merge_and_normalize(definition, params=params, preset_id=preset_id)
        task_spec = definition.build_task_spec(
            self.project_root,
            self.python_executable,
            normalized,
        )
        runtime_meta = _task_runtime_metadata(task_spec, normalized)
        return {
            "task": _serialize_template(definition),
            "normalized_params": normalized,
            "spec": _serialize_task_spec(task_spec),
            "effective_plan": runtime_meta["effective_plan"],
            "plan_warnings": runtime_meta["plan_warnings"],
            "effective_save_option": runtime_meta["effective_save_option"],
            "runtime_storage_backend": runtime_meta["runtime_storage_backend"],
        }

    def list_presets(self, task_slug: str | None = None) -> list[dict[str, Any]]:
        presets = self.store.load_presets()
        if task_slug:
            presets = [preset for preset in presets if preset.get("task_slug") == task_slug]
        presets.sort(
            key=lambda preset: (not preset.get("is_default", False), preset.get("updated_at", "")),
        )
        return presets

    def list_browsermint_sessions(self) -> dict[str, Any]:
        if not self.browsermint_client.configured:
            return {
                "configured": False,
                "sessions": [],
            }
        sessions = self.browsermint_client.list_sessions()
        return {
            "configured": True,
            "sessions": [asdict(session) for session in sessions],
        }

    def create_preset(
        self,
        *,
        task_slug: str,
        name: str,
        params: dict[str, Any],
        is_default: bool = False,
    ) -> dict[str, Any]:
        definition = self._get_definition(task_slug)
        normalized = definition.normalize_params(params)
        presets = self.store.load_presets()
        preset = {
            "id": f"preset_{task_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            "task_slug": task_slug,
            "name": name.strip() or f"{definition.template.title} 预设",
            "params": normalized,
            "is_default": is_default,
            "updated_at": datetime.now().isoformat(),
        }
        if is_default:
            for current in presets:
                if current.get("task_slug") == task_slug:
                    current["is_default"] = False
        presets.append(preset)
        self.store.save_presets(presets)
        return preset

    def update_preset(
        self,
        preset_id: str,
        *,
        name: str,
        params: dict[str, Any],
        is_default: bool = False,
    ) -> dict[str, Any]:
        if preset_id in self.seed_preset_ids:
            raise ValueError("Seed presets are managed by code/config. Save as a new preset instead.")
        presets = self.store.load_presets()
        for preset in presets:
            if preset.get("id") != preset_id:
                continue
            definition = self._get_definition(str(preset["task_slug"]))
            preset["name"] = name.strip() or preset["name"]
            preset["params"] = definition.normalize_params(params)
            preset["is_default"] = is_default
            preset["updated_at"] = datetime.now().isoformat()
            if is_default:
                for other in presets:
                    if other is not preset and other.get("task_slug") == preset.get("task_slug"):
                        other["is_default"] = False
            self.store.save_presets(presets)
            return preset
        raise KeyError(f"Preset not found: {preset_id}")

    def delete_preset(self, preset_id: str) -> bool:
        if preset_id in self.seed_preset_ids:
            raise ValueError("Seed presets are managed by code/config and cannot be deleted.")
        presets = self.store.load_presets()
        updated = [preset for preset in presets if preset.get("id") != preset_id]
        if len(updated) == len(presets):
            return False
        self.store.save_presets(updated)
        return True

    def start_run(
        self,
        *,
        task_slug: str,
        params: dict[str, Any] | None = None,
        preset_id: str | None = None,
    ) -> dict[str, Any]:
        definition = self._get_definition(task_slug)
        normalized = self._merge_and_normalize(definition, params=params, preset_id=preset_id)
        if self.get_active_run():
            raise RuntimeError("Another task is already running.")
        task_spec = definition.build_task_spec(
            self.project_root,
            self.python_executable,
            normalized,
        )
        return self.run_manager.start_run(
            task_spec,
            normalized_params=normalized,
            preset_id=preset_id,
            setup_hook=self._build_run_setup_hook(task_spec, normalized),
            initial_status="queued",
        )

    def stop_active_run(self) -> dict[str, Any] | None:
        return self.run_manager.stop_active_run()

    def get_active_run(self) -> dict[str, Any] | None:
        return self.run_manager.get_active_run()

    def list_runs(self) -> list[dict[str, Any]]:
        return self.run_manager.list_runs()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.run_manager.get_run(run_id)

    def get_run_logs(self, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return self.run_manager.get_run_logs(run_id, limit=limit)

    def get_recent_active_logs(self, limit: int = 200) -> list[dict[str, Any]]:
        return self.run_manager.get_recent_active_logs(limit=limit)

    def get_events_since(self, event_id: int) -> list[dict[str, Any]]:
        return self.run_manager.get_events_since(event_id)

    def get_latest_event_id(self) -> int:
        return self.run_manager.get_latest_event_id()

    def _merge_and_normalize(
        self,
        definition: TaskDefinition,
        *,
        params: dict[str, Any] | None,
        preset_id: str | None,
    ) -> dict[str, Any]:
        merged_params = {}
        if preset_id:
            preset = self._get_preset_or_raise(preset_id)
            if preset.get("task_slug") != definition.template.slug:
                raise ValueError("Preset task does not match selected task.")
            merged_params.update(preset.get("params", {}))
        if params:
            merged_params.update(params)
            self._overlay_param_aliases(merged_params, params)
        return definition.normalize_params(merged_params)

    @staticmethod
    def _overlay_param_aliases(merged_params: dict[str, Any], user_params: dict[str, Any]) -> None:
        for canonical_key, aliases in _PARAM_ALIAS_GROUPS:
            if canonical_key in user_params:
                canonical_value = user_params[canonical_key]
                for alias_key in aliases:
                    merged_params[alias_key] = canonical_value
                continue
            for alias_key in aliases:
                if alias_key not in user_params:
                    continue
                alias_value = user_params[alias_key]
                merged_params[canonical_key] = alias_value
                for sibling_alias in aliases:
                    merged_params[sibling_alias] = alias_value
                break

    def _get_definition(self, slug: str) -> TaskDefinition:
        definition = self.definitions.get(slug)
        if not definition:
            raise KeyError(f"Task not found: {slug}")
        return definition

    def _build_run_setup_hook(self, task_spec, normalized_params: dict[str, Any]):
        browser_provider = str(normalized_params.get("browser_provider") or "local").strip().lower()
        if browser_provider != "browsermint":
            return None

        def setup_hook(context, event_handler, emit_log, emit_update) -> None:
            def mark_step(step_key: str, *, detail: str) -> None:
                steps = context.lifecycle.setdefault(
                    "preflight_steps",
                    deepcopy(task_spec.metadata.get("effective_plan", {}).get("preflight_steps") or []),
                )
                for step in steps:
                    current_key = str(step.get("key") or "")
                    if current_key == step_key:
                        step["status"] = "running"
                    elif str(step.get("status") or "") != "completed":
                        step["status"] = "pending"
                context.lifecycle["detail"] = detail
                context.lifecycle["updated_at"] = datetime.now().isoformat()
                emit_update()

            def complete_step(step_key: str, *, detail: str) -> None:
                steps = context.lifecycle.setdefault(
                    "preflight_steps",
                    deepcopy(task_spec.metadata.get("effective_plan", {}).get("preflight_steps") or []),
                )
                for step in steps:
                    if str(step.get("key") or "") == step_key:
                        step["status"] = "completed"
                context.lifecycle["detail"] = detail
                context.lifecycle["updated_at"] = datetime.now().isoformat()
                emit_update()

            session_id = str(normalized_params.get("browser_session_id") or "").strip()
            mark_step("connect_session", detail="正在连接 BrowserMint 会话。")
            emit_log(f"Connecting Browsermint session {session_id or '<missing>'}.", "info")
            try:
                connection = self.browsermint_client.connect_session(session_id)
            except Exception as exc:
                raise RunSetupError(str(exc), status="waiting_user", level="warning") from exc
            complete_step(
                "connect_session",
                detail=f"BrowserMint 会话已连接：{connection.name or connection.session_id}。",
            )

            mark_step("validate_login", detail="正在校验目标平台登录态。")
            emit_log(
                (
                    f"Browsermint session connected: {connection.name or connection.session_id} "
                    f"({connection.status}). Validating login state."
                ),
                "info",
            )
            try:
                probe_result = probe_browsermint_login(connection, normalized_params)
            except BrowsermintUserActionRequired as exc:
                raise RunSetupError(str(exc), status="waiting_user", level="warning") from exc
            except BrowsermintProbeFailed as exc:
                raise RunSetupError(str(exc), status="failed", level="error") from exc
            except Exception as exc:
                raise RunSetupError(str(exc), status="failed", level="error") from exc
            skipped_platforms = (
                probe_result.get("skipped_platforms")
                if isinstance(probe_result, dict)
                else []
            )
            if isinstance(skipped_platforms, list) and skipped_platforms:
                labels = ", ".join(str(item) for item in skipped_platforms if str(item).strip())
                if labels:
                    emit_log(
                        f"Browsermint 登录预检已跳过未支持平台: {labels}。",
                        "warning",
                    )
            complete_step("validate_login", detail="登录态校验通过。")
            complete_step("verify_homepage", detail="首页可访问检查通过。")
            complete_step("verify_runtime_readiness", detail="轻量读取能力检查通过。")

            mark_step("generate_plan", detail="正在注入远端会话参数并生成有效执行计划。")
            for stage in task_spec.stages:
                for job in stage.jobs:
                    job.env.update(
                        {
                            "CDP_REMOTE_WS_URL": connection.cdp_ws_url,
                            "SOCIAL_CRAWLER_BROWSER_PROVIDER": "browsermint",
                            "SOCIAL_CRAWLER_BROWSER_SESSION_ID": connection.session_id,
                        }
                    )
            complete_step("generate_plan", detail="有效执行计划已生成，准备启动任务。")
            emit_log(
                (
                    f"Browsermint preflight passed for {len(task_spec.stages)} stage(s); "
                    "task execution is starting."
                ),
                "info",
            )

        return setup_hook

    def _get_preset_or_raise(self, preset_id: str) -> dict[str, Any]:
        for preset in self.store.load_presets():
            if preset.get("id") == preset_id:
                return preset
        raise KeyError(f"Preset not found: {preset_id}")

    def _ensure_seed_presets(self) -> None:
        seeds = []
        for definition in self.definitions.values():
            for seed in definition.preset_seeds:
                seeds.append(
                    {
                        "id": seed.id,
                        "task_slug": seed.task_slug,
                        "name": seed.name,
                        "params": seed.params,
                        "is_default": seed.is_default,
                        "is_seed": True,
                        "updated_at": datetime.now().isoformat(),
                    }
                )
        presets = self.store.ensure_seed_presets(seeds)
        seed_map = {seed["id"]: seed for seed in seeds}
        changed = False
        for preset in presets:
            seed = seed_map.get(str(preset.get("id", "")))
            if not seed:
                continue
            if (
                preset.get("task_slug") != seed["task_slug"]
                or preset.get("name") != seed["name"]
                or preset.get("params") != seed["params"]
                or preset.get("is_default") != seed["is_default"]
                or preset.get("is_seed") is not True
            ):
                preset["task_slug"] = seed["task_slug"]
                preset["name"] = seed["name"]
                preset["params"] = seed["params"]
                preset["is_default"] = seed["is_default"]
                preset["is_seed"] = True
                preset["updated_at"] = datetime.now().isoformat()
                changed = True

        if changed:
            self.store.save_presets(presets)


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
task_center_service = TaskCenterService(
    project_root=_PROJECT_ROOT,
    python_executable=sys.executable,
)


def get_task_center_service() -> TaskCenterService:
    return task_center_service
