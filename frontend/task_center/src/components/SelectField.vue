<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

export interface SelectFieldOption {
  value: string;
  label: string;
  description?: string;
}

const props = withDefaults(
  defineProps<{
    modelValue: string;
    options: SelectFieldOption[];
    disabled?: boolean;
    compact?: boolean;
    placeholder?: string;
  }>(),
  {
    disabled: false,
    compact: false,
    placeholder: "请选择",
  },
);

const emit = defineEmits<{
  (event: "update:modelValue", value: string): void;
}>();

const rootRef = ref<HTMLElement | null>(null);
const open = ref(false);
const activeIndex = ref(0);

const selectedOption = computed(() => props.options.find((option) => option.value === props.modelValue) ?? null);

const displayLabel = computed(() => selectedOption.value?.label ?? props.placeholder);
const displayDescription = computed(() =>
  selectedOption.value?.description && !props.compact ? selectedOption.value.description : "",
);

function clampIndex(index: number): number {
  if (!props.options.length) return 0;
  return Math.min(props.options.length - 1, Math.max(0, index));
}

function openMenu() {
  if (props.disabled || !props.options.length) return;
  open.value = true;
  const selectedIndex = props.options.findIndex((option) => option.value === props.modelValue);
  activeIndex.value = selectedIndex >= 0 ? selectedIndex : 0;
}

function closeMenu() {
  open.value = false;
}

function toggleMenu() {
  if (open.value) {
    closeMenu();
    return;
  }
  openMenu();
}

function selectOption(value: string) {
  emit("update:modelValue", value);
  closeMenu();
}

function onTriggerKeydown(event: KeyboardEvent) {
  if (props.disabled) return;
  if (event.key === "ArrowDown") {
    event.preventDefault();
    if (!open.value) {
      openMenu();
      return;
    }
    activeIndex.value = clampIndex(activeIndex.value + 1);
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    if (!open.value) {
      openMenu();
      return;
    }
    activeIndex.value = clampIndex(activeIndex.value - 1);
    return;
  }
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (!open.value) {
      openMenu();
      return;
    }
    const option = props.options[activeIndex.value];
    if (option) selectOption(option.value);
    return;
  }
  if (event.key === "Escape") {
    closeMenu();
  }
}

function onDocumentPointerDown(event: PointerEvent) {
  if (!open.value) return;
  const target = event.target as Node | null;
  if (target && rootRef.value?.contains(target)) return;
  closeMenu();
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (!open.value) return;
  if (event.key === "Escape") closeMenu();
}

watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) closeMenu();
  },
);

watch(
  () => props.options,
  (options) => {
    if (!options.length) {
      closeMenu();
      return;
    }
    activeIndex.value = clampIndex(activeIndex.value);
  },
);

onMounted(() => {
  document.addEventListener("pointerdown", onDocumentPointerDown);
  document.addEventListener("keydown", onDocumentKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown);
  document.removeEventListener("keydown", onDocumentKeydown);
});
</script>

<template>
  <div ref="rootRef" class="select-field" :class="{ compact: compact, disabled: disabled, open: open }">
    <button
      type="button"
      class="select-field-trigger"
      :disabled="disabled"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggleMenu"
      @keydown="onTriggerKeydown"
    >
      <span class="select-value">
        <strong>{{ displayLabel }}</strong>
        <small v-if="displayDescription">{{ displayDescription }}</small>
      </span>
      <span class="select-chevron" aria-hidden="true">
        <svg viewBox="0 0 20 20" fill="none">
          <path
            d="M5 7.5L10 12.5L15 7.5"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
    </button>

    <div v-if="open" class="select-menu" role="listbox">
      <button
        v-for="(option, index) in options"
        :key="option.value"
        type="button"
        class="select-option"
        :class="{
          selected: option.value === modelValue,
          active: index === activeIndex,
        }"
        role="option"
        :aria-selected="option.value === modelValue"
        @mouseenter="activeIndex = index"
        @click="selectOption(option.value)"
      >
        <span class="select-option-copy">
          <strong>{{ option.label }}</strong>
          <small v-if="option.description && !compact">{{ option.description }}</small>
        </span>
        <span class="select-option-check" aria-hidden="true">✓</span>
      </button>
    </div>
  </div>
</template>
