<script setup lang="ts">
import { computed, ref, watch } from "vue";
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

type LogScope = "job" | "stage" | "run";

type JobView = TaskJob & {
  stageKey: string;
  stageName: string;
  ref: string;
  logCount: number;
  errorCount: number;
  warningCount: number;
  latestLogAt: string | null;
  latestLogMessage: string;
  failureReason: string;
  commandText: string;
  durationText: string;
};

type StageView = {
  key: string;
  name: string;
  status: string;
  jobs: JobView[];
  firstJobRef: string | null;
  totalJobs: number;
  completedJobs: number;
  failedJobs: number;
  runningJobs: number;
  waitingJobs: number;
  stalledJobs: number;
  errorCount: number;
  latestLogAt: string | null;
  latestLogMessage: string;
  progressPercent: number;
  stageIndex: number;
};

const logScope = ref<LogScope>("job");
const selectedLogLevel = ref("all");

const completedStatuses = new Set(["completed", "complete", "success", "succeeded", "finished", "done"]);
const failedStatuses = new Set(["failed", "error", "aborted", "terminated", "killed", "timeout"]);
const runningStatuses = new Set(["running", "processing", "active"]);
const waitingStatuses = new Set(["waiting", "pending", "queued", "idle", "created"]);

function normalizeStatusKey(status?: string | null): string {
  return String(status ?? "waiting")
    .trim()
    .toLowerCase() || "waiting";
}

function isCompletedStatus(status?: string | null): boolean {
  return completedStatuses.has(normalizeStatusKey(status));
}

function isFailedStatus(status?: string | null): boolean {
  return failedStatuses.has(normalizeStatusKey(status));
}

function isRunningStatus(status?: string | null): boolean {
  return runningStatuses.has(normalizeStatusKey(status));
}

function isWaitingStatus(status?: string | null): boolean {
  return waitingStatuses.has(normalizeStatusKey(status));
}

function parseDate(value?: string | number | null): number | null {
  if (value === null || value === undefined || value === "") return null;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? null : time;
}

function formatTime(value?: string | number | null, withSeconds = true): string {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: withSeconds ? "2-digit" : undefined,
  });
}

