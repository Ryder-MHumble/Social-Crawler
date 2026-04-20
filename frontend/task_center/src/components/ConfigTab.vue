<script setup lang="ts">
import { computed } from "vue";
import SelectField from "./SelectField.vue";
import ToggleSwitch from "./ToggleSwitch.vue";
import type { GroupedFieldSection, Primitive, TaskFieldSchema } from "../types";

const props = defineProps<{
  groups: GroupedFieldSection[];
  selectedGroup: string;
  formParams: Record<string, unknown>;
  previewLoading: boolean;
}>();

const emit = defineEmits<{
  (event: "select-group", groupName: string): void;
  (event: "update-field", key: string, value: unknown): void;
}>();

const activeGroup = computed(
  () => props.groups.find((group) => group.name === props.selectedGroup) ?? props.groups[0] ?? null,
);

function isSameValue(actual: unknown, expected: unknown): boolean {
  if (Array.isArray(actual) && Array.isArray(expected)) {
    return actual.length === expected.length && actual.every((value, index) => value === expected[index]);
  }
  return actual === expected;
}

function isFieldDisabled(field: TaskFieldSchema): boolean {
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
  <section class="tab-panel">
    <div class="tab-panel-head">
      <div>
        <h2>配置</h2>
        <p>按字段分组切换，只编辑当前组，不再把所有参数平铺出来。</p>
      </div>
      <span class="state-chip" :class="previewLoading ? 'running' : 'neutral'">
        {{ previewLoading ? "命令解析中" : "命令已同步" }}
      </span>
    </div>

    <div class="group-tabs">
      <button
        v-for="group in groups"
        :key="group.name"
        class="group-tab"
        :class="{ active: group.name === selectedGroup }"
        @click="emit('select-group', group.name)"
      >
        <strong>{{ group.name }}</strong>
        <span>{{ group.fields.length }} 项</span>
      </button>
    </div>

    <div v-if="activeGroup" class="config-grid">
      <article
        v-for="field in activeGroup.fields"
        :key="field.key"
        class="config-field"
        :class="{
          wide: field.layout === 'full' || field.component === 'textarea' || field.component === 'multiselect',
          'switch-card': field.component === 'switch',
        }"
      >
        <div v-if="field.component !== 'switch'" class="config-field-head">
          <label :for="field.key">{{ field.label }}</label>
          <span class="field-badges">
            <small v-if="field.required">必填</small>
            <small v-if="field.badge">{{ field.badge }}</small>
          </span>
        </div>

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

        <div v-if="helperLines(field).length" class="field-meta">
          <span v-for="line in helperLines(field)" :key="line">{{ line }}</span>
        </div>
      </article>
    </div>
  </section>
</template>
