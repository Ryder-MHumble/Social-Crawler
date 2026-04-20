<script setup lang="ts">
import { computed } from "vue";
import type { SqliteStatus, TaskPreview, TaskStage } from "../types";

interface PreviewStageSummary extends TaskStage {
  index: number;
  jobCount: number;
  jobKeys: string;
}

const props = defineProps<{
  preview: TaskPreview | null;
  sqliteStatus: SqliteStatus | null;
  storageSummary: string;
}>();

const normalizedParamEntries = computed(() => {
  if (!props.preview) return [];
  return Object.entries(props.preview.normalized_params).map(([key, value]) => {
    const full = prettyValue(value);
    const compact = full.length > 180 ? `${full.slice(0, 180)}...` : full;
    return {
      key,
      full,
      compact,
      expandable: full.length > 180 || full.includes("\n"),
    };
  });
});

const stageSummaries = computed<PreviewStageSummary[]>(() =>
  props.preview?.spec.stages.map((stage, index) => ({
    ...stage,
    index: index + 1,
    jobCount: stage.jobs.length,
    jobKeys: stage.jobs.map((job) => job.key).join(" / "),
  })) ?? [],
);

const totalJobCount = computed(() =>
  stageSummaries.value.reduce((count, stage) => count + stage.jobCount, 0),
);

const storageCards = computed(() => [
  {
    label: "存储落点",
    value: props.storageSummary,
    note: props.preview ? `${props.preview.spec.slug} · ${props.preview.task.title}` : "等待任务预览",
  },
  {
    label: "SQLite",
    value: props.sqliteStatus?.path ?? "SQLite 路径未加载",
    note: props.sqliteStatus
      ? `${props.sqliteStatus.initialized ? "已初始化" : "未初始化"} · ${props.sqliteStatus.table_count} tables`
      : "等待 SQLite 状态",
  },
  {
    label: "执行规模",
    value: `${stageSummaries.value.length} stages / ${totalJobCount.value} jobs`,
    note: `${normalizedParamEntries.value.length} 项归一化参数`,
  },
]);

function prettyValue(value: unknown): string {
  if (typeof value === "string") return value.trim() || "(empty string)";
  if (value === undefined) return "undefined";
  return JSON.stringify(value, null, 2) ?? String(value);
}

async function copyCommand(stage: TaskStage, jobKey: string) {
  const job = stage.jobs.find((item) => item.key === jobKey);
  if (!job) return;
  await navigator.clipboard.writeText(job.display_command || job.command.join(" "));
}
</script>

<template>
  <section class="tab-panel commands-tab">
    <div class="tab-panel-head">
      <div>
        <h2>命令</h2>
        <p>把归一化参数、stage / job 概览和本次存储落点收拢进同一个内联预览面板。</p>
      </div>
      <div class="command-storage">
        <span class="state-chip neutral">{{ storageSummary }}</span>
        <span class="state-chip neutral">{{ sqliteStatus?.path ?? "SQLite 路径未加载" }}</span>
      </div>
    </div>

    <article v-if="preview" class="preview-inline-panel">
      <header class="preview-inline-head">
        <div class="preview-inline-copy">
          <span class="preview-inline-kicker">Quiet Ops Preview</span>
          <h3>{{ preview.spec.title }}</h3>
          <p>{{ preview.spec.slug }} · 命令预览已与当前参数同步。</p>
        </div>

        <div class="preview-inline-metrics">
          <article class="preview-inline-metric">
            <span>Params</span>
            <strong>{{ normalizedParamEntries.length }}</strong>
          </article>
          <article class="preview-inline-metric">
            <span>Stages</span>
            <strong>{{ stageSummaries.length }}</strong>
          </article>
          <article class="preview-inline-metric">
            <span>Jobs</span>
            <strong>{{ totalJobCount }}</strong>
          </article>
        </div>
      </header>

      <div class="storage-inline-grid">
        <article v-for="card in storageCards" :key="card.label" class="storage-inline-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.note }}</small>
        </article>
      </div>

      <div class="preview-inline-body">
        <section class="preview-inline-section preview-inline-params">
          <div class="preview-section-head">
            <div>
              <h4>归一化参数</h4>
              <p>这些值是命令展开前的最终输入，可直接用来核对默认值、覆盖项和格式化结果。</p>
            </div>
            <span class="state-chip neutral">{{ normalizedParamEntries.length }} 项</span>
          </div>

          <div v-if="normalizedParamEntries.length" class="param-pill-grid">
            <article
              v-for="entry in normalizedParamEntries"
              :key="entry.key"
              class="param-pill"
              :class="{ expandable: entry.expandable }"
            >
              <div class="param-pill-head">
                <strong>{{ entry.key }}</strong>
              </div>

              <code v-if="!entry.expandable">{{ entry.compact }}</code>

              <details v-else class="param-pill-details">
                <summary>{{ entry.compact }}</summary>
                <pre><code>{{ entry.full }}</code></pre>
              </details>
            </article>
          </div>

          <div v-else class="inline-empty">当前任务没有归一化参数。</div>
        </section>

        <section class="preview-inline-section preview-inline-flow">
          <div class="preview-section-head">
            <div>
              <h4>Stage / Job 概览</h4>
              <p>按阶段展开作业顺序、执行模式和实际命令，便于在执行前检查整条链路。</p>
            </div>
            <span class="state-chip neutral">{{ stageSummaries.length }} 个阶段</span>
          </div>

          <div v-if="stageSummaries.length" class="stage-flow">
            <article v-for="stage in stageSummaries" :key="stage.key" class="stage-flow-card">
              <div class="stage-flow-head">
                <div class="stage-flow-copy">
                  <span class="stage-flow-index">Stage {{ stage.index }}</span>
                  <h5>{{ stage.name }}</h5>
                  <p>
                    {{ stage.key }} · {{ stage.concurrent ? "并行" : "串行" }} ·
                    {{ stage.abort_on_failure ? "失败即停" : "失败后继续" }}
                  </p>
                </div>

                <div class="stage-flow-stats">
                  <span>{{ stage.jobCount }} jobs</span>
                  <small>{{ stage.jobKeys || "无 job key" }}</small>
                </div>
              </div>

              <div class="job-inline-list">
                <article v-for="job in stage.jobs" :key="job.key" class="job-inline-card">
                  <div class="job-inline-head">
                    <div class="job-inline-copy">
                      <strong>{{ job.name }}</strong>
                      <span>{{ job.key }}</span>
                    </div>

                    <div class="job-inline-meta">
                      <code>{{ job.cwd }}</code>
                      <button class="btn ghost small" @click="copyCommand(stage, job.key)">复制命令</button>
                    </div>
                  </div>

                  <pre><code>{{ job.display_command || job.command.join(" ") }}</code></pre>
                </article>
              </div>
            </article>
          </div>

          <div v-else class="inline-empty">当前任务还没有生成 stage / job。</div>
        </section>
      </div>
    </article>

    <div v-else class="empty-state">修改配置后，这里会显示归一化参数、stage / job 命令和存储落点。</div>
  </section>
