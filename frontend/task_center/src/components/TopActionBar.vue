<script setup lang="ts">
import SelectField from "./SelectField.vue";
import ToggleSwitch from "./ToggleSwitch.vue";
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

function presetOptions(presets: TaskPreset[]) {
  return [
    { value: "", label: "使用任务默认值" },
    ...presets.map((preset) => ({
      value: preset.id,
      label: preset.name,
    })),
  ];
}
</script>

<template>
  <header class="topbar topbar-rebalanced">
    <section class="topbar-zone preset-zone">
      <div class="zone-header">
        <div>
          <h3>预设编辑区</h3>
          <p>管理预设选择、命名与保存策略</p>
        </div>
      </div>

      <div class="preset-grid">
        <div class="topbar-field">
          <label>预设</label>
          <SelectField
            compact
            :model-value="selectedPresetId ?? ''"
            :options="presetOptions(presets)"
            @update:model-value="emit('select-preset', $event || null)"
          />
        </div>

        <div class="topbar-field topbar-name">
          <label>名称</label>
          <input
            :value="presetName"
            placeholder="预设名称"
            @input="emit('update:presetName', ($event.target as HTMLInputElement).value)"
          />
        </div>

        <div class="preset-toggle-wrap">
          <ToggleSwitch
            class="topbar-toggle-control"
            compact
            label="默认预设"
            :model-value="presetIsDefault"
            on-label="默认"
            off-label="普通"
            @update:model-value="emit('update:presetIsDefault', $event)"
          />
        </div>
      </div>

      <div class="topbar-inline-actions preset-actions">
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
    </section>

    <section class="topbar-zone control-zone">
      <div class="zone-header">
        <div>
          <h3>运行控制区</h3>
          <p>查看状态并执行启停操作</p>
        </div>
      </div>

      <div class="status-chip-grid">
        <span class="state-chip" :class="hasUnsavedChanges ? 'warning' : 'neutral'">
          {{ hasUnsavedChanges ? "未保存变更" : "草稿已同步" }}
        </span>
        <span class="state-chip" :class="sqliteStatus?.initialized ? 'success' : 'warning'">
          SQLite {{ sqliteStatus?.initialized ? "已初始化" : "待初始化" }}
        </span>
        <span class="state-chip state-chip-wide" :class="activeRun?.status === 'running' ? 'running' : 'neutral'">
          {{ activeRun?.status === "running" ? `运行中 · ${activeRun.title}` : "当前无活跃任务" }}
        </span>
      </div>

      <div class="run-actions">
        <button class="btn primary" :disabled="isStartingRun || activeRun?.status === 'running'" @click="emit('start-run')">
          启动
        </button>
        <button class="btn danger" :disabled="activeRun?.status !== 'running'" @click="emit('stop-run')">
          停止
        </button>
      </div>
    </section>
  </header>
</template>

<style scoped>
.topbar.topbar-rebalanced {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(340px, 0.95fr);
  gap: 14px;
  align-items: stretch;
}

.topbar-zone {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  padding: 14px;
  border: 1px solid rgba(22, 32, 43, 0.1);
  border-radius: 16px;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.76), rgba(251, 246, 239, 0.52));
}

.zone-header h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
}

.zone-header p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.preset-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 10px;
  align-items: end;
}

.preset-toggle-wrap {
  display: flex;
  min-width: 0;
}

.preset-toggle-wrap :deep(.toggle-switch) {
  width: 100%;
}

.preset-actions {
  justify-content: flex-start;
}

.status-chip-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.status-chip-grid .state-chip {
  display: flex;
  width: 100%;
  justify-content: center;
  text-align: center;
}

.state-chip-wide {
  grid-column: 1 / -1;
}

.run-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.run-actions .btn {
  width: 100%;
}

@media (max-width: 1360px) {
  .topbar.topbar-rebalanced {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 920px) {
  .preset-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 620px) {
  .status-chip-grid,
  .run-actions {
    grid-template-columns: 1fr;
  }
}
</style>
