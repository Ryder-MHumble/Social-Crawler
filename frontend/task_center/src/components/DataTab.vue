<script setup lang="ts">
import { computed } from "vue";
import SelectField from "./SelectField.vue";
import type {
  DataBrowseMode,
  DataFileFilters,
  DataFileInfo,
  DataFilePreview,
  SqliteRow,
  SqliteRowFilters,
  SqliteRowsResponse,
  SqliteStats,
  SqliteTableSummary,
  TaskRun,
} from "../types";

const props = defineProps<{
  mode: DataBrowseMode;
  tables: SqliteTableSummary[];
  supportedTables: string[];
  filters: SqliteRowFilters;
  fileFilters: DataFileFilters;
  files: DataFileInfo[];
  selectedFilePath: string | null;
  filePreview: DataFilePreview | null;
  fileLoading: boolean;
  sqlitePath: string;
  stats: SqliteStats | null;
  rows: SqliteRowsResponse | null;
  selectedRow: SqliteRow | null;
  selectedRun: TaskRun | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  (event: "switch-mode", value: DataBrowseMode): void;
  (event: "update-filter", key: keyof SqliteRowFilters, value: string | number): void;
  (event: "update-file-filter", key: keyof DataFileFilters, value: string): void;
  (event: "refresh"): void;
  (event: "refresh-files"): void;
  (event: "open-row", row: SqliteRow): void;
  (event: "close-row"): void;
  (event: "focus-execution"): void;
  (event: "clear-run-filter"): void;
  (event: "select-file", filePath: string): void;
}>();

const modeOptions: Array<{ value: DataBrowseMode; label: string }> = [
  { value: "sqlite", label: "清洗数据" },
  { value: "files", label: "文件结果" },
];

const sqliteTableOptions = computed(() =>
  props.supportedTables.map((table) => ({
    value: table,
    label: table,
  })),
);

const platformOptions = [
  { value: "", label: "全部平台" },
  { value: "xhs", label: "Xiaohongshu" },
  { value: "dy", label: "Douyin" },
  { value: "bili", label: "Bilibili" },
  { value: "zhihu", label: "Zhihu" },
  { value: "wb", label: "Weibo" },
  { value: "tieba", label: "Tieba" },
  { value: "ks", label: "Kuaishou" },
];

const entityTypeOptions = [
  { value: "", label: "全部实体" },
  { value: "content", label: "内容" },
  { value: "comment", label: "评论" },
  { value: "creator", label: "创作者" },
];

const cleanStatusOptions = [
  { value: "", label: "全部状态" },
  { value: "accepted", label: "Accepted" },
  { value: "filtered", label: "Filtered" },
  { value: "deduped", label: "Deduped" },
  { value: "error", label: "Error" },
];

const fileTypeOptions = [
  { value: "", label: "全部类型" },
  { value: "json", label: "JSON" },
  { value: "csv", label: "CSV" },
  { value: "xlsx", label: "XLSX" },
  { value: "xls", label: "XLS" },
];

const runSaveOption = computed(() =>
  String(
    props.selectedRun?.normalized_params.save_option ??
      props.selectedRun?.normalized_params.save_data_option ??
      "",
  )
    .trim()
    .toLowerCase(),
);

const visibleFiles = computed(() => {
  const query = props.fileFilters.q.trim().toLowerCase();
  if (!query) return props.files;
  return props.files.filter((file) =>
    [file.name, file.path, file.type].some((value) => String(value).toLowerCase().includes(query)),
  );
});

const selectedFile = computed(
  () =>
    props.files.find((file) => file.path === props.selectedFilePath) ??
    visibleFiles.value[0] ??
    null,
);

const filePreviewRows = computed<Array<Record<string, unknown>>>(() => {
  const data = props.filePreview?.data;
  if (!Array.isArray(data)) return [];
  return data.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null);
});

const filePreviewColumns = computed(() => {
  if (props.filePreview?.columns?.length) {
    return props.filePreview.columns.slice(0, 10);
  }
  const firstRow = filePreviewRows.value[0];
  return firstRow ? Object.keys(firstRow).slice(0, 10) : [];
});

