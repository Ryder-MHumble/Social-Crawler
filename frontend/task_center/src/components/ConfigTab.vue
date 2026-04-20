<script setup lang="ts">
import { computed } from "vue";
import SelectField from "./SelectField.vue";
import ToggleSwitch from "./ToggleSwitch.vue";
import type { BrowsermintSession, GroupedFieldSection, Primitive, TaskFieldSchema } from "../types";

interface GroupProgressSummary extends GroupedFieldSection {
  configuredCount: number;
  requiredReadyCount: number;
  disabledCount: number;
  position: number;
}

const props = defineProps<{
  groups: GroupedFieldSection[];
  selectedGroup: string;
  formParams: Record<string, unknown>;
  previewLoading: boolean;
  browsermintLoading: boolean;
  browsermintSessionDisabled: boolean;
  browsermintSelectedSession: BrowsermintSession | null;
}>();

const emit = defineEmits<{
  (event: "select-group", groupName: string): void;
  (event: "update-field", key: string, value: unknown): void;
  (event: "open-browsermint"): void;
  (event: "refresh-browsermint"): void;
}>();

const activeGroup = computed(
  () => props.groups.find((group) => group.name === props.selectedGroup) ?? props.groups[0] ?? null,
);

const groupSummaries = computed<GroupProgressSummary[]>(() =>
  props.groups.map((group, index) => ({
    ...group,
    configuredCount: group.fields.filter((field) => hasDisplayValue(props.formParams[field.key])).length,
    requiredReadyCount: group.fields.filter(
      (field) => field.required && hasDisplayValue(props.formParams[field.key]),
    ).length,
    disabledCount: group.fields.filter((field) => isFieldDisabled(field)).length,
    position: index + 1,
  })),
);

const activeGroupSummary = computed(
  () => groupSummaries.value.find((group) => group.name === activeGroup.value?.name) ?? groupSummaries.value[0] ?? null,
);

const totalFieldCount = computed(() =>
  groupSummaries.value.reduce((count, group) => count + group.fields.length, 0),
);

const totalRequiredCount = computed(() =>
  groupSummaries.value.reduce((count, group) => count + group.requiredCount, 0),
);

const totalConfiguredCount = computed(() =>
  groupSummaries.value.reduce((count, group) => count + group.configuredCount, 0),
);

const totalRequiredReadyCount = computed(() =>
  groupSummaries.value.reduce((count, group) => count + group.requiredReadyCount, 0),
);

const overallCompletion = computed(() => {
  if (!totalFieldCount.value) return 0;
  return Math.round((totalConfiguredCount.value / totalFieldCount.value) * 100);
});

const activeCompletion = computed(() => {
  if (!activeGroupSummary.value?.fields.length) return 0;
  return Math.round((activeGroupSummary.value.configuredCount / activeGroupSummary.value.fields.length) * 100);
});

function hasDisplayValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (typeof value === "number") return !Number.isNaN(value);
  if (typeof value === "boolean") return true;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as Record<string, unknown>).length > 0;
  return false;
}

function groupSummaryText(group: GroupProgressSummary): string {
  const missingRequired = Math.max(group.requiredCount - group.requiredReadyCount, 0);
  if (!group.fields.length) return "当前 section 暂无字段。";
  if (missingRequired > 0) {
    return `已就绪 ${group.configuredCount}/${group.fields.length}，还有 ${missingRequired} 项关键配置待补齐`;
  }
  return `已就绪 ${group.configuredCount}/${group.fields.length}，当前关键配置已齐备`;
}

function activeGroupSummaryText(group: GroupProgressSummary): string {
  const missingRequired = Math.max(group.requiredCount - group.requiredReadyCount, 0);
  if (!group.requiredCount) {
    return `本段包含 ${group.fields.length} 项可选配置，当前已确定 ${group.configuredCount} 项。`;
  }
  if (missingRequired > 0) {
    return `本段共有 ${group.requiredCount} 项关键配置，当前还差 ${missingRequired} 项。`;
  }
  return `本段 ${group.requiredCount} 项关键配置已经齐备，可以继续检查依赖项和高级参数。`;
}

