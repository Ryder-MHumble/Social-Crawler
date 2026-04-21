<script setup lang="ts">
import { computed, ref, watch } from "vue";
import SelectField from "./SelectField.vue";
import type { TaskJob, TaskLogEntry, TaskRun, TaskRunPlanItem, TaskRunWarning, TaskStage } from "../types";

const props = defineProps<{
  run: TaskRun | null;
  logs: TaskLogEntry[];
  selectedJobRef?: string | null;
  now: number;
}>();

const emit = defineEmits<{
  (event: "select-job", jobRef: string): void;
}>();

type LogScope = "run" | "stage" | "job";

type JobView = TaskJob & {
  stageKey: string;
  stageName: string;
  ref: string;
};

type StageView = {
  key: string;
  name: string;
  status: string;
  jobs: JobView[];
  firstJobRef: string | null;
};

type IssueSummary = {
  key: string;
  label: string;
  count: number;
  hint: string;
  sample?: string;
};

type SliceProgress = {
  key: string;
  label: string;
  total: number;
  completed: number;
  running: number;
  failed: number;
  waiting: number;
  percent: number;
  detail?: string;
  status?: string | null;
};

type PlatformProgress = SliceProgress & {
  platform: string;
};

type ProgressGroup = {
  key: string;
  label: string;
  slices: SliceProgress[];
};

type ExecutionAlert = {
  key: string;
  code: string;
  label: string;
  detail: string;
  level: string;
  status?: string | null;
  tone: "warning" | "danger" | "running" | "neutral";
  source: string;
};

const platformLabels: Record<string, string> = {
  xhs: "Xiaohongshu",
  dy: "Douyin",
  bili: "Bilibili",
  zhihu: "Zhihu",
  wb: "Weibo",
  tieba: "Baidu Tieba",
  ks: "Kuaishou",
};

const progressGroupLabels: Record<string, string> = {
  slices: "执行切片",
  slice_progress: "执行切片",
  by_slice: "执行切片",
  platforms: "平台进度",
  platform_progress: "平台进度",
  by_platform: "平台进度",
  keywords: "关键词切片",
  keyword_slices: "关键词切片",
  keyword_progress: "关键词切片",
  by_keyword: "关键词切片",
  accounts: "账号切片",
  account_slices: "账号切片",
  account_progress: "账号切片",
  by_account: "账号切片",
  stages: "阶段进度",
  stage_progress: "阶段进度",
  jobs: "作业进度",
  job_progress: "作业进度",
};

const metricLabels: Record<string, string> = {
  accepted: "Accepted",
  filtered: "Filtered",
  deduped: "Deduped",
  errors: "Errors",
  stalled_jobs: "Stalled Jobs",
  candidate_count: "候选内容",
  detail_requests: "详情请求",
  detail_successes: "详情成功",
  detail_failures: "详情失败",
  skipped: "Skipped",
};

const completedStatuses = new Set(["completed", "complete", "success", "succeeded", "finished", "done"]);
const failedStatuses = new Set(["failed", "error", "aborted", "terminated", "killed", "timeout", "stopped"]);
const runningStatuses = new Set(["running", "processing", "active", "queued", "pending", "starting", "preflight"]);

const logScope = ref<LogScope>("run");
const selectedLogLevel = ref("all");
const localSelectedJobRef = ref<string | null>(null);

function normalizeStatusKey(status?: string | null): string {
  return String(status ?? "unknown").trim().toLowerCase() || "unknown";
}

function normalizeLogLevel(level?: string | null): string {
  return String(level ?? "info").trim().toLowerCase() || "info";
}

function asRecord(input: unknown): Record<string, unknown> | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  return input as Record<string, unknown>;
}

