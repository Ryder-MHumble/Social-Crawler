<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  activeRunSocketUrl,
  createPreset,
  deletePreset,
  fetchActiveRun,
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

type MainTab = "config" | "commands" | "execution" | "data" | "system";

const mainTabs: Array<{ key: MainTab; label: string }> = [
  { key: "config", label: "配置" },
  { key: "commands", label: "命令" },
  { key: "execution", label: "执行" },
  { key: "data", label: "数据" },
  { key: "system", label: "系统" },
];

const tasks = ref<TaskTemplate[]>([]);
const presets = ref<TaskPreset[]>([]);
const runs = ref<TaskRun[]>([]);
const activeRun = ref<TaskRun | null>(null);
const logs = ref<TaskLogEntry[]>([]);
const preview = ref<TaskPreview | null>(null);

const sqliteStatus = ref<SqliteStatus | null>(null);
const sqliteTables = ref<SqliteTableSummary[]>([]);
const sqliteSupportedTables = ref<string[]>([]);
const sqliteStats = ref<SqliteStats | null>(null);
const sqliteRows = ref<SqliteRowsResponse | null>(null);
const selectedDataRow = ref<SqliteRow | null>(null);
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

const isLoading = ref(true);
const isPreviewLoading = ref(false);
const isSavingPreset = ref(false);
const isStartingRun = ref(false);
const isSystemLoading = ref(false);
const isDataLoading = ref(false);
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

let previewTimer: number | null = null;
let dataTimer: number | null = null;
let reconnectTimer: number | null = null;
let clockTimer: number | null = null;
let socket: WebSocket | null = null;

const selectedTask = computed(
  () => tasks.value.find((task) => task.slug === selectedTaskSlug.value) ?? null,
);

const selectedTaskPresets = computed(() =>
  presets.value.filter((preset) => preset.task_slug === selectedTaskSlug.value),
);

const selectedPreset = computed(
  () => selectedTaskPresets.value.find((preset) => preset.id === selectedPresetId.value) ?? null,
);

const visibleFields = computed(() =>
  (selectedTask.value?.fields ?? []).filter((field) => isFieldVisible(field)),
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

const displayedRun = computed(() => {
  if (selectedRunId.value && activeRun.value?.id === selectedRunId.value) {
    return activeRun.value;
  }
  if (selectedRunId.value) {
    return runs.value.find((run) => run.id === selectedRunId.value) ?? activeRun.value ?? null;
  }
  return activeRun.value ?? runs.value[0] ?? null;
});

const recentRuns = computed(() =>
  runs.value
    .filter((run) => run.id !== activeRun.value?.id)
    .slice(0, 8),
);

const currentPresetName = computed(
  () => selectedPreset.value?.name || presetName.value || "任务默认值",
);

const storageSummary = computed(() => {
  if (selectedTaskSlug.value === "creator_outreach") {
    return "SQLite · candidate / delivery tables";
  }
  const saveOption = String(formParams.value.save_option ?? formParams.value.save_data_option ?? "").trim();
  if (saveOption === "sqlite") return "SQLite · crawl tables + observations";
  if (!saveOption) return "默认输出 · 任务定义决定";
  return `${saveOption.toUpperCase()} · 非 SQLite`;
});

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

    selectedRunId.value = loadedActiveRun?.id ?? loadedRuns[0]?.id ?? null;
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
      if (!selectedRunId.value) {
        selectedRunId.value = nextRun.id;
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
  resetMessages();
  const preset =
    presets.value.filter((item) => item.task_slug === taskSlug).find((item) => item.is_default) ??
    presets.value.filter((item) => item.task_slug === taskSlug)[0] ??
    null;
  applyPreset(preset);
}

function handleSelectPreset(presetId: string | null) {
  const preset = selectedTaskPresets.value.find((item) => item.id === presetId) ?? null;
  applyPreset(preset);
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
    message.value = "任务已启动";
    selectedMainTab.value = "execution";
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isStartingRun.value = false;
  }
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
      await loadData();
    }
    message.value = "SQLite 已初始化";
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isInitializingSqlite.value = false;
  }
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
    void triggerPreview();
  },
  { deep: true },
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
      scheduleDataLoad();
    }
    if (tab === "system") {
      void refreshSystem();
    }
  },
  { immediate: false },
);

watch(
  dataFilters,
  () => {
    if (selectedMainTab.value === "data") {
      scheduleDataLoad();
    }
  },
  { deep: true },
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
      :active-run="activeRun"
      :selected-run-id="selectedRunId"
      :socket-state="socketState"
      :sqlite-ready="Boolean(sqliteStatus?.initialized)"
      @select-task="handleSelectTask"
      @select-run="selectedRunId = $event"
    />

    <main class="workspace-main">
      <TopActionBar
        :presets="selectedTaskPresets"
        :selected-preset-id="selectedPresetId"
        :preset-name="presetName"
        :preset-is-default="presetIsDefault"
        :has-unsaved-changes="hasUnsavedChanges"
        :active-run="activeRun"
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

      <section class="workspace-header">
        <div>
          <p class="workspace-kicker">{{ selectedTask?.slug || "task-center" }}</p>
          <h2>{{ selectedTask?.title || "任务工作台" }}</h2>
          <p>{{ selectedTask?.description || "把任务、命令、执行和数据集中到一个控制台里。" }}</p>
        </div>
        <div class="workspace-capabilities">
          <span v-for="capability in selectedTask?.capabilities ?? []" :key="capability">
            {{ capability }}
          </span>
        </div>
      </section>

      <section v-if="message || errorMessage" class="workspace-messages">
        <div v-if="message" class="message-banner success">{{ message }}</div>
        <div v-if="errorMessage" class="message-banner error">{{ errorMessage }}</div>
      </section>

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

      <section v-if="isLoading" class="loading-screen">任务中心加载中…</section>

      <ConfigTab
        v-else-if="selectedMainTab === 'config'"
        :groups="groupedFields"
        :selected-group="selectedConfigGroup"
        :form-params="formParams"
        :preview-loading="isPreviewLoading"
        @select-group="selectedConfigGroup = $event"
        @update-field="updateField"
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
        v-else-if="selectedMainTab === 'data'"
        :tables="sqliteTables"
        :supported-tables="sqliteSupportedTables"
        :filters="dataFilters"
        :stats="sqliteStats"
        :rows="sqliteRows"
        :selected-row="selectedDataRow"
        :loading="isDataLoading"
        @update-filter="updateDataFilter"
        @refresh="loadData"
        @open-row="openDataRow"
        @close-row="selectedDataRow = null"
      />

      <SystemTab
        v-else
        :sqlite-status="sqliteStatus"
        :tables="sqliteTables"
        :env-check="envCheck"
        :loading="isSystemLoading"
        :init-loading="isInitializingSqlite"
        @init-sqlite="handleInitSqlite"
        @refresh-system="refreshSystem"
      />
    </main>
  </div>
</template>
