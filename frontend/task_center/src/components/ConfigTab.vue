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
  if (!group.fields.length) return "暂无字段";
  if (missingRequired > 0) {
    return `${group.configuredCount}/${group.fields.length} 已配置，缺 ${missingRequired} 必填`;
  }
  return `${group.configuredCount}/${group.fields.length} 已配置`;
}

function activeGroupSummaryText(group: GroupProgressSummary): string {
  const missingRequired = Math.max(group.requiredCount - group.requiredReadyCount, 0);
  if (!group.requiredCount) {
    return `可选项 ${group.fields.length}，当前已配置 ${group.configuredCount}。`;
  }
  if (missingRequired > 0) {
    return `必填项还差 ${missingRequired} 项。`;
  }
  return "必填项已齐备。";
}

function completionPercent(done: number, total: number): number {
  if (!total) return 0;
  return Math.round((done / total) * 100);
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
        <p>左侧查看进度与分段，右侧专注当前 section 字段编辑。</p>
      </div>
      <span class="state-chip" :class="previewLoading ? 'running' : 'neutral'">
        {{ previewLoading ? "命令解析中" : "命令已同步" }}
      </span>
    </div>

    <div v-if="activeGroup && activeGroupSummary" class="config-shell">
      <aside class="config-nav" aria-label="Section 导航">
        <section class="config-overview">
          <div class="config-overview-head">
            <span class="config-progress-kicker">Overall</span>
            <span class="state-chip neutral">{{ overallCompletion }}%</span>
          </div>
          <div class="config-progress-track" aria-hidden="true">
            <span :style="{ width: `${overallCompletion}%` }" />
          </div>
          <div class="config-overview-metrics">
            <span>{{ totalConfiguredCount }}/{{ totalFieldCount }} 已配置</span>
            <span>{{ totalRequiredReadyCount }}/{{ totalRequiredCount || 0 }} 必填就绪</span>
          </div>
        </section>

        <div class="config-group-list">
          <button
            v-for="group in groupSummaries"
            :key="group.name"
            class="config-group-item"
            :class="{ active: group.name === selectedGroup }"
            @click="emit('select-group', group.name)"
          >
            <div class="config-group-line">
              <strong>{{ group.name }}</strong>
              <span class="state-chip small" :class="sectionTone(group)">
                {{ completionPercent(group.configuredCount, group.fields.length) }}%
              </span>
            </div>
            <p>{{ groupSummaryText(group) }}</p>
            <div class="config-group-meta">
              <span>{{ group.requiredReadyCount }}/{{ group.requiredCount || group.fields.length }} 必填</span>
              <span>{{ group.configuredCount }}/{{ group.fields.length }} 已配置</span>
              <span v-if="group.disabledCount">{{ group.disabledCount }} 待解锁</span>
            </div>
          </button>
        </div>
      </aside>

      <section class="config-main">
        <header class="config-main-head">
          <div class="config-main-title">
            <span class="config-progress-kicker">Section {{ activeGroupSummary.position }}</span>
            <h3>{{ activeGroup.name }}</h3>
            <p>{{ activeGroupSummaryText(activeGroupSummary) }}</p>
          </div>
          <div class="config-main-chips">
            <span class="state-chip neutral">{{ activeCompletion }}% 完成度</span>
            <span class="state-chip neutral">{{ activeGroup.fields.length }} 项字段</span>
            <span class="state-chip" :class="sectionTone(activeGroupSummary)">
              {{
                activeGroupSummary.requiredCount
                  ? `${activeGroupSummary.requiredReadyCount}/${activeGroupSummary.requiredCount} 必填`
                  : "无必填"
              }}
            </span>
            <span v-if="activeGroupSummary.disabledCount" class="state-chip warning">
              {{ activeGroupSummary.disabledCount }} 待解锁
            </span>
          </div>
        </header>

        <div class="config-field-grid">
          <article
            v-for="field in activeGroup.fields"
            :key="field.key"
            class="config-field"
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
                <small v-if="isFieldDisabled(field)">待解锁</small>
                <small v-else-if="hasDisplayValue(formParams[field.key])">已配置</small>
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

              <div v-else-if="field.component === 'multiselect'" class="multi-card-grid">
                <label
                  v-for="option in field.options"
                  :key="String(option.value)"
                  class="multi-card"
                  :class="{
                    selected: isMultiSelected(field, option.value),
                    disabled: isFieldDisabled(field),
                  }"
                >
                  <input
                    class="multi-card-input"
                    type="checkbox"
                    :checked="isMultiSelected(field, option.value)"
                    :disabled="isFieldDisabled(field)"
                    @change="toggleMultiValue(field, option.value, ($event.target as HTMLInputElement).checked)"
                  />
                  <span class="multi-card-title">{{ option.label }}</span>
                  <small v-if="option.description" class="multi-card-desc">{{ option.description }}</small>
                  <span class="multi-card-state">
                    {{ isMultiSelected(field, option.value) ? "已选" : "可选" }}
                  </span>
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
  gap: 16px;
}

