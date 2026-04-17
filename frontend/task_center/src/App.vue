<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  activeRunSocketUrl,
  createPreset,
  deletePreset,
  fetchActiveRun,
  fetchPresets,
  fetchRunLogs,
  fetchRuns,
  fetchTaskPreview,
  fetchTasks,
  startRun,
  stopActiveRun,
  updatePreset,
} from "./api";
import type {
  TaskFieldSchema,
  TaskLogEntry,
  TaskPreset,
  TaskPreview,
  TaskRun,
  TaskTemplate,
} from "./types";

const tasks = ref<TaskTemplate[]>([]);
const presets = ref<TaskPreset[]>([]);
const runs = ref<TaskRun[]>([]);
const activeRun = ref<TaskRun | null>(null);
const logs = ref<TaskLogEntry[]>([]);
const preview = ref<TaskPreview | null>(null);
const isLoading = ref(true);
const isPreviewLoading = ref(false);
const isSavingPreset = ref(false);
const isStartingRun = ref(false);
const message = ref("");
const errorMessage = ref("");
const selectedTaskSlug = ref("");
const selectedPresetId = ref<string | null>(null);
const presetName = ref("");
const presetIsDefault = ref(false);
const formParams = ref<Record<string, unknown>>({});

let previewTimer: number | null = null;
let socket: WebSocket | null = null;
let reconnectTimer: number | null = null;

const selectedTask = computed(() =>
  tasks.value.find((task) => task.slug === selectedTaskSlug.value) ?? null,
);

const selectedPreset = computed(() =>
  presets.value.find((preset) => preset.id === selectedPresetId.value) ?? null,
);

const selectedTaskPresets = computed(() =>
  presets.value.filter((preset) => preset.task_slug === selectedTaskSlug.value),
);

const groupedFields = computed(() => {
  const groups = new Map<string, TaskFieldSchema[]>();
  for (const field of selectedTask.value?.fields ?? []) {
    if (!isFieldVisible(field)) {
      continue;
    }
    const group = groups.get(field.group) ?? [];
    group.push(field);
    groups.set(field.group, group);
  }
  return Array.from(groups.entries());
});

function isFieldVisible(field: TaskFieldSchema): boolean {
  if (!field.visible_when) {
    return true;
  }
  return Object.entries(field.visible_when).every(([key, expected]) => {
    return formParams.value[key] === expected;
  });
}

function isFieldDisabled(field: TaskFieldSchema): boolean {
  if (!field.disabled_when) {
    return false;
  }
  return Object.entries(field.disabled_when).every(([key, expected]) => {
    return formParams.value[key] === expected;
  });
}

function taskDraftKey(taskSlug: string): string {
  return `task_center_draft:${taskSlug}`;
}

function cloneParams(input: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(input));
}

function applyPreset(preset: TaskPreset | null) {
  if (!selectedTask.value) {
    return;
  }
  selectedPresetId.value = preset?.id ?? null;
  presetName.value = preset?.name ?? "";
  presetIsDefault.value = preset?.is_default ?? false;
  const base = preset ? cloneParams(preset.params) : cloneParams(selectedTask.value.defaults);
  const draft = loadDraft(selectedTask.value.slug);
  formParams.value = draft ? { ...base, ...draft } : base;
  triggerPreview();
}

function loadDraft(taskSlug: string): Record<string, unknown> | null {
  const raw = window.localStorage.getItem(taskDraftKey(taskSlug));
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function saveDraft() {
  if (!selectedTaskSlug.value) {
    return;
  }
  window.localStorage.setItem(
    taskDraftKey(selectedTaskSlug.value),
    JSON.stringify(formParams.value),
  );
}

async function initialize() {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    const [loadedTasks, loadedPresets, loadedRuns, loadedActiveRun] = await Promise.all([
      fetchTasks(),
      fetchPresets(),
      fetchRuns(),
      fetchActiveRun(),
    ]);
    tasks.value = loadedTasks;
    presets.value = loadedPresets;
    runs.value = loadedRuns;
    activeRun.value = loadedActiveRun;

    const defaultPreset =
      loadedPresets.find((preset) => preset.is_default) ??
      loadedPresets.find((preset) => preset.task_slug === "sentiment_monitor") ??
      loadedPresets[0];
    const initialTaskSlug = defaultPreset?.task_slug ?? loadedTasks[0]?.slug ?? "";
    if (initialTaskSlug) {
      selectedTaskSlug.value = initialTaskSlug;
      const preset =
        loadedPresets.find((item) => item.id === defaultPreset?.id) ??
        loadedPresets.find((item) => item.task_slug === initialTaskSlug) ??
        null;
      applyPreset(preset);
    }
    if (loadedActiveRun) {
      logs.value = await fetchRunLogs(loadedActiveRun.id, 300);
    }
    connectSocket();
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isLoading.value = false;
  }
}

