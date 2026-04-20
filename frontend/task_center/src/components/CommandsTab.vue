<script setup lang="ts">
import type { SqliteStatus, TaskPreview, TaskStage } from "../types";

defineProps<{
  preview: TaskPreview | null;
  sqliteStatus: SqliteStatus | null;
  storageSummary: string;
}>();

function prettyValue(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

async function copyCommand(stage: TaskStage, jobKey: string) {
  const job = stage.jobs.find((item) => item.key === jobKey);
  if (!job) return;
  await navigator.clipboard.writeText(job.display_command || job.command.join(" "));
}
</script>

<template>
  <section class="tab-panel">
    <div class="tab-panel-head">
      <div>
        <h2>命令</h2>
        <p>先看归一化参数，再看 stage / job 实际命令，以及本次写入的存储落点。</p>
      </div>
      <div class="command-storage">
        <span class="state-chip neutral">{{ storageSummary }}</span>
        <span class="state-chip neutral">{{ sqliteStatus?.path ?? "SQLite 路径未加载" }}</span>
      </div>
    </div>

    <div v-if="preview" class="command-layout">
      <article class="command-card">
        <h3>归一化参数</h3>
        <div class="kv-table">
          <div v-for="(value, key) in preview.normalized_params" :key="key" class="kv-row">
            <span>{{ key }}</span>
            <code>{{ prettyValue(value) }}</code>
          </div>
        </div>
      </article>

      <article class="command-card">
        <h3>命令预览</h3>
        <div class="stage-command-list">
          <section v-for="stage in preview.spec.stages" :key="stage.key" class="stage-command">
            <div class="stage-command-head">
              <div>
                <strong>{{ stage.name }}</strong>
                <span>{{ stage.key }} · {{ stage.concurrent ? "并行" : "串行" }}</span>
              </div>
            </div>
            <div v-for="job in stage.jobs" :key="job.key" class="job-command">
              <div class="job-command-head">
                <div>
                  <strong>{{ job.name }}</strong>
                  <span>{{ job.key }}</span>
                </div>
                <button class="btn ghost small" @click="copyCommand(stage, job.key)">复制命令</button>
              </div>
              <pre><code>{{ job.display_command || job.command.join(" ") }}</code></pre>
            </div>
          </section>
        </div>
      </article>
    </div>

    <div v-else class="empty-state">修改配置后，这里会显示实际将执行的命令。</div>
  </section>
</template>