function sectionTone(group: GroupProgressSummary): "warning" | "success" | "neutral" {
  if (group.requiredReadyCount < group.requiredCount) return "warning";
  if (group.configuredCount > 0) return "success";
  return "neutral";
}

function fieldTone(field: TaskFieldSchema): "warning" | "success" | "neutral" {
  if (field.required && !hasDisplayValue(props.formParams[field.key])) return "warning";
  if (hasDisplayValue(props.formParams[field.key])) return "success";
  return "neutral";
}

function isSameValue(actual: unknown, expected: unknown): boolean {
  if (Array.isArray(actual) && Array.isArray(expected)) {
    return actual.length === expected.length && actual.every((value, index) => value === expected[index]);
  }
  return actual === expected;
}

function isFieldDisabled(field: TaskFieldSchema): boolean {
  if (field.key === "browser_session_id" && props.browsermintSessionDisabled) return true;
  if (!field.disabled_when) return false;
  return Object.entries(field.disabled_when).every(([key, expected]) => isSameValue(props.formParams[key], expected));
}

function getOptionValueFromInput(field: TaskFieldSchema, rawValue: string): Primitive {
  const matched = field.options.find((option) => String(option.value) === rawValue);
  return matched?.value ?? rawValue;
}

function updateField(field: TaskFieldSchema, event: Event) {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
  if (field.component === "number") {
    emit("update-field", field.key, target.value === "" ? "" : Number(target.value));
    return;
  }
  if (field.component === "switch") {
    emit("update-field", field.key, (target as HTMLInputElement).checked);
    return;
  }
  if (field.component === "select") {
    emit("update-field", field.key, getOptionValueFromInput(field, target.value));
    return;
  }
  emit("update-field", field.key, target.value);
}

function toggleMultiValue(field: TaskFieldSchema, value: Primitive, checked: boolean) {
  const current = Array.isArray(props.formParams[field.key])
    ? [...(props.formParams[field.key] as Primitive[])]
    : [];
  if (checked && !current.some((item) => item === value)) {
    emit("update-field", field.key, [...current, value]);
    return;
  }
  emit(
    "update-field",
    field.key,
    current.filter((item) => item !== value),
  );
}

function helperLines(field: TaskFieldSchema): string[] {
  const lines =
    field.component === "switch"
      ? []
      : ([field.helper_text, field.description].filter(Boolean) as string[]);
  if (field.validation?.min !== undefined) lines.push(`最小值 ${field.validation.min}`);
  if (field.validation?.max !== undefined) lines.push(`最大值 ${field.validation.max}`);
  if (field.validation?.step !== undefined) lines.push(`步长 ${field.validation.step}`);
  if (field.validation?.min_length !== undefined) lines.push(`至少 ${field.validation.min_length} 个字符`);
  if (field.validation?.max_length !== undefined) lines.push(`最多 ${field.validation.max_length} 个字符`);
  if (field.validation?.min_items !== undefined) lines.push(`至少选择 ${field.validation.min_items} 项`);
  if (field.validation?.max_items !== undefined) lines.push(`最多选择 ${field.validation.max_items} 项`);
  return lines;
}

function isMultiSelected(field: TaskFieldSchema, value: Primitive): boolean {
  return Array.isArray(props.formParams[field.key])
    ? (props.formParams[field.key] as Primitive[]).includes(value)
    : false;
}

function switchDescription(field: TaskFieldSchema): string {
  return [field.helper_text, field.description].filter(Boolean).join(" · ");
}

function selectOptions(field: TaskFieldSchema) {
  return field.options.map((option) => ({
    value: String(option.value),
    label: option.label,
    description: option.description,
  }));
}
</script>

