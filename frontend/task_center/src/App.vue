<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  activeRunSocketUrl,
  createPreset,
  deletePreset,
  fetchBrowsermintSessions,
  fetchActiveRun,
  fetchDataFilePreview,
  fetchDataFiles,
  fetchEnvCheck,
  fetchPresets,
  fetchRunLogs,
  fetchRuns,
  fetchSqliteRow,
  fetchSqliteRows,
  fetchSqliteStats,
  fetchSqliteStatus,
  fetchSqliteTables,
  fetchTaskPreview,
  fetchTasks,
  initSqlite,
  startRun,
  stopActiveRun,
  updatePreset,
} from "./api";
import CommandsTab from "./components/CommandsTab.vue";
import ConfigTab from "./components/ConfigTab.vue";
import DataTab from "./components/DataTab.vue";
import ExecutionTab from "./components/ExecutionTab.vue";
import SystemTab from "./components/SystemTab.vue";
import TopActionBar from "./components/TopActionBar.vue";
import WorkspaceSidebar from "./components/WorkspaceSidebar.vue";
import type {
  BrowsermintSession,
  DataBrowseMode,
  DataFileFilters,
  DataFileInfo,
  DataFilePreview,
  EnvCheckResult,
  GroupedFieldSection,
  SqliteRow,
  SqliteRowFilters,
  SqliteRowsResponse,
  SqliteStats,
  SqliteStatus,
  SqliteTableSummary,
  TaskLogEntry,
  TaskPreset,
  TaskPreview,
  TaskRun,
  TaskTemplate,
} from "./types";

type MainTab = "config" | "commands" | "execution" | "data";

const mainTabs: Array<{ key: MainTab; label: string }> = [
  { key: "config", label: "配置与预览" },
  { key: "commands", label: "命令" },
  { key: "execution", label: "运行监控" },
  { key: "data", label: "结果中心" },
];

const tasks = ref<TaskTemplate[]>([]);
const presets = ref<TaskPreset[]>([]);
const runs = ref<TaskRun[]>([]);
const activeRun = ref<TaskRun | null>(null);
const logs = ref<TaskLogEntry[]>([]);
const preview = ref<TaskPreview | null>(null);
const browsermintSessions = ref<BrowsermintSession[]>([]);
const browsermintConfigured = ref(false);

const sqliteStatus = ref<SqliteStatus | null>(null);
const sqliteTables = ref<SqliteTableSummary[]>([]);
const sqliteSupportedTables = ref<string[]>([]);
const sqliteStats = ref<SqliteStats | null>(null);
const sqliteRows = ref<SqliteRowsResponse | null>(null);
const selectedDataRow = ref<SqliteRow | null>(null);
const selectedDataMode = ref<DataBrowseMode>("sqlite");
const dataFiles = ref<DataFileInfo[]>([]);
const selectedDataFilePath = ref<string | null>(null);
const selectedDataFilePreview = ref<DataFilePreview | null>(null);
const envCheck = ref<EnvCheckResult | null>(null);

const selectedTaskSlug = ref("");
const selectedPresetId = ref<string | null>(null);
const presetName = ref("");
const presetIsDefault = ref(false);
const formParams = ref<Record<string, unknown>>({});
const selectedMainTab = ref<MainTab>("config");
const selectedConfigGroup = ref("");
const selectedRunId = ref<string | null>(null);
const selectedExecutionJobRef = ref<string | null>(null);
const socketState = ref<"connecting" | "connected" | "disconnected">("connecting");
const isSystemPanelOpen = ref(false);

const isLoading = ref(true);
const isPreviewLoading = ref(false);
const isSavingPreset = ref(false);
const isStartingRun = ref(false);
const isBrowsermintLoading = ref(false);
const isSystemLoading = ref(false);
const isDataLoading = ref(false);
const isFileLoading = ref(false);
const isInitializingSqlite = ref(false);

const message = ref("");
const errorMessage = ref("");
const now = ref(Date.now());

const dataFilters = ref<SqliteRowFilters>({
  table: "crawl_observations",
  run_id: "",
  task_slug: "",
  platform: "",
  entity_type: "",
  clean_status: "",
  q: "",
  limit: 50,
  offset: 0,
});
const dataFileFilters = ref<DataFileFilters>({
  platform: "",
  file_type: "",
  q: "",
});

let previewTimer: number | null = null;
let dataTimer: number | null = null;
let fileTimer: number | null = null;
let reconnectTimer: number | null = null;
let clockTimer: number | null = null;
let socket: WebSocket | null = null;

const selectedTask = computed(
  () => tasks.value.find((task) => task.slug === selectedTaskSlug.value) ?? null,
);

const selectedBrowsermintSession = computed(
  () =>
    browsermintSessions.value.find(
      (session) => session.session_id === String(formParams.value.browser_session_id ?? "").trim(),
    ) ?? null,
);

const activeRunBrowsermintSession = computed(() => {
  const activeSessionId = String(activeRun.value?.normalized_params?.browser_session_id ?? "").trim();
  if (!activeSessionId) return null;
  return browsermintSessions.value.find((session) => session.session_id === activeSessionId) ?? null;
});

type RunGuide = {
  title: string;
  detail: string;
  openBrowsermint: boolean;
  openLabel: string;
};