function connectSocket() {
  if (socket) {
    socket.close();
  }
  socket = new WebSocket(activeRunSocketUrl());
  socket.onmessage = async (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "run_updated" && payload.run) {
      activeRun.value = payload.run as TaskRun;
      if (activeRun.value.status !== "running") {
        runs.value = await fetchRuns();
      }
      return;
    }
    if (payload.type === "log" && payload.entry) {
      logs.value = [...logs.value, payload.entry as TaskLogEntry].slice(-300);
      return;
    }
  };
  socket.onclose = () => {
    if (reconnectTimer) {
      window.clearTimeout(reconnectTimer);
    }
    reconnectTimer = window.setTimeout(connectSocket, 2000);
  };
}

async function triggerPreview() {
  if (!selectedTask.value) {
    preview.value = null;
    return;
  }
  if (previewTimer) {
    window.clearTimeout(previewTimer);
  }
  previewTimer = window.setTimeout(async () => {
    isPreviewLoading.value = true;
    errorMessage.value = "";
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
  }, 240);
}

function selectTask(task: TaskTemplate) {
  selectedTaskSlug.value = task.slug;
  const preset =
    selectedTaskPresets.value.find((item) => item.is_default) ??
    selectedTaskPresets.value[0] ??
    null;
  applyPreset(preset);
}

function selectPreset(preset: TaskPreset) {
  applyPreset(preset);
}

function updateField(field: TaskFieldSchema, event: Event) {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
  if (field.component === "number") {
    formParams.value[field.key] = target.value === "" ? "" : Number(target.value);
  } else if (field.component === "switch") {
    formParams.value[field.key] = (target as HTMLInputElement).checked;
  } else {
    formParams.value[field.key] = target.value;
  }
}

function toggleMultiValue(fieldKey: string, value: string, checked: boolean) {
  const current = Array.isArray(formParams.value[fieldKey])
    ? [...(formParams.value[fieldKey] as string[])]
    : [];
  if (checked && !current.includes(value)) {
    current.push(value);
  }
  if (!checked) {
    const next = current.filter((item) => item !== value);
    formParams.value[fieldKey] = next;
    return;
  }
  formParams.value[fieldKey] = current;
}

async function handleCreatePreset() {
  if (!selectedTask.value) {
    return;
  }
  isSavingPreset.value = true;
  errorMessage.value = "";
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
  if (!selectedPreset.value) {
    return;
  }
  isSavingPreset.value = true;
  errorMessage.value = "";
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
  if (!selectedPreset.value) {
    return;
  }
  if (!window.confirm(`删除预设 “${selectedPreset.value.name}” 吗？`)) {
    return;
  }
  errorMessage.value = "";
  try {
    await deletePreset(selectedPreset.value.id);
    presets.value = await fetchPresets();
    const fallback =
      selectedTaskPresets.value.find((item) => item.task_slug === selectedTaskSlug.value) ?? null;
    applyPreset(fallback);
    message.value = "预设已删除";
  } catch (error) {
    errorMessage.value = (error as Error).message;
  }
}

async function handleStartRun() {
  if (!selectedTask.value) {
    return;
  }
  isStartingRun.value = true;
  errorMessage.value = "";
  try {
    const run = await startRun({
      task_slug: selectedTask.value.slug,
      params: formParams.value,
      preset_id: selectedPresetId.value,
    });
    activeRun.value = run;
    logs.value = [];
    runs.value = await fetchRuns();
    message.value = "任务已启动";
  } catch (error) {
    errorMessage.value = (error as Error).message;
  } finally {
    isStartingRun.value = false;
  }
}

async function handleStopRun() {
  errorMessage.value = "";
  try {
    const run = await stopActiveRun();
    activeRun.value = run;
    message.value = "已发送停止信号";
  } catch (error) {
    errorMessage.value = (error as Error).message;
  }
}

watch(selectedTaskSlug, () => {
  message.value = "";
  errorMessage.value = "";
});

watch(
  formParams,
  () => {
    saveDraft();
    triggerPreview();
  },
  { deep: true },
);

onMounted(() => {
  void initialize();
});

onBeforeUnmount(() => {
  if (previewTimer) {
    window.clearTimeout(previewTimer);
  }
  if (reconnectTimer) {
    window.clearTimeout(reconnectTimer);
  }
  socket?.close();
});
</script>

