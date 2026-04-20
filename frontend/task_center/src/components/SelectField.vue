<script setup lang="ts">
export interface SelectFieldOption {
  value: string;
  label: string;
  description?: string;
}

withDefaults(
  defineProps<{
    modelValue: string;
    options: SelectFieldOption[];
    disabled?: boolean;
    compact?: boolean;
  }>(),
  {
    disabled: false,
    compact: false,
  },
);

const emit = defineEmits<{
  (event: "update:modelValue", value: string): void;
}>();
</script>

<template>
  <label class="select-field" :class="{ compact: compact, disabled: disabled }">
    <select
      :value="modelValue"
      :disabled="disabled"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
    <span class="select-chevron" aria-hidden="true">
      <svg viewBox="0 0 20 20" fill="none">
        <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </span>
  </label>
</template>
