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

const modeOptions: Array<{ value: DataBrowseMode; label: string; description: string }> = [
  { value: "sqlite", label: "SQLite 结果", description: "查看清洗后的结构化结果" },
  { value: "files", label: "文件结果", description: "查看 runtime/data 原始文件" },
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
  if (props.filePreview?.columns?.length) return props.filePreview.columns.slice(0, 8);
  const firstRow = filePreviewRows.value[0];
  return firstRow ? Object.keys(firstRow).slice(0, 8) : [];
});

const sqliteSummaryCards = computed(() => [
  {
    label: "当前表",
    value: props.filters.table,
    note: `${props.tables.find((table) => table.name === props.filters.table)?.row_count ?? 0} rows`,
  },
  {
    label: "结果数",
    value: String(props.rows?.total ?? 0),
    note: props.selectedRun ? "当前 run 视角" : "全局视角",
  },
  {
    label: "Accepted",
    value: String(props.stats?.observation_status_counts.accepted ?? 0),
    note: "已进入结果集",
  },
  {
    label: "Filtered",
    value: String(props.stats?.observation_status_counts.filtered ?? 0),
    note: "已被规则过滤",
  },
]);

const fileSummaryCards = computed(() => [
  {
    label: "匹配文件",
    value: String(visibleFiles.value.length),
    note: "基于当前筛选",
  },
  {
    label: "当前类型",
    value: props.fileFilters.file_type || "全部",
    note: "文件扩展名",
  },
  {
    label: "选中文件",
    value: selectedFile.value?.name || "未选择",
    note: selectedFile.value ? formatTime(selectedFile.value.modified_at) : "等待选择",
  },
  {
    label: "预览记录",
    value: String(props.filePreview?.total ?? 0),
    note: "原始预览数据",
  },
]);

const hasSqliteAdvancedFilters = computed(() =>
  Boolean(props.filters.run_id || props.filters.task_slug || props.filters.clean_status),
);

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
    return "围绕当前 run 浏览 SQLite 清洗结果，常用筛选前置，技术筛选下沉到高级面板。";
  }
  return "围绕当前 run 浏览 runtime/data 目录下的 JSON / CSV / Excel 文件，并预览原始输出。";
}
</script>

