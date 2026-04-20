<script setup lang="ts">
import { computed } from "vue";
import SelectField from "./SelectField.vue";
import ToggleSwitch from "./ToggleSwitch.vue";
import type { SqliteStatus, TaskPreset, TaskRun } from "../types";

const props = defineProps<{
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

const selectedPresetLabel = computed(() => {
  if (!props.selectedPresetId) return "任务默认值";
  return props.presets.find((preset) => preset.id === props.selectedPresetId)?.name ?? "已选预设";
});

const selectedPresetMeta = computed(() => {
  if (!props.selectedPresetId) return "使用任务级默认参数";
  return props.presetIsDefault ? "默认预设" : "自定义预设";
});

const draftLabel = computed(() => (props.hasUnsavedChanges ? "草稿未保存" : "草稿已同步"));

const draftMeta = computed(() => {
  const name = props.presetName.trim();
  if (!name) return "当前名称为空";
  return props.hasUnsavedChanges ? `编辑中 · ${name}` : `名称 · ${name}`;
});

const sqliteLabel = computed(() => {
  if (!props.sqliteStatus) return "SQLite 未检测";
  return props.sqliteStatus.initialized ? "SQLite 已初始化" : "SQLite 待初始化";
});

const sqliteMeta = computed(() => {
  if (!props.sqliteStatus) return "等待系统状态";
  if (props.sqliteStatus.initialized) {
    const schemaVersion = props.sqliteStatus.schema_version ?? "-";
    return `${props.sqliteStatus.table_count} 表 · schema ${schemaVersion}`;
  }
  return props.sqliteStatus.exists ? "已发现数据库文件" : "未发现数据库文件";
});

const currentRunLabel = computed(() => props.activeRun?.title || "当前无活跃运行");

const currentRunMeta = computed(() => {
  if (!props.activeRun) return "准备启动新的任务运行";
  return `${statusLabel(props.activeRun.status)} · ${shortRunId(props.activeRun.id)}`;
});

function presetOptions(presets: TaskPreset[]) {
  return [
    { value: "", label: "使用任务默认值" },
    ...presets.map((preset) => ({
      value: preset.id,
      label: preset.name,
    })),
  ];
}

function normalizeStatus(status?: string | null): string {
  return String(status ?? "")
    .trim()
    .toLowerCase();
}

function statusLabel(status?: string | null): string {
  const key = normalizeStatus(status);
  if (["running", "queued", "pending", "starting", "active", "in_progress"].includes(key)) {
    return "运行中";
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
    return "失败";
  }
  if (["completed", "complete", "success", "succeeded", "done", "finished"].includes(key)) {
    return "已完成";
  }
  if (!key) return "未知";
  return String(status);
}

function statusTone(status?: string | null): "running" | "failed" | "done" | "neutral" {
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
  if (["completed", "complete", "success", "succeeded", "done", "finished"].includes(key)) {
    return "done";
  }
  return "neutral";
}

function shortRunId(runId: string): string {
  const value = runId.trim();
  if (value.length <= 18) return value;
  return `${value.slice(0, 15)}...`;
}
</script>

<template>
  <header class="command-deck">
    <div class="deck-head">
      <div class="deck-title">
        <p>Command Deck</p>
        <h3>Quiet Ops Shell</h3>
      </div>

      <div class="deck-summary">
        <article class="summary-card">
          <span class="summary-label">当前预设</span>
          <strong>{{ selectedPresetLabel }}</strong>
          <small>{{ selectedPresetMeta }}</small>
        </article>

        <article class="summary-card" :class="hasUnsavedChanges ? 'is-warning' : 'is-neutral'">
          <span class="summary-label">草稿状态</span>
          <strong>{{ draftLabel }}</strong>
          <small>{{ draftMeta }}</small>
        </article>

        <article
          class="summary-card"
          :class="sqliteStatus?.initialized ? 'is-success' : 'is-warning'"
        >
          <span class="summary-label">SQLite</span>
          <strong>{{ sqliteLabel }}</strong>
          <small>{{ sqliteMeta }}</small>
        </article>

        <article class="summary-card summary-run" :class="`is-${statusTone(activeRun?.status)}`">
          <span class="summary-label">当前 Run</span>
          <strong>{{ currentRunLabel }}</strong>
          <small>{{ currentRunMeta }}</small>
        </article>
      </div>
    </div>

    <div class="deck-body">
      <section class="deck-panel preset-panel">
        <div class="panel-head">
          <div>
            <p>Preset Editor</p>
            <h4>预设编辑</h4>
          </div>
          <span class="panel-badge">{{ selectedPresetId ? "已选预设" : "默认参数" }}</span>
        </div>

        <div class="preset-grid">
          <label class="field-shell">
            <span>预设</span>
            <SelectField
              compact
              :model-value="selectedPresetId ?? ''"
              :options="presetOptions(presets)"
              @update:model-value="emit('select-preset', $event || null)"
            />
          </label>

          <label class="field-shell">
            <span>名称</span>
            <input
              :value="presetName"
              placeholder="预设名称"
              @input="emit('update:presetName', ($event.target as HTMLInputElement).value)"
            />
          </label>

          <div class="toggle-shell">
            <ToggleSwitch
              compact
              label="默认预设"
              :model-value="presetIsDefault"
              on-label="默认"
              off-label="普通"
              @update:model-value="emit('update:presetIsDefault', $event)"
            />
          </div>
        </div>

        <div class="panel-actions secondary-actions">
          <button
            type="button"
            class="deck-button deck-button-secondary"
            :disabled="isSavingPreset || !selectedPresetId"
            @click="emit('update-preset')"
          >
            保存修改
          </button>
          <button
            type="button"
            class="deck-button deck-button-secondary"
            :disabled="isSavingPreset"
            @click="emit('create-preset')"
          >
            另存为新预设
          </button>
          <button
            type="button"
            class="deck-button deck-button-ghost"
            :disabled="isSavingPreset || !selectedPresetId"
            @click="emit('delete-preset')"
          >
            删除
          </button>
        </div>
      </section>

      <section class="deck-panel run-panel">
        <div class="panel-head">
          <div>
            <p>Run Control</p>
            <h4>执行控制</h4>
          </div>
          <span class="panel-badge" :class="`is-${statusTone(activeRun?.status)}`">
            {{ activeRun ? statusLabel(activeRun.status) : "Idle" }}
          </span>
        </div>

        <div class="run-brief">
          <strong>{{ currentRunLabel }}</strong>
          <small>{{ currentRunMeta }}</small>
        </div>

        <div class="panel-actions primary-actions">
          <button
            type="button"
            class="deck-button deck-button-primary"
            :disabled="isStartingRun || activeRun?.status === 'running'"
            @click="emit('start-run')"
          >
            {{ isStartingRun ? "启动中..." : "启动运行" }}
          </button>
          <button
            type="button"
            class="deck-button deck-button-danger"
            :disabled="activeRun?.status !== 'running'"
            @click="emit('stop-run')"
          >
            停止运行
          </button>
        </div>
      </section>
    </div>
  </header>
</template>

<style scoped>
.command-deck {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  border: 1px solid rgba(20, 28, 38, 0.1);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 240, 232, 0.76)),
    rgba(255, 255, 255, 0.88);
  box-shadow: 0 18px 36px rgba(19, 26, 35, 0.04);
  color: var(--ink, #17202b);
}

