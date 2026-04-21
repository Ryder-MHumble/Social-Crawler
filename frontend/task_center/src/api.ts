import type {
  BrowsermintSessionsPayload,
  DataFileInfo,
  DataFilePreview,
  DataFileFilters,
  EnvCheckResult,
  SqliteRow,
  SqliteRowFilters,
  SqliteRowsResponse,
  SqliteStats,
  SqliteStatus,
  SqliteTablesPayload,
  TaskJob,
  TaskLogEntry,
  TaskRunPlanItem,
  TaskRunProgress,
  TaskPreset,
  TaskPreview,
  TaskRunIssue,
  TaskRunLifecycle,
  TaskRunMetrics,
  TaskRunWarning,
  TaskStage,
  TaskRun,
  TaskTemplate,
} from "./types";

function asRecord(input: unknown): Record<string, unknown> | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  return input as Record<string, unknown>;
}

function prettifyKey(key: string): string {
  const compact = key.trim();
  if (!compact) return "Unknown";
  return compact
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeTaskJob(input: Partial<TaskJob> | null | undefined): TaskJob {
  const job = input ?? {};
  return {
    key: String(job.key ?? ""),
    name: String(job.name ?? job.key ?? "Unnamed Job"),
    cwd: String(job.cwd ?? ""),
    command: Array.isArray(job.command) ? job.command.map((item) => String(item)) : [],
    display_command: job.display_command,
    metadata:
      job.metadata && typeof job.metadata === "object"
        ? (job.metadata as Record<string, unknown>)
        : {},
    status: job.status,
    log_path: job.log_path,
    exit_code: job.exit_code ?? null,
    line_count: job.line_count,
    last_line: job.last_line,
    pid: job.pid ?? null,
    last_output_at: job.last_output_at ?? null,
    last_state_change_at: job.last_state_change_at ?? null,
    watchdog_status: job.watchdog_status ?? null,
    stall_deadline_at: job.stall_deadline_at ?? null,
    termination_reason: job.termination_reason ?? null,
    started_at: job.started_at ?? null,
    finished_at: job.finished_at ?? null,
  };
}

function normalizeTaskStage(input: Partial<TaskStage> | null | undefined): TaskStage {
  const stage = input ?? {};
  return {
    key: String(stage.key ?? ""),
    name: String(stage.name ?? stage.key ?? "Unnamed Stage"),
    concurrent: Boolean(stage.concurrent),
    max_parallel: stage.max_parallel ?? null,
    abort_on_failure: Boolean(stage.abort_on_failure),
    status: stage.status,
    jobs: Array.isArray(stage.jobs) ? stage.jobs.map((job) => normalizeTaskJob(job)) : [],
  };
}

function normalizeTaskMetrics(input: Partial<TaskRunMetrics> | null | undefined): TaskRunMetrics {
  const metrics = asRecord(input) ?? {};
  const normalized: TaskRunMetrics = {
    accepted: Number(metrics.accepted ?? 0),
    filtered: Number(metrics.filtered ?? 0),
    deduped: Number(metrics.deduped ?? 0),
    errors: Number(metrics.errors ?? 0),
    stalled_jobs: Number(metrics.stalled_jobs ?? 0),
    candidate_count: Number(metrics.candidate_count ?? 0),
    detail_requests: Number(metrics.detail_requests ?? 0),
    detail_successes: Number(metrics.detail_successes ?? 0),
    detail_failures: Number(metrics.detail_failures ?? 0),
  };
  for (const [key, value] of Object.entries(metrics)) {
    const numericValue = Number(value);
    if (Number.isFinite(numericValue)) {
      normalized[key] = numericValue;
    }
  }
  return normalized;
}

function normalizeTaskLifecycle(
  input: Partial<TaskRunLifecycle> | null | undefined,
): TaskRunLifecycle | null {
  if (!input) return null;
  return {
    phase: String(input.phase ?? ""),
    label: String(input.label ?? ""),
    detail: String(input.detail ?? ""),
    updated_at: input.updated_at ?? null,
    current_stage_key: input.current_stage_key ?? null,
    current_stage_name: input.current_stage_name ?? null,
    stage_index: Number(input.stage_index ?? 0),
    stage_total: Number(input.stage_total ?? 0),
  };
}

function normalizeTaskIssue(input: Partial<TaskRunIssue> | null | undefined): TaskRunIssue | null {
  if (!input || !input.fingerprint) return null;
  return {
    fingerprint: String(input.fingerprint),
    category_key: String(input.category_key ?? "other"),
    label: String(input.label ?? "Other"),
    hint: String(input.hint ?? ""),
    count: Number(input.count ?? 0),
    level: String(input.level ?? "warning"),
    sample_message: input.sample_message,
    last_message: input.last_message,
    first_seen_at: input.first_seen_at ?? null,
    last_seen_at: input.last_seen_at ?? null,
    stage_key: input.stage_key ?? null,
    stage_name: input.stage_name ?? null,
    job_key: input.job_key ?? null,
    job_name: input.job_name ?? null,
  };
}

function normalizeTaskPlanItem(input: unknown, index: number): TaskRunPlanItem | null {
  if (typeof input === "string") {
    const text = input.trim();
    if (!text) return null;
    return {
      key: `plan_${index}`,
      label: text,
      detail: "",
      status: null,
    };
  }

  const item = asRecord(input);
  if (!item) return null;

  const key = String(item.key ?? item.id ?? item.code ?? `plan_${index}`).trim() || `plan_${index}`;
  const label =
    String(item.label ?? item.title ?? item.name ?? prettifyKey(key)).trim() || prettifyKey(key);
  const detail = String(item.detail ?? item.reason ?? item.summary ?? item.message ?? "").trim();
  const status = item.status == null ? null : String(item.status).trim() || null;

  return {
    ...item,
    key,
    label,
    detail,
    status,
  };
}

function normalizeTaskPlan(input: unknown): TaskRunPlanItem[] | null {
  if (!input) return null;
  if (Array.isArray(input)) {
    const items = input
      .map((item, index) => normalizeTaskPlanItem(item, index))
      .filter((item): item is TaskRunPlanItem => Boolean(item));
    return items.length ? items : null;
  }

  const record = asRecord(input);
  if (!record) return null;

  const nestedItems = [record.steps, record.items, record.plan, record.phases].find(Array.isArray);
  if (Array.isArray(nestedItems)) {
    return normalizeTaskPlan(nestedItems);
  }

  const entries = Object.entries(record)
    .filter(([key]) => !["label", "title", "detail", "summary", "status"].includes(key))
    .map(([key, value], index) => {
      if (typeof value === "boolean") {
        return normalizeTaskPlanItem(
          {
            key,
            label: prettifyKey(key),
            detail: value ? "Enabled" : "Disabled",
            status: value ? "enabled" : "disabled",
          },
          index,
        );
      }
      if (typeof value === "string" || typeof value === "number") {
        return normalizeTaskPlanItem(
          {
            key,
            label: prettifyKey(key),
            detail: String(value),
          },
          index,
        );
      }
      const nestedRecord = asRecord(value);
      if (nestedRecord) {
        return normalizeTaskPlanItem(
          {
            key,
            label: nestedRecord.label ?? nestedRecord.title ?? prettifyKey(key),
            ...nestedRecord,
          },
          index,
        );
      }
      return null;
    })
    .filter((item): item is TaskRunPlanItem => Boolean(item));

  return entries.length ? entries : null;
}

function normalizeTaskWarning(
  input: unknown,
  index: number,
  fallbackCode = "warning",
): TaskRunWarning | null {
  if (typeof input === "string") {
    const text = input.trim();
    if (!text) return null;
    return {
      key: `${fallbackCode}_${index}`,
      code: fallbackCode,
      label: text,
      detail: text,
      level: "warning",
      status: null,
    };
  }

  const warning = asRecord(input);
  if (!warning) return null;

  const code =
    String(warning.code ?? warning.kind ?? warning.category ?? warning.status ?? fallbackCode).trim()
    || fallbackCode;
  const key =
    String(warning.key ?? warning.fingerprint ?? warning.id ?? `${code}_${index}`).trim()
    || `${code}_${index}`;
  const label =
    String(warning.label ?? warning.title ?? warning.name ?? prettifyKey(code)).trim()
    || prettifyKey(code);
  const detail = String(warning.detail ?? warning.message ?? warning.reason ?? warning.hint ?? "").trim();
  const level = String(warning.level ?? warning.severity ?? "warning").trim().toLowerCase() || "warning";
  const status = warning.status == null ? null : String(warning.status).trim() || null;

  return {
    ...warning,
    key,
    code,
    label,
    detail,
    level,
    status,
  };
}

function normalizeTaskWarnings(input: unknown, fallbackCode = "warning"): TaskRunWarning[] {
  if (!input) return [];
  if (Array.isArray(input)) {
    return input
      .map((item, index) => normalizeTaskWarning(item, index, fallbackCode))
      .filter((item): item is TaskRunWarning => Boolean(item));
  }

  const record = asRecord(input);
  if (!record) return [];

  const nestedItems = [record.items, record.entries, record.warnings].find(Array.isArray);
  if (Array.isArray(nestedItems)) {
    return normalizeTaskWarnings(nestedItems, fallbackCode);
  }

  return Object.entries(record)
    .map(([key, value], index) => {
      const nestedRecord = asRecord(value);
      return normalizeTaskWarning(
        nestedRecord
          ? {
              key,
              code: key,
              ...nestedRecord,
            }
          : {
              key,
              code: key,
              label: prettifyKey(key),
              detail: String(value ?? "").trim(),
            },
        index,
        fallbackCode,
      );
    })
    .filter((item): item is TaskRunWarning => Boolean(item));
}

function normalizeTaskProgress(input: unknown): TaskRunProgress | null {
  const progress = asRecord(input);
  if (!progress) return null;
  return { ...progress };
}

export function normalizeTaskRun(input: Partial<TaskRun> | null | undefined): TaskRun | null {
  if (!input || !input.id || !input.task_slug) return null;
  return {
    id: String(input.id),
    task_slug: String(input.task_slug),
    title: String(input.title ?? input.task_slug),
    status: String(input.status ?? "unknown"),
    preset_id: input.preset_id ?? null,
    normalized_params:
      input.normalized_params && typeof input.normalized_params === "object"
        ? (input.normalized_params as Record<string, unknown>)
        : {},
    started_at: input.started_at ?? null,
    finished_at: input.finished_at ?? null,
    log_path: input.log_path ?? null,
    metrics: normalizeTaskMetrics(input.metrics),
    lifecycle: normalizeTaskLifecycle(input.lifecycle),
    issues: Array.isArray(input.issues)
      ? input.issues.map((issue) => normalizeTaskIssue(issue)).filter((issue): issue is TaskRunIssue => Boolean(issue))
      : [],
    effective_plan: normalizeTaskPlan(input.effective_plan),
    plan_warnings: normalizeTaskWarnings(input.plan_warnings, "plan_warning"),
    effective_save_option: input.effective_save_option == null ? null : String(input.effective_save_option),
    runtime_storage_backend:
      input.runtime_storage_backend == null ? null : String(input.runtime_storage_backend),
    progress: normalizeTaskProgress(input.progress),
    warnings: normalizeTaskWarnings(input.warnings),
    breakdowns:
      input.breakdowns && typeof input.breakdowns === "object"
        ? (input.breakdowns as TaskRun["breakdowns"])
        : null,
    stages: Array.isArray(input.stages) ? input.stages.map((stage) => normalizeTaskStage(stage)) : [],
  };
}

function requireNormalizedRun(input: Partial<TaskRun> | null | undefined, context: string): TaskRun {
  const run = normalizeTaskRun(input);
  if (!run) {
    throw new Error(`${context} returned an invalid run payload`);
  }
  return run;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail ?? payload.message ?? detail;
    } catch {
      // ignore invalid json
    }
    throw new Error(detail || "Request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    if (text.startsWith("<!doctype") || text.startsWith("<html")) {
      throw new Error(
        "API returned HTML instead of JSON. Please ensure backend is running on :8080 and Vite proxy is enabled.",
      );
    }
    throw new Error(`Unexpected response type: ${contentType || "unknown"}`);
  }

  return (await response.json()) as T;
}

