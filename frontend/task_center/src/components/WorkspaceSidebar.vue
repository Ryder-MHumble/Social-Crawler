<script setup lang="ts">
import { computed, ref } from "vue";
import type { TaskRun, TaskTemplate } from "../types";

const props = defineProps<{
  tasks: TaskTemplate[];
  selectedTaskSlug: string;
  currentPresetName: string;
  recentRuns: TaskRun[];
  activeRun: TaskRun | null;
  selectedRunId: string | null;
  socketState: "connecting" | "connected" | "disconnected";
  sqliteReady: boolean;
}>();

const emit = defineEmits<{
  (event: "select-task", taskSlug: string): void;
  (event: "select-run", runId: string): void;
}>();

type RunFilterKey = "all" | "running" | "failed";

const runFilterOptions: Array<{ key: RunFilterKey; label: string }> = [
  { key: "all", label: "全部" },
  { key: "running", label: "运行中" },
  { key: "failed", label: "失败" },
];

const selectedRunFilter = ref<RunFilterKey>("all");

const socketLabel = computed(() => {
  if (props.socketState === "connected") return "已连接";
  if (props.socketState === "connecting") return "连接中";
  return "已断开";
});

const selectedTask = computed(
  () => props.tasks.find((task) => task.slug === props.selectedTaskSlug) ?? null,
);

const mergedRuns = computed(() => {
  const merged: TaskRun[] = [];
  const seen = new Set<string>();
  const pushRun = (run: TaskRun | null | undefined) => {
    if (!run || seen.has(run.id)) return;
    seen.add(run.id);
    merged.push(run);
  };
  pushRun(props.activeRun);
  props.recentRuns.forEach(pushRun);
  return merged;
});

const filteredRuns = computed(() => {
  const selected = selectedRunFilter.value;
  if (selected === "all") return mergedRuns.value;
  return mergedRuns.value.filter((run) => runFilterKey(run.status) === selected);
});