const runStartGuide = computed<RunGuide | null>(() => {
  if (isStartingRun.value) {
    return {
      title: "正在启动任务并检查浏览器连接…",
      detail: "请稍候几秒，系统会完成会话预检后进入执行。",
      openBrowsermint: false,
      openLabel: "",
    };
  }

  const run = activeRun.value;
  if (!run || run.status !== "running") return null;

  const browserProvider = String(run.normalized_params.browser_provider ?? "local")
    .trim()
    .toLowerCase();
  const loginType = String(run.normalized_params.login_type ?? "")
    .trim()
    .toLowerCase();

  if (browserProvider === "browsermint" && loginType === "qrcode") {
    return {
      title: "任务已启动，请先在 Browsermint 会话完成扫码/登录确认。",
      detail: "扫码完成后回到“执行”页查看实时日志；未登录会导致平台接口无权限。",
      openBrowsermint: Boolean(guideBrowsermintDeepLink.value),
      openLabel: "打开 Browsermint 去扫码",
    };
  }

  if (browserProvider === "browsermint") {
    return {
      title: "任务已启动，正在借用 Browsermint 会话执行。",
      detail: "可在“执行”页查看连接状态和实时日志输出。",
      openBrowsermint: Boolean(guideBrowsermintDeepLink.value),
      openLabel: "打开 Browsermint 会话",
    };
  }

  if (loginType === "qrcode") {
    return {
      title: "任务已启动，请在本地浏览器完成扫码登录。",
      detail: "登录完成后返回“执行”页观察日志与采集进度。",
      openBrowsermint: false,
      openLabel: "",
    };
  }

  return null;
});

const guideBrowsermintDeepLink = computed(() => {
  const fromActiveRun = String(activeRunBrowsermintSession.value?.deep_link_url ?? "").trim();
  if (fromActiveRun) return fromActiveRun;
  const fromFormSelection = String(selectedBrowsermintSession.value?.deep_link_url ?? "").trim();
  return fromFormSelection;
});

const selectedTaskPresets = computed(() =>
  presets.value.filter((preset) => preset.task_slug === selectedTaskSlug.value),
);

const selectedPreset = computed(
  () => selectedTaskPresets.value.find((preset) => preset.id === selectedPresetId.value) ?? null,
);

function enrichFieldOptions(field: TaskTemplate["fields"][number]): TaskTemplate["fields"][number] {
  if (field.key !== "browser_session_id") return field;
  const currentValue = String(formParams.value.browser_session_id ?? "").trim();
  const options = browsermintSessions.value.map((session) => ({
    value: session.session_id,
    label: `${session.name} · ${session.status}`,
    description: session.last_active_at ? `Last active: ${session.last_active_at}` : "",
  }));
  if (currentValue && !options.some((option) => String(option.value) === currentValue)) {
    options.unshift({
      value: currentValue,
      label: `${currentValue} · 当前值`,
      description: "当前值不在可选列表中，可能已停止或被删除。",
    });
  }
  if (!options.length) {
    options.push({
      value: "",
      label: browsermintConfigured.value ? "暂无可用会话" : "Browsermint 未配置",
      description: browsermintConfigured.value
        ? "请先在 Browsermint 中启动并登录会话。"
        : "请先配置 Browsermint 后端集成。",
    });
  }
  const helperTextParts = [field.helper_text];
  if (!browsermintConfigured.value) {
    helperTextParts.push("当前环境未配置 Browsermint 集成。");
  } else if (isBrowsermintLoading.value) {
    helperTextParts.push("正在刷新 Browsermint 会话列表。");
  } else if (!browsermintSessions.value.length) {
    helperTextParts.push("暂无 running/paused 会话，请先到 Browsermint 完成扫码登录。");
  }
  return {
    ...field,
    options,
    helper_text: helperTextParts.filter(Boolean).join(" "),
  };
}

const visibleFields = computed(() =>
  (selectedTask.value?.fields ?? [])
    .map((field) => enrichFieldOptions(field))
    .filter((field) => isFieldVisible(field)),
);

const groupedFields = computed<GroupedFieldSection[]>(() => {
  const groups = new Map<string, GroupedFieldSection>();
  for (const field of visibleFields.value) {
    const existing = groups.get(field.group) ?? {
      name: field.group,
      fields: [],
      requiredCount: 0,
    };
    existing.fields.push(field);
    if (field.required) existing.requiredCount += 1;
    groups.set(field.group, existing);
  }
  return Array.from(groups.values());
});

function findRun(runId: string | null): TaskRun | null {
  if (!runId) return null;
  if (activeRun.value?.id === runId) return activeRun.value;
  return runs.value.find((run) => run.id === runId) ?? null;
}

const selectedTaskRun = computed(() => {
  const run = findRun(selectedRunId.value);
  if (!run || run.task_slug !== selectedTaskSlug.value) return null;
  return run;
});

const taskActiveRun = computed(() => {
  const run = activeRun.value;
  if (!run || run.task_slug !== selectedTaskSlug.value) return null;
  return run;
});

const otherTaskActiveRun = computed(() => {
  const run = activeRun.value;
  if (!run || run.task_slug === selectedTaskSlug.value) return null;
  return run;
});

const taskRuns = computed(() => {
  const merged: TaskRun[] = [];
  const seen = new Set<string>();
  const pushRun = (run: TaskRun | null | undefined) => {
    if (!run || run.task_slug !== selectedTaskSlug.value || seen.has(run.id)) return;
    seen.add(run.id);
    merged.push(run);
  };
  pushRun(taskActiveRun.value);
  runs.value.forEach(pushRun);
  return merged;
});

const selectedRun = computed(() => selectedTaskRun.value);

