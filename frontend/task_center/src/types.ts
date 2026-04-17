export type Primitive = string | number | boolean | null;

export interface TaskFieldOption {
  value: Primitive;
  label: string;
  description?: string;
}

export interface TaskFieldSchema {
  key: string;
  component: "textarea" | "number" | "switch" | "select" | "multiselect";
  label: string;
  default: unknown;
  description?: string;
  group: string;
  required: boolean;
  options: TaskFieldOption[];
  visible_when?: Record<string, unknown> | null;
  disabled_when?: Record<string, unknown> | null;
  validation?: Record<string, unknown> | null;
}

export interface TaskTemplate {
  slug: string;
  title: string;
  description: string;
  defaults: Record<string, unknown>;
  capabilities: string[];
  fields: TaskFieldSchema[];
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
  started_at?: string | null;
  finished_at?: string | null;
}

export interface TaskStage {
  key: string;
  name: string;
  concurrent: boolean;
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