function formatTime(value?: string | null): string {
  if (!value) return "未运行";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function runHint(run: TaskRun): string {
  if (runFilterKey(run.status) === "running") return "查看执行回放";
  const saveOption = String(
    run.normalized_params.save_option ?? run.normalized_params.save_data_option ?? "",
  )
    .trim()
    .toLowerCase();
  if (["json", "csv", "excel"].includes(saveOption)) {
    return "查看文件结果";
  }
  return "查看清洗结果";
}

function normalizeStatus(status?: string | null): string {
  return String(status ?? "")
    .trim()
    .toLowerCase();
}

function runFilterKey(status?: string | null): RunFilterKey | "other" {
  const key = normalizeStatus(status);
  if (["running", "queued", "pending", "starting", "active", "in_progress"].includes(key)) {
    return "running";
  }
  if (
    [
      "failed",
      "error",
      "errored",
      "timeout",
      "cancelled",
      "canceled",
      "aborted",
      "stopped",
    ].includes(key)
  ) {
    return "failed";
  }
  return "other";
}

function statusLabel(status?: string | null): string {
  const key = normalizeStatus(status);
  if (runFilterKey(key) === "running") return "运行中";
  if (runFilterKey(key) === "failed") return "失败";
  if (["completed", "complete", "success", "succeeded", "done", "finished"].includes(key)) {
    return "已完成";
  }
  if (!key) return "未知";
  return String(status);
}

function statusTone(status?: string | null): "running" | "failed" | "done" | "neutral" {
  const key = normalizeStatus(status);
  if (runFilterKey(key) === "running") return "running";
  if (runFilterKey(key) === "failed") return "failed";
  if (["completed", "complete", "success", "succeeded", "done", "finished"].includes(key)) {
    return "done";
  }
  return "neutral";
}

function shortRunId(runId: string): string {
  const value = runId.trim();
  if (value.length <= 22) return value;
  return `${value.slice(0, 19)}...`;
}
</script>

<template>
  <aside class="workspace-sidebar">
    <section class="sidebar-brand-strip">
      <div class="brand-lockup">
        <p class="sidebar-kicker">Quiet Ops</p>
        <h1>Social-Crawler</h1>
      </div>
      <div class="brand-context">
        <span class="context-label">当前任务</span>
        <strong>{{ selectedTask?.title || "未选择任务" }}</strong>
      </div>
    </section>

    <section class="sidebar-system-strip" aria-label="系统状态">
      <span class="system-pill" :class="`is-${socketState}`">
        <span class="system-pill-label">Socket</span>
        <strong>{{ socketLabel }}</strong>
      </span>
      <span class="system-pill" :class="sqliteReady ? 'is-success' : 'is-warning'">
        <span class="system-pill-label">SQLite</span>
        <strong>{{ sqliteReady ? "已就绪" : "待初始化" }}</strong>
      </span>
      <span class="system-pill is-neutral preset-pill">
        <span class="system-pill-label">Preset</span>
        <strong>{{ currentPresetName || "任务默认值" }}</strong>
      </span>
    </section>

    <section class="sidebar-block task-block">
      <div class="sidebar-block-head">
        <div>
          <p>Task Set</p>
          <h2>任务空间</h2>
        </div>
        <span>{{ tasks.length }}</span>
      </div>
      <div class="sidebar-list">
        <button
          v-for="task in tasks"
          :key="task.slug"
          class="sidebar-item task-item"
          :class="{ active: task.slug === selectedTaskSlug }"
          @click="emit('select-task', task.slug)"
        >
          <strong>{{ task.title }}</strong>
          <span>{{ task.slug }}</span>
        </button>
      </div>
    </section>

    <section class="sidebar-block sidebar-runs">
      <div class="sidebar-block-head">
        <div>
          <p>Run Switcher</p>
          <h2>最近运行</h2>
        </div>
        <span>{{ filteredRuns.length }}/{{ mergedRuns.length }}</span>
      </div>
      <div class="run-filters" role="tablist" aria-label="运行记录筛选">
        <button
          v-for="filter in runFilterOptions"
          :key="filter.key"
          class="run-filter-tab"
          :class="{ active: selectedRunFilter === filter.key }"
          role="tab"
          :aria-selected="selectedRunFilter === filter.key"
          @click="selectedRunFilter = filter.key"
        >
          {{ filter.label }}
        </button>
      </div>
      <div class="sidebar-list run-list">
        <button
          v-for="run in filteredRuns"
          :key="run.id"
          class="sidebar-item run-item"
          :class="{ active: selectedRunId === run.id }"
          @click="emit('select-run', run.id)"
        >
          <div class="run-item-topline">
            <strong>{{ run.title }}</strong>
            <span class="run-status-chip" :class="`is-${statusTone(run.status)}`">
              {{ statusLabel(run.status) }}
            </span>
          </div>
          <div class="run-item-meta">
            <span class="run-item-id">{{ shortRunId(run.id) }}</span>
            <span>{{ formatTime(run.started_at) }}</span>
          </div>
          <small class="run-item-hint">{{ runHint(run) }}</small>
        </button>
        <p v-if="!filteredRuns.length" class="run-empty-tip">当前筛选下暂无运行记录</p>
      </div>
    </section>
  </aside>
</template>

<style scoped>
.workspace-sidebar {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  color: var(--ink, #17202b);
}

.sidebar-brand-strip,
.sidebar-block {
  border: 1px solid rgba(20, 28, 38, 0.1);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(247, 242, 234, 0.82)),
    rgba(255, 255, 255, 0.9);
  box-shadow: 0 16px 32px rgba(19, 26, 35, 0.04);
}

.sidebar-brand-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
}

.brand-lockup {
  min-width: 0;
}

.sidebar-kicker {
  margin: 0 0 4px;
  font-size: 10px;
  line-height: 1;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted, #6d7784);
}

.brand-lockup h1 {
  margin: 0;
  font-size: 17px;
  line-height: 1.1;
  font-weight: 700;
}

.brand-context {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  padding-left: 12px;
  border-left: 1px solid rgba(20, 28, 38, 0.08);
  text-align: right;
}

.context-label {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted, #6d7784);
}

