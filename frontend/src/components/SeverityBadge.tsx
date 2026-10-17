import type { ReportStatus, Severity } from "../types";

interface SeverityBadgeProps {
  severity: Severity;
}

const SEVERITY_LABELS: Record<Severity, string> = {
  error: "Error",
  warning: "Warning",
  info: "Info",
};

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const label = SEVERITY_LABELS[severity] || severity;
  return <span className={`badge badge-${severity}`}>{label}</span>;
}

interface StatusBadgeProps {
  status: ReportStatus;
}

const STATUS_LABELS: Record<ReportStatus, string> = {
  passed: "Passed",
  warnings: "Warnings",
  failed: "Failed",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const label = STATUS_LABELS[status] || status;
  const dotClass = `status-dot status-dot-${status}`;
  return (
    <span className={`badge badge-${status}`}>
      <span className={dotClass}></span> {label}
    </span>
  );
}