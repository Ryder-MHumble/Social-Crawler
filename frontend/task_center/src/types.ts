export type Primitive = string | number | boolean | null;

export interface TaskFieldOption {
  value: Primitive;
  label: string;
  description?: string;
}

export interface TaskFieldValidation {
  min?: number;
  max?: number;
  step?: number;
  min_length?: number;
  max_length?: number;
  min_items?: number;
  max_items?: number;
  pattern?: string;
  [key: string]: unknown;
}

export interface TaskFieldSchema {
  key: string;
  component: "textarea" | "number" | "switch" | "select" | "multiselect" | "text";
  label: string;
  default: unknown;
  description?: string;
  group: string;
  required: boolean;
  options: TaskFieldOption[];
  placeholder?: string;
  rows?: number;
  layout?: "default" | "full";
  helper_text?: string;
  badge?: string;
  visible_when?: Record<string, unknown> | null;
  disabled_when?: Record<string, unknown> | null;
  validation?: TaskFieldValidation | null;
}

export interface TaskTemplate {
  slug: string;
  title: string;
  description: string;
  defaults: Record<string, unknown>;
  capabilities: string[];
  fields: TaskFieldSchema[];
}

export interface BrowsermintSession {
  session_id: string;
  name: string;
  status: string;
  last_active_at: string | null;
  deep_link_url: string;
  expires_at: string | null;
}

export interface BrowsermintSessionsPayload {
  configured: boolean;
  sessions: BrowsermintSession[];
}

export interface TaskPreset {
  id: string;
  task_slug: string;
  name: string;
  params: Record<string, unknown>;
  is_default: boolean;
  updated_at: string;
}

export interface TaskJob {
  key: string;
  name: string;
  cwd: string;
  command: string[];
  display_command?: string;
  status?: string;
  log_path?: string;
  exit_code?: number | null;
  line_count?: number;
  last_line?: string;
  pid?: number | null;
  last_output_at?: string | null;
  last_state_change_at?: string | null;
  watchdog_status?: string | null;
  stall_deadline_at?: string | null;
  termination_reason?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface TaskStage {
  key: string;
  name: string;
  concurrent: boolean;
  max_parallel?: number | null;
  abort_on_failure: boolean;
  status?: string;
  jobs: TaskJob[];
}

export interface TaskPreview {
  task: TaskTemplate;
  normalized_params: Record<string, unknown>;
  spec: {
    slug: string;
    title: string;
    stages: TaskStage[];
  };
}

export interface TaskRunMetrics {
  accepted: number;
  filtered: number;
  deduped: number;
  errors: number;
  stalled_jobs: number;
  [key: string]: number;
}

export interface TaskRun {
  id: string;
  task_slug: string;
  title: string;
  status: string;
  preset_id?: string | null;
  normalized_params: Record<string, unknown>;
  started_at?: string | null;
  finished_at?: string | null;
  log_path?: string | null;
  metrics: TaskRunMetrics;
  stages: TaskStage[];
}

export interface TaskLogEntry {
  id: number;
  timestamp: string;
  level: string;
  message: string;
  stage_key?: string | null;
  stage_name?: string | null;
  job_key?: string | null;
  job_name?: string | null;
}

export interface SqliteStatus {
  path: string;
  exists: boolean;
  initialized: boolean;
  schema_version: number | null;
  table_count: number;
  table_names: string[];
  db_size_bytes: number;
  last_modified_at: string | null;
  watchdog: {
    job_start_timeout_sec: number;
    job_stall_timeout_sec: number;
    terminate_grace_sec: number;
  };
}

export interface SqliteTableSummary {
  name: string;
  row_count: number;
  columns: string[];
  order_by: string;
}

export interface SqliteTablesPayload {
  tables: SqliteTableSummary[];
  supported_tables: string[];
}

export interface SqliteStats {
  table_counts: Record<string, number>;
  observation_status_counts: Record<string, number>;
}

export type SqliteRow = Record<string, unknown> & { id: number };

export interface SqliteRowsResponse {
  table: string;
  columns: string[];
  rows: SqliteRow[];
  total: number;
}

export interface DataFileInfo {
  name: string;
  path: string;
  size: number;
  modified_at: number;
  record_count: number | null;
  type: string;
}

export interface DataFilePreview {
  data: unknown;
  total: number;
  columns?: string[];
}

export type DataBrowseMode = "sqlite" | "files";

export interface SqliteRowFilters {
  table: string;
  run_id: string;
  task_slug: string;
  platform: string;
  entity_type: string;
  clean_status: string;
  q: string;
  limit: number;
  offset: number;
}

export interface DataFileFilters {
  platform: string;
  file_type: string;
  q: string;
}

export interface EnvCheckResult {
  success: boolean;
  message: string;
  output?: string;
  error?: string;
}

export interface GroupedFieldSection {
  name: string;
  fields: TaskFieldSchema[];
  requiredCount: number;
}