.deck-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.deck-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.deck-title p {
  margin: 0;
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted, #6d7784);
}

.deck-title h3 {
  margin: 0;
  font-size: 15px;
  line-height: 1.2;
}

.deck-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.summary-card,
.deck-panel {
  border: 1px solid rgba(20, 28, 38, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding: 10px 12px;
}

.summary-label {
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted, #6d7784);
}

.summary-card strong,
.run-brief strong {
  min-width: 0;
  overflow: hidden;
  font-size: 13px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.summary-card small,
.run-brief small {
  min-width: 0;
  overflow: hidden;
  font-size: 11px;
  line-height: 1.4;
  color: var(--muted, #6d7784);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.summary-card.is-warning {
  background: rgba(250, 238, 214, 0.92);
  border-color: rgba(164, 105, 21, 0.16);
}

.summary-card.is-success {
  background: rgba(228, 244, 234, 0.9);
  border-color: rgba(38, 110, 74, 0.16);
}

.summary-card.is-running {
  background: rgba(227, 239, 255, 0.92);
  border-color: rgba(63, 90, 140, 0.16);
}

.summary-card.is-failed {
  background: rgba(248, 232, 228, 0.94);
  border-color: rgba(140, 58, 48, 0.16);
}

.summary-card.is-done {
  background: rgba(231, 244, 236, 0.9);
  border-color: rgba(38, 110, 74, 0.16);
}

.deck-body {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.9fr);
  gap: 10px;
}

.deck-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-head p {
  margin: 0 0 2px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted, #6d7784);
}

.panel-head h4 {
  margin: 0;
  font-size: 13px;
  line-height: 1.2;
}

.panel-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(20, 28, 38, 0.06);
  font-size: 11px;
  color: var(--muted, #6d7784);
}

.panel-badge.is-running {
  background: rgba(227, 239, 255, 0.92);
  color: #31598d;
}

.panel-badge.is-failed {
  background: rgba(248, 232, 228, 0.94);
  color: #8c3a30;
}

.panel-badge.is-done {
  background: rgba(228, 244, 234, 0.9);
  color: #235b3b;
}

.preset-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1.05fr) minmax(180px, 0.8fr);
  gap: 10px;
  align-items: end;
}