<template>
  <section class="tab-panel config-tab">
    <div class="tab-panel-head">
      <div>
        <h2>配置</h2>
        <p>围绕当前 section 聚焦编辑，左侧保留导航和完成度，右侧专注字段排版与输入。</p>
      </div>
      <span class="state-chip" :class="previewLoading ? 'running' : 'neutral'">
        {{ previewLoading ? "命令解析中" : "命令已同步" }}
      </span>
    </div>

    <div v-if="activeGroup && activeGroupSummary" class="config-shell">
      <section class="config-progress-strip" aria-label="配置进度">
        <div class="config-progress-copy">
          <span class="config-progress-kicker">Section Progress</span>
          <strong>分段式配置</strong>
          <p>
            {{ groupSummaries.length }} 个 section，已配置 {{ totalConfiguredCount }}/{{ totalFieldCount }} 项字段，
            关键配置完成 {{ totalRequiredReadyCount }}/{{ totalRequiredCount || 0 }}。
          </p>
        </div>

        <div class="config-progress-visual">
          <div class="config-progress-track" aria-hidden="true">
            <span :style="{ width: `${overallCompletion}%` }" />
          </div>
          <div class="config-progress-meta">
            <span>{{ overallCompletion }}% overall readiness</span>
            <span>当前 section {{ activeCompletion }}%</span>
          </div>
        </div>
      </section>

      <aside class="config-rail">
        <div class="config-rail-head">
          <div>
            <span class="config-progress-kicker">Navigator</span>
            <h3>Section 导航</h3>
          </div>
          <span class="state-chip neutral">{{ groupSummaries.length }} 段</span>
        </div>

        <div class="config-group-list">
          <button
            v-for="group in groupSummaries"
            :key="group.name"
            class="config-group-card"
            :class="{ active: group.name === selectedGroup }"
            @click="emit('select-group', group.name)"
          >
            <div class="config-group-card-head">
              <span class="config-group-order">Section {{ group.position }}</span>
              <span class="state-chip small" :class="sectionTone(group)">
                {{ group.requiredReadyCount }}/{{ group.requiredCount || group.fields.length }}
              </span>
            </div>
            <strong>{{ group.name }}</strong>
            <p>{{ groupSummaryText(group) }}</p>
            <div class="config-group-card-foot">
              <span>{{ group.fields.length }} 项</span>
              <span>{{ group.requiredCount }} 必填</span>
              <span v-if="group.disabledCount">{{ group.disabledCount }} 待解锁</span>
            </div>
          </button>
        </div>

        <article class="config-rail-summary" :class="sectionTone(activeGroupSummary)">
          <div class="config-rail-summary-head">
            <div>
              <span class="config-progress-kicker">Current Focus</span>
              <h4>{{ activeGroup.name }}</h4>
            </div>
            <span class="state-chip" :class="sectionTone(activeGroupSummary)">
              {{ activeGroupSummary.position.toString().padStart(2, "0") }}
            </span>
          </div>
          <p>{{ activeGroupSummaryText(activeGroupSummary) }}</p>
          <div class="config-rail-summary-grid">
            <span>{{ activeGroupSummary.configuredCount }}/{{ activeGroupSummary.fields.length }} 已配置</span>
            <span>{{ activeGroupSummary.requiredReadyCount }}/{{ activeGroupSummary.requiredCount || activeGroupSummary.fields.length }} 关键项</span>
            <span>{{ activeGroupSummary.disabledCount }} 待解锁</span>
          </div>
        </article>
      </aside>

      <section class="config-stage-panel">
        <header class="config-stage-header">
          <div class="config-stage-title">
            <span class="config-progress-kicker">Section {{ activeGroupSummary.position }}</span>
            <h3>{{ activeGroup.name }}</h3>
            <p>{{ activeGroupSummaryText(activeGroupSummary) }}</p>
          </div>

          <div class="config-stage-meta">
            <span class="state-chip neutral">{{ activeGroup.fields.length }} 项字段</span>
            <span class="state-chip" :class="sectionTone(activeGroupSummary)">
              {{
                activeGroupSummary.requiredCount
                  ? `${activeGroupSummary.requiredReadyCount}/${activeGroupSummary.requiredCount} 关键配置`
                  : "无关键项"
              }}
            </span>
            <span v-if="activeGroupSummary.disabledCount" class="state-chip warning">
              {{ activeGroupSummary.disabledCount }} 项待解锁
            </span>
          </div>
        </header>

        <div class="config-stage-banner">
          <span>字段修改会实时影响命令预览、stage/job 计划和存储落点。</span>
        </div>

        <div class="config-grid config-stage-grid">
          <article
            v-for="field in activeGroup.fields"
            :key="field.key"
            class="config-field config-stage-field"
            :class="{
              wide: field.layout === 'full' || field.component === 'textarea' || field.component === 'multiselect',
              'switch-card': field.component === 'switch',
              disabled: isFieldDisabled(field),
              [`is-${fieldTone(field)}`]: true,
            }"
          >
            <div v-if="field.component !== 'switch'" class="config-field-head">
              <div class="config-field-copy">
                <label :for="field.key">{{ field.label }}</label>
                <small class="config-field-key">{{ field.key }}</small>
              </div>
              <span class="field-badges">
                <small v-if="field.required">必填</small>
                <small v-else-if="hasDisplayValue(formParams[field.key])">已设置</small>
                <small v-if="field.badge">{{ field.badge }}</small>
              </span>
            </div>

            <div class="config-control">
              <textarea
                v-if="field.component === 'textarea'"
                :id="field.key"
                :rows="field.rows ?? 4"
                :value="String(formParams[field.key] ?? '')"
                :placeholder="field.placeholder"
                :disabled="isFieldDisabled(field)"
                @input="updateField(field, $event)"
              />

              <input
                v-else-if="field.component === 'text'"
                :id="field.key"
                type="text"
                :value="String(formParams[field.key] ?? '')"
                :placeholder="field.placeholder"
                :disabled="isFieldDisabled(field)"
                @input="updateField(field, $event)"
              />

              <input
                v-else-if="field.component === 'number'"
                :id="field.key"
                type="number"
                :value="String(formParams[field.key] ?? '')"
                :placeholder="field.placeholder"
                :disabled="isFieldDisabled(field)"
                @input="updateField(field, $event)"
              />

              <SelectField
                v-else-if="field.component === 'select'"
                :model-value="String(formParams[field.key] ?? '')"
                :options="selectOptions(field)"
                :disabled="isFieldDisabled(field)"
                @update:model-value="emit('update-field', field.key, getOptionValueFromInput(field, $event))"
              />

              <ToggleSwitch
                v-else-if="field.component === 'switch'"
                :model-value="Boolean(formParams[field.key])"
                :label="field.label"
                :description="switchDescription(field)"
                :disabled="isFieldDisabled(field)"
                @update:model-value="emit('update-field', field.key, $event)"
              />

              <div v-else-if="field.component === 'multiselect'" class="multi-grid">
                <label v-for="option in field.options" :key="String(option.value)" class="multi-option">
                  <input
                    type="checkbox"
                    :checked="isMultiSelected(field, option.value)"
                    :disabled="isFieldDisabled(field)"
                    @change="toggleMultiValue(field, option.value, ($event.target as HTMLInputElement).checked)"
                  />
                  <span>{{ option.label }}</span>
                </label>
              </div>
            </div>

            <div
              v-if="field.key === 'browser_session_id' && String(formParams.browser_provider ?? '') === 'browsermint'"
              class="field-meta field-meta-actions"
            >
              <button
                type="button"
                class="btn ghost small"
                :disabled="!browsermintSelectedSession"
                @click="emit('open-browsermint')"
              >
                打开 Browsermint
              </button>
              <button
                type="button"
                class="btn ghost small"
                :disabled="browsermintLoading"
                @click="emit('refresh-browsermint')"
              >
                {{ browsermintLoading ? "刷新中…" : "刷新会话" }}
              </button>
              <span v-if="browsermintSelectedSession">
                {{ browsermintSelectedSession.status }} · {{ browsermintSelectedSession.name }}
              </span>
            </div>

            <div v-if="helperLines(field).length" class="field-meta field-meta-copy">
              <span v-for="line in helperLines(field)" :key="line">{{ line }}</span>
            </div>
          </article>
        </div>
      </section>
    </div>

    <div v-else class="empty-state">当前任务没有可编辑配置。</div>
  </section>
