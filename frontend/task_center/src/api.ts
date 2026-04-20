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
  TaskLogEntry,
  TaskPreset,
  TaskPreview,
  TaskRun,
  TaskTemplate,
} from "./types";

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
  return payload.runs;
}

export async function fetchActiveRun(): Promise<TaskRun | null> {
  const payload = await request<{ run: TaskRun | null }>("/runs/active");
  return payload.run;
}

export async function startRun(input: {
  task_slug: string;
  params: Record<string, unknown>;
  preset_id?: string | null;
}): Promise<TaskRun> {
  return request<TaskRun>("/runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function stopActiveRun(): Promise<TaskRun> {
  const payload = await request<{ status: string; run: TaskRun }>("/runs/active/stop", {
    method: "POST",
  });
  return payload.run;
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