const displayedRun = computed(() => {
  return selectedRun.value ?? taskRuns.value[0] ?? null;
});

const recentRuns = computed(() =>
  taskRuns.value
    .filter((run) => run.id !== taskActiveRun.value?.id)
    .slice(0, 8),
);

const currentPresetName = computed(
  () => selectedPreset.value?.name || presetName.value || "任务默认值",
);

const storageSummary = computed(() =>
  buildStorageSummary(selectedTaskSlug.value, formParams.value),
);

const runSelectOptions = computed(() => [
  { value: "", label: "当前任务暂无运行记录" },
  ...taskRuns.value.map((run) => ({
    value: run.id,
    label: `${run.title} · ${run.status}`,
  })),
]);

function buildStorageSummary(taskSlug: string, params?: Record<string, unknown> | null): string {
  if (taskSlug === "creator_outreach") {
    return "SQLite · candidate / delivery tables";
  }
  const saveOption = resolveSaveOption(params);
  if (saveOption === "sqlite") return "SQLite · crawl tables + observations";
  if (saveOption === "json") return "JSON 文件 · runtime/data";
  if (saveOption === "csv") return "CSV 文件 · runtime/data";
  if (saveOption === "excel") return "Excel 文件 · runtime/data";
  if (saveOption === "supabase") return "Supabase · remote dataset";
  if (!saveOption) return "默认输出 · 任务定义决定";
  return `${saveOption.toUpperCase()} · 任务存储`;
}

const baselineParams = computed<Record<string, unknown>>(() =>
  cloneParams(selectedPreset.value?.params ?? selectedTask.value?.defaults ?? {}),
);

const hasUnsavedChanges = computed(
  () => JSON.stringify(formParams.value) !== JSON.stringify(baselineParams.value),
);

function cloneParams(input: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(input));
}

function taskDraftKey(taskSlug: string): string {
  return `task_center_draft:${taskSlug}`;
}