function prettifyKey(key: string): string {
  const compact = key.trim();
  if (!compact) return "Unknown";
  return compact
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function metricLabel(key: string): string {
  return metricLabels[key] ?? prettifyKey(key);
}

function toFiniteNumber(value: unknown, fallback = 0): number {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : fallback;
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function normalizePercent(value: unknown, completed: number, total: number): number {
  const numericValue = Number(value);
  if (Number.isFinite(numericValue)) {
    if (numericValue >= 0 && numericValue <= 1) {
      return clampPercent(numericValue * 100);
    }
    return clampPercent(numericValue);
  }
  if (total > 0) {
    return clampPercent((completed / total) * 100);
  }
  return 0;
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

function statusTone(status?: string | null): "success" | "running" | "warning" | "danger" | "neutral" {
  const normalized = normalizeStatusKey(status);
  if (normalized === "waiting_user" || normalized === "degraded" || normalized === "session_locked") {
    return "warning";
  }
  if (isCompletedStatus(normalized)) return "success";
  if (isRunningStatus(normalized)) return "running";
  if (isFailedStatus(normalized)) return "danger";
  if (normalized === "stalled") return "warning";
  return "neutral";
}

function formatStatusLabel(status?: string | null): string {
  const normalized = normalizeStatusKey(status);
  if (normalized === "queued" || normalized === "preflight") return "预检中";
  if (isRunningStatus(normalized)) return "运行中";
  if (isCompletedStatus(normalized)) return "已完成";
  if (isFailedStatus(normalized)) return "失败";
  if (normalized === "waiting_user") return "等待用户处理";
  if (normalized === "degraded") return "降级执行";
  if (normalized === "session_locked") return "会话锁定";
  if (normalized === "enabled") return "启用";
  if (normalized === "disabled") return "停用";
  if (normalized === "waiting") return "等待中";
  return normalized || "未知";
}

function formatLogLevel(level?: string | null): string {
  const normalized = normalizeLogLevel(level);
  if (normalized === "error") return "ERROR";
  if (normalized === "warning" || normalized === "warn") return "WARN";
  if (normalized === "debug") return "DEBUG";
  return normalized.toUpperCase();
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
  if (!value) return "--:--:--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function parseDate(value?: string | number | null): number | null {
  if (value === null || value === undefined || value === "") return null;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? null : time;
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

function splitCsv(raw: unknown): string[] {
  const text = String(raw ?? "").trim();
  if (!text) return [];
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function safeStages(run: TaskRun | null): TaskStage[] {
  if (!run || !Array.isArray(run.stages)) return [];
  return run.stages;
}

function jobMetadata(job: TaskJob): Record<string, unknown> {
  return job.metadata && typeof job.metadata === "object" ? job.metadata : {};
}

function parsePlatformFromJob(job: JobView): string {
  const metadataPlatform = String(jobMetadata(job).platform ?? "").trim().toLowerCase();
  if (metadataPlatform) return metadataPlatform;
  const key = String(job.key ?? "").trim().toLowerCase();
  const matched = key.match(/^(?:search|creator)_([a-z0-9]+)(?:_\d+)?$/);
  if (matched?.[1]) return matched[1];
  return "unknown";
}

function parseSliceValues(job: JobView): string[] {
  const rawValues = jobMetadata(job).values;
  if (Array.isArray(rawValues)) {
    return rawValues.map((item) => String(item).trim()).filter(Boolean);
  }
  return [];
}

function looksLikeSliceRecord(record: Record<string, unknown>): boolean {
  return [
    "total",
    "completed",
    "done",
    "success",
    "running",
    "active",
    "failed",
    "errors",
    "waiting",
    "pending",
    "queued",
    "percent",
    "progress",
  ].some((key) => key in record);
}

function toSliceProgress(input: unknown, fallbackKey: string, fallbackLabel?: string): SliceProgress | null {
  const record = asRecord(input);
  if (!record || !looksLikeSliceRecord(record)) return null;

  const total = toFiniteNumber(record.total ?? record.count ?? record.target ?? record.expected ?? record.size);
  const completed = toFiniteNumber(record.completed ?? record.done ?? record.success ?? record.succeeded);
  const running = toFiniteNumber(record.running ?? record.active ?? record.in_progress);
  const failed = toFiniteNumber(record.failed ?? record.errors ?? record.error ?? record.failures);
  const waiting = toFiniteNumber(
    record.waiting ?? record.pending ?? record.queued,
    Math.max(0, total - completed - running - failed),
  );
  const percent = normalizePercent(record.percent ?? record.progress ?? record.progress_pct, completed, total);

  if (!total && !completed && !running && !failed && !waiting && !percent) return null;

  const key = String(record.key ?? record.id ?? record.name ?? fallbackKey).trim() || fallbackKey;
  const label =
    String(record.label ?? record.title ?? record.name ?? fallbackLabel ?? prettifyKey(key)).trim()
    || prettifyKey(key);

  return {
    key,
    label,
    total,
    completed,
    running,
    failed,
    waiting,
    percent,
    detail: String(record.detail ?? record.summary ?? record.message ?? "").trim(),
    status: record.status == null ? null : String(record.status).trim() || null,
  };
}

function toSliceCollection(input: unknown, groupKey: string): SliceProgress[] {
  if (!input) return [];
  if (Array.isArray(input)) {
    return input
      .map((item, index) => toSliceProgress(item, `${groupKey}_${index}`))
      .filter((item): item is SliceProgress => Boolean(item));
  }

  const record = asRecord(input);
  if (!record) return [];

  return Object.entries(record)
    .map(([key, value]) => {
      const nestedRecord = asRecord(value);
      if (!nestedRecord) return null;
      return toSliceProgress(
        {
          key,
          label: nestedRecord.label ?? nestedRecord.title ?? prettifyKey(key),
          ...nestedRecord,
        },
        `${groupKey}_${key}`,
      );
    })
    .filter((item): item is SliceProgress => Boolean(item));
}

function platformLabel(platform: string): string {
  return platformLabels[platform] ?? platform;
}

const stageViews = computed<StageView[]>(() =>
  safeStages(props.run).map((stage, stageIndex) => {
    const stageKey = String(stage.key ?? `stage_${stageIndex}`);
    const stageName = String(stage.name ?? stageKey);
    const stageJobs = Array.isArray(stage.jobs) ? stage.jobs : [];
    const jobs: JobView[] = stageJobs.map((job, jobIndex) => {
      const jobKey = String(job.key ?? `job_${jobIndex}`);
      return {
        ...job,
        stageKey,
        stageName,
        ref: `${stageKey}::${jobKey}`,
        key: jobKey,
        name: String(job.name ?? jobKey),
        command: Array.isArray(job.command) ? job.command : [],
      };
    });

    return {
      key: stageKey,
      name: stageName,
      status: String(stage.status ?? "waiting"),
      jobs,
      firstJobRef: jobs[0]?.ref ?? null,
    };
  }),
);

const jobs = computed(() => stageViews.value.flatMap((stage) => stage.jobs));

watch(
  () => props.selectedJobRef,
  (value) => {
    if (value !== undefined) {
      localSelectedJobRef.value = value ?? null;
    }
  },
  { immediate: true },
);

watch(
  [stageViews, () => props.selectedJobRef, localSelectedJobRef],
  ([stages, selectedRef]) => {
    if (!stages.length) return;
    const allRefs = stages.flatMap((stage) => stage.jobs.map((job) => job.ref));
    if (selectedRef && allRefs.includes(selectedRef)) return;
    const nextRef = stages[0].firstJobRef;
    if (nextRef) {
      localSelectedJobRef.value = nextRef;
      emit("select-job", nextRef);
    }
  },
  { immediate: true },
);

const resolvedSelectedJobRef = computed(() =>
  props.selectedJobRef !== undefined ? props.selectedJobRef : localSelectedJobRef.value,
);

const activeJob = computed(
  () => jobs.value.find((job) => job.ref === resolvedSelectedJobRef.value) ?? jobs.value[0] ?? null,
);

const activeStage = computed(() => {
  if (!activeJob.value) return stageViews.value[0] ?? null;
  return stageViews.value.find((stage) => stage.key === activeJob.value?.stageKey) ?? stageViews.value[0] ?? null;
});

const activeStageJobs = computed(() => activeStage.value?.jobs ?? []);

function handleStageChange(stageKey: string) {
  const stage = stageViews.value.find((item) => item.key === stageKey);
  if (stage?.firstJobRef) {
    localSelectedJobRef.value = stage.firstJobRef;
    emit("select-job", stage.firstJobRef);
  }
}

function handleJobChange(jobRef: string) {
  if (!jobRef) return;
  localSelectedJobRef.value = jobRef;
  emit("select-job", jobRef);
}

const activeStageLogs = computed(() => {
  if (!activeStage.value) return [];
  return props.logs.filter((entry) => entry.stage_key === activeStage.value?.key);
});

const activeJobLogs = computed(() => {
  if (!activeJob.value) return [];
  return props.logs.filter(
    (entry) => entry.stage_key === activeJob.value?.stageKey && entry.job_key === activeJob.value?.key,
  );
});

const scopedLogs = computed(() => {
  if (logScope.value === "stage") return activeStageLogs.value;
  if (logScope.value === "job") return activeJobLogs.value;
  return props.logs;
});

const logLevelOptions = computed(() => {
  const levels = Array.from(new Set(scopedLogs.value.map((entry) => normalizeLogLevel(entry.level))));
  return ["all", ...levels];
});

const stageSelectOptions = computed(() =>
  stageViews.value.map((stage) => ({
    value: stage.key,
    label: stage.name,
    description: formatStatusLabel(stage.status),
  })),
);

const jobSelectOptions = computed(() =>
  activeStageJobs.value.map((job) => ({
    value: job.ref,
    label: job.name,
    description: formatStatusLabel(job.status),
  })),
);

const logLevelSelectOptions = computed(() =>
  logLevelOptions.value.map((level) => ({
    value: level,
    label: level === "all" ? "全部级别" : formatLogLevel(level),
    description: level === "all" ? "展示所有日志" : `仅展示 ${formatLogLevel(level)}`,
  })),
);

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

const totalJobs = computed(() => jobs.value.length);
const completedJobs = computed(() => jobs.value.filter((job) => isCompletedStatus(job.status)).length);
const failedJobs = computed(() => jobs.value.filter((job) => isFailedStatus(job.status)).length);
const runningJobs = computed(() => jobs.value.filter((job) => isRunningStatus(job.status)).length);

const runDurationText = computed(() => {
  if (!props.run?.started_at) return "未开始";
  const end = props.run.finished_at ?? (isRunningStatus(props.run.status) ? props.now : undefined);
  return formatDuration(props.run.started_at, end);
});

const errorCount = computed(() => {
  const metricError = Number(props.run?.metrics?.errors ?? 0);
  if (metricError > 0) return metricError;
  return props.logs.filter((entry) => normalizeLogLevel(entry.level) === "error").length;
});

const acceptedCount = computed(() => Number(props.run?.metrics?.accepted ?? 0));
const candidateCount = computed(() => Number(props.run?.metrics?.candidate_count ?? 0));
const detailRequestCount = computed(() => Number(props.run?.metrics?.detail_requests ?? 0));
const detailSuccessCount = computed(() => Number(props.run?.metrics?.detail_successes ?? 0));
const detailFailureCount = computed(() => Number(props.run?.metrics?.detail_failures ?? 0));

const runParams = computed<Record<string, unknown>>(() => {
  const params = props.run?.normalized_params;
  return params && typeof params === "object" ? params : {};
});

const configuredPlatforms = computed(() => {
  const raw = runParams.value.platforms;
  if (Array.isArray(raw)) {
    return raw.map((item) => String(item).trim()).filter(Boolean);
  }
  const single = String(runParams.value.platform ?? "").trim();
  return single ? [single] : [];
});

const configuredKeywords = computed(() => {
  const raw = runParams.value.keywords ?? runParams.value.search_keywords ?? "";
  if (Array.isArray(raw)) {
    return raw.map((item) => String(item).trim()).filter(Boolean);
  }
  return splitCsv(raw);
});

function formatSaveOption(value?: string | null): string {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) return "未返回";
  if (normalized === "json") return "JSON";
  if (normalized === "csv") return "CSV";
  if (["excel", "xlsx", "xls"].includes(normalized)) return "Excel";
  if (normalized === "sqlite") return "SQLite";
  return normalized.toUpperCase();
}

function formatStorageBackend(value?: string | null): string {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (!normalized) return "未返回";
  if (["filesystem", "files", "local_files", "file"].includes(normalized)) return "runtime/data";
  if (normalized === "sqlite") return "SQLite";
  if (normalized === "supabase") return "Supabase";
  return normalized;
}

const activeStageBatchNoun = computed(() => {
  const key = String(activeStage.value?.key ?? "").toLowerCase();
  if (key.includes("keyword")) return "关键词批次";
  if (key.includes("creator") || key.includes("account")) return "账号批次";
  return "执行批次";
});

const activeStageBatchProgress = computed(() => {
  const currentJobs = activeStageJobs.value;
  const total = currentJobs.length;
  const completed = currentJobs.filter((job) => isCompletedStatus(job.status)).length;
  const failed = currentJobs.filter((job) => isFailedStatus(job.status)).length;
  const running = currentJobs.filter((job) => isRunningStatus(job.status)).length;
  const waiting = Math.max(0, total - completed - failed - running);
  const percent = total ? Math.round((completed / total) * 100) : 0;
  return { total, completed, failed, running, waiting, percent };
});

const activeStagePlatformProgress = computed<PlatformProgress[]>(() => {
  const byPlatform = new Map<string, PlatformProgress>();
  for (const job of activeStageJobs.value) {
    const platform = parsePlatformFromJob(job);
    const existing = byPlatform.get(platform) ?? {
      key: platform,
      platform,
      label: platformLabel(platform),
      total: 0,
      completed: 0,
      running: 0,
      failed: 0,
      waiting: 0,
      percent: 0,
    };
    existing.total += 1;
    if (isCompletedStatus(job.status)) existing.completed += 1;
    else if (isFailedStatus(job.status)) existing.failed += 1;
    else if (isRunningStatus(job.status)) existing.running += 1;
    else existing.waiting += 1;
    byPlatform.set(platform, existing);
  }
  return Array.from(byPlatform.values())
    .map((item) => ({
      ...item,
      percent: item.total ? Math.round((item.completed / item.total) * 100) : 0,
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
});

const sliceProgress = computed<SliceProgress[]>(() => {
  const bySlice = new Map<string, SliceProgress>();
  for (const job of jobs.value) {
    const values = parseSliceValues(job);
    if (!values.length) continue;
    for (const value of values) {
      const key = value;
      const existing = bySlice.get(key) ?? {
        key,
        label: value,
        total: 0,
        completed: 0,
        running: 0,
        failed: 0,
        waiting: 0,
        percent: 0,
      };
      existing.total += 1;
      if (isCompletedStatus(job.status)) existing.completed += 1;
      else if (isFailedStatus(job.status)) existing.failed += 1;
      else if (isRunningStatus(job.status)) existing.running += 1;
      else existing.waiting += 1;
      bySlice.set(key, existing);
    }
  }
  return Array.from(bySlice.values())
    .map((item) => ({
      ...item,
      percent: item.total ? Math.round((item.completed / item.total) * 100) : 0,
    }))
    .sort((a, b) => a.label.localeCompare(b.label))
    .slice(0, 12);
});

const progressPayload = computed<Record<string, unknown> | null>(() => {
  const progress = props.run?.progress;
  return progress && typeof progress === "object" ? (progress as Record<string, unknown>) : null;
});

const backendProgressSummary = computed(() => {
  const progress = progressPayload.value;
  if (!progress) return null;

  const summaryCandidates = [
    progress.summary,
    progress.overall,
    progress.totals,
    progress.progress_summary,
    progress,
  ];

  for (const [index, candidate] of summaryCandidates.entries()) {
    const summary = toSliceProgress(
      candidate,
      `summary_${index}`,
      String(progress.label ?? progress.title ?? "Overall"),
    );
    if (summary) return summary;
  }

  return null;
});

const platformProgressList = computed<PlatformProgress[]>(() => {
  const progress = progressPayload.value;
  if (progress) {
    for (const [groupKey, value] of [
      ["platforms", progress.platforms],
      ["platform_progress", progress.platform_progress],
      ["by_platform", progress.by_platform],
    ] as Array<[string, unknown]>) {
      const slices = toSliceCollection(value, groupKey).map((item) => ({
        platform: item.key,
        ...item,
      }));
      if (slices.length) return slices.slice(0, 8);
    }
  }
  return activeStagePlatformProgress.value;
});

const backendSliceGroups = computed<ProgressGroup[]>(() => {
  const progress = progressPayload.value;
  if (!progress) return [];

  const groups: ProgressGroup[] = [];
  const seen = new Set<string>();

  const addGroup = (groupKey: string, rawValue: unknown) => {
    if (seen.has(groupKey)) return;
    const slices = toSliceCollection(rawValue, groupKey).slice(0, 12);
    if (!slices.length) return;
    seen.add(groupKey);
    groups.push({
      key: groupKey,
      label: progressGroupLabels[groupKey] ?? prettifyKey(groupKey),
      slices,
    });
  };

  for (const [groupKey, rawValue] of [
    ["slices", progress.slices],
    ["slice_progress", progress.slice_progress],
    ["by_slice", progress.by_slice],
    ["keywords", progress.keywords],
    ["keyword_slices", progress.keyword_slices],
    ["keyword_progress", progress.keyword_progress],
    ["by_keyword", progress.by_keyword],
    ["accounts", progress.accounts],
    ["account_slices", progress.account_slices],
    ["account_progress", progress.account_progress],
    ["by_account", progress.by_account],
    ["stages", progress.stages],
    ["stage_progress", progress.stage_progress],
    ["jobs", progress.jobs],
    ["job_progress", progress.job_progress],
  ] as Array<[string, unknown]>) {
    addGroup(groupKey, rawValue);
  }

  const ignoredKeys = new Set([
    "summary",
    "overall",
    "totals",
    "progress_summary",
    "label",
    "title",
    "detail",
    "status",
    "percent",
    "progress",
    "total",
    "completed",
    "done",
    "running",
    "active",
    "failed",
    "errors",
    "waiting",
    "pending",
    "queued",
    "platforms",
    "platform_progress",
    "by_platform",
  ]);

  for (const [key, value] of Object.entries(progress)) {
    if (ignoredKeys.has(key)) continue;
    addGroup(key, value);
  }

  return groups;
});

const displayedSliceGroups = computed<ProgressGroup[]>(() => {
  if (backendSliceGroups.value.length) return backendSliceGroups.value;
  if (sliceProgress.value.length) {
    return [
      {
        key: "derived_slices",
        label: "关键词 / 账号切片",
        slices: sliceProgress.value,
      },
    ];
  }
  return [];
});

const topFilterReasons = computed(() => {
  const reasons = props.run?.breakdowns?.filter_reasons;
  if (!Array.isArray(reasons)) return [];
  return reasons
    .map((item) => ({
      key: String(item.reason ?? ""),
      label: String(item.reason ?? "Unknown"),
      count: Number(item.count ?? 0),
    }))
    .filter((item) => item.label)
    .slice(0, 6);
});

const roleGuideCards = computed(() => [
  {
    label: "Run",
    title: props.run?.title || "当前任务运行",
    detail: "一次完整采集任务（包含多个阶段）。",
  },
  {
    label: "Stage",
    title: activeStage.value?.name || "当前阶段",
    detail: "一个流程阶段（例如关键词采集、账号采集）。",
  },
  {
    label: "Job",
    title: activeJob.value?.name || "当前作业",
    detail: "阶段内最小执行单元，通常是“某平台 + 一批关键词/账号”。",
  },
]);

function classifyIssue(message: string): { key: string; label: string; hint: string } {
  const text = message.toLowerCase();
  if (/timeout|timed out|page\.goto/i.test(text)) {
    return { key: "timeout", label: "页面超时", hint: "网络慢或站点响应慢，建议降低并发或加长超时。" };
  }
  if (/failed to get note detail after api and html fallback/i.test(text)) {
    return { key: "detail_fallback", label: "详情抓取失败", hint: "API 与 HTML 回退都失败，通常是风控或内容不可见导致。" };
  }
  if (/login|cookie|session|qrcode|unauthorized|401|forbidden|403/i.test(text)) {
    return { key: "auth", label: "登录/权限问题", hint: "请检查登录状态、Cookie 或会话有效性。" };
  }
  if (/captcha|risk|rate limit|too many|429|风控|验证码/i.test(text)) {
    return { key: "risk", label: "频控/风控", hint: "请求过快触发风控，建议降速并更换会话。" };
  }
  if (/net::|network|dns|econn|proxy|connection/i.test(text)) {
    return { key: "network", label: "网络连接问题", hint: "检查代理、网络连通性和 DNS。" };
  }
  return { key: "other", label: "其他异常", hint: "查看终端日志详情定位具体报错。" };
}

const topIssues = computed<IssueSummary[]>(() => {
  if (Array.isArray(props.run?.issues) && props.run.issues.length) {
    return props.run.issues
      .map((issue) => ({
        key: issue.fingerprint,
        label: issue.label,
        count: Number(issue.count ?? 0),
        hint: issue.hint ?? "",
        sample: issue.last_message ?? issue.sample_message ?? "",
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  }
  const buckets = new Map<string, IssueSummary>();
  for (const entry of props.logs) {
    const level = normalizeLogLevel(entry.level);
    if (!["error", "warning", "warn"].includes(level)) continue;
    const issue = classifyIssue(String(entry.message ?? ""));
    const existing = buckets.get(issue.key) ?? {
      key: issue.key,
      label: issue.label,
      count: 0,
      hint: issue.hint,
      sample: String(entry.message ?? ""),
    };
    existing.count += 1;
    buckets.set(issue.key, existing);
  }
  return Array.from(buckets.values())
    .sort((a, b) => b.count - a.count)
    .slice(0, 4);
});

function inferAlertCode(input: Pick<ExecutionAlert, "code" | "label" | "detail" | "status">): string {
  const haystack = `${input.code} ${input.label} ${input.detail} ${input.status ?? ""}`.toLowerCase();
  if (/session[_ -]?locked|locked session|会话.*锁/.test(haystack)) return "session_locked";
  if (haystack.includes("waiting_user") || haystack.includes("waiting for user") || haystack.includes("等待用户")) {
    return "waiting_user";
  }
  if (haystack.includes("degraded") || haystack.includes("降级")) return "degraded";
  return String(input.code ?? "warning").trim().toLowerCase() || "warning";
}

function alertTone(
  code: string,
  level?: string | null,
  status?: string | null,
  detail?: string,
): "warning" | "danger" | "running" | "neutral" {
  const normalizedCode = inferAlertCode({
    code,
    label: code,
    detail: detail ?? "",
    status,
  });
  const normalizedLevel = String(level ?? "warning").trim().toLowerCase();
  if (normalizedCode === "session_locked" || normalizedLevel === "error" || normalizedLevel === "danger") {
    return "danger";
  }
  if (normalizedCode === "waiting_user" || normalizedCode === "degraded" || normalizedLevel === "warning") {
    return "warning";
  }
  if (normalizedLevel === "info") return "running";
  return "neutral";
}

function alertPriority(alert: ExecutionAlert): number {
  const code = inferAlertCode(alert);
  if (code === "session_locked") return 0;
  if (code === "waiting_user") return 1;
  if (code === "degraded") return 2;
  if (alert.tone === "danger") return 3;
  return 10;
}

function normalizeExecutionAlert(warning: TaskRunWarning, source: string): ExecutionAlert {
  const code = inferAlertCode({
    code: warning.code,
    label: warning.label,
    detail: warning.detail,
    status: warning.status,
  });

  return {
    key: `${source}:${warning.key}`,
    code,
    label: warning.label || prettifyKey(code),
    detail: warning.detail || warning.label || prettifyKey(code),
    level: warning.level || "warning",
    status: warning.status ?? null,
    tone: alertTone(code, warning.level, warning.status, warning.detail),
    source,
  };
}

const effectivePlanItems = computed<TaskRunPlanItem[]>(() => props.run?.effective_plan ?? []);

const effectiveSaveOptionText = computed(() =>
  formatSaveOption(props.run?.effective_save_option ?? String(runParams.value.save_option ?? runParams.value.save_data_option ?? "")),
);

const runtimeStorageBackendText = computed(() =>
  formatStorageBackend(props.run?.runtime_storage_backend),
);

const lifecycleNarrative = computed(() => {
  const lifecycle = props.run?.lifecycle;
  const phase = normalizeStatusKey(lifecycle?.phase ?? props.run?.status);

  if (phase === "queued" || phase === "preflight") {
    return {
      title: "预检中",
      detail:
        lifecycle?.detail
        || "系统正在连接 Browsermint 会话、校验目标平台登录态，并确认会话是否可继续借用。",
      hint: "预检阶段不会启动正式抓取；如果停留过久，优先检查会话是否需要人工确认。",
    };
  }

  if (phase === "waiting_user") {
    return {
      title: "等待用户处理",
      detail:
        lifecycle?.detail
        || "系统已暂停在预检阶段，等待你处理登录、风控或会话锁定问题。",
      hint: "处理完成后保持此页打开，等待 websocket 推送新的运行状态。",
    };
  }

  if (phase === "running") {
    return {
      title: lifecycle?.current_stage_name || lifecycle?.label || "任务执行中",
      detail: lifecycle?.detail || "任务已通过预检并开始执行各阶段作业。",
      hint:
        lifecycle?.stage_total
          ? `当前阶段 ${lifecycle.stage_index ?? 0}/${lifecycle.stage_total}`
          : "等待更多阶段信息。",
    };
  }

  if (phase === "finalizing") {
    return {
      title: "正在收尾",
      detail: lifecycle?.detail || "系统正在持久化最终状态并整理结果。",
      hint: "此阶段通常很短，完成后会切换到最终状态。",
    };
  }

  return {
    title: lifecycle?.label || formatStatusLabel(props.run?.status),
    detail: lifecycle?.detail || "等待更多运行信息。",
    hint:
      lifecycle?.stage_total
        ? `阶段进度 ${lifecycle.stage_index ?? 0}/${lifecycle.stage_total}`
        : "未返回阶段元数据。",
  };
});

const lifecycleGuideCards = computed(() => [
  {
    label: "Lifecycle",
    title: lifecycleNarrative.value.title,
    detail: lifecycleNarrative.value.hint,
  },
  {
    label: "Phase",
    title: props.run?.lifecycle?.phase || normalizeStatusKey(props.run?.status) || "unknown",
    detail: props.run?.lifecycle?.detail || "等待更多运行信息。",
  },
  {
    label: "Stage",
    title: props.run?.lifecycle?.current_stage_name || activeStage.value?.name || "待分配",
    detail:
      props.run?.lifecycle?.stage_total
        ? `${props.run.lifecycle.stage_index ?? 0}/${props.run.lifecycle.stage_total}`
        : "未返回阶段序号",
  },
]);

const executionAlerts = computed<ExecutionAlert[]>(() => {
  const alerts: ExecutionAlert[] = [];

  for (const warning of props.run?.plan_warnings ?? []) {
    alerts.push(normalizeExecutionAlert(warning, "plan"));
  }

  for (const warning of props.run?.warnings ?? []) {
    alerts.push(normalizeExecutionAlert(warning, "run"));
  }

  const phase = normalizeStatusKey(props.run?.lifecycle?.phase ?? props.run?.status);
  const lifecycleDetail = String(props.run?.lifecycle?.detail ?? "").trim();

  if (phase === "waiting_user" && !alerts.some((alert) => inferAlertCode(alert) === "waiting_user")) {
    alerts.push({
      key: "lifecycle:waiting_user",
      code: "waiting_user",
      label: "等待用户处理",
      detail: lifecycleDetail || "当前运行已暂停，等待你在 Browsermint / 平台侧完成手动处理。",
      level: "warning",
      status: "waiting_user",
      tone: "warning",
      source: "lifecycle",
    });
  }

  if (phase === "degraded" && !alerts.some((alert) => inferAlertCode(alert) === "degraded")) {
    alerts.push({
      key: "lifecycle:degraded",
      code: "degraded",
      label: "执行已降级",
      detail: lifecycleDetail || "后端已切换到降级计划，请结合 effective_plan 确认实际执行范围。",
      level: "warning",
      status: "degraded",
      tone: "warning",
      source: "lifecycle",
    });
  }

  if (
    /session[_ -]?locked|locked session|会话.*锁/.test(lifecycleDetail.toLowerCase())
    && !alerts.some((alert) => inferAlertCode(alert) === "session_locked")
  ) {
    alerts.push({
      key: "lifecycle:session_locked",
      code: "session_locked",
      label: "会话锁定",
      detail: lifecycleDetail,
      level: "warning",
      status: "session_locked",
      tone: "danger",
      source: "lifecycle",
    });
  }

  const deduped = new Map<string, ExecutionAlert>();
  for (const alert of alerts) {
    const fingerprint = `${inferAlertCode(alert)}:${alert.detail}`;
    if (!deduped.has(fingerprint)) {
      deduped.set(fingerprint, alert);
    }
  }

  return Array.from(deduped.values()).sort((left, right) => alertPriority(left) - alertPriority(right));
});

const summaryCards = computed(() => {
  const cards = [
    {
      label: "运行状态",
      value: formatStatusLabel(props.run?.status),
      helper: props.run ? `${props.run.title} · ${props.run.id}` : "无运行记录",
    },
    {
      label: "运行时长",
      value: runDurationText.value,
      helper: props.run ? `开始于 ${formatTime(props.run.started_at, false)}` : "--",
    },
    backendProgressSummary.value
      ? {
          label: "后端进度",
          value: `${backendProgressSummary.value.completed}/${backendProgressSummary.value.total || 0}`,
          helper: `${backendProgressSummary.value.percent}% · ${backendProgressSummary.value.running} 运行中 · ${backendProgressSummary.value.failed} 失败`,
        }
      : {
          label: "作业进度",
          value: `${completedJobs.value}/${totalJobs.value || 0}`,
          helper: `${runningJobs.value} 运行中 · ${failedJobs.value} 失败`,
        },
    {
      label: "候选内容",
      value: String(candidateCount.value),
      helper: "搜索阶段识别到的候选量",
    },
    {
      label: "Accepted",
      value: String(acceptedCount.value),
      helper: "进入结果中心的数据量",
    },
    {
      label: "详情成功/失败",
      value: `${detailSuccessCount.value}/${detailFailureCount.value}`,
      helper: `${detailRequestCount.value} 次详情请求`,
    },
    {
      label: "Issue Groups",
      value: String(topIssues.value.length || errorCount.value),
      helper: props.run?.lifecycle?.label || "实时错误聚合",
    },
  ];

  if (runtimeStorageBackendText.value !== "未返回" || effectiveSaveOptionText.value !== "未返回") {
    cards.push({
      label: "存储落点",
      value:
        runtimeStorageBackendText.value !== "未返回"
          ? runtimeStorageBackendText.value
          : effectiveSaveOptionText.value,
      helper: `结果格式 · ${effectiveSaveOptionText.value}`,
    });
  }

  return cards;
});

const extraMetricCards = computed(() =>
  Object.entries(props.run?.metrics ?? {})
    .filter(([key, value]) => {
      if ([
        "accepted",
        "filtered",
        "deduped",
        "errors",
        "stalled_jobs",
        "candidate_count",
        "detail_requests",
        "detail_successes",
        "detail_failures",
      ].includes(key)) {
        return false;
      }
      return Number.isFinite(Number(value)) && Number(value) > 0;
    })
    .slice(0, 4)
    .map(([key, value]) => ({
      label: metricLabel(key),
      value: String(Number(value)),
      helper: "后端附加指标",
    })),
);

const monitorCards = computed(() => [...summaryCards.value, ...extraMetricCards.value]);

function scopeLabel(scope: LogScope): string {
  if (scope === "job") return "当前 Job";
  if (scope === "stage") return "当前 Stage";
  return "整次 Run";
}

function formatAlertBadge(alert: ExecutionAlert): string {
  if (alert.status) return formatStatusLabel(alert.status);
  if (alert.level === "warning") return "WARN";
  if (alert.level === "error") return "ERROR";
  return alert.level.toUpperCase();
}
</script>

<template>
  <section class="tab-panel execution-tab">
    <div class="tab-panel-head">
      <div>
        <h2>运行监控</h2>
        <p>补充业务进度与术语解释，避免只看到抽象 run/stage/job。</p>
      </div>
      <span v-if="run" class="state-chip" :class="statusTone(run.status)">
        {{ formatStatusLabel(run.status) }}
      </span>
    </div>

    <div v-if="run" class="execution-shell">
      <section class="monitor-cards">
        <article v-for="card in monitorCards" :key="card.label" class="monitor-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.helper }}</small>
        </article>
      </section>

      <section v-if="run.lifecycle" class="monitor-toolbar lifecycle-bar">
        <div class="lifecycle-copy">
          <h3>{{ lifecycleNarrative.title }}</h3>
          <p>{{ lifecycleNarrative.detail }}</p>
          <small>{{ lifecycleNarrative.hint }}</small>
        </div>
        <div class="guide-list compact lifecycle-guide-list">
          <div v-for="item in lifecycleGuideCards" :key="item.label" class="guide-item">
            <span class="guide-label">{{ item.label }}</span>
            <strong>{{ item.title }}</strong>
            <small>{{ item.detail }}</small>
          </div>
        </div>
      </section>

      <section class="insight-grid">
        <article class="insight-card">
          <h3>Run / Stage / Job 是什么</h3>
          <div class="guide-list">
            <div v-for="item in roleGuideCards" :key="item.label" class="guide-item">
              <span class="guide-label">{{ item.label }}</span>
              <strong>{{ item.title }}</strong>
              <small>{{ item.detail }}</small>
            </div>
          </div>
        </article>

        <article class="insight-card">
          <h3>总体进度</h3>
          <div class="progress-overview">
            <span>已选平台：{{ configuredPlatforms.length || 0 }}</span>
            <span>关键词：{{ configuredKeywords.length || 0 }}</span>
            <span v-if="backendProgressSummary">
              后端汇总：{{ backendProgressSummary.completed }}/{{ backendProgressSummary.total }}
            </span>
            <span v-else>
              {{ activeStageBatchNoun }}：{{ activeStageBatchProgress.completed }}/{{ activeStageBatchProgress.total }}
            </span>
          </div>
          <div class="progress-track" aria-hidden="true">
            <span :style="{ width: `${backendProgressSummary?.percent ?? activeStageBatchProgress.percent}%` }" />
          </div>
          <small v-if="backendProgressSummary?.detail" class="inline-note">{{ backendProgressSummary.detail }}</small>
          <div class="platform-list" v-if="platformProgressList.length">
            <div v-for="item in platformProgressList" :key="item.platform" class="platform-item">
              <div class="platform-head">
                <strong>{{ item.label }}</strong>
                <small>{{ item.completed }}/{{ item.total }} 完成</small>
              </div>
              <div class="progress-track compact" aria-hidden="true">
                <span :style="{ width: `${item.percent}%` }" />
              </div>
              <div class="platform-meta">
                <span>{{ item.running }} 运行中</span>
                <span>{{ item.failed }} 失败</span>
                <span>{{ item.waiting }} 等待</span>
              </div>
              <small v-if="item.detail">{{ item.detail }}</small>
            </div>
          </div>
          <div v-else class="inline-empty">当前阶段暂无可统计的平台任务。</div>
        </article>

        <article class="insight-card" v-if="executionAlerts.length">
          <h3>运行警告 / 待处理事项</h3>
          <div class="issue-list">
            <div v-for="alert in executionAlerts" :key="alert.key" class="issue-item alert-item" :class="`tone-${alert.tone}`">
              <div class="issue-head">
                <strong>{{ alert.label }}</strong>
                <span class="state-chip" :class="alert.tone">{{ formatAlertBadge(alert) }}</span>
              </div>
              <small>{{ alert.detail }}</small>
            </div>
          </div>
        </article>

        <article
          class="insight-card"
          v-if="effectivePlanItems.length || runtimeStorageBackendText !== '未返回' || effectiveSaveOptionText !== '未返回'"
        >
          <h3>有效执行计划</h3>
          <div class="plan-meta-grid">
            <div class="guide-item">
              <span class="guide-label">Storage</span>
              <strong>{{ runtimeStorageBackendText }}</strong>
              <small>`runtime_storage_backend`</small>
            </div>
            <div class="guide-item">
              <span class="guide-label">Save</span>
              <strong>{{ effectiveSaveOptionText }}</strong>
              <small>`effective_save_option`</small>
            </div>
          </div>
          <div v-if="effectivePlanItems.length" class="issue-list">
            <div v-for="item in effectivePlanItems" :key="item.key" class="issue-item">
              <div class="issue-head">
                <strong>{{ item.label }}</strong>
                <span v-if="item.status" class="state-chip" :class="statusTone(item.status)">
                  {{ formatStatusLabel(item.status) }}
                </span>
              </div>
              <small>{{ item.detail || "后端未返回该计划项的额外说明。" }}</small>
            </div>
          </div>
          <div v-else class="inline-empty">后端尚未返回 `effective_plan` 细项。</div>
        </article>

        <article class="insight-card" v-if="displayedSliceGroups.length">
          <h3>切片进度</h3>
          <div class="progress-group-stack">
            <section v-for="group in displayedSliceGroups" :key="group.key" class="progress-group">
              <div class="progress-group-head">
                <strong>{{ group.label }}</strong>
                <small>{{ group.slices.length }} 项</small>
              </div>
              <div class="platform-list">
                <div v-for="item in group.slices" :key="item.key" class="platform-item">
                  <div class="platform-head">
                    <strong>{{ item.label }}</strong>
                    <small>{{ item.completed }}/{{ item.total }} 完成</small>
                  </div>
                  <div class="progress-track compact" aria-hidden="true">
                    <span :style="{ width: `${item.percent}%` }" />
                  </div>
                  <div class="platform-meta">
                    <span>{{ item.running }} 运行中</span>
                    <span>{{ item.failed }} 失败</span>
                    <span>{{ item.waiting }} 等待</span>
                  </div>
                  <small v-if="item.detail">{{ item.detail }}</small>
                </div>
              </div>
            </section>
          </div>
        </article>

        <article class="insight-card" v-if="topIssues.length">
          <h3>高频问题汇总</h3>
          <div class="issue-list">
            <div v-for="issue in topIssues" :key="issue.key" class="issue-item">
              <div class="issue-head">
                <strong>{{ issue.label }}</strong>
                <span class="state-chip warning">{{ issue.count }} 次</span>
              </div>
              <small>{{ issue.hint }}</small>
              <code v-if="issue.sample">{{ issue.sample }}</code>
            </div>
          </div>
        </article>

        <article class="insight-card" v-if="topFilterReasons.length">
          <h3>过滤原因 Top</h3>
          <div class="issue-list">
            <div v-for="item in topFilterReasons" :key="item.key" class="issue-item">
              <div class="issue-head">
                <strong>{{ item.label }}</strong>
                <span class="state-chip neutral">{{ item.count }} 条</span>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section class="monitor-toolbar">
        <div class="scope-switch" role="tablist" aria-label="日志范围">
          <button class="scope-button" :class="{ active: logScope === 'run' }" @click="logScope = 'run'">Run</button>
          <button class="scope-button" :class="{ active: logScope === 'stage' }" :disabled="!activeStage" @click="logScope = 'stage'">Stage</button>
          <button class="scope-button" :class="{ active: logScope === 'job' }" :disabled="!activeJob" @click="logScope = 'job'">Job</button>
        </div>

        <div class="toolbar-selects">
          <label class="toolbar-field" v-if="stageSelectOptions.length">
            <span>Stage</span>
            <SelectField compact :model-value="activeStage?.key || ''" :options="stageSelectOptions" @update:model-value="handleStageChange" />
          </label>

          <label class="toolbar-field" v-if="jobSelectOptions.length">
            <span>Job</span>
            <SelectField compact :model-value="activeJob?.ref || ''" :options="jobSelectOptions" @update:model-value="handleJobChange" />
          </label>

          <label class="toolbar-field">
            <span>级别</span>
            <SelectField compact :model-value="selectedLogLevel" :options="logLevelSelectOptions" @update:model-value="selectedLogLevel = $event" />
          </label>
        </div>
      </section>

      <section class="terminal-card">
        <div class="terminal-head">
          <div>
            <h3>实时日志终端</h3>
            <p>{{ scopeLabel(logScope) }} · {{ visibleLogs.length }} 条</p>
          </div>
          <span v-if="activeJob && logScope !== 'run'" class="state-chip neutral">
            {{ activeJob.stageName }} / {{ activeJob.name }}
          </span>
        </div>

        <div class="terminal-stream">
          <div v-if="visibleLogs.length" class="terminal-list">
            <article
              v-for="(entry, index) in visibleLogs"
              :key="`${entry.id}-${entry.timestamp}-${index}`"
              class="terminal-line"
              :class="`level-${normalizeLogLevel(entry.level)}`"
            >
              <span class="terminal-time">{{ formatShortTime(entry.timestamp) }}</span>
              <span class="terminal-level">{{ formatLogLevel(entry.level) }}</span>
              <span class="terminal-origin" v-if="logScope === 'run'">
                {{ entry.stage_name || entry.stage_key || "run" }} / {{ entry.job_name || entry.job_key || "job" }}
              </span>
              <code>{{ entry.message }}</code>
            </article>
          </div>
          <div v-else class="empty-state">当前范围还没有日志输出。</div>
        </div>
      </section>
    </div>

    <div v-else class="empty-state">选择一个运行记录后，这里会展示实时运行结果。</div>
  </section>
</template>

<style scoped>
.execution-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.execution-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.monitor-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}

.monitor-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(255, 255, 255, 0.88);
}

.monitor-card span,
.monitor-card small {
  color: var(--muted);
  font-size: 12px;
}

.monitor-card strong {
  font-family: "Manrope", sans-serif;
  font-size: 20px;
  line-height: 1.2;
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.insight-card,
.monitor-toolbar,
.terminal-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(255, 255, 255, 0.9);
}

.insight-card h3 {
  margin: 0;
  font-size: 17px;
}

.lifecycle-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.lifecycle-copy h3,
.lifecycle-copy p,
.lifecycle-copy small {
  margin: 0;
}

.lifecycle-copy p,
.lifecycle-copy small,
.inline-note {
  color: var(--muted);
}

.guide-list,
.issue-list,
.platform-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.plan-meta-grid,
.progress-group-stack {
  display: grid;
  gap: 10px;
}

.plan-meta-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.progress-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.guide-list.compact {
  gap: 0;
}

.progress-group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.guide-item,
.issue-item,
.platform-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(22, 32, 43, 0.08);
  background: rgba(247, 249, 252, 0.9);
}

.issue-item code {
  white-space: normal;
  word-break: break-word;
  color: var(--ink);
  font-size: 11px;
}

.alert-item.tone-warning {
  border-color: rgba(236, 185, 82, 0.28);
  background: rgba(236, 185, 82, 0.08);
}

.alert-item.tone-danger {
  border-color: rgba(194, 60, 54, 0.24);
  background: rgba(194, 60, 54, 0.08);
}

.alert-item.tone-running {
  border-color: rgba(31, 79, 209, 0.2);
  background: rgba(31, 79, 209, 0.06);
}

.guide-label {
  width: fit-content;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(31, 79, 209, 0.1);
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
}

.guide-item small,
.issue-item small,
.platform-meta,
.progress-overview,
.inline-empty {
  color: var(--muted);
  font-size: 12px;
}

.progress-overview,
.platform-meta,
.platform-head,
.issue-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.progress-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(20, 35, 55, 0.08);
}

.progress-track > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #cf6b42, #1f4fd1);
}

.progress-track.compact {
  height: 6px;
}

.scope-switch {
  display: inline-grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  width: 260px;
  padding: 4px;
  border-radius: 12px;
  border: 1px solid rgba(22, 32, 43, 0.1);
  background: rgba(20, 35, 55, 0.04);
  gap: 4px;
}

.scope-button {
  min-height: 34px;
  border-radius: 9px;
  background: transparent;
  color: var(--muted);
  font-weight: 600;
}

.scope-button.active {
  background: rgba(31, 79, 209, 0.14);
  color: var(--ink);
}

.toolbar-selects {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.toolbar-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.toolbar-field span {
  color: var(--muted);
  font-size: 12px;
}

.terminal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.terminal-head h3 {
  margin: 0;
}

.terminal-head p {
  margin: 4px 0 0;
  color: var(--muted);
}

.terminal-stream {
  min-height: 560px;
  max-height: 72vh;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(17, 23, 34, 0.3);
  background: #101722;
  overflow: auto;
}

.terminal-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.terminal-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-start;
  padding: 9px 10px;
  border-radius: 10px;
  border: 1px solid rgba(124, 142, 168, 0.16);
  background: rgba(255, 255, 255, 0.03);
  color: #d9e4f4;
}

.terminal-time,
.terminal-level,
.terminal-origin {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.1);
  color: #9bb0cb;
}

.terminal-line code {
  flex: 1;
  min-width: 200px;
  white-space: pre-wrap;
  word-break: break-word;
}

.terminal-line.level-error {
  border-color: rgba(255, 125, 97, 0.35);
  background: rgba(194, 60, 54, 0.16);
}

.terminal-line.level-warning,
.terminal-line.level-warn {
  border-color: rgba(236, 185, 82, 0.3);
  background: rgba(236, 185, 82, 0.1);
}

@media (max-width: 1280px) {
  .monitor-cards,
  .insight-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .plan-meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .toolbar-selects {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 760px) {
  .monitor-cards,
  .insight-grid,
  .toolbar-selects,
  .scope-switch {
    grid-template-columns: 1fr;
    width: 100%;
  }

  .plan-meta-grid {
    grid-template-columns: 1fr;
  }

  .terminal-stream {
    min-height: 420px;
    max-height: 68vh;
  }
}
</style>