function formatShortTime(value?: string | number | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(start?: string | null, end?: string | number | null): string {
  const startTime = parseDate(start);
  if (!startTime) return "未开始";
  const endTime = parseDate(end ?? props.now) ?? props.now;
  const diff = Math.max(0, endTime - startTime);
  const totalSeconds = Math.floor(diff / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function formatStatusLabel(status?: string | null): string {
  const normalized = normalizeStatusKey(status);
  if (normalized === "running") return "运行中";
  if (isCompletedStatus(normalized)) return "已完成";
  if (isFailedStatus(normalized)) return "失败";
  if (isWaitingStatus(normalized)) return "等待中";
  return normalized || "未知";
}

function statusTone(status?: string | null): "success" | "running" | "warning" | "danger" | "neutral" {
  const normalized = normalizeStatusKey(status);
  if (isCompletedStatus(normalized)) return "success";
  if (isRunningStatus(normalized)) return "running";
  if (isFailedStatus(normalized)) return "danger";
  if (normalized === "stalled") return "warning";
  return "neutral";
}

function watchdogTone(status?: string | null): "success" | "warning" | "danger" | "neutral" {
  const normalized = normalizeStatusKey(status);
  if (normalized === "healthy") return "success";
  if (normalized === "stalled") return "warning";
  if (["dead", "timeout", "failed"].includes(normalized)) return "danger";
  return "neutral";
}

function formatWatchdog(status?: string | null): string {
  const normalized = normalizeStatusKey(status);
  if (normalized === "healthy") return "watchdog 健康";
  if (normalized === "stalled") return "watchdog 告警";
  if (normalized === "idle") return "watchdog 空闲";
  return normalized ? `watchdog ${normalized}` : "watchdog 未记录";
}

function normalizeLogLevel(level?: string | null): string {
  return String(level ?? "info")
    .trim()
    .toLowerCase() || "info";
}

function formatLogLevel(level?: string | null): string {
  const normalized = normalizeLogLevel(level);
  if (normalized === "error") return "ERROR";
  if (normalized === "warning" || normalized === "warn") return "WARN";
  if (normalized === "debug") return "DEBUG";
  return normalized.toUpperCase();
}

function summarizeMessage(message?: string | null, limit = 120): string {
  const value = String(message ?? "").trim();
  if (!value) return "暂无摘要";
  if (value.length <= limit) return value;
  return `${value.slice(0, limit - 1)}…`;
}

function joinCommand(job: TaskJob): string {
  if (job.display_command?.trim()) return job.display_command.trim();
  if (job.command?.length) return job.command.join(" ");
  return "未记录";
}

function resolveFailureReason(job: TaskJob, entries: TaskLogEntry[]): string {
  if (job.termination_reason?.trim()) return job.termination_reason.trim();
  if (!isFailedStatus(job.status) && !entries.some((entry) => normalizeLogLevel(entry.level) === "error")) {
    return "无明确失败原因";
  }

  for (let index = entries.length - 1; index >= 0; index -= 1) {
    const entry = entries[index];
    const message = String(entry.message ?? "").trim();
    if (!message) continue;
    if (normalizeLogLevel(entry.level) === "error") return message;
    if (/(error|exception|traceback|datafetcherror|failed)/i.test(message)) return message;
  }

  if (job.last_line?.trim()) return job.last_line.trim();
  if (job.exit_code !== null && job.exit_code !== undefined) return `进程退出码：${job.exit_code}`;
  return "任务失败，但没有采集到更明确的错误文本。";
}

function deriveStageStatus(stage: TaskRun["stages"][number]): string {
  if (stage.status?.trim()) return stage.status.trim();
  if (stage.jobs.some((job) => isFailedStatus(job.status))) return "failed";
  if (stage.jobs.some((job) => isRunningStatus(job.status))) return "running";
  if (stage.jobs.length > 0 && stage.jobs.every((job) => isCompletedStatus(job.status))) return "completed";
  if (stage.jobs.some((job) => !isWaitingStatus(job.status))) return "pending";
  return "waiting";
}

function countdownText(job: TaskJob | null): string {
  if (!job?.stall_deadline_at || !isRunningStatus(job.status)) return "无倒计时";
  const deadline = new Date(job.stall_deadline_at).getTime();
  if (Number.isNaN(deadline)) return "无倒计时";
  const diff = Math.max(0, Math.ceil((deadline - props.now) / 1000));
  return `${diff}s`;
}

const stageViews = computed<StageView[]>(() =>
  props.run?.stages.map((stage, stageIndex) => {
    const stageLogs = props.logs.filter((entry) => entry.stage_key === stage.key);

    const jobs = stage.jobs.map((job) => {
      const jobLogs = stageLogs.filter((entry) => entry.job_key === job.key);
      const latestEntry = jobLogs[jobLogs.length - 1] ?? null;
      return {
        ...job,
        stageKey: stage.key,
        stageName: stage.name,
        ref: `${stage.key}::${job.key}`,
        logCount: jobLogs.length,
        errorCount: jobLogs.filter((entry) => normalizeLogLevel(entry.level) === "error").length,
        warningCount: jobLogs.filter((entry) => ["warning", "warn"].includes(normalizeLogLevel(entry.level))).length,
        latestLogAt: latestEntry?.timestamp ?? job.last_output_at ?? null,
        latestLogMessage: summarizeMessage(latestEntry?.message ?? job.last_line, 92),
        failureReason: resolveFailureReason(job, jobLogs),
        commandText: joinCommand(job),
        durationText: formatDuration(job.started_at, job.finished_at ?? (isRunningStatus(job.status) ? props.now : undefined)),
      };
    });

    const completedJobs = jobs.filter((job) => isCompletedStatus(job.status)).length;
    const failedJobs = jobs.filter((job) => isFailedStatus(job.status)).length;
    const runningJobs = jobs.filter((job) => isRunningStatus(job.status)).length;
    const waitingJobs = jobs.filter((job) => isWaitingStatus(job.status)).length;
    const stalledJobs = jobs.filter((job) => normalizeStatusKey(job.watchdog_status) === "stalled").length;
    const latestStageEntry = stageLogs[stageLogs.length - 1] ?? null;

    return {
      key: stage.key,
      name: stage.name,
      status: deriveStageStatus(stage),
      jobs,
      firstJobRef: jobs[0]?.ref ?? null,
      totalJobs: jobs.length,
      completedJobs,
      failedJobs,
      runningJobs,
      waitingJobs,
      stalledJobs,
      errorCount: jobs.reduce((sum, job) => sum + job.errorCount, 0),
      latestLogAt: latestStageEntry?.timestamp ?? jobs.find((job) => job.latestLogAt)?.latestLogAt ?? null,
      latestLogMessage: summarizeMessage(latestStageEntry?.message, 110),
      progressPercent: jobs.length ? Math.round((completedJobs / jobs.length) * 100) : 0,
      stageIndex,
    };
  }) ?? [],
);

const jobs = computed(() => stageViews.value.flatMap((stage) => stage.jobs));

const activeJob = computed(() => jobs.value.find((job) => job.ref === props.selectedJobRef) ?? jobs.value[0] ?? null);

const activeStage = computed(() => {
  if (!activeJob.value) return stageViews.value[0] ?? null;
  return stageViews.value.find((stage) => stage.key === activeJob.value?.stageKey) ?? stageViews.value[0] ?? null;
});

const activeJobLogs = computed(() => {
  if (!activeJob.value) return [];
  return props.logs.filter(
    (entry) => entry.stage_key === activeJob.value?.stageKey && entry.job_key === activeJob.value?.key,
  );
});

const activeStageLogs = computed(() => {
  if (!activeStage.value) return [];
  return props.logs.filter((entry) => entry.stage_key === activeStage.value?.key);
});

const scopedLogs = computed(() => {
  if (logScope.value === "run") return props.logs;
  if (logScope.value === "stage") return activeStageLogs.value;
  return activeJobLogs.value;
});

const logLevelOptions = computed(() => {
  const uniqueLevels = Array.from(new Set(scopedLogs.value.map((entry) => normalizeLogLevel(entry.level))));
  return ["all", ...uniqueLevels];
});

watch(
  logLevelOptions,
  (options) => {
    if (!options.includes(selectedLogLevel.value)) {
      selectedLogLevel.value = "all";
    }
  },
  { immediate: true },
);

const visibleLogs = computed(() => {
  if (selectedLogLevel.value === "all") return scopedLogs.value;
  return scopedLogs.value.filter((entry) => normalizeLogLevel(entry.level) === selectedLogLevel.value);
});

const runMetricCards = computed(() => {
  const totalJobs = jobs.value.length;
  const completedJobs = jobs.value.filter((job) => isCompletedStatus(job.status)).length;
  const completedStages = stageViews.value.filter(
    (stage) => stage.totalJobs > 0 && stage.completedJobs === stage.totalJobs,
  ).length;

  return [
    { label: "Accepted", value: props.run?.metrics.accepted ?? 0, helper: "进入结果中心" },
    { label: "Filtered", value: props.run?.metrics.filtered ?? 0, helper: "被规则过滤" },
    { label: "Deduped", value: props.run?.metrics.deduped ?? 0, helper: "去重后丢弃" },
    {
      label: "Errors",
      value: props.run?.metrics.errors ?? 0,
      helper: "运行统计错误数",
      tone: (props.run?.metrics.errors ?? 0) > 0 ? "danger" : "neutral",
    },
    {
      label: "Jobs",
      value: `${completedJobs}/${totalJobs || 0}`,
      helper: "已完成 / 总 job",
    },
    {
      label: "Stages",
      value: `${completedStages}/${stageViews.value.length || 0}`,
      helper: "已完成阶段",
    },
  ];
});

const logScopeOptions = computed(() => [
  { value: "job" as const, label: "当前 Job", count: activeJobLogs.value.length },
  { value: "stage" as const, label: "当前 Stage", count: activeStageLogs.value.length },
  { value: "run" as const, label: "整次 Run", count: props.logs.length },
]);

const runDurationText = computed(() => {
  if (!props.run?.started_at) return "未开始";
  return formatDuration(props.run.started_at, props.run.finished_at ?? (props.run.status === "running" ? props.now : undefined));
});

const runHeadline = computed(() => {
  if (!props.run) return "";
  return `${props.run.id} · ${props.run.task_slug}`;
});

const activeJobMeta = computed(() => {
  if (!activeJob.value) return [];
  return [
    { label: "PID", value: activeJob.value.pid ?? "未记录" },
    { label: "执行时长", value: activeJob.value.durationText },
    { label: "最后输出", value: formatTime(activeJob.value.last_output_at) },
    { label: "状态变化", value: formatTime(activeJob.value.last_state_change_at) },
    { label: "Watchdog", value: formatWatchdog(activeJob.value.watchdog_status) },
    { label: "超时倒计时", value: countdownText(activeJob.value) },
    { label: "退出码", value: activeJob.value.exit_code ?? "未记录" },
    { label: "日志条数", value: activeJob.value.logCount },
  ];
});
</script>

<template>
  <section class="tab-panel execution-tab">
    <div class="tab-panel-head">
      <div>
        <h2>运行监控</h2>
        <p>以 run 为中心查看阶段推进、job 健康度、失败原因和日志上下文。</p>
      </div>

      <div v-if="run" class="execution-head-chips">
        <span class="state-chip" :class="statusTone(run.status)">
          {{ run.title }} · {{ formatStatusLabel(run.status) }}
        </span>
        <span class="state-chip neutral">持续 {{ runDurationText }}</span>
      </div>
    </div>

    <div v-if="run" class="execution-shell">
      <section class="run-overview-card">
        <div class="run-overview-main">
          <span class="run-kicker">Run Center</span>
          <h3>{{ run.title }}</h3>
          <p>{{ runHeadline }}</p>
        </div>

        <div class="run-overview-facts">
          <div class="overview-fact">
            <span>开始时间</span>
            <strong>{{ formatTime(run.started_at) }}</strong>
          </div>
          <div class="overview-fact">
            <span>结束时间</span>
            <strong>{{ formatTime(run.finished_at) }}</strong>
          </div>
          <div class="overview-fact">
            <span>日志文件</span>
            <code>{{ run.log_path || "未记录" }}</code>
          </div>
        </div>

        <div class="run-metrics-grid">
          <article
            v-for="metric in runMetricCards"
            :key="metric.label"
            class="run-metric-card"
            :class="{ danger: metric.tone === 'danger' }"
          >
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
            <small>{{ metric.helper }}</small>
          </article>
        </div>
      </section>

      <div class="execution-layout">
        <aside class="execution-rail">
          <section class="rail-card">
            <div class="section-head">
              <div>
                <h3>Stage 导航</h3>
                <p>{{ stageViews.length }} 个阶段，按阶段切换第一个 job。</p>
              </div>
              <span class="state-chip neutral">{{ jobs.length }} jobs</span>
            </div>

            <div class="stage-card-list">
              <button
                v-for="stage in stageViews"
                :key="stage.key"
                class="stage-card"
                :class="{ active: stage.key === activeStage?.key }"
                :disabled="!stage.firstJobRef"
                @click="stage.firstJobRef && emit('select-job', stage.firstJobRef)"
              >
                <div class="stage-card-head">
                  <div>
                    <span class="stage-order">Stage {{ stage.stageIndex + 1 }}</span>
                    <strong>{{ stage.name }}</strong>
                  </div>
                  <span class="state-chip small" :class="statusTone(stage.status)">
                    {{ formatStatusLabel(stage.status) }}
                  </span>
                </div>

                <div class="stage-card-stats">
                  <span>{{ stage.completedJobs }}/{{ stage.totalJobs }} 完成</span>
                  <span>{{ stage.failedJobs }} 失败</span>
                  <span>{{ stage.runningJobs }} 运行中</span>
                </div>

                <div class="stage-progress">
                  <span :style="{ width: `${stage.progressPercent}%` }"></span>
                </div>

                <div class="stage-card-foot">
                  <small>{{ stage.errorCount }} error logs</small>
                  <small>{{ formatShortTime(stage.latestLogAt) }}</small>
                </div>

                <p class="stage-card-copy">
                  {{ stage.latestLogMessage || "当前阶段还没有日志输出。" }}
                </p>
              </button>
            </div>
          </section>
        </aside>

        <section class="execution-main">
          <div v-if="activeStage" class="stage-detail-card">
            <div class="section-head">
              <div>
                <h3>{{ activeStage.name }}</h3>
                <p>{{ activeStage.key }} · 当前 stage 的 job 状态与失败摘要</p>
              </div>
              <span class="state-chip" :class="statusTone(activeStage.status)">
                {{ formatStatusLabel(activeStage.status) }}
              </span>
            </div>

            <div class="stage-summary-grid">
              <div class="stage-summary-item">
                <span>完成</span>
                <strong>{{ activeStage.completedJobs }}/{{ activeStage.totalJobs }}</strong>
              </div>
              <div class="stage-summary-item">
                <span>失败</span>
                <strong>{{ activeStage.failedJobs }}</strong>
              </div>
              <div class="stage-summary-item">
                <span>等待</span>
                <strong>{{ activeStage.waitingJobs }}</strong>
              </div>
              <div class="stage-summary-item">
                <span>Watchdog 告警</span>
                <strong>{{ activeStage.stalledJobs }}</strong>
              </div>
            </div>

            <div class="job-list">
              <button
                v-for="job in activeStage.jobs"
                :key="job.ref"
                class="job-card"
                :class="{ active: job.ref === activeJob?.ref, failed: statusTone(job.status) === 'danger' }"
                @click="emit('select-job', job.ref)"
              >
                <div class="job-card-head">
                  <div>
                    <strong>{{ job.name }}</strong>
                    <p>{{ job.key }}</p>
                  </div>
                  <div class="job-chip-stack">
                    <span class="state-chip small" :class="statusTone(job.status)">
                      {{ formatStatusLabel(job.status) }}
                    </span>
                    <span class="state-chip small" :class="watchdogTone(job.watchdog_status)">
                      {{ job.watchdog_status || "idle" }}
                    </span>
                  </div>
                </div>

                <div class="job-card-meta">
                  <span>{{ job.durationText }}</span>
                  <span>{{ job.logCount }} logs</span>
                  <span>{{ job.errorCount }} errors</span>
                </div>

                <p class="job-card-copy">
                  {{
                    statusTone(job.status) === "danger" || job.termination_reason
                      ? summarizeMessage(job.failureReason, 96)
                      : job.latestLogMessage
                  }}
                </p>
              </button>
            </div>
          </div>

          <div v-else class="empty-state">当前 run 没有 stage 可展示。</div>
        </section>

        <aside class="execution-inspector">
          <div v-if="activeJob" class="inspector-card">
            <div class="section-head">
              <div>
                <h3>{{ activeJob.name }}</h3>
                <p>{{ activeJob.stageName }} · {{ activeJob.key }}</p>
              </div>
              <div class="job-chip-stack">
                <span class="state-chip" :class="statusTone(activeJob.status)">
                  {{ formatStatusLabel(activeJob.status) }}
                </span>
                <span class="state-chip" :class="watchdogTone(activeJob.watchdog_status)">
                  {{ formatWatchdog(activeJob.watchdog_status) }}
                </span>
              </div>
            </div>

            <div class="job-meta-grid">
              <div v-for="item in activeJobMeta" :key="item.label" class="job-meta-item">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>

            <div
              class="failure-card"
              :class="{ danger: statusTone(activeJob.status) === 'danger' || Boolean(activeJob.termination_reason) }"
            >
              <span>失败 / 终止原因</span>
              <strong>{{ activeJob.failureReason }}</strong>
            </div>

            <div class="command-card">
              <div class="command-block">
                <span>命令</span>
                <code>{{ activeJob.commandText }}</code>
              </div>
              <div class="command-block">
                <span>工作目录</span>
                <code>{{ activeJob.cwd || "未记录" }}</code>
              </div>
              <div class="command-block">
                <span>Log Path</span>
                <code>{{ activeJob.log_path || "未记录" }}</code>
              </div>
            </div>
          </div>

          <div class="log-card">
            <div class="section-head">
              <div>
                <h3>日志</h3>
                <p>{{ visibleLogs.length }} 条，按 job / stage / run 切换。</p>
              </div>

              <label class="log-level-filter">
                <span>级别</span>
                <select v-model="selectedLogLevel">
                  <option v-for="level in logLevelOptions" :key="level" :value="level">
                    {{ level === "all" ? "全部" : formatLogLevel(level) }}
                  </option>
                </select>
              </label>
            </div>

            <div class="scope-tabs">
              <button
                v-for="option in logScopeOptions"
                :key="option.value"
                class="scope-tab"
                :class="{ active: logScope === option.value }"
                @click="logScope = option.value"
              >
                <span>{{ option.label }}</span>
                <strong>{{ option.count }}</strong>
              </button>
            </div>

            <div class="log-stream">
              <div v-if="visibleLogs.length" class="log-list">
                <article
                  v-for="entry in visibleLogs"
                  :key="entry.id"
                  class="log-entry-card"
                  :class="`level-${normalizeLogLevel(entry.level)}`"
                >
                  <div class="log-entry-meta">
                    <span>{{ formatShortTime(entry.timestamp) }}</span>
                    <small>{{ formatLogLevel(entry.level) }}</small>
                    <small v-if="logScope === 'run'">{{ entry.stage_name || entry.stage_key || "run" }}</small>
                    <small v-if="logScope !== 'job'">{{ entry.job_name || entry.job_key || "job" }}</small>
                  </div>
                  <code>{{ entry.message }}</code>
                </article>
              </div>
              <div v-else class="empty-state">
                {{ logScope === "job" ? "当前 job 还没有可展示的日志。" : logScope === "stage" ? "当前 stage 还没有日志。" : "当前 run 还没有日志。" }}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>

    <div v-else class="empty-state">选择一个运行记录后，这里会展示 run 级监控视图。</div>
  </section>
</template>

<style scoped>
.execution-tab {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.execution-head-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.execution-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.run-overview-card,
.rail-card,
.stage-detail-card,
.inspector-card,
.log-card {
  border: 1px solid rgba(22, 32, 43, 0.1);
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(249, 244, 238, 0.78)),
    var(--panel-strong);
  padding: 18px;
}

.run-overview-card {
  display: grid;
  grid-template-columns: minmax(220px, 1.15fr) minmax(260px, 1fr);
  gap: 16px;
  align-items: start;
}

.run-overview-main h3,
.section-head h3 {
  margin: 0;
}

.run-overview-main p,
.section-head p,
.stage-card-copy,
.job-card-copy {
  margin: 0;
  color: var(--muted);
}

.run-kicker {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(178, 79, 44, 0.12);
  color: var(--brand-deep);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.run-overview-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.run-overview-facts,
.run-metrics-grid,
.job-meta-grid,
.stage-summary-grid {
  display: grid;
  gap: 10px;
}

.run-overview-facts {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-column: 1 / -1;
}

.overview-fact,
.run-metric-card,
.stage-summary-item,
.job-meta-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(20, 35, 55, 0.05);
}

.overview-fact span,
.run-metric-card span,
.stage-summary-item span,
.job-meta-item span,
.command-block span,
.log-level-filter span,
.stage-order,
.stage-card-stats span,
.job-card-meta span {
  color: var(--muted);
  font-size: 12px;
}

.overview-fact strong,
.run-metric-card strong,
.stage-summary-item strong,
.job-meta-item strong {
  font-family: "Manrope", sans-serif;
  font-size: 18px;
}

.overview-fact code,
.command-block code {
  display: block;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(20, 35, 55, 0.06);
  color: var(--ink);
  white-space: pre-wrap;
  word-break: break-word;
}

.run-metrics-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
  grid-column: 1 / -1;
}

.run-metric-card small {
  color: var(--muted);
  font-size: 11px;
}

.run-metric-card.danger {
  background: rgba(178, 60, 56, 0.08);
  color: var(--danger);
}

.execution-tab .execution-layout {
  display: grid;
  grid-template-columns: minmax(260px, 300px) minmax(320px, 1.05fr) minmax(360px, 1.1fr);
  gap: 16px;
  align-items: start;
}

.execution-rail,
.execution-main,
.execution-inspector {
  min-width: 0;
}

.execution-inspector {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.stage-card-list,
.job-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.stage-card,
.job-card,
.scope-tab {
  width: 100%;
  border: 1px solid rgba(22, 32, 43, 0.08);
  border-radius: 16px;
  background: rgba(20, 35, 55, 0.04);
  color: inherit;
  text-align: left;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    transform 0.14s ease,
    box-shadow 0.16s ease;
}

.stage-card,
.job-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
}

.stage-card:hover:not(:disabled),
.job-card:hover,
.scope-tab:hover {
  transform: translateY(-1px);
  border-color: rgba(178, 79, 44, 0.22);
  background: rgba(255, 248, 242, 0.86);
}

.stage-card.active,
.job-card.active,
.scope-tab.active {
  border-color: rgba(178, 79, 44, 0.28);
  background:
    linear-gradient(155deg, rgba(255, 248, 242, 0.96), rgba(255, 255, 255, 0.92)),
    rgba(255, 248, 242, 0.78);
  box-shadow: 0 14px 28px rgba(178, 79, 44, 0.12);
}

.job-card.failed {
  border-color: rgba(178, 60, 56, 0.18);
}

.stage-card-head,
.job-card-head,
.stage-card-foot,
.job-card-meta,
.job-chip-stack,
.scope-tabs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.stage-card-head,
.job-card-head {
  justify-content: space-between;
}

.stage-card-head strong,
.job-card-head strong {
  display: block;
}

.job-card-head p,
.stage-card-copy,
.job-card-copy {
  overflow-wrap: anywhere;
  word-break: break-word;
}

.job-card-head p {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 12px;
}

.stage-card-stats,
.stage-card-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stage-progress {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(20, 35, 55, 0.08);
  overflow: hidden;
}

.stage-progress > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #cf6b42, #e2a161);
}

.job-meta-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.failure-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(20, 35, 55, 0.05);
}

