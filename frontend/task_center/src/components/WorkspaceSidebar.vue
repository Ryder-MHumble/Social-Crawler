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
  if (runFilterKey(run.status) === "running") return "点击查看执行回放";
  const saveOption = String(
    run.normalized_params.save_option ?? run.normalized_params.save_data_option ?? "",
  )
    .trim()
    .toLowerCase();
  if (["json", "csv", "excel"].includes(saveOption)) {
    return "点击查看文件结果";
  }
  return "点击查看清洗结果";
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
    <section class="sidebar-card sidebar-brand">
      <p class="sidebar-kicker">Task Workspace</p>
      <h1>Social-Crawler</h1>
      <p class="sidebar-copy">任务、命令、执行和数据都收口到一个工作台里。</p>
    </section>

    <section class="sidebar-card sidebar-status">
      <div class="sidebar-stat">
        <span class="sidebar-label">连接</span>
        <strong :class="`status-${socketState}`">{{ socketLabel }}</strong>
      </div>
      <div class="sidebar-stat">
        <span class="sidebar-label">SQLite</span>
        <strong :class="sqliteReady ? 'status-success' : 'status-warning'">
          {{ sqliteReady ? "已就绪" : "未初始化" }}
        </strong>
      </div>
      <div class="sidebar-stat">
        <span class="sidebar-label">当前预设</span>
        <strong>{{ currentPresetName || "未选择" }}</strong>
      </div>
    </section>

    <section class="sidebar-block">
      <div class="sidebar-block-head">
        <h2>任务</h2>
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
        <h2>最近运行</h2>
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
          <strong>{{ run.title }}</strong>
          <span class="run-item-id">{{ shortRunId(run.id) }}</span>
          <small class="run-item-meta">
            <span>{{ formatTime(run.started_at) }}</span>
            <span class="run-status-chip" :class="`is-${statusTone(run.status)}`">
              {{ statusLabel(run.status) }}
            </span>
          </small>
          <small class="run-item-hint">{{ runHint(run) }}</small>
        </button>
        <p v-if="!filteredRuns.length" class="run-empty-tip">当前筛选下暂无运行记录</p>
      </div>
    </section>
  </aside>
</template>
