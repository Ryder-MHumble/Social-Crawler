<script setup lang="ts">
import type { SqliteStatus, TaskPreset, TaskRun } from "../types";

defineProps<{
  presets: TaskPreset[];
  selectedPresetId: string | null;
  presetName: string;
  presetIsDefault: boolean;
  hasUnsavedChanges: boolean;
  activeRun: TaskRun | null;
  sqliteStatus: SqliteStatus | null;
  isSavingPreset: boolean;
  isStartingRun: boolean;
}>();

const emit = defineEmits<{
  (event: "select-preset", presetId: string | null): void;
  (event: "update:presetName", value: string): void;
  (event: "update:presetIsDefault", value: boolean): void;
  (event: "create-preset"): void;
  (event: "update-preset"): void;
  (event: "delete-preset"): void;
  (event: "start-run"): void;
  (event: "stop-run"): void;
}>();
</script>

<template>
  <header class="topbar">
    <div class="topbar-cluster topbar-preset">
      <div class="topbar-field">
        <label>预设</label>
        <select
          :value="selectedPresetId ?? ''"
          @change="emit('select-preset', ($event.target as HTMLSelectElement).value || null)"
        >
          <option value="">使用任务默认值</option>
          <option v-for="preset in presets" :key="preset.id" :value="preset.id">
            {{ preset.name }}
          </option>
        </select>
      </div>

      <div class="topbar-field topbar-name">
        <label>名称</label>
        <input
          :value="presetName"
          placeholder="预设名称"
          @input="emit('update:presetName', ($event.target as HTMLInputElement).value)"
        />
      </div>

      <label class="topbar-toggle">
        <input
          type="checkbox"
          :checked="presetIsDefault"
          @change="emit('update:presetIsDefault', ($event.target as HTMLInputElement).checked)"
        />
        <span>默认预设</span>
      </label>

      <div class="topbar-inline-actions">
        <button class="btn secondary" :disabled="isSavingPreset" @click="emit('create-preset')">
          保存新预设
        </button>
        <button class="btn secondary" :disabled="isSavingPreset || !selectedPresetId" @click="emit('update-preset')">
          更新预设
        </button>
        <button class="btn ghost" :disabled="isSavingPreset || !selectedPresetId" @click="emit('delete-preset')">
          删除
        </button>
      </div>
    </div>

    <div class="topbar-cluster topbar-actions">
      <span class="state-chip" :class="hasUnsavedChanges ? 'warning' : 'neutral'">
        {{ hasUnsavedChanges ? "未保存变更" : "草稿已同步" }}
      </span>
      <span class="state-chip" :class="sqliteStatus?.initialized ? 'success' : 'warning'">
        SQLite {{ sqliteStatus?.initialized ? "已初始化" : "待初始化" }}
      </span>
      <span class="state-chip" :class="activeRun?.status === 'running' ? 'running' : 'neutral'">
        {{ activeRun?.status === "running" ? `运行中 · ${activeRun.title}` : "当前无活跃任务" }}
      </span>
      <button class="btn primary" :disabled="isStartingRun || activeRun?.status === 'running'" @click="emit('start-run')">
        启动
      </button>
      <button class="btn danger" :disabled="activeRun?.status !== 'running'" @click="emit('stop-run')">
        停止
      </button>
    </div>
  </header>
</template>