export async function fetchTasks(): Promise<TaskTemplate[]> {
  const payload = await request<{ tasks: TaskTemplate[] }>("/tasks");
  return payload.tasks;
}

export async function fetchBrowsermintSessions(): Promise<BrowsermintSessionsPayload> {
  return request<BrowsermintSessionsPayload>("/browsermint/sessions");
}

export async function fetchTaskPreview(
  slug: string,
  params: Record<string, unknown>,
  presetId?: string | null,
): Promise<TaskPreview> {
  return request<TaskPreview>(`/tasks/${slug}/preview`, {
    method: "POST",
    body: JSON.stringify({ params, preset_id: presetId ?? null }),
  });
}

export async function fetchPresets(taskSlug?: string): Promise<TaskPreset[]> {
  const query = taskSlug ? `?task_slug=${encodeURIComponent(taskSlug)}` : "";
  const payload = await request<{ presets: TaskPreset[] }>(`/presets${query}`);
  return payload.presets;
}

export async function createPreset(input: {
  task_slug: string;
  name: string;
  params: Record<string, unknown>;
  is_default: boolean;
}): Promise<TaskPreset> {
  return request<TaskPreset>("/presets", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updatePreset(
  presetId: string,
  input: { name: string; params: Record<string, unknown>; is_default: boolean },
): Promise<TaskPreset> {
  return request<TaskPreset>(`/presets/${presetId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function deletePreset(presetId: string): Promise<void> {
  await request(`/presets/${presetId}`, { method: "DELETE" });
}

export async function fetchRuns(): Promise<TaskRun[]> {
  const payload = await request<{ runs: TaskRun[] }>("/runs");
  return (payload.runs ?? [])
    .map((run) => normalizeTaskRun(run))
    .filter((run): run is TaskRun => Boolean(run));
}

export async function fetchActiveRun(): Promise<TaskRun | null> {
  const payload = await request<{ run: TaskRun | null }>("/runs/active");
  return normalizeTaskRun(payload.run);
}

export async function startRun(input: {
  task_slug: string;
  params: Record<string, unknown>;
  preset_id?: string | null;
}): Promise<TaskRun> {
  const payload = await request<TaskRun>("/runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return requireNormalizedRun(payload, "POST /runs");
}

export async function stopActiveRun(): Promise<TaskRun> {
  const payload = await request<{ status: string; run: TaskRun }>("/runs/active/stop", {
    method: "POST",
  });
  return requireNormalizedRun(payload.run, "POST /runs/active/stop");
}

export async function fetchRunLogs(runId: string, limit = 200): Promise<TaskLogEntry[]> {
  const payload = await request<{ logs: TaskLogEntry[] }>(`/runs/${runId}/logs?limit=${limit}`);
  return payload.logs;
}

export async function fetchSqliteStatus(): Promise<SqliteStatus> {
  return request<SqliteStatus>("/storage/sqlite/status");
}

export async function initSqlite(): Promise<SqliteStatus> {
  return request<SqliteStatus>("/storage/sqlite/init", { method: "POST" });
}

export async function fetchSqliteStats(
  filters: Partial<Pick<SqliteRowFilters, "table" | "run_id" | "task_slug" | "platform" | "entity_type" | "clean_status" | "q">> = {},
): Promise<SqliteStats> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  return request<SqliteStats>(`/data/sqlite/stats${params.toString() ? `?${params.toString()}` : ""}`);
}

export async function fetchSqliteTables(): Promise<SqliteTablesPayload> {
  return request<SqliteTablesPayload>("/data/sqlite/tables");
}

export async function fetchSqliteRows(filters: SqliteRowFilters): Promise<SqliteRowsResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  return request<SqliteRowsResponse>(`/data/sqlite/rows?${params.toString()}`);
}

export async function fetchSqliteRow(table: string, rowId: number): Promise<SqliteRow> {
  return request<SqliteRow>(
    `/data/sqlite/row?table=${encodeURIComponent(table)}&row_id=${encodeURIComponent(String(rowId))}`,
  );
}

export async function fetchDataFiles(filters: Partial<Pick<DataFileFilters, "platform" | "file_type">> = {}): Promise<DataFileInfo[]> {
  const params = new URLSearchParams();
  if (filters.platform) params.set("platform", filters.platform);
  if (filters.file_type) params.set("file_type", filters.file_type);
  const payload = await request<{ files: DataFileInfo[] }>(
    `/data/files${params.toString() ? `?${params.toString()}` : ""}`,
  );
  return payload.files;
}

export async function fetchDataFilePreview(filePath: string, limit = 100): Promise<DataFilePreview> {
  return request<DataFilePreview>(
    `/data/files/${encodeURIComponent(filePath)}?preview=true&limit=${encodeURIComponent(String(limit))}`,
  );
}

export async function fetchEnvCheck(): Promise<EnvCheckResult> {
  return request<EnvCheckResult>("/env/check");
}

export function activeRunSocketUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/ws/runs/active`;
}