</template>

<style scoped>
.config-tab {
  gap: 20px;
}

.config-shell {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
}

.config-progress-strip,
.config-rail,
.config-stage-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  border-radius: 22px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.92)),
    var(--panel-strong);
  box-shadow: 0 16px 34px rgba(22, 32, 43, 0.05);
}

.config-progress-strip {
  grid-column: 1 / -1;
  gap: 14px;
}

.config-progress-kicker,
.config-group-order {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}

.config-progress-copy,
.config-rail-head > div,
.config-rail-summary-head > div,
.config-stage-title {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-progress-copy strong,
.config-rail-head h3,
.config-rail-summary-head h4,
.config-stage-title h3 {
  margin: 0;
}

.config-progress-copy p,
.config-rail-summary p,
.config-stage-title p {
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}

.config-progress-visual {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.config-progress {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.config-progress-track {
  height: 8px;
  border-radius: 999px;
  background: rgba(20, 35, 55, 0.08);
  overflow: hidden;
}

.config-progress-track > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #c87a49, #1f4fd1);
}

.config-progress-meta,
.config-group-card-foot,
.config-rail-summary-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  color: var(--muted);
  font-size: 12px;
}

.config-rail-head,
.config-rail-summary-head,
.config-stage-header,
.config-group-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.config-group-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.config-group-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding: 14px 15px;
  border-radius: 16px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(247, 249, 252, 0.88);
  text-align: left;
  transition: transform 0.14s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.config-group-card:hover {
  transform: translateY(-1px);
  border-color: rgba(31, 79, 209, 0.18);
}

.config-group-card.active {
  border-color: rgba(31, 79, 209, 0.22);
  background: linear-gradient(145deg, rgba(234, 242, 255, 0.92), rgba(255, 255, 255, 0.98));
  box-shadow: 0 14px 30px rgba(31, 79, 209, 0.1);
}

.config-group-card strong {
  font-size: 16px;
  color: var(--ink);
}

.config-group-card p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.55;
}

