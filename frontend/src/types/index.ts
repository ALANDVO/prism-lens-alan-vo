/** Shared TypeScript types mirroring the backend API schemas. */

export type Severity = "error" | "warning" | "info";

export type ReportStatus = "passed" | "warnings" | "failed";

export interface CheckResult {
  check_id: string;
  category: string;
  severity: Severity;
  title: string;
  message: string;
  file_path?: string | null;
  line?: number | null;
}

export interface ValidationReport {
  report_id: string;
  plugin_name: string;
  plugin_version?: string | null;
  plugin_path?: string | null;
  status: ReportStatus;
  started_at: string;
  completed_at?: string | null;
  checks: CheckResult[];
  summary: Record<string, number>;
  llm_advisory?: string | null;
}

export interface ReportSummary {
  report_id: string;
  plugin_name: string;
  plugin_version?: string | null;
  status: ReportStatus;
  started_at: string;
  error_count: number;
  warning_count: number;
  info_count: number;
}

export interface ValidateResponse {
  report_id: string;
}

export type ExportFormat = "json" | "text";