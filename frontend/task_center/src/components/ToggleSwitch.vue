<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    label: string;
    description?: string;
    disabled?: boolean;
    compact?: boolean;
    onLabel?: string;
    offLabel?: string;
  }>(),
  {
    description: "",
    disabled: false,
    compact: false,
    onLabel: "开启",
    offLabel: "关闭",
  },
);

const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void;
}>();

function toggle() {
  if (props.disabled) return;
  emit("update:modelValue", !props.modelValue);
}
</script>

<template>
  <button
    type="button"
    class="toggle-switch"
    :class="{ on: modelValue, off: !modelValue, compact, disabled }"
    role="switch"
    :aria-checked="modelValue"
    :aria-label="label"
    :disabled="disabled"
    @click="toggle"
  >
    <span class="toggle-copy" :class="{ compact: compact }">
      <strong>{{ label }}</strong>
      <span v-if="description && !compact">{{ description }}</span>
    </span>

    <span class="toggle-control">
      <span class="toggle-status">{{ modelValue ? onLabel : offLabel }}</span>
      <span class="toggle-track" aria-hidden="true">
        <span class="toggle-thumb" />
      </span>
    </span>
  </button>
</template>