.brand-context strong {
  max-width: 180px;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-system-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.system-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 7px 10px;
  border: 1px solid rgba(20, 28, 38, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.74);
  color: var(--ink, #17202b);
}

.preset-pill {
  flex: 1 1 180px;
}

.system-pill-label {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted, #6d7784);
}

.system-pill strong {
  min-width: 0;
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.system-pill.is-connected {
  border-color: rgba(38, 110, 74, 0.18);
  background: rgba(228, 244, 234, 0.9);
  color: #235b3b;
}

.system-pill.is-connecting,
.system-pill.is-warning {
  border-color: rgba(164, 105, 21, 0.18);
  background: rgba(250, 238, 214, 0.94);
  color: #8c5f1d;
}

.system-pill.is-disconnected {
  border-color: rgba(140, 58, 48, 0.16);
  background: rgba(248, 232, 228, 0.94);
  color: #8c3a30;
}

.system-pill.is-success {
  border-color: rgba(38, 110, 74, 0.18);
  background: rgba(228, 244, 234, 0.9);
  color: #235b3b;
}

.system-pill.is-neutral {
  border-color: rgba(20, 28, 38, 0.08);
  background: rgba(255, 255, 255, 0.76);
  color: var(--ink, #17202b);
}

.sidebar-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
}

.sidebar-block-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.sidebar-block-head p {
  margin: 0 0 2px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted, #6d7784);
}

.sidebar-block-head h2 {
  margin: 0;
  font-size: 14px;
  line-height: 1.2;
}

.sidebar-block-head > span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(20, 28, 38, 0.06);
  font-size: 12px;
  font-weight: 700;
  color: var(--muted, #6d7784);
}

.sidebar-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sidebar-item {
  width: 100%;
  border: 1px solid rgba(20, 28, 38, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.74);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    background 160ms ease,
    transform 160ms ease,
    box-shadow 160ms ease;
}

.sidebar-item:hover {
  border-color: rgba(20, 28, 38, 0.18);
  background: rgba(255, 255, 255, 0.95);
  transform: translateY(-1px);
}

.sidebar-item:focus-visible {
  outline: 2px solid rgba(166, 82, 44, 0.36);
  outline-offset: 2px;
}

.task-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 11px 12px;
}

.task-item strong,
.run-item strong {
  min-width: 0;
  overflow: hidden;
  font-size: 13px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-item span {
  min-width: 0;
  overflow: hidden;
  font-size: 11px;
  color: var(--muted, #6d7784);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-item.active {
  border-color: rgba(166, 82, 44, 0.3);
  background: linear-gradient(180deg, rgba(255, 249, 242, 0.98), rgba(252, 242, 232, 0.94));
  box-shadow: inset 3px 0 0 #b6663d;
}

.run-filters {
  display: inline-flex;
  width: fit-content;
  max-width: 100%;
  padding: 4px;
  border: 1px solid rgba(20, 28, 38, 0.08);
  border-radius: 999px;
  background: rgba(244, 239, 233, 0.86);
}

.run-filter-tab {
  border: 0;
  border-radius: 999px;
  background: transparent;
  padding: 7px 12px;
  font-size: 12px;
  color: var(--muted, #6d7784);
  cursor: pointer;
  transition:
    background 160ms ease,
    color 160ms ease;
}

.run-filter-tab.active {
  background: rgba(255, 255, 255, 0.96);
  color: var(--ink, #17202b);
  box-shadow: 0 4px 12px rgba(19, 26, 35, 0.06);
}

.run-list {
  gap: 10px;
}

.run-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
}

.run-item.active {
  border-color: rgba(91, 116, 153, 0.3);
  background: linear-gradient(180deg, rgba(245, 248, 252, 0.98), rgba(236, 241, 247, 0.94));
  box-shadow: 0 10px 24px rgba(34, 46, 62, 0.08);
}

.run-item-topline,
.run-item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.run-item-meta {
  font-size: 11px;
  color: var(--muted, #6d7784);
}

.run-item-id {
  min-width: 0;
  overflow: hidden;
  font-family: "SFMono-Regular", "SFMono", "IBM Plex Mono", monospace;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-item-hint {
  font-size: 11px;
  line-height: 1.35;
  color: var(--muted, #6d7784);
}

.run-status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  min-width: 56px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.run-status-chip.is-running {
  background: rgba(227, 239, 255, 0.92);
  color: #31598d;
}

.run-status-chip.is-failed {
  background: rgba(248, 232, 228, 0.94);
  color: #8c3a30;
}

.run-status-chip.is-done {
  background: rgba(228, 244, 234, 0.9);
  color: #235b3b;
}

.run-status-chip.is-neutral {
  background: rgba(20, 28, 38, 0.08);
  color: var(--muted, #6d7784);
}

.run-empty-tip {
  margin: 0;
  padding: 18px 12px;
  border: 1px dashed rgba(20, 28, 38, 0.14);
  border-radius: 14px;
  font-size: 12px;
  text-align: center;
  color: var(--muted, #6d7784);
}

@media (max-width: 920px) {
  .sidebar-brand-strip {
    flex-direction: column;
    align-items: flex-start;
  }

  .brand-context {
    width: 100%;
    padding-left: 0;
    padding-top: 10px;
    border-left: 0;
    border-top: 1px solid rgba(20, 28, 38, 0.08);
    text-align: left;
  }

  .brand-context strong {
    max-width: none;
  }

  .run-item-topline,
  .run-item-meta {
    flex-wrap: wrap;
  }
}
</style>