.failure-card.danger {
  background: rgba(178, 60, 56, 0.08);
  color: var(--danger);
}

.command-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.command-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.log-level-filter {
  display: inline-flex;
  flex-direction: column;
  gap: 6px;
  min-width: 120px;
}

.log-level-filter select {
  border: 1px solid rgba(22, 32, 43, 0.14);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--ink);
  padding: 9px 12px;
}

.scope-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.scope-tab {
  padding: 12px 14px;
}

.scope-tab span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}

.scope-tab strong {
  display: block;
  margin-top: 4px;
  font-size: 18px;
  font-family: "Manrope", sans-serif;
}

.log-stream {
  min-height: 360px;
  max-height: 720px;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(17, 23, 34, 0.32);
  background:
    radial-gradient(circle at top, rgba(55, 84, 120, 0.2), transparent 38%),
    #111722;
  overflow: auto;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.log-entry-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(124, 142, 168, 0.12);
  color: #dfe8f6;
}

.log-entry-card.level-error {
  border-color: rgba(255, 125, 97, 0.28);
  background: rgba(178, 60, 56, 0.16);
}

.log-entry-card.level-warning,
.log-entry-card.level-warn {
  border-color: rgba(230, 185, 82, 0.22);
  background: rgba(230, 185, 82, 0.1);
}

.log-entry-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.log-entry-meta small,
.log-entry-meta span {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #93a8c3;
  font-size: 11px;
}

.log-entry-card code {
  white-space: pre-wrap;
  word-break: break-word;
}

.state-chip.small {
  padding: 4px 8px;
  font-size: 11px;
}

.state-chip.danger {
  background: rgba(178, 60, 56, 0.1);
  color: var(--danger);
}

@media (max-width: 1500px) {
  .execution-tab .execution-layout {
    grid-template-columns: minmax(240px, 290px) minmax(0, 1fr);
  }

  .execution-inspector {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1200px) {
  .run-overview-card,
  .run-overview-facts,
  .run-metrics-grid,
  .job-meta-grid,
  .stage-summary-grid,
  .scope-tabs,
  .execution-tab .execution-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .run-overview-card,
  .rail-card,
  .stage-detail-card,
  .inspector-card,
  .log-card {
    padding: 16px;
    border-radius: 18px;
  }

  .execution-head-chips {
    justify-content: flex-start;
  }

  .section-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
