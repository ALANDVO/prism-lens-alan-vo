import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { CheckList } from "../components/CheckList";
import { StatusBadge } from "../components/SeverityBadge";
import { getClient } from "../api/client";
import { ApiError } from "../api/client";
import type { ValidationReport } from "../types";

export default function ReportDetail() {
  const { reportId } = useParams<{ reportId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = async () => {
    if (!reportId) return;
    setLoading(true);
    setError(null);
    try {
      const client = getClient();
      const data = await client.getReport(reportId);
      setReport(data);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Failed to load report (${e.status}): ${e.message}`);
      } else {
        setError("Failed to load report");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [reportId]);

  const handleExport = async (format: string) => {
    if (!reportId) return;
    try {
      const client = getClient();
      const content = await client.exportReport(reportId, format as "json" | "text");
      const blob = new Blob([content], {
        type: format === "json" ? "application/json" : "text/plain",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `prism-lens-${reportId}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Export failed: ${e.message}`);
      }
    }
  };

  const handleAdvisory = async () => {
    if (!reportId) return;
    setLoading(true);
    setError(null);
    try {
      const client = getClient();
      const data = await client.requestAdvisory(reportId);
      setReport(data);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Advisory failed (${e.status}): ${e.message}`);
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading report…</div>;
  }

  if (error) {
    return <div className="error-state">{error}</div>;
  }

  if (!report) {
    return <div className="empty-state">No report found.</div>;
  }

  return (
    <section>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.5rem" }}>
        <div>
          <h2>{report.plugin_name}</h2>
          <p style={{ color: "var(--text-muted)" }}>
            v{report.plugin_version || "—"} · <StatusBadge status={report.status} />
          </p>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
            Created: {new Date(report.started_at).toLocaleString()}
          </p>
        </div>
        <Link to="/" className="btn btn-sm">
          ← Back to Dashboard
        </Link>
      </div>

      <div className="card">
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem" }}>
          <span className="tag">
            Errors: {report.summary.error || 0}
          </span>
          <span className="tag">
            Warnings: {report.summary.warning || 0}
          </span>
          <span className="tag">
            Info: {report.summary.info || 0}
          </span>
        </div>

        <CheckList checks={report.checks} />
      </div>

      <div className="card">
        <h3>Export &amp; Advisory</h3>
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
          <button className="btn" onClick={() => handleExport("text")}>
            Export as Text
          </button>
          <button className="btn" onClick={() => handleExport("json")}>
            Export as JSON
          </button>
          <button
            className="btn"
            onClick={handleAdvisory}
            disabled={report.llm_advisory !== null}
          >
            {report.llm_advisory
              ? "Advisory Generated"
              : "Request LLM Advisory"}
          </button>
        </div>

        {report.llm_advisory && (
          <div className="advisory-box">
            <span className="advisory-label">Advisory (LLM-generated, labeled)</span>
            <p className="advisory-text">{report.llm_advisory}</p>
          </div>
        )}
      </div>
    </section>
  );
}