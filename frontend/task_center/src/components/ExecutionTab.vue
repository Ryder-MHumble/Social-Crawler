<script setup lang="ts">
import { computed } from "vue";
import type { TaskJob, TaskLogEntry, TaskRun } from "../types";

const props = defineProps<{
  run: TaskRun | null;
  logs: TaskLogEntry[];
  selectedJobRef: string | null;
  now: number;
}>();

const emit = defineEmits<{
  (event: "select-job", jobRef: string): void;
}>();

const jobs = computed(() =>
  props.run?.stages.flatMap((stage) =>
    stage.jobs.map((job) => ({
      ...job,
      stageKey: stage.key,
      stageName: stage.name,
      ref: `${stage.key}::${job.key}`,
    })),
  ) ?? [],
);

const activeJob = computed(() => {
  const selected =
    jobs.value.find((job) => job.ref === props.selectedJobRef) ??
    jobs.value[0] ??
    null;
  return selected;
});

const filteredLogs = computed(() => {
  if (!activeJob.value) return props.logs;
  return props.logs.filter(
    (entry) => entry.stage_key === activeJob.value?.stageKey && entry.job_key === activeJob.value?.key,
  );
});

function formatTime(value?: string | null): string {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function countdownText(job: TaskJob | null): string {
  if (!job?.stall_deadline_at || job.status !== "running") return "无倒计时";
  const deadline = new Date(job.stall_deadline_at).getTime();
  if (Number.isNaN(deadline)) return "无倒计时";
  const diff = Math.max(0, Math.ceil((deadline - props.now) / 1000));
  return `${diff}s`;
}
</script>

<template>
  <section class="tab-panel">
    <div class="tab-panel-head">
      <div>
        <h2>执行</h2>
        <p>按阶段回放任务过程，关注 watchdog、最后输出时间和失败原因。</p>
      </div>
      <span v-if="run" class="state-chip" :class="run.status === 'running' ? 'running' : 'neutral'">
        {{ run.title }} · {{ run.status }}
      </span>
    </div>

    <div v-if="run" class="execution-layout">
      <aside class="execution-sidebar">
        <section class="execution-summary">
          <div class="summary-stat">
            <span>Accepted</span>
            <strong>{{ run.metrics.accepted }}</strong>
          </div>
          <div class="summary-stat">
            <span>Filtered</span>
            <strong>{{ run.metrics.filtered }}</strong>
          </div>
          <div class="summary-stat">
            <span>Deduped</span>
            <strong>{{ run.metrics.deduped }}</strong>
          </div>
          <div class="summary-stat">
            <span>Stalled</span>
            <strong>{{ run.metrics.stalled_jobs }}</strong>
          </div>
        </section>

        <section v-for="stage in run.stages" :key="stage.key" class="execution-stage">
          <div class="execution-stage-head">
            <strong>{{ stage.name }}</strong>
            <span>{{ stage.status || "waiting" }}</span>
          </div>
          <button
            v-for="job in stage.jobs"
            :key="job.key"
            class="execution-job"
            :class="{ active: `${stage.key}::${job.key}` === activeJob?.ref }"
            @click="emit('select-job', `${stage.key}::${job.key}`)"
          >
            <div>
              <strong>{{ job.name }}</strong>
              <span>{{ job.status || "waiting" }}</span>
            </div>
            <small>{{ job.watchdog_status || "idle" }}</small>
          </button>
        </section>
      </aside>

      <section class="execution-main">
        <div v-if="activeJob" class="execution-job-card">
          <div class="execution-job-top">
            <div>
              <h3>{{ activeJob.name }}</h3>
              <p>{{ activeJob.stageName }} · {{ activeJob.key }}</p>
            </div>
            <span class="state-chip" :class="activeJob.watchdog_status === 'healthy' ? 'success' : 'neutral'">
              {{ activeJob.watchdog_status || "idle" }}
            </span>
          </div>

          <div class="execution-job-grid">
            <div>
              <span>PID</span>
              <strong>{{ activeJob.pid ?? "未记录" }}</strong>
            </div>
            <div>
              <span>最后输出</span>
              <strong>{{ formatTime(activeJob.last_output_at) }}</strong>
            </div>
            <div>
              <span>状态变化</span>
              <strong>{{ formatTime(activeJob.last_state_change_at) }}</strong>
            </div>
            <div>
              <span>超时倒计时</span>
              <strong>{{ countdownText(activeJob) }}</strong>
            </div>
          </div>

          <div class="termination-box" :class="{ error: activeJob.termination_reason }">
            <span>失败 / 终止原因</span>
            <strong>{{ activeJob.termination_reason || "无" }}</strong>
          </div>

          <div class="log-stream">
            <div v-if="filteredLogs.length" class="log-list">
              <article v-for="entry in filteredLogs" :key="entry.id" class="log-entry" :class="`level-${entry.level}`">
                <span class="log-time">{{ entry.timestamp.slice(11, 19) }}</span>
                <span class="log-level">{{ entry.level }}</span>
                <code>{{ entry.message }}</code>
              </article>
            </div>
            <div v-else class="empty-state">当前 job 还没有可展示的日志。</div>
          </div>
        </div>
      </section>
    </div>

    <div v-else class="empty-state">选择一个运行记录后，这里会展示完整回放。</div>
  </section>
</template>