function loadDraft(taskSlug: string): Record<string, unknown> | null {
  const raw = window.localStorage.getItem(taskDraftKey(taskSlug));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function saveDraft() {
  if (!selectedTaskSlug.value) return;
  window.localStorage.setItem(taskDraftKey(selectedTaskSlug.value), JSON.stringify(formParams.value));
}

function isSameValue(actual: unknown, expected: unknown): boolean {
  if (Array.isArray(actual) && Array.isArray(expected)) {
    return actual.length === expected.length && actual.every((value, index) => value === expected[index]);
  }
  return actual === expected;
}

function isFieldVisible(field: TaskTemplate["fields"][number]): boolean {
  if (!field.visible_when) return true;
  return Object.entries(field.visible_when).every(([key, expected]) =>
    isSameValue(formParams.value[key], expected),
  );
}

function resetMessages() {
  message.value = "";
  errorMessage.value = "";
}

function firstJobRef(run: TaskRun | null): string | null {
  const stage = run?.stages[0];
  const job = stage?.jobs[0];
  return stage && job ? `${stage.key}::${job.key}` : null;
}

function formatDateTime(value?: string | null): string {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function normalizeRunStatus(status?: string | null): string {
  return String(status ?? "")
    .trim()
    .toLowerCase();
}

function runStatusTone(status?: string | null): "running" | "danger" | "success" | "warning" | "neutral" {
  const normalized = normalizeRunStatus(status);
  if (["running", "queued", "pending", "starting", "active", "in_progress"].includes(normalized)) {
    return "running";
  }
  if (["failed", "error", "errored", "timeout", "cancelled", "canceled", "aborted", "stopped"].includes(normalized)) {
    return "danger";
  }
  if (["completed", "complete", "success", "succeeded", "done", "finished"].includes(normalized)) {
    return "success";
  }
  if (normalized) return "warning";
  return "neutral";
}

function resolveSaveOption(params?: Record<string, unknown> | null): string {
  if (String(params?.browser_provider ?? "").trim().toLowerCase() === "browsermint") {
    return "sqlite";
  }
  return String(params?.save_option ?? params?.save_data_option ?? "")
    .trim()
    .toLowerCase();
}

function preferredDataMode(taskSlug?: string | null, saveOption?: string | null): DataBrowseMode {
  if (taskSlug === "creator_outreach") return "sqlite";
  return ["json", "csv", "excel"].includes(String(saveOption ?? "").toLowerCase()) ? "files" : "sqlite";
}

function preferredFileType(saveOption?: string | null): string {
  const normalized = String(saveOption ?? "").toLowerCase();
  if (normalized === "json" || normalized === "csv") return normalized;
  return "";
}

function resolveRunPlatforms(run: TaskRun | null): string[] {
  if (!run) return [];
  const rawPlatforms = run.normalized_params.platforms;
  if (Array.isArray(rawPlatforms)) {
    return rawPlatforms
      .map((platform) => String(platform).trim())
      .filter(Boolean);
  }
  const singlePlatform = String(run.normalized_params.platform ?? "").trim();
  return singlePlatform ? [singlePlatform] : [];
}

function preferredDataTable(taskSlug?: string | null): string {
  if (taskSlug === "creator_outreach") return "outreach_candidates";
  if (taskSlug === "vibe_coding") return "vibe_content_scores";
  return "crawl_observations";
}

function applyTaskDataDefaults(taskSlug: string) {
  const saveOption = resolveSaveOption(formParams.value);
  selectedDataMode.value = preferredDataMode(taskSlug, saveOption);
  dataFilters.value = {
    ...dataFilters.value,
    table: preferredDataTable(taskSlug),
    run_id: "",
    task_slug: "",
    platform: "",
    entity_type: "",
    clean_status: "",
    q: "",
    offset: 0,
  };
  dataFileFilters.value = {
    ...dataFileFilters.value,
    platform: "",
    file_type: preferredFileType(saveOption),
    q: "",
  };
  selectedDataRow.value = null;
  selectedDataFilePath.value = null;
  selectedDataFilePreview.value = null;
}

function ensureSelectedConfigGroup() {
  if (!groupedFields.value.length) {
    selectedConfigGroup.value = "";
    return;
  }
  if (!groupedFields.value.some((group) => group.name === selectedConfigGroup.value)) {
    selectedConfigGroup.value = groupedFields.value[0].name;
  }
}

function applyPreset(preset: TaskPreset | null) {
  if (!selectedTask.value) return;
  selectedPresetId.value = preset?.id ?? null;
  presetName.value = preset?.name ?? "";
  presetIsDefault.value = preset?.is_default ?? false;
  const base = cloneParams(preset?.params ?? selectedTask.value.defaults);
  const draft = loadDraft(selectedTask.value.slug);
  formParams.value = draft ? { ...base, ...draft } : base;
  ensureSelectedConfigGroup();
  void triggerPreview();
}

async function initialize() {
  isLoading.value = true;
  resetMessages();
  try {
    const [loadedTasks, loadedPresets, loadedRuns, loadedActiveRun, loadedSqliteStatus] = await Promise.all([
      fetchTasks(),
      fetchPresets(),
      fetchRuns(),
      fetchActiveRun(),
      fetchSqliteStatus(),
    ]);
    tasks.value = loadedTasks;
    presets.value = loadedPresets;
    runs.value = loadedRuns;
    activeRun.value = loadedActiveRun;
    sqliteStatus.value = loadedSqliteStatus;

    const defaultPreset =
      loadedPresets.find((preset) => preset.is_default) ??
      loadedPresets.find((preset) => preset.task_slug === loadedTasks[0]?.slug) ??
      loadedPresets[0] ??
      null;
    const initialTaskSlug = defaultPreset?.task_slug ?? loadedTasks[0]?.slug ?? "";
    if (initialTaskSlug) {
      selectedTaskSlug.value = initialTaskSlug;
      const preset =
        loadedPresets.find((item) => item.id === defaultPreset?.id) ??
        loadedPresets.find((item) => item.task_slug === initialTaskSlug) ??
        null;
      applyPreset(preset);
    }

    const initialRun =
      [loadedActiveRun, ...loadedRuns].find(
        (run): run is TaskRun => run !== null && run.task_slug === initialTaskSlug,
      ) ?? null;
    selectedRunId.value = initialRun?.id ?? null;
    if (initialRun) {
      applyRunDataContext(initialRun);
    } else {
      applyTaskDataDefaults(initialTaskSlug);
    }
    if (selectedRunId.value) {
      logs.value = await fetchRunLogs(selectedRunId.value, 1000);
    }
    await refreshSqliteTables();
    connectSocket();
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isLoading.value = false;
  }
}

async function loadBrowsermintSessions(force = false) {
  if (!force && isBrowsermintLoading.value) return;
  isBrowsermintLoading.value = true;
  try {
    const payload = await fetchBrowsermintSessions();
    browsermintConfigured.value = payload.configured;
    browsermintSessions.value = payload.sessions;
  } catch (error) {
    browsermintConfigured.value = false;
    browsermintSessions.value = [];
    errorMessage.value = (error as Error).message;
  } finally {
    isBrowsermintLoading.value = false;
  }
}

async function refreshRunsList() {
  runs.value = await fetchRuns();
}

async function refreshSqliteTables() {
  const tablesPayload = await fetchSqliteTables();
  sqliteTables.value = tablesPayload.tables;
  sqliteSupportedTables.value = tablesPayload.supported_tables;
}

async function refreshSystem() {
  isSystemLoading.value = true;
  try {
    const [status, tablesPayload, envResult] = await Promise.all([
      fetchSqliteStatus(),
      fetchSqliteTables(),
      fetchEnvCheck(),
    ]);
    sqliteStatus.value = status;
    sqliteTables.value = tablesPayload.tables;
    sqliteSupportedTables.value = tablesPayload.supported_tables;
    envCheck.value = envResult;
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isSystemLoading.value = false;
  }
}

async function loadData() {
  isDataLoading.value = true;
  try {
    const [status, stats, rows, tablesPayload] = await Promise.all([
      fetchSqliteStatus(),
      fetchSqliteStats(dataFilters.value),
      fetchSqliteRows(dataFilters.value),
      fetchSqliteTables(),
    ]);
    sqliteStatus.value = status;
    sqliteStats.value = stats;
    sqliteRows.value = rows;
    sqliteTables.value = tablesPayload.tables;
    sqliteSupportedTables.value = tablesPayload.supported_tables;
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isDataLoading.value = false;
  }
}

async function loadDataFiles() {
  isFileLoading.value = true;
  try {
    dataFiles.value = await fetchDataFiles({
      platform: dataFileFilters.value.platform || undefined,
      file_type: dataFileFilters.value.file_type || undefined,
    });

    const nextSelectedPath =
      dataFiles.value.find((file) => file.path === selectedDataFilePath.value)?.path ??
      dataFiles.value[0]?.path ??
      null;

    if (!nextSelectedPath) {
      selectedDataFilePath.value = null;
      selectedDataFilePreview.value = null;
      return;
    }

    if (nextSelectedPath !== selectedDataFilePath.value) {
      selectedDataFilePath.value = nextSelectedPath;
      return;
    }

    await loadSelectedFilePreview(nextSelectedPath);
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isFileLoading.value = false;
  }
}

async function loadSelectedFilePreview(filePath = selectedDataFilePath.value) {
  if (!filePath) {
    selectedDataFilePreview.value = null;
    return;
  }
  isFileLoading.value = true;
  try {
    selectedDataFilePreview.value = await fetchDataFilePreview(filePath, 100);
  } catch (error) {
    selectedDataFilePreview.value = null;
    errorMessage.value = (error as Error).message;
  } finally {
    isFileLoading.value = false;
  }
}

async function openDataRow(row: SqliteRow) {
  try {
    selectedDataRow.value = await fetchSqliteRow(dataFilters.value.table, Number(row.id));
  } catch (error) {
    errorMessage.value = (error as Error).message;
  }
}

function scheduleDataLoad() {
  if (dataTimer) window.clearTimeout(dataTimer);
  dataTimer = window.setTimeout(() => {
    void loadData();
  }, 200);
}

function scheduleFileLoad() {
  if (fileTimer) window.clearTimeout(fileTimer);
  fileTimer = window.setTimeout(() => {
    void loadDataFiles();
  }, 200);
}

async function triggerPreview() {
  if (!selectedTask.value) {
    preview.value = null;
    return;
  }
  if (previewTimer) window.clearTimeout(previewTimer);
  previewTimer = window.setTimeout(async () => {
    isPreviewLoading.value = true;
    try {
      preview.value = await fetchTaskPreview(
        selectedTask.value!.slug,
        formParams.value,
        selectedPresetId.value,
      );
    } catch (error) {
      preview.value = null;
      errorMessage.value = (error as Error).message;
    } finally {
      isPreviewLoading.value = false;
    }
  }, 180);
}

function connectSocket() {
  socketState.value = "connecting";
  if (socket) socket.close();
  socket = new WebSocket(activeRunSocketUrl());
  socket.onopen = () => {
    socketState.value = "connected";
  };
  socket.onmessage = async (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "run_updated" && payload.run) {
      const nextRun = payload.run as TaskRun;
      activeRun.value = nextRun;
      if (!selectedRunId.value && nextRun.task_slug === selectedTaskSlug.value) {
        selectedRunId.value = nextRun.id;
        applyRunDataContext(nextRun);
      } else if (selectedRunId.value === nextRun.id && nextRun.task_slug === selectedTaskSlug.value) {
        applyRunDataContext(nextRun);
      }
      if (nextRun.status !== "running") {
        await refreshRunsList();
      }
      return;
    }
    if (payload.type === "log" && payload.entry) {
      if (payload.run_id === selectedRunId.value) {
        logs.value = [...logs.value, payload.entry as TaskLogEntry].slice(-4000);
      }
    }
  };
  socket.onerror = () => {
    socketState.value = "disconnected";
  };
  socket.onclose = () => {
    socketState.value = "disconnected";
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    reconnectTimer = window.setTimeout(connectSocket, 2000);
  };
}

function handleSelectTask(taskSlug: string) {
  selectedTaskSlug.value = taskSlug;
  selectedMainTab.value = "config";
  resetMessages();
  const preset =
    presets.value.filter((item) => item.task_slug === taskSlug).find((item) => item.is_default) ??
    presets.value.filter((item) => item.task_slug === taskSlug)[0] ??
    null;
  applyPreset(preset);
  const scopedRun =
    [activeRun.value, ...runs.value].find(
      (run): run is TaskRun => run !== null && run.task_slug === taskSlug,
    ) ?? null;
  selectedRunId.value = scopedRun?.id ?? null;
  selectedExecutionJobRef.value = firstJobRef(scopedRun);
  if (scopedRun) {
    applyRunDataContext(scopedRun);
    return;
  }
  applyTaskDataDefaults(taskSlug);
}

function handleSelectPreset(presetId: string | null) {
  const preset = selectedTaskPresets.value.find((item) => item.id === presetId) ?? null;
  applyPreset(preset);
}

function isBrowsermintQrcode(
  params: Record<string, unknown> | TaskRun["normalized_params"] | null | undefined,
): boolean {
  const browserProvider = String(params?.browser_provider ?? "local").trim().toLowerCase();
  const loginType = String(params?.login_type ?? "").trim().toLowerCase();
  return browserProvider === "browsermint" && loginType === "qrcode";
}

async function handleCreatePreset() {
  if (!selectedTask.value) return;
  isSavingPreset.value = true;
  resetMessages();
  try {
    const preset = await createPreset({
      task_slug: selectedTask.value.slug,
      name: presetName.value || `${selectedTask.value.title} 预设`,
      params: formParams.value,
      is_default: presetIsDefault.value,
    });
    presets.value = await fetchPresets();
    applyPreset(presets.value.find((item) => item.id === preset.id) ?? preset);
    message.value = "预设已保存";
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isSavingPreset.value = false;
  }
}

async function handleUpdatePreset() {
  if (!selectedPreset.value) return;
  isSavingPreset.value = true;
  resetMessages();
  try {
    const preset = await updatePreset(selectedPreset.value.id, {
      name: presetName.value || selectedPreset.value.name,
      params: formParams.value,
      is_default: presetIsDefault.value,
    });
    presets.value = await fetchPresets();
    applyPreset(presets.value.find((item) => item.id === preset.id) ?? preset);
    message.value = "预设已更新";
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isSavingPreset.value = false;
  }
}

async function handleDeletePreset() {
  if (!selectedPreset.value) return;
  if (!window.confirm(`删除预设 “${selectedPreset.value.name}” 吗？`)) return;
  resetMessages();
  try {
    await deletePreset(selectedPreset.value.id);
    presets.value = await fetchPresets();
    const fallback =
      presets.value.filter((item) => item.task_slug === selectedTaskSlug.value).find((item) => item.is_default) ??
      presets.value.filter((item) => item.task_slug === selectedTaskSlug.value)[0] ??
      null;
    applyPreset(fallback);
    message.value = "预设已删除";
  } catch (error) {
    errorMessage.value = (error as Error).message;
  }
}

async function handleStartRun() {
  if (!selectedTask.value) return;
  const needsBrowsermintQrcodeGuide = isBrowsermintQrcode(formParams.value);
  const deepLink = guideBrowsermintDeepLink.value;
  const popup =
    needsBrowsermintQrcodeGuide && deepLink
      ? window.open(deepLink, "_blank", "noopener")
      : null;

  isStartingRun.value = true;
  resetMessages();
  try {
    const run = await startRun({
      task_slug: selectedTask.value.slug,
      params: formParams.value,
      preset_id: selectedPresetId.value,
    });
    activeRun.value = run;
    selectedRunId.value = run.id;
    selectedExecutionJobRef.value = firstJobRef(run);
    logs.value = [];
    await refreshRunsList();
    if (isBrowsermintQrcode(run.normalized_params)) {
      message.value = "任务已启动，请在 Browsermint 会话完成扫码后返回执行页查看日志。";
      if (!popup && deepLink) {
        window.open(deepLink, "_blank", "noopener");
      }
    } else {
      message.value = "任务已启动";
      if (popup && !popup.closed) {
        popup.close();
      }
    }
    selectedMainTab.value = "execution";
  } catch (error) {
    if (popup && !popup.closed) {
      popup.close();
    }
    errorMessage.value = (error as Error).message;
  } finally {
    isStartingRun.value = false;
  }
}

function handleOpenBrowsermint() {
  if (!selectedBrowsermintSession.value?.deep_link_url) return;
  window.open(selectedBrowsermintSession.value.deep_link_url, "_blank", "noopener");
}

function handleOpenGuideBrowsermint() {
  if (!guideBrowsermintDeepLink.value) return;
  window.open(guideBrowsermintDeepLink.value, "_blank", "noopener");
}

async function handleStopRun() {
  resetMessages();
  try {
    const run = await stopActiveRun();
    activeRun.value = run;
    message.value = "已发送停止信号";
  } catch (error) {
    errorMessage.value = (error as Error).message;
  }
}

async function handleInitSqlite() {
  isInitializingSqlite.value = true;
  resetMessages();
  try {
    sqliteStatus.value = await initSqlite();
    await refreshSystem();
    if (selectedMainTab.value === "data") {
      if (selectedDataMode.value === "sqlite") {
        await loadData();
      } else {
        await loadDataFiles();
      }
    }
    message.value = "SQLite 已初始化";
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isInitializingSqlite.value = false;
  }
}

function applyRunDataContext(run: TaskRun) {
  const saveOption = resolveSaveOption(run.normalized_params);
  const runPlatforms = resolveRunPlatforms(run);
  selectedDataMode.value = preferredDataMode(run.task_slug, saveOption);

  dataFilters.value = {
    ...dataFilters.value,
    table: preferredDataTable(run.task_slug),
    run_id: run.id,
    task_slug: run.task_slug,
    platform: "",
    entity_type: "",
    clean_status: "",
    q: "",
    offset: 0,
  };
  selectedDataRow.value = null;

  dataFileFilters.value = {
    ...dataFileFilters.value,
    platform: runPlatforms.length === 1 ? runPlatforms[0] : "",
    file_type: preferredFileType(saveOption),
    q: "",
  };
  selectedDataFilePath.value = null;
  selectedDataFilePreview.value = null;
}

function clearRunDataContext() {
  applyTaskDataDefaults(selectedTaskSlug.value);
}

function handleSelectRun(runId: string) {
  const run = findRun(runId);
  if (!run || run.task_slug !== selectedTaskSlug.value) return;
  selectedRunId.value = run.id;
  selectedExecutionJobRef.value = firstJobRef(run);
  applyRunDataContext(run);
}

function handleRunSwitch(runId: string) {
  if (!runId) return;
  handleSelectRun(runId);
}

function updateField(key: string, value: unknown) {
  formParams.value = {
    ...formParams.value,
    [key]: value,
  };
}

function updateDataFilter(key: keyof SqliteRowFilters, value: string | number) {
  dataFilters.value = {
    ...dataFilters.value,
    [key]: value,
    offset: key === "offset" ? Number(value) : 0,
  };
  if (key === "table") {
    selectedDataRow.value = null;
  }
}

function updateFileFilter(key: keyof DataFileFilters, value: string) {
  dataFileFilters.value = {
    ...dataFileFilters.value,
    [key]: value,
  };
  if (key === "platform" || key === "file_type") {
    selectedDataFilePath.value = null;
    selectedDataFilePreview.value = null;
  }
}

watch(
  groupedFields,
  () => {
    ensureSelectedConfigGroup();
  },
  { immediate: true },
);

watch(
  formParams,
  () => {
    saveDraft();
    if (!selectedRunId.value) {
      selectedDataMode.value = preferredDataMode(selectedTaskSlug.value, resolveSaveOption(formParams.value));
    }
    void triggerPreview();
  },
  { deep: true },
);

watch(
  () => [selectedTaskSlug.value, String(formParams.value.browser_provider ?? "")],
  ([taskSlug, provider]) => {
    const task = tasks.value.find((item) => item.slug === taskSlug);
    const supportsBrowsermint = Boolean(task?.fields.some((field) => field.key === "browser_provider"));
    if (supportsBrowsermint && provider === "browsermint") {
      void loadBrowsermintSessions(true);
    }
  },
  { immediate: false },
);

watch(
  () => [activeRun.value?.id, String(activeRun.value?.normalized_params?.browser_provider ?? "")],
  ([, providerRaw]) => {
    const provider = String(providerRaw ?? "").trim().toLowerCase();
    if (
      provider === "browsermint"
      && !browsermintSessions.value.length
      && !isBrowsermintLoading.value
    ) {
      void loadBrowsermintSessions(true);
    }
  },
  { immediate: true },
);

watch(
  displayedRun,
  async (run) => {
    selectedExecutionJobRef.value = firstJobRef(run);
    if (run?.id) {
      logs.value = await fetchRunLogs(run.id, 1000);
    } else {
      logs.value = [];
    }
  },
  { immediate: false },
);

watch(
  selectedMainTab,
  (tab) => {
    if (tab === "data") {
      if (selectedDataMode.value === "sqlite") {
        scheduleDataLoad();
      } else {
        scheduleFileLoad();
      }
    }
  },
  { immediate: false },
);

watch(
  isSystemPanelOpen,
  (open) => {
    if (open) {
      void refreshSystem();
    }
  },
  { immediate: false },
);

watch(
  dataFilters,
  () => {
    if (selectedMainTab.value === "data" && selectedDataMode.value === "sqlite") {
      scheduleDataLoad();
    }
  },
  { deep: true },
);

watch(
  () => [dataFileFilters.value.platform, dataFileFilters.value.file_type],
  () => {
    if (selectedMainTab.value === "data" && selectedDataMode.value === "files") {
      scheduleFileLoad();
    }
  },
);

watch(
  selectedDataMode,
  (mode) => {
    if (selectedMainTab.value !== "data") return;
    if (mode === "sqlite") {
      scheduleDataLoad();
      return;
    }
    scheduleFileLoad();
  },
);

watch(
  selectedDataFilePath,
  (filePath) => {
    if (selectedMainTab.value === "data" && selectedDataMode.value === "files") {
      void loadSelectedFilePreview(filePath);
    }
  },
);

onMounted(() => {
  void initialize();
  clockTimer = window.setInterval(() => {
    now.value = Date.now();
  }, 1000);
});

onBeforeUnmount(() => {
  if (previewTimer) window.clearTimeout(previewTimer);
  if (dataTimer) window.clearTimeout(dataTimer);
  if (fileTimer) window.clearTimeout(fileTimer);
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  if (clockTimer) window.clearInterval(clockTimer);
  socket?.close();
});
</script>

<template>
  <div class="workspace-shell">
    <WorkspaceSidebar
      :tasks="tasks"
      :selected-task-slug="selectedTaskSlug"
      :current-preset-name="currentPresetName"
      :recent-runs="recentRuns"
      :active-run="taskActiveRun"
      :selected-run-id="selectedRunId"
      :socket-state="socketState"
      :sqlite-ready="Boolean(sqliteStatus?.initialized)"
      @select-task="handleSelectTask"
      @select-run="handleSelectRun"
    />

    <main class="workspace-main">
      <TopActionBar
        :presets="selectedTaskPresets"
        :selected-preset-id="selectedPresetId"
        :preset-name="presetName"
        :preset-is-default="presetIsDefault"
        :has-unsaved-changes="hasUnsavedChanges"
        :active-run="taskActiveRun"
        :sqlite-status="sqliteStatus"
        :is-saving-preset="isSavingPreset"
        :is-starting-run="isStartingRun"
        @select-preset="handleSelectPreset"
        @update:preset-name="presetName = $event"
        @update:preset-is-default="presetIsDefault = $event"
        @create-preset="handleCreatePreset"
        @update-preset="handleUpdatePreset"
        @delete-preset="handleDeletePreset"
        @start-run="handleStartRun"
        @stop-run="handleStopRun"
      />

      <section v-if="otherTaskActiveRun || runStartGuide || message || errorMessage" class="workspace-messages">
        <div v-if="otherTaskActiveRun" class="message-banner warning">
          当前全局活跃任务为 {{ otherTaskActiveRun.title }}，你正在浏览 {{ selectedTask?.title || "当前任务" }} 的配置与历史运行。
        </div>
        <div v-if="runStartGuide" class="message-banner info guide-banner">
          <div class="guide-copy">
            <strong>{{ runStartGuide.title }}</strong>
            <span>{{ runStartGuide.detail }}</span>
          </div>
          <div class="guide-actions">
            <button
              v-if="runStartGuide.openBrowsermint"
              type="button"
              class="btn secondary small"
              @click="handleOpenGuideBrowsermint"
            >
              {{ runStartGuide.openLabel }}
            </button>
            <button
              v-if="taskActiveRun?.status === 'running' && selectedMainTab !== 'execution'"
              type="button"
              class="btn ghost small"
              @click="selectedMainTab = 'execution'"
            >
              查看运行监控
            </button>
          </div>
        </div>
        <div v-if="message" class="message-banner success">{{ message }}</div>
        <div v-if="errorMessage" class="message-banner error">{{ errorMessage }}</div>
      </section>

      <section class="tab-strip">
        <nav class="main-tabs">
          <button
            v-for="tab in mainTabs"
            :key="tab.key"
            class="main-tab"
            :class="{ active: selectedMainTab === tab.key }"
            @click="selectedMainTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </nav>

        <button type="button" class="btn ghost tab-strip-button" @click="isSystemPanelOpen = true">
          系统工具
        </button>
      </section>

      <section v-if="isLoading" class="loading-screen">任务中心加载中…</section>

      <template v-else>
        <section
          v-if="selectedMainTab === 'execution' || selectedMainTab === 'data'"
          class="run-context-bar"
          :class="{ empty: !displayedRun }"
        >
          <div v-if="displayedRun" class="run-context-copy">
            <p class="workspace-kicker">Run Context</p>
            <h3>{{ displayedRun.title }}</h3>
            <p>{{ displayedRun.id }} · {{ formatDateTime(displayedRun.started_at) }}</p>
          </div>
          <div v-if="displayedRun" class="run-context-metrics">
            <div class="run-context-metric">
              <span>状态</span>
              <strong class="metric-chip" :class="runStatusTone(displayedRun.status)">{{ displayedRun.status }}</strong>
            </div>
            <div class="run-context-metric">
              <span>Accepted</span>
              <strong>{{ displayedRun.metrics.accepted }}</strong>
            </div>
            <div class="run-context-metric">
              <span>Filtered</span>
              <strong>{{ displayedRun.metrics.filtered }}</strong>
            </div>
            <div class="run-context-metric">
              <span>Deduped</span>
              <strong>{{ displayedRun.metrics.deduped }}</strong>
            </div>
          </div>
          <div v-if="displayedRun" class="run-context-actions">
            <div class="run-switch-field">
              <span>当前 run</span>
              <select
                :value="displayedRun.id"
                :disabled="!taskRuns.length"
                @change="handleRunSwitch(($event.target as HTMLSelectElement).value)"
              >
                <option v-for="option in runSelectOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>
          </div>
          <div v-else class="empty-state compact">当前任务还没有可用的运行记录。</div>
        </section>

        <ConfigTab
          v-if="selectedMainTab === 'config'"
          :groups="groupedFields"
          :selected-group="selectedConfigGroup"
          :form-params="formParams"
          :preview-loading="isPreviewLoading"
          :browsermint-loading="isBrowsermintLoading"
          :browsermint-session-disabled="!browsermintConfigured || !browsermintSessions.length"
          :browsermint-selected-session="selectedBrowsermintSession"
          @select-group="selectedConfigGroup = $event"
          @update-field="updateField"
          @open-browsermint="handleOpenBrowsermint"
          @refresh-browsermint="loadBrowsermintSessions(true)"
        />

        <CommandsTab
          v-else-if="selectedMainTab === 'commands'"
          :preview="preview"
          :sqlite-status="sqliteStatus"
          :storage-summary="storageSummary"
        />

        <ExecutionTab
          v-else-if="selectedMainTab === 'execution'"
          :run="displayedRun"
          :logs="logs"
          :selected-job-ref="selectedExecutionJobRef"
          :now="now"
          @select-job="selectedExecutionJobRef = $event"
        />

        <DataTab
          v-else
          :mode="selectedDataMode"
          :tables="sqliteTables"
          :supported-tables="sqliteSupportedTables"
          :filters="dataFilters"
          :file-filters="dataFileFilters"
          :files="dataFiles"
          :selected-file-path="selectedDataFilePath"
          :file-preview="selectedDataFilePreview"
          :stats="sqliteStats"
          :rows="sqliteRows"
          :selected-row="selectedDataRow"
          :selected-run="displayedRun"
          :loading="isDataLoading"
          :file-loading="isFileLoading"
          :sqlite-path="sqliteStatus?.path ?? 'runtime/data/sqlite.db'"
          @update-filter="updateDataFilter"
          @update-file-filter="updateFileFilter"
          @switch-mode="selectedDataMode = $event"
          @select-file="selectedDataFilePath = $event"
          @refresh="loadData"
          @refresh-files="loadDataFiles"
          @open-row="openDataRow"
          @close-row="selectedDataRow = null"
          @focus-execution="selectedMainTab = 'execution'"
          @clear-run-filter="clearRunDataContext"
        />
      </template>
    </main>

    <transition name="panel-fade">
      <div v-if="isSystemPanelOpen" class="system-panel-layer">
        <button
          type="button"
          class="system-panel-backdrop"
          aria-label="关闭系统工具面板"
          @click="isSystemPanelOpen = false"
        />
        <aside class="system-panel">
          <div class="system-panel-head">
            <div>
              <p class="workspace-kicker">System Tools</p>
              <h3>系统工具面板</h3>
              <p>查看 SQLite、watchdog 和环境检查，不打断主工作流。</p>
            </div>
            <button type="button" class="btn ghost small" @click="isSystemPanelOpen = false">
              关闭
            </button>
          </div>

          <SystemTab
            :sqlite-status="sqliteStatus"
            :tables="sqliteTables"
            :env-check="envCheck"
            :loading="isSystemLoading"
            :init-loading="isInitializingSqlite"
            @init-sqlite="handleInitSqlite"
            @refresh-system="refreshSystem"
          />
        </aside>
      </div>
    </transition>
  </div>
</template>