.field-shell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.field-shell > span {
  font-size: 11px;
  color: var(--muted, #6d7784);
}

.field-shell input {
  width: 100%;
  min-width: 0;
  height: 40px;
  padding: 0 12px;
  border: 1px solid rgba(20, 28, 38, 0.12);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--ink, #17202b);
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.field-shell input::placeholder {
  color: rgba(109, 119, 132, 0.8);
}

.field-shell input:focus {
  outline: none;
  border-color: rgba(166, 82, 44, 0.36);
  box-shadow: 0 0 0 3px rgba(166, 82, 44, 0.12);
}

.field-shell :deep(.select-field) {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 40px;
  padding: 0 36px 0 12px;
  border: 1px solid rgba(20, 28, 38, 0.12);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.field-shell :deep(.select-field:focus-within) {
  border-color: rgba(166, 82, 44, 0.36);
  box-shadow: 0 0 0 3px rgba(166, 82, 44, 0.12);
}

.field-shell :deep(.select-field select) {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--ink, #17202b);
  font-size: 13px;
  appearance: none;
  outline: none;
}

.field-shell :deep(.select-field.disabled) {
  opacity: 0.56;
}

.field-shell :deep(.select-chevron) {
  position: absolute;
  right: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--muted, #6d7784);
}

.field-shell :deep(.select-chevron svg) {
  width: 16px;
  height: 16px;
}

.toggle-shell {
  min-width: 0;
}

.toggle-shell :deep(.toggle-switch) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-height: 40px;
  padding: 8px 12px;
  border: 1px solid rgba(20, 28, 38, 0.12);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--ink, #17202b);
}

.toggle-shell :deep(.toggle-switch.disabled) {
  opacity: 0.56;
}

.toggle-shell :deep(.toggle-copy strong) {
  font-size: 12px;
}

.toggle-shell :deep(.toggle-control) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.toggle-shell :deep(.toggle-status) {
  font-size: 11px;
  color: var(--muted, #6d7784);
}

.toggle-shell :deep(.toggle-track) {
  position: relative;
  display: inline-flex;
  align-items: center;
  width: 38px;
  height: 20px;
  padding: 2px;
  border-radius: 999px;
  background: rgba(20, 28, 38, 0.18);
  transition: background 160ms ease;
}

.toggle-shell :deep(.toggle-thumb) {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(19, 26, 35, 0.18);
  transition: transform 160ms ease;
}

.toggle-shell :deep(.toggle-switch.on .toggle-track) {
  background: #1f3b5a;
}

.toggle-shell :deep(.toggle-switch.on .toggle-thumb) {
  transform: translateX(18px);
}

.panel-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.secondary-actions {
  justify-content: flex-start;
}

.primary-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(120px, auto);
}

.run-brief {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding: 12px;
  border: 1px solid rgba(20, 28, 38, 0.08);
  border-radius: 14px;
  background: rgba(244, 239, 233, 0.58);
}

.deck-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 160ms ease,
    box-shadow 160ms ease,
    background 160ms ease,
    border-color 160ms ease,
    color 160ms ease;
}

.deck-button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.deck-button:focus-visible {
  outline: 2px solid rgba(166, 82, 44, 0.36);
  outline-offset: 2px;
}

.deck-button:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.deck-button-primary {
  background: #1f3b5a;
  color: #f4f7fb;
  box-shadow: 0 10px 22px rgba(31, 59, 90, 0.18);
}

.deck-button-secondary {
  background: rgba(255, 255, 255, 0.92);
  border-color: rgba(20, 28, 38, 0.12);
  color: var(--ink, #17202b);
}

.deck-button-ghost {
  background: transparent;
  border-color: rgba(20, 28, 38, 0.12);
  color: var(--muted, #6d7784);
}

.deck-button-danger {
  background: rgba(255, 240, 238, 0.98);
  border-color: rgba(140, 58, 48, 0.12);
  color: #8c3a30;
}

@media (max-width: 1360px) {
  .deck-summary,
  .deck-body {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .summary-run,
  .run-panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 980px) {
  .deck-summary,
  .deck-body,
  .preset-grid,
  .primary-actions {
    grid-template-columns: 1fr;
  }

  .deck-title {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 640px) {
  .command-deck,
  .deck-panel {
    padding: 10px;
  }

  .summary-card,
  .run-brief {
    padding: 10px;
  }

  .panel-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .deck-button {
    width: 100%;
  }
}
</style>