<template>
  <section class="tab-panel results-tab">
    <div class="tab-panel-head">
      <div>
        <h2>结果中心</h2>
        <p>{{ resultDescription() }}</p>
      </div>

      <div class="results-head-actions">
        <div class="data-mode-tabs">
          <button
            v-for="option in modeOptions"
            :key="option.value"
            class="data-mode-tab"
            :class="{ active: mode === option.value }"
            @click="emit('switch-mode', option.value)"
          >
            <strong>{{ option.label }}</strong>
            <span>{{ option.description }}</span>
          </button>
        </div>

        <button v-if="mode === 'sqlite'" class="btn secondary" @click="emit('refresh')">
          刷新 SQLite
        </button>
        <button v-else class="btn secondary" @click="emit('refresh-files')">
          刷新文件
        </button>
      </div>
    </div>

    <article v-if="selectedRun" class="run-context-card">
      <div class="run-context-copy">
        <span class="run-context-kicker">Result Context</span>
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
          {{ mode === "sqlite" ? (filters.run_id ? "已绑定当前 run" : "当前为全局结果视图") : `${fileResultLabel()} · runtime/data` }}
        </span>
        <button class="btn ghost small" @click="emit('focus-execution')">查看运行监控</button>
        <button
          v-if="mode === 'sqlite'"
          class="btn ghost small"
          :disabled="!filters.run_id"
          @click="emit('clear-run-filter')"
        >
          清除 run 过滤
        </button>
      </div>
    </article>

    <div v-if="mode === 'sqlite'" class="results-stack">
      <div class="results-summary-grid">
        <article v-for="card in sqliteSummaryCards" :key="card.label" class="summary-metric-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.note }}</small>
        </article>
      </div>

      <section class="results-filter-panel">
        <div class="filter-grid">
          <label class="filter-field">
            <span>数据表</span>
            <SelectField
              :model-value="filters.table"
              :options="sqliteTableOptions"
              @update:model-value="emit('update-filter', 'table', $event)"
            />
          </label>

          <label class="filter-field">
            <span>平台</span>
            <SelectField
              :model-value="filters.platform"
              :options="platformOptions"
              @update:model-value="emit('update-filter', 'platform', $event)"
            />
          </label>

          <label class="filter-field">
            <span>实体类型</span>
            <SelectField
              :model-value="filters.entity_type"
              :options="entityTypeOptions"
              @update:model-value="emit('update-filter', 'entity_type', $event)"
            />
          </label>

          <label class="filter-field filter-field-wide">
            <span>文本搜索</span>
            <input
              :value="filters.q"
              placeholder="关键词 / 标题 / 文本片段"
              @input="emit('update-filter', 'q', ($event.target as HTMLInputElement).value)"
            />
          </label>
        </div>

        <details class="advanced-filter-panel" :open="hasSqliteAdvancedFilters">
          <summary>高级筛选</summary>
          <div class="advanced-filter-grid">
            <label class="filter-field">
              <span>清洗状态</span>
              <SelectField
                :model-value="filters.clean_status"
                :options="cleanStatusOptions"
                @update:model-value="emit('update-filter', 'clean_status', $event)"
              />
            </label>

            <label class="filter-field">
              <span>run_id</span>
              <input
                :value="filters.run_id"
                placeholder="run_id"
                @input="emit('update-filter', 'run_id', ($event.target as HTMLInputElement).value)"
              />
            </label>

            <label class="filter-field">
              <span>task_slug</span>
              <input
                :value="filters.task_slug"
                placeholder="task_slug"
                @input="emit('update-filter', 'task_slug', ($event.target as HTMLInputElement).value)"
              />
            </label>
          </div>
        </details>
      </section>

      <div class="results-layout">
        <section class="results-main-card">
          <div class="table-toolbar">
            <div>
              <strong>{{ pageLabel() }}</strong>
              <span>SQLite · {{ props.sqlitePath }}</span>
            </div>

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

          <div v-if="loading" class="empty-state">SQLite 结果加载中…</div>
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
            {{ selectedRun ? `当前 run 在 ${filters.table} 下还没有匹配记录，可以切换表或放宽筛选条件。` : "当前筛选条件下没有数据。" }}
          </div>
        </section>

        <aside class="results-inspector">
          <div class="row-drawer-head">
            <div>
              <h3>结果 Inspector</h3>
              <p>选中一行后在这里查看完整 JSON。</p>
            </div>
            <button class="btn ghost small" :disabled="!selectedRow" @click="emit('close-row')">
              清空
            </button>
          </div>

          <pre v-if="selectedRow"><code>{{ JSON.stringify(selectedRow, null, 2) }}</code></pre>
          <div v-else class="empty-state compact">从左侧结果表格中选择一行后，这里会展示完整记录。</div>
        </aside>
      </div>
    </div>

    <div v-else class="results-stack">
      <div class="results-summary-grid">
        <article v-for="card in fileSummaryCards" :key="card.label" class="summary-metric-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.note }}</small>
        </article>
      </div>

      <section class="results-filter-panel">
        <div class="filter-grid">
          <label class="filter-field">
            <span>平台</span>
            <SelectField
              :model-value="fileFilters.platform"
              :options="platformOptions"
              @update:model-value="emit('update-file-filter', 'platform', $event)"
            />
          </label>

          <label class="filter-field">
            <span>文件类型</span>
            <SelectField
              :model-value="fileFilters.file_type"
              :options="fileTypeOptions"
              @update:model-value="emit('update-file-filter', 'file_type', $event)"
            />
          </label>

          <label class="filter-field filter-field-wide">
            <span>文件搜索</span>
            <input
              :value="fileFilters.q"
              placeholder="按文件名 / 路径搜索"
              @input="emit('update-file-filter', 'q', ($event.target as HTMLInputElement).value)"
            />
          </label>
        </div>
      </section>

      <div class="file-browser-layout">
        <aside class="file-sidebar">
          <div class="table-toolbar">
            <div>
              <strong>runtime/data</strong>
              <span>{{ visibleFiles.length }} 个匹配文件</span>
            </div>
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

            <div class="preview-kv-grid">
              <article class="summary-metric-card">
                <span>类型</span>
                <strong>{{ selectedFile.type.toUpperCase() }}</strong>
                <small>{{ fileResultLabel() }}</small>
              </article>
              <article class="summary-metric-card">
                <span>大小</span>
                <strong>{{ formatBytes(selectedFile.size) }}</strong>
                <small>{{ formatTime(selectedFile.modified_at) }}</small>
              </article>
              <article class="summary-metric-card">
                <span>记录数</span>
                <strong>{{ selectedFile.record_count ?? filePreview?.total ?? "—" }}</strong>
                <small>预览或文件统计</small>
              </article>
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

            <article class="results-inspector file-inspector">
              <div class="row-drawer-head">
                <div>
                  <h3>原始预览</h3>
                  <p>{{ filePreview?.total ?? 0 }} records · SQLite {{ sqlitePath }}</p>
                </div>
              </div>
              <pre v-if="filePreview"><code>{{ JSON.stringify(filePreview.data, null, 2) }}</code></pre>
              <div v-else class="empty-state compact">选择文件后，这里会展示原始预览内容。</div>
            </article>
          </div>

          <div v-else class="empty-state">从左侧选择文件后，这里会展示表格预览和原始内容。</div>
        </section>
      </div>
    </div>
  </section>
</template>

<style scoped>
.results-tab {
  gap: 20px;
}

.results-head-actions,
.run-context-card,
.run-context-actions,
.filter-grid,
.advanced-filter-grid,
.results-layout,
.results-summary-grid,
.file-browser-layout,
.preview-kv-grid {
  display: grid;
  gap: 12px;
}