</template>

<style scoped>
.commands-tab {
  gap: 20px;
}

.preview-inline-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px;
  border-radius: 24px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background:
    linear-gradient(160deg, rgba(250, 245, 239, 0.92), rgba(255, 255, 255, 0.98)),
    var(--panel-strong);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.7),
    0 18px 42px rgba(22, 32, 43, 0.06);
}

.preview-inline-head,
.preview-section-head,
.stage-flow-head,
.job-inline-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.preview-inline-kicker,
.stage-flow-index {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}

.preview-inline-copy,
.preview-section-head > div,
.stage-flow-copy,
.job-inline-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-inline-copy h3,
.preview-section-head h4,
.stage-flow-copy h5 {
  margin: 0;
}

.preview-inline-copy p,
.preview-section-head p,
.stage-flow-copy p,
.job-inline-copy span,
.stage-flow-stats,
.stage-flow-stats small {
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}

.preview-inline-metrics,
.storage-inline-grid {
  display: grid;
  gap: 12px;
}

.preview-inline-metrics {
  grid-template-columns: repeat(3, minmax(96px, 1fr));
}

.preview-inline-metric,
.storage-inline-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(255, 255, 255, 0.74);
}

.preview-inline-metric span,
.storage-inline-card span {
  font-size: 12px;
  color: var(--muted);
}

.preview-inline-metric strong,
.storage-inline-card strong {
  font-size: 22px;
  line-height: 1.1;
}

.storage-inline-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.storage-inline-card strong {
  font-size: 14px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.storage-inline-card small {
  color: var(--muted);
  line-height: 1.5;
}

.preview-inline-body {
  display: grid;
  grid-template-columns: minmax(320px, 0.95fr) minmax(0, 1.2fr);
  gap: 16px;
  align-items: start;
}

.preview-inline-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(255, 255, 255, 0.68);
}

.param-pill-grid,
.stage-flow,
.job-inline-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.param-pill-grid {
  max-height: min(70vh, 760px);
  overflow: auto;
  padding-right: 4px;
}

.param-pill {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border-radius: 18px;
  background: rgba(20, 35, 55, 0.04);
  border: 1px solid rgba(22, 32, 43, 0.08);
}

.param-pill.expandable {
  background: rgba(255, 250, 244, 0.86);
}

.param-pill-head strong {
  font-size: 14px;
}

.param-pill code {
  display: block;
  margin: 0;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(20, 35, 55, 0.06);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.param-pill-details {
  padding: 8px 10px;
  border-radius: 14px;
  border: 1px solid rgba(22, 32, 43, 0.1);
  background: rgba(255, 255, 255, 0.8);
}

.param-pill-details summary {
  cursor: pointer;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.param-pill-details pre,
.job-inline-card pre {
  margin: 0;
  overflow: auto;
}

.param-pill-details pre {
  margin-top: 8px;
  max-height: 220px;
}

.stage-flow-card,
.job-inline-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(255, 255, 255, 0.84);
}

.stage-flow-stats {
  align-items: flex-end;
  gap: 6px;
  display: flex;
  flex-direction: column;
  font-size: 12px;
}

.job-inline-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.job-inline-meta code {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(20, 35, 55, 0.06);
  color: var(--ink);
  overflow-wrap: anywhere;
  word-break: break-word;
}

.job-inline-card pre {
  padding: 14px;
  border-radius: 14px;
  background: #121722;
  color: #e6ecf6;
  white-space: pre-wrap;
  word-break: break-word;
}

.inline-empty {
  padding: 18px;
  border-radius: 16px;
  border: 1px dashed rgba(22, 32, 43, 0.14);
  color: var(--muted);
  text-align: center;
}

@media (max-width: 1180px) {
  .preview-inline-body {
    grid-template-columns: 1fr;
  }

  .stage-flow-stats {
    align-items: flex-start;
  }
}

@media (max-width: 860px) {
  .preview-inline-head {
    flex-direction: column;
  }

  .preview-inline-metrics,
  .storage-inline-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .preview-inline-panel,
  .preview-inline-section {
    padding: 16px;
  }

  .job-inline-meta {
    width: 100%;
    justify-content: space-between;
  }

  .job-inline-meta code {
    width: 100%;
  }
}
</style>
