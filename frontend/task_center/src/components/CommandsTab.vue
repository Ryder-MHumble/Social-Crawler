<script setup lang="ts">
import { computed } from "vue";
import type { SqliteStatus, TaskPreview, TaskStage } from "../types";

const props = defineProps<{
  preview: TaskPreview | null;
  sqliteStatus: SqliteStatus | null;
  storageSummary: string;
}>();

const normalizedParamEntries = computed(() => {
  if (!props.preview) return [];
  return Object.entries(props.preview.normalized_params).map(([key, value]) => {
    const full = prettyValue(value);
    const compact =
      full.length > 180 ? `${full.slice(0, 180)}...` : full;
    return {
      key,
      full,
      compact,
      expandable: full.length > 180 || full.includes("\n"),
    };
  });
});

function prettyValue(value: unknown): string {
  if (typeof value === "string") return value.trim();
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
      <article class="command-card command-card-params">
        <div class="command-card-head">
          <h3>归一化参数</h3>
          <span class="state-chip neutral">{{ normalizedParamEntries.length }} 项</span>
        </div>
        <div class="kv-table command-param-table">
          <div
            v-for="entry in normalizedParamEntries"
            :key="entry.key"
            class="kv-row command-param-row"
          >
            <span class="command-param-key">{{ entry.key }}</span>
            <div class="command-param-value">
              <code v-if="!entry.expandable">{{ entry.compact }}</code>
              <details v-else class="command-param-details">
                <summary>{{ entry.compact }}</summary>
                <pre><code>{{ entry.full }}</code></pre>
              </details>
            </div>
          </div>
        </div>
      </article>

      <article class="command-card command-card-jobs">
        <div class="command-card-head">
          <h3>命令预览</h3>
          <span class="state-chip neutral">{{ preview.spec.stages.length }} 个阶段</span>
        </div>
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