function prettyCell(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function pageLabel(): string {
  if (!props.rows) return "0 / 0";
  if (props.rows.total === 0) return "0 / 0";
  const start = props.filters.offset + 1;
  const end = Math.min(props.filters.offset + props.filters.limit, props.rows.total);
  return `${start}-${end} / ${props.rows.total}`;
}

function formatTime(value?: string | number | null): string {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatBytes(value?: number | null): string {
  if (!value) return "0 B";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function fileDownloadUrl(path: string): string {
  return `/api/data/download/${encodeURI(path)}`;
}

function fileResultLabel(): string {
  if (runSaveOption.value === "csv") return "CSV 文件";
  if (runSaveOption.value === "excel") return "Excel 文件";
  return "JSON 文件";
}

function resultDescription(): string {
  if (props.mode === "sqlite") {
    return "只读浏览 SQLite 清洗结果，支持 run、平台、实体和清洗状态筛选。";
  }
  return "浏览 runtime/data 目录下的 JSON / CSV / Excel 结果文件，并预览原始抓取输出。";
}
</script>

<template>
  <section class="tab-panel">
    <div class="tab-panel-head">
      <div>
        <h2>数据</h2>
        <p>{{ resultDescription() }}</p>
      </div>

      <div class="data-toolbar">
        <div class="data-mode-tabs">
          <button
            v-for="option in modeOptions"
            :key="option.value"
            class="data-mode-tab"
            :class="{ active: mode === option.value }"
            @click="emit('switch-mode', option.value)"
          >
            {{ option.label }}
          </button>
        </div>

        <button v-if="mode === 'sqlite'" class="btn secondary" @click="emit('refresh')">刷新 SQLite</button>
        <button v-else class="btn secondary" @click="emit('refresh-files')">刷新文件</button>
      </div>
    </div>

    <article v-if="selectedRun" class="run-context-card">
      <div class="run-context-copy">
        <span class="run-context-kicker">当前结果上下文</span>
        <h3>{{ selectedRun.title }}</h3>
        <p>{{ selectedRun.id }} · {{ formatTime(selectedRun.started_at) }} · {{ selectedRun.status }}</p>
        <p v-if="mode === 'files'">
          文件视图不按 run_id 建索引，当前优先展示与本次任务平台和输出类型匹配的最近文件。
        </p>
      </div>

      <div class="run-context-metrics">
        <div class="run-context-metric">
          <span>Accepted</span>
          <strong>{{ selectedRun.metrics.accepted }}</strong>
        </div>
        <div class="run-context-metric">
          <span>Filtered</span>
          <strong>{{ selectedRun.metrics.filtered }}</strong>
        </div>
        <div class="run-context-metric">
          <span>Deduped</span>
          <strong>{{ selectedRun.metrics.deduped }}</strong>
        </div>
      </div>

      <div class="run-context-actions">
        <span class="state-chip" :class="mode === 'sqlite' && filters.run_id ? 'success' : 'neutral'">
          {{ mode === "sqlite" ? (filters.run_id ? "已过滤到本次 run" : "当前为全局视图") : "文件视图按目录浏览" }}
        </span>
        <span class="state-chip neutral">
          {{ mode === "sqlite" ? `表：${filters.table}` : `${fileResultLabel()} · runtime/data` }}
        </span>
        <button class="btn ghost small" @click="emit('focus-execution')">查看执行</button>
        <button v-if="mode === 'sqlite'" class="btn ghost small" :disabled="!filters.run_id" @click="emit('clear-run-filter')">
          清除 run 过滤
        </button>
      </div>
    </article>

    <template v-if="mode === 'sqlite'">
      <div class="data-filters">
        <SelectField
          :model-value="filters.table"
          :options="sqliteTableOptions"
          @update:model-value="emit('update-filter', 'table', $event)"
        />
        <input :value="filters.run_id" placeholder="run_id" @input="emit('update-filter', 'run_id', ($event.target as HTMLInputElement).value)" />
        <input :value="filters.task_slug" placeholder="task_slug" @input="emit('update-filter', 'task_slug', ($event.target as HTMLInputElement).value)" />
        <SelectField
          :model-value="filters.platform"
          :options="platformOptions"
          @update:model-value="emit('update-filter', 'platform', $event)"
        />
        <SelectField
          :model-value="filters.entity_type"
          :options="entityTypeOptions"
          @update:model-value="emit('update-filter', 'entity_type', $event)"
        />
        <SelectField
          :model-value="filters.clean_status"
          :options="cleanStatusOptions"
          @update:model-value="emit('update-filter', 'clean_status', $event)"
        />
        <input class="search" :value="filters.q" placeholder="关键词 / 文本搜索" @input="emit('update-filter', 'q', ($event.target as HTMLInputElement).value)" />
      </div>

      <div class="data-overview">
        <article class="data-stat">
          <span>当前表</span>
          <strong>{{ filters.table }}</strong>
        </article>
        <article class="data-stat">
          <span>结果数</span>
          <strong>{{ rows?.total ?? 0 }}</strong>
        </article>
        <article class="data-stat">
          <span>Accepted</span>
          <strong>{{ stats?.observation_status_counts.accepted ?? 0 }}</strong>
        </article>
        <article class="data-stat">
          <span>Filtered</span>
          <strong>{{ stats?.observation_status_counts.filtered ?? 0 }}</strong>
        </article>
      </div>

      <div class="data-layout">
        <section class="data-table-card">
          <div class="table-toolbar">
            <span>{{ pageLabel() }}</span>
            <div class="topbar-inline-actions">
              <button
                class="btn ghost small"
                :disabled="filters.offset === 0"
                @click="emit('update-filter', 'offset', Math.max(0, filters.offset - filters.limit))"
              >
                上一页
              </button>
              <button
                class="btn ghost small"
                :disabled="(rows?.total ?? 0) <= filters.offset + filters.limit"
                @click="emit('update-filter', 'offset', filters.offset + filters.limit)"
              >
                下一页
              </button>
            </div>
          </div>

          <div v-if="loading" class="empty-state">数据加载中…</div>
          <div v-else-if="rows?.rows.length" class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th v-for="column in rows.columns.slice(0, 8)" :key="column">{{ column }}</th>
                  <th>详情</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rows.rows" :key="row.id">
                  <td v-for="column in rows.columns.slice(0, 8)" :key="`${row.id}-${column}`">
                    {{ prettyCell(row[column]) }}
                  </td>
                  <td>
                    <button class="btn ghost small" @click="emit('open-row', row)">查看</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty-state">
            {{ selectedRun ? `当前 run 在 ${filters.table} 下还没有匹配记录，可以试试切换别的表。` : "当前筛选条件下没有数据。" }}
          </div>
        </section>

        <aside class="row-drawer">
          <div class="row-drawer-head">
            <h3>原始 JSON</h3>
            <button class="btn ghost small" :disabled="!selectedRow" @click="emit('close-row')">关闭</button>
          </div>
          <pre v-if="selectedRow"><code>{{ JSON.stringify(selectedRow, null, 2) }}</code></pre>
          <div v-else class="empty-state">从表格中选择一行后，这里会展示完整记录。</div>
        </aside>
      </div>
    </template>

    <template v-else>
      <div class="file-filters">
        <SelectField
          :model-value="fileFilters.platform"
          :options="platformOptions"
          @update:model-value="emit('update-file-filter', 'platform', $event)"
        />
        <SelectField
          :model-value="fileFilters.file_type"
          :options="fileTypeOptions"
          @update:model-value="emit('update-file-filter', 'file_type', $event)"
        />
        <input
          class="search"
          :value="fileFilters.q"
          placeholder="按文件名 / 路径搜索"
          @input="emit('update-file-filter', 'q', ($event.target as HTMLInputElement).value)"
        />
      </div>

      <div class="data-overview">
        <article class="data-stat">
          <span>匹配文件</span>
          <strong>{{ visibleFiles.length }}</strong>
        </article>
        <article class="data-stat">
          <span>当前类型</span>
          <strong>{{ fileFilters.file_type || "全部" }}</strong>
        </article>
        <article class="data-stat">
          <span>选中文件</span>
          <strong>{{ selectedFile?.name || "未选择" }}</strong>
        </article>
        <article class="data-stat">
          <span>预览记录</span>
          <strong>{{ filePreview?.total ?? 0 }}</strong>
        </article>
      </div>

      <div class="file-browser-layout">
        <aside class="file-sidebar">
          <div class="table-toolbar">
            <span>runtime/data</span>
            <span class="state-chip neutral">{{ fileFilters.file_type || "all" }}</span>
          </div>

          <div v-if="fileLoading && !files.length" class="empty-state">文件列表加载中…</div>
          <div v-else-if="visibleFiles.length" class="file-list">
            <button
              v-for="file in visibleFiles"
              :key="file.path"
              class="file-item"
              :class="{ active: file.path === selectedFilePath }"
              @click="emit('select-file', file.path)"
            >
              <div class="file-item-copy">
                <strong>{{ file.name }}</strong>
                <span>{{ file.path }}</span>
              </div>
              <div class="file-item-meta">
                <small>{{ file.type.toUpperCase() }}</small>
                <small>{{ file.record_count ?? "—" }} rows</small>
                <small>{{ formatBytes(file.size) }}</small>
                <small>{{ formatTime(file.modified_at) }}</small>
              </div>
            </button>
          </div>
          <div v-else class="empty-state">当前筛选条件下没有可预览的文件。</div>
        </aside>

        <section class="file-preview-card">
          <div v-if="selectedFile" class="preview-stack">
            <div class="file-preview-head">
              <div>
                <h3>{{ selectedFile.name }}</h3>
                <p>{{ selectedFile.path }}</p>
              </div>
              <a class="btn ghost small" :href="fileDownloadUrl(selectedFile.path)" target="_blank" rel="noreferrer">
                下载原文件
              </a>
            </div>

            <div class="kv-table file-kv-table">
              <div class="kv-row">
                <span>类型</span>
                <strong>{{ selectedFile.type.toUpperCase() }}</strong>
              </div>
              <div class="kv-row">
                <span>大小</span>
                <strong>{{ formatBytes(selectedFile.size) }}</strong>
              </div>
              <div class="kv-row">
                <span>记录数</span>
                <strong>{{ selectedFile.record_count ?? filePreview?.total ?? "—" }}</strong>
              </div>
              <div class="kv-row">
                <span>最近修改</span>
                <strong>{{ formatTime(selectedFile.modified_at) }}</strong>
              </div>
              <div class="kv-row">
                <span>SQLite</span>
                <code>{{ sqlitePath }}</code>
              </div>
            </div>

            <div v-if="fileLoading" class="empty-state">文件预览加载中…</div>

            <div v-else-if="filePreviewRows.length" class="table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    <th v-for="column in filePreviewColumns" :key="column">{{ column }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, index) in filePreviewRows" :key="`${selectedFile.path}-${index}`">
                    <td v-for="column in filePreviewColumns" :key="`${index}-${column}`">
                      {{ prettyCell(row[column]) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <article class="row-drawer file-json-view">
              <div class="row-drawer-head">
                <h3>原始预览</h3>
                <span>{{ filePreview?.total ?? 0 }} records</span>
              </div>
              <pre v-if="filePreview"><code>{{ JSON.stringify(filePreview.data, null, 2) }}</code></pre>
              <div v-else class="empty-state">选择文件后，这里会展示预览内容。</div>
            </article>
          </div>

          <div v-else class="empty-state">从左侧选择文件后，这里会展示表格预览和原始内容。</div>
        </section>
      </div>
    </template>
  </section>
</template>