.config-shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.config-nav,
.config-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.94));
}

.config-nav {
  position: sticky;
  top: 12px;
}

.config-overview {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(247, 249, 252, 0.9);
}

.config-overview-head,
.config-group-line,
.config-main-head,
.config-field-head,
.config-field-copy,
.field-meta-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.config-progress-kicker,
.config-field-key {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--muted);
}

.config-main-head {
  align-items: center;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(22, 32, 43, 0.08);
  flex-wrap: wrap;
}

.config-main-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.config-main-title h3 {
  margin: 0;
  font-size: 22px;
  line-height: 1.2;
}

.config-main-title p {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
}

.config-main-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.config-progress-track {
  height: 7px;
  border-radius: 999px;
  background: rgba(20, 35, 55, 0.1);
  overflow: hidden;
}

.config-progress-track > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #c87a49, #1f4fd1);
}

.config-overview-metrics,
.config-group-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  color: var(--muted);
  font-size: 12px;
}

.config-group-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.config-group-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: 11px 12px;
  border-radius: 14px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(247, 249, 252, 0.7);
  text-align: left;
  transition: border-color 0.16s ease, background 0.16s ease;
}

.config-group-item:hover {
  border-color: rgba(31, 79, 209, 0.18);
  background: rgba(238, 245, 255, 0.78);
}

.config-group-item.active {
  border-color: rgba(31, 79, 209, 0.22);
  background: linear-gradient(145deg, rgba(234, 242, 255, 0.92), rgba(255, 255, 255, 0.98));
}

.config-group-item strong {
  font-size: 14px;
  line-height: 1.35;
  color: var(--ink);
}

.config-group-item p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.4;
}

.field-meta span {
  color: var(--muted);
  line-height: 1.5;
}

.config-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.config-field {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
}

.config-field::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 2px;
  border-radius: 16px 0 0 16px;
  background: rgba(22, 32, 43, 0.08);
}

.config-field.is-success::before {
  background: rgba(23, 118, 88, 0.62);
}

.config-field.is-warning::before {
  background: rgba(154, 102, 20, 0.62);
}

.config-field.disabled {
  opacity: 0.66;
  background: rgba(246, 247, 249, 0.88);
}

.config-field.wide,
.config-field.switch-card {
  grid-column: span 2;
}

.config-field-copy {
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 2px;
}

.config-field-head label {
  font-weight: 600;
  color: var(--ink);
  line-height: 1.35;
}

.field-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.field-badges small {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  background: rgba(20, 35, 55, 0.06);
  color: var(--muted);
  font-size: 11px;
  font-weight: 600;
}

.config-control {
  display: flex;
  flex-direction: column;
  gap: 8px;
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

.multi-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
}

.multi-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  min-height: 72px;
  padding: 10px 11px;
  border-radius: 14px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(247, 249, 252, 0.86);
  cursor: pointer;
}

.multi-card.selected {
  border-color: rgba(31, 79, 209, 0.28);
  background: linear-gradient(160deg, rgba(236, 244, 255, 0.94), rgba(255, 255, 255, 0.98));
}

.multi-card.disabled {
  cursor: not-allowed;
}

.multi-card-input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.multi-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.multi-card-desc {
  font-size: 11px;
  color: var(--muted);
}

.multi-card-state {
  margin-top: auto;
  font-size: 11px;
  color: var(--muted);
}

.field-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
}

.field-meta-actions span {
  color: var(--muted);
  font-size: 12px;
}

@media (max-width: 1200px) {
  .config-shell {
    grid-template-columns: 220px minmax(0, 1fr);
  }
}

@media (max-width: 940px) {
  .config-shell {
    grid-template-columns: 1fr;
  }

  .config-nav {
    position: static;
  }

  .config-group-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .config-field-grid,
  .config-group-list,
  .multi-card-grid {
    grid-template-columns: 1fr;
  }

  .config-field.wide,
  .config-field.switch-card {
    grid-column: span 1;
  }
}

@media (max-width: 640px) {
  .config-nav,
  .config-main {
    padding: 14px;
    border-radius: 16px;
  }

  .config-main-title h3 {
    font-size: 20px;
  }
}
</style>