<template>
  <div class="app-shell">
    <aside class="panel sidebar">
      <section class="brand">
        <p class="eyebrow">Task Center</p>
        <h1>Social Crawler 看板</h1>
        <p>把三类任务统一成“模板 + 参数 + 预设 + 运行状态”的操作面板。</p>
      </section>

      <section>
        <h2 class="section-title">任务方向</h2>
        <div class="stack">
          <button
            v-for="task in tasks"
            :key="task.slug"
            class="task-card"
            :class="{ 'is-active': task.slug === selectedTaskSlug }"
            @click="selectTask(task)"
          >
            <div class="task-title">{{ task.title }}</div>
            <small>{{ task.description }}</small>
          </button>
        </div>
      </section>

      <section>
        <h2 class="section-title">当前任务预设</h2>
        <div v-if="selectedTaskPresets.length" class="stack">
          <button
            v-for="preset in selectedTaskPresets"
            :key="preset.id"
            class="preset-item"
            :class="{ 'is-active': preset.id === selectedPresetId }"
            @click="selectPreset(preset)"
          >
            <strong>{{ preset.name }}</strong>
            <span class="muted">
              {{ preset.is_default ? "默认预设" : "自定义预设" }}
            </span>
          </button>
        </div>
        <div v-else class="empty">这个任务还没有预设。</div>
      </section>
    </aside>

    <main class="panel content">
      <section v-if="selectedTask" class="hero">
        <div>
          <p class="eyebrow">{{ selectedTask.slug }}</p>
          <h2 class="task-title">{{ selectedTask.title }}</h2>
          <p>{{ selectedTask.description }}</p>
        </div>
        <div class="stack">
          <span v-if="selectedTask.slug === 'creator_outreach'" class="badge bilibili-only">
            Bilibili only
          </span>
          <span class="badge">{{ selectedTask.fields.length }} 个参数入口</span>
        </div>
      </section>

      <div v-if="message" class="status-strip">
        <span>{{ message }}</span>
      </div>
      <div v-if="errorMessage" class="status-strip">
        <span>{{ errorMessage }}</span>
      </div>

      <div v-if="selectedTask" class="layout-row">
        <section class="stack">
          <article class="card">
            <div class="section-title">参数表单</div>
            <div class="cap-list">
              <span v-for="cap in selectedTask.capabilities" :key="cap" class="cap-pill">
                {{ cap }}
              </span>
            </div>
            <div
              v-for="[groupName, fields] in groupedFields"
              :key="groupName"
              class="stack"
              style="margin-top: 18px"
            >
              <h3 class="section-title">{{ groupName }}</h3>
              <div class="field-grid">
                <div v-for="field in fields" :key="field.key" class="field">
                  <label :for="field.key">{{ field.label }}</label>

                  <textarea
                    v-if="field.component === 'textarea'"
                    :id="field.key"
                    :disabled="isFieldDisabled(field)"
                    :value="String(formParams[field.key] ?? '')"
                    @input="updateField(field, $event)"
                  />

                  <input
                    v-else-if="field.component === 'number'"
                    :id="field.key"
                    type="number"
                    :disabled="isFieldDisabled(field)"
                    :value="String(formParams[field.key] ?? '')"
                    @input="updateField(field, $event)"
                  />

                  <select
                    v-else-if="field.component === 'select'"
                    :id="field.key"
                    :disabled="isFieldDisabled(field)"
                    :value="String(formParams[field.key] ?? '')"
                    @change="updateField(field, $event)"
                  >
                    <option
                      v-for="option in field.options"
                      :key="String(option.value)"
                      :value="String(option.value)"
                    >
                      {{ option.label }}
                    </option>
                  </select>

                  <label v-else-if="field.component === 'switch'" class="switch">
                    <input
                      type="checkbox"
                      :checked="Boolean(formParams[field.key])"
                      :disabled="isFieldDisabled(field)"
                      @change="updateField(field, $event)"
                    />
                    <span>{{ Boolean(formParams[field.key]) ? "已开启" : "已关闭" }}</span>
                  </label>

                  <div v-else-if="field.component === 'multiselect'" class="chips">
                    <label
                      v-for="option in field.options"
                      :key="String(option.value)"
                      class="chip"
                    >
                      <input
                        type="checkbox"
                        :checked="Array.isArray(formParams[field.key]) &&
                          (formParams[field.key] as unknown[]).includes(option.value)"
                        :disabled="isFieldDisabled(field)"
                        @change="
                          toggleMultiValue(
                            field.key,
                            String(option.value),
                            ($event.target as HTMLInputElement).checked,
                          )
                        "
                      />
                      <span>{{ option.label }}</span>
                    </label>
                  </div>

                  <div v-if="field.description" class="field-help">
                    {{ field.description }}
                  </div>
                </div>
              </div>
            </div>
          </article>

          <article class="card">
            <div class="section-title">预设管理</div>
            <div class="stack">
              <div class="input-row">
                <input v-model="presetName" placeholder="预设名称" />
              </div>
              <label class="switch">
                <input v-model="presetIsDefault" type="checkbox" />
                <span>设为这个任务的默认预设</span>
              </label>
              <div class="actions">
                <button class="btn btn-primary" :disabled="isSavingPreset" @click="handleCreatePreset">
                  另存为新预设
                </button>
                <button
                  class="btn btn-secondary"
                  :disabled="!selectedPreset || isSavingPreset"
                  @click="handleUpdatePreset"
                >
                  更新当前预设
                </button>
                <button
                  class="btn btn-danger"
                  :disabled="!selectedPreset || isSavingPreset"
                  @click="handleDeletePreset"
                >
                  删除当前预设
                </button>
              </div>
            </div>
          </article>
        </section>

        <section class="stack">
          <article class="card">
            <div class="inline-actions" style="justify-content: space-between; align-items: center">
              <div class="section-title">命令预览</div>
              <span v-if="isPreviewLoading" class="badge">解析中</span>
            </div>
            <div v-if="preview" class="stack">
              <div
                v-for="stage in preview.spec.stages"
                :key="stage.key"
                class="stage-block"
              >
                <div class="stage-header">
                  <strong>{{ stage.name }}</strong>
                  <span class="muted">
                    {{ stage.concurrent ? "并行" : "串行" }} · {{ stage.jobs.length }} jobs
                  </span>
                </div>
                <pre
                  v-for="job in stage.jobs"
                  :key="job.key"
                  class="command-block"
                ><code>{{ job.display_command || job.command.join(" ") }}</code></pre>
              </div>
            </div>
            <div v-else class="empty">表单参数变更后会在这里展示解析出的实际任务。</div>
          </article>

          <article class="card">
            <div class="section-title">启动控制</div>
            <div class="actions">
              <button
                class="btn btn-primary"
                :disabled="!preview || isStartingRun || activeRun?.status === 'running'"
                @click="handleStartRun"
              >
                启动任务
              </button>
              <button
                class="btn btn-danger"
                :disabled="activeRun?.status !== 'running'"
                @click="handleStopRun"
              >
                停止当前任务
              </button>
            </div>
          </article>
        </section>
      </div>

      <div v-else-if="isLoading" class="empty">任务模板加载中…</div>
      <div v-else class="empty">没有可用任务模板。</div>
    </main>

    <aside class="panel activity">
      <section class="card">
        <div class="inline-actions" style="justify-content: space-between; align-items: center">
          <h2 class="section-title">当前运行</h2>
          <span v-if="activeRun" class="badge" :class="`status-${activeRun.status}`">
            {{ activeRun.status }}
          </span>
        </div>
        <div v-if="activeRun" class="stack">
          <div class="run-title">{{ activeRun.title }}</div>
          <div class="muted mono">{{ activeRun.id }}</div>
          <div
            v-for="stage in activeRun.stages"
            :key="stage.key"
            class="stage-block"
          >
            <div class="stage-header">
              <strong>{{ stage.name }}</strong>
              <span class="badge" :class="`status-${stage.status || 'waiting'}`">
                {{ stage.status || "waiting" }}
              </span>
            </div>
            <div class="stack">
              <div
                v-for="job in stage.jobs"
                :key="job.key"
                class="preset-item"
              >
                <strong>{{ job.name }}</strong>
                <span class="muted">
                  {{ job.status || "waiting" }} · {{ job.line_count ?? 0 }} lines
                </span>
                <span class="mono">{{ job.last_line || "暂无输出" }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty">当前没有运行中的任务。</div>
      </section>

      <section class="card">
        <h2 class="section-title">实时日志</h2>
        <div v-if="logs.length" class="log-list">
          <div
            v-for="entry in logs"
            :key="entry.id"
            class="log-entry"
            :class="`is-${entry.level}`"
          >
            <span class="mono">{{ entry.timestamp.slice(11, 19) }}</span>
            <span class="badge">{{ entry.level }}</span>
            <span>{{ entry.message }}</span>
          </div>
        </div>
        <div v-else class="empty">运行中的日志会出现在这里。</div>
      </section>

      <section class="card">
        <h2 class="section-title">最近运行</h2>
        <div v-if="runs.length" class="stack">
          <div v-for="run in runs.slice(0, 8)" :key="run.id" class="run-item">
            <strong>{{ run.title }}</strong>
            <span class="muted mono">{{ run.id }}</span>
            <span class="badge" :class="`status-${run.status}`">{{ run.status }}</span>
          </div>
        </div>
        <div v-else class="empty">还没有运行历史。</div>
      </section>
    </aside>
  </div>
</template>
