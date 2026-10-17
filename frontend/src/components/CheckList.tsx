import { useMemo, useState } from "react";
import { SeverityBadge } from "./SeverityBadge";
import type { CheckResult, Severity } from "../types";

interface CheckListProps {
  checks: CheckResult[];
}

const SEVERITY_FILTERS: { label: string; value: Severity | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Errors", value: "error" },
  { label: "Warnings", value: "warning" },
  { label: "Info", value: "info" },
];

export function CheckList({ checks }: CheckListProps) {
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const c of checks) set.add(c.category);
    return Array.from(set).sort();
  }, [checks]);

  const filtered = useMemo(() => {
    return checks.filter((c) => {
      if (severityFilter !== "all" && c.severity !== severityFilter) return false;
      if (categoryFilter !== "all" && c.category !== categoryFilter) return false;
      return true;
    });
  }, [checks, severityFilter, categoryFilter]);

  if (checks.length === 0) {
    return <p className="empty-state">No checks were run.</p>;
  }

  return (
    <div>
      <div className="filter-bar">
        <label>Severity:</label>
        <div className="tag-list">
          {SEVERITY_FILTERS.map((f) => (
            <button
              key={f.value}
              className={`btn btn-sm ${
                severityFilter === f.value ? "btn-primary" : ""
              }`}
              onClick={() => setSeverityFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>

        <label>Category:</label>
        <div className="tag-list">
          <button
            className={`btn btn-sm ${categoryFilter === "all" ? "btn-primary" : ""}`}
            onClick={() => setCategoryFilter("all")}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              className={`btn btn-sm ${
                categoryFilter === cat ? "btn-primary" : ""
              }`}
              onClick={() => setCategoryFilter(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
        Showing {filtered.length} of {checks.length} findings
      </p>

      <ul className="check-list">
        {filtered.map((c, i) => (
          <li key={`${c.check_id}-${i}`} className="check-item">
            <div className="check-title">
              <SeverityBadge severity={c.severity} />
              <span style={{ marginLeft: "0.5rem" }}>{c.title}</span>
            </div>
            <p className="check-message">{c.message}</p>
            {c.file_path && (
              <p className="check-location">
                {c.file_path}
                {c.line ? `:${c.line}` : ""}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}