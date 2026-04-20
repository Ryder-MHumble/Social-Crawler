<script setup lang="ts">
import type { EnvCheckResult, SqliteStatus, SqliteTableSummary } from "../types";

defineProps<{
  sqliteStatus: SqliteStatus | null;
  tables: SqliteTableSummary[];
  envCheck: EnvCheckResult | null;
  loading: boolean;
  initLoading: boolean;
}>();

const emit = defineEmits<{
  (event: "init-sqlite"): void;
  (event: "refresh-system"): void;
}>();
</script>

<template>
  <section class="tab-panel">
    <div class="tab-panel-head">
      <div>
        <h2>系统</h2>
        <p>检查 SQLite、watchdog 和当前环境，必要时在这里初始化本地存储。</p>
      </div>
      <div class="topbar-inline-actions">
        <button class="btn secondary" :disabled="loading" @click="emit('refresh-system')">刷新状态</button>
        <button class="btn primary" :disabled="initLoading" @click="emit('init-sqlite')">初始化 SQLite</button>
      </div>
    </div>

    <div class="system-grid">
      <article class="system-card">
        <h3>SQLite 状态</h3>
        <div class="kv-table">
          <div class="kv-row">
            <span>路径</span>
            <code>{{ sqliteStatus?.path ?? "未加载" }}</code>
          </div>
          <div class="kv-row">
            <span>初始化</span>
            <strong>{{ sqliteStatus?.initialized ? "已完成" : "未完成" }}</strong>
          </div>
          <div class="kv-row">
            <span>Schema 版本</span>
            <strong>{{ sqliteStatus?.schema_version ?? "—" }}</strong>
          </div>
          <div class="kv-row">
            <span>表数量</span>
            <strong>{{ sqliteStatus?.table_count ?? 0 }}</strong>
          </div>
          <div class="kv-row">
            <span>最近写入</span>
            <strong>{{ sqliteStatus?.last_modified_at ?? "—" }}</strong>
          </div>
        </div>
      </article>

      <article class="system-card">
        <h3>Watchdog 配置</h3>
        <div class="kv-table">
          <div class="kv-row">
            <span>启动超时</span>
            <strong>{{ sqliteStatus?.watchdog.job_start_timeout_sec ?? "—" }}s</strong>
          </div>
          <div class="kv-row">
            <span>卡死超时</span>
            <strong>{{ sqliteStatus?.watchdog.job_stall_timeout_sec ?? "—" }}s</strong>
          </div>
          <div class="kv-row">
            <span>强杀宽限</span>
            <strong>{{ sqliteStatus?.watchdog.terminate_grace_sec ?? "—" }}s</strong>
          </div>
        </div>
      </article>

      <article class="system-card">
        <h3>表概览</h3>
        <div class="table-summary-list">
          <div v-for="table in tables" :key="table.name" class="table-summary-item">
            <strong>{{ table.name }}</strong>
            <span>{{ table.row_count }} rows</span>
          </div>
        </div>
      </article>

      <article class="system-card system-card-wide">
        <h3>环境检查</h3>
        <div v-if="envCheck" class="env-check">
          <span class="state-chip" :class="envCheck.success ? 'success' : 'warning'">
            {{ envCheck.success ? "检查通过" : "检查失败" }}
          </span>
          <p>{{ envCheck.message }}</p>
          <pre><code>{{ envCheck.output || envCheck.error || "无输出" }}</code></pre>
        </div>
        <div v-else class="empty-state">点击刷新状态后会拉取环境检查结果。</div>
      </article>
    </div>
  </section>
</template>
