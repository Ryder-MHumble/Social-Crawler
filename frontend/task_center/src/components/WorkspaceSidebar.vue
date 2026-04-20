<script setup lang="ts">
import { computed } from "vue";
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

const socketLabel = computed(() => {
  if (props.socketState === "connected") return "已连接";
  if (props.socketState === "connecting") return "连接中";
  return "已断开";
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

    <section class="sidebar-block">
      <div class="sidebar-block-head">
        <h2>最近运行</h2>
        <span>{{ recentRuns.length }}</span>
      </div>
      <div class="sidebar-list">
        <button
          v-if="activeRun"
          class="sidebar-item run-item"
          :class="{ active: selectedRunId === activeRun.id }"
          @click="emit('select-run', activeRun.id)"
        >
          <strong>{{ activeRun.title }}</strong>
          <span>{{ activeRun.id }}</span>
          <small>{{ formatTime(activeRun.started_at) }} · {{ activeRun.status }}</small>
        </button>
        <button
          v-for="run in recentRuns"
          :key="run.id"
          class="sidebar-item run-item"
          :class="{ active: selectedRunId === run.id }"
          @click="emit('select-run', run.id)"
        >
          <strong>{{ run.title }}</strong>
          <span>{{ run.id }}</span>
          <small>{{ formatTime(run.started_at) }} · {{ run.status }}</small>
        </button>
      </div>
    </section>
  </aside>
</template>