.results-head-actions {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.data-mode-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.data-mode-tab {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(20, 35, 55, 0.08);
  background: rgba(255, 255, 255, 0.72);
  text-align: left;
  color: var(--ink);
}

.data-mode-tab.active {
  border-color: rgba(31, 79, 209, 0.24);
  background: linear-gradient(145deg, rgba(232, 241, 255, 0.88), rgba(255, 255, 255, 0.98));
  box-shadow: 0 12px 26px rgba(31, 79, 209, 0.1);
}

.data-mode-tab span {
  color: var(--muted);
  font-size: 12px;
}

.run-context-card {
  grid-template-columns: minmax(220px, 1.1fr) repeat(2, minmax(0, 1fr));
  align-items: center;
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid rgba(20, 35, 55, 0.08);
  background:
    linear-gradient(135deg, rgba(249, 244, 238, 0.88), rgba(255, 255, 255, 0.98)),
    var(--panel-strong);
  box-shadow: 0 18px 40px rgba(20, 35, 55, 0.05);
}

.run-context-copy,
.run-context-actions,
.results-stack,
.preview-stack,
.file-item-copy {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.run-context-kicker {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 4px 9px;
  border-radius: 999px;
  background: rgba(31, 79, 209, 0.1);
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.run-context-copy h3,
.file-preview-head h3 {
  margin: 0;
}

.run-context-copy p,
.file-preview-head p {
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}

.run-context-metrics,
.results-summary-grid,
.preview-kv-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.run-context-metric,
.summary-metric-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(20, 35, 55, 0.08);
  background: rgba(255, 255, 255, 0.76);
}

.run-context-metric span,
.summary-metric-card span {
  color: var(--muted);
  font-size: 12px;
}

.run-context-metric strong,
.summary-metric-card strong {
  font-size: 22px;
  font-family: "Manrope", sans-serif;
}

.summary-metric-card small {
  color: var(--muted);
}

.run-context-actions {
  align-items: flex-end;
}

.results-filter-panel,
.results-main-card,
.results-inspector,
.file-sidebar,
.file-preview-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(20, 35, 55, 0.08);
  background: rgba(255, 255, 255, 0.84);
}

.filter-grid,
.advanced-filter-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-field span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
}

.filter-field input {
  min-height: 44px;
  padding: 0 14px;
  border-radius: 14px;
  border: 1px solid rgba(20, 35, 55, 0.12);
  background: rgba(255, 255, 255, 0.96);
  color: var(--ink);
}

.filter-field-wide {
  grid-column: span 2;
}

.advanced-filter-panel {
  padding-top: 4px;
  border-top: 1px solid rgba(20, 35, 55, 0.08);
}

.advanced-filter-panel summary {
  cursor: pointer;
  color: var(--muted);
  font-weight: 600;
}

.advanced-filter-grid {
  margin-top: 12px;
}

.results-layout {
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.85fr);
}

.table-toolbar,
.row-drawer-head,
.file-preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.table-toolbar > div,
.row-drawer-head > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.table-toolbar span,
.row-drawer-head p {
  color: var(--muted);
  font-size: 12px;
  margin: 0;
}

.results-inspector pre,
.file-inspector pre {
  margin: 0;
  max-height: 640px;
  padding: 16px;
  border-radius: 18px;
  background: #101722;
  color: #dbe6f5;
  overflow: auto;
}

.file-browser-layout {
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  align-items: start;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(20, 35, 55, 0.08);
  background: rgba(248, 250, 252, 0.9);
  text-align: left;
  color: inherit;
}

.file-item.active {
  border-color: rgba(31, 79, 209, 0.22);
  background: linear-gradient(145deg, rgba(234, 242, 255, 0.92), rgba(255, 255, 255, 0.98));
  box-shadow: 0 16px 32px rgba(31, 79, 209, 0.08);
}

.file-item-copy span {
  color: var(--muted);
  font-size: 12px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.file-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.file-item-meta small {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(20, 35, 55, 0.06);
  color: var(--muted);
}

@media (max-width: 1280px) {
  .run-context-card,
  .results-layout,
  .file-browser-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1024px) {
  .results-head-actions,
  .filter-grid,
  .advanced-filter-grid,
  .run-context-metrics,
  .results-summary-grid,
  .preview-kv-grid {
    grid-template-columns: 1fr 1fr;
  }

  .filter-field-wide {
    grid-column: span 2;
  }
}

@media (max-width: 720px) {
  .results-head-actions,
  .data-mode-tabs,
  .filter-grid,
  .advanced-filter-grid,
  .run-context-metrics,
  .results-summary-grid,
  .preview-kv-grid {
    grid-template-columns: 1fr;
  }

  .filter-field-wide {
    grid-column: span 1;
  }

  .run-context-actions {
    align-items: flex-start;
  }
}
</style>