.config-rail-summary {
  background: rgba(248, 250, 252, 0.9);
}

.config-rail-summary.warning {
  background: linear-gradient(180deg, rgba(154, 102, 20, 0.08), rgba(255, 255, 255, 0.96));
}

.config-rail-summary.success {
  background: linear-gradient(180deg, rgba(23, 118, 88, 0.08), rgba(255, 255, 255, 0.96));
}

.config-stage-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.config-stage-banner {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(31, 79, 209, 0.08);
  background: linear-gradient(180deg, rgba(31, 79, 209, 0.06), rgba(255, 255, 255, 0.94));
}

.config-stage-banner span,
.config-field-key,
.field-meta span {
  color: var(--muted);
  line-height: 1.6;
}

.config-stage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.config-stage-field {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
}

.config-stage-field::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  border-radius: 18px 0 0 18px;
  background: rgba(22, 32, 43, 0.08);
}

.config-stage-field.is-success::before {
  background: rgba(23, 118, 88, 0.62);
}

.config-stage-field.is-warning::before {
  background: rgba(154, 102, 20, 0.62);
}

.config-stage-field.disabled {
  opacity: 0.66;
  background: rgba(246, 247, 249, 0.88);
}

.config-stage-field.wide,
.config-stage-field.switch-card {
  grid-column: span 2;
}

.config-field-head,
.config-field-copy {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.config-field-copy {
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
}

.config-field-head label {
  font-weight: 700;
  color: var(--ink);
}

.field-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.field-badges small {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(20, 35, 55, 0.06);
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
}

.config-control {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.config-control input,
.config-control textarea,
.config-control :deep(.select-field),
.config-control :deep(.toggle-switch) {
  width: 100%;
}

.config-control input,
.config-control textarea {
  min-height: 48px;
  padding: 0 14px;
  border-radius: 14px;
  border: 1px solid rgba(22, 32, 43, 0.12);
  background: rgba(255, 255, 255, 0.96);
  color: var(--ink);
}

.config-control textarea {
  min-height: 120px;
  padding: 12px 14px;
  resize: vertical;
}

.multi-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.multi-option {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 12px;
  border-radius: 14px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(247, 249, 252, 0.92);
}

.field-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 10px;
}

.field-meta-actions {
  align-items: center;
}

.field-meta-actions span {
  color: var(--muted);
  font-size: 12px;
}

@media (max-width: 1280px) {
  .config-shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 860px) {
  .config-stage-grid,
  .multi-grid {
    grid-template-columns: 1fr;
  }

  .config-stage-field.wide,
  .config-stage-field.switch-card {
    grid-column: span 1;
  }
}

@media (max-width: 640px) {
  .config-progress-strip,
  .config-rail,
  .config-stage-panel {
    padding: 16px;
    border-radius: 18px;
  }
}
</style>
