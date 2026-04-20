<script setup lang="ts">
import type { SqliteRow, SqliteRowFilters, SqliteRowsResponse, SqliteStats, SqliteTableSummary } from "../types";

const props = defineProps<{
  tables: SqliteTableSummary[];
  supportedTables: string[];
  filters: SqliteRowFilters;
  stats: SqliteStats | null;
  rows: SqliteRowsResponse | null;
  selectedRow: SqliteRow | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  (event: "update-filter", key: keyof SqliteRowFilters, value: string | number): void;
  (event: "refresh"): void;
  (event: "open-row", row: SqliteRow): void;
  (event: "close-row"): void;
}>();

function prettyCell(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function pageLabel(): string {
  if (!props.rows) return "0 / 0";
  const start = props.filters.offset + 1;
  const end = Math.min(props.filters.offset + props.filters.limit, props.rows.total);
  return `${start}-${end} / ${props.rows.total}`;
}
</script>

<template>
  <section class="tab-panel">
    <div class="tab-panel-head">
      <div>
        <h2>数据</h2>
        <p>只读浏览 SQLite 清洗结果，支持任务、运行、平台、实体和文本筛选。</p>
      </div>
      <button class="btn secondary" @click="emit('refresh')">刷新数据</button>
    </div>

    <div class="data-filters">
      <select :value="filters.table" @change="emit('update-filter', 'table', ($event.target as HTMLSelectElement).value)">
        <option v-for="table in supportedTables" :key="table" :value="table">{{ table }}</option>
      </select>
      <input :value="filters.run_id" placeholder="run_id" @input="emit('update-filter', 'run_id', ($event.target as HTMLInputElement).value)" />
      <input :value="filters.task_slug" placeholder="task_slug" @input="emit('update-filter', 'task_slug', ($event.target as HTMLInputElement).value)" />
      <input :value="filters.platform" placeholder="platform" @input="emit('update-filter', 'platform', ($event.target as HTMLInputElement).value)" />
      <input :value="filters.entity_type" placeholder="entity_type" @input="emit('update-filter', 'entity_type', ($event.target as HTMLInputElement).value)" />
      <input :value="filters.clean_status" placeholder="clean_status" @input="emit('update-filter', 'clean_status', ($event.target as HTMLInputElement).value)" />
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
        <div v-else class="empty-state">当前筛选条件下没有数据。</div>
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
  </section>
</template>
