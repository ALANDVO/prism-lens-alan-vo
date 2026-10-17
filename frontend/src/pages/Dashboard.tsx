import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { SearchBar } from "../components/SearchBar";
import { StatusBadge } from "../components/SeverityBadge";
import { getClient } from "../api/client";
import { ApiError } from "../api/client";
import type { ReportSummary } from "../types";

export default function Dashboard() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const fetchReports = async (searchTerm: string) => {
    setLoading(true);
    setError(null);
    try {
      const client = getClient();
      const data = await client.listReports({ search: searchTerm || undefined });
      setReports(data);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Failed to load reports (${e.status}): ${e.message}`);
      } else {
        setError("Failed to load reports");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports(search);
  }, [search]);

  const handleSearch = (value: string) => setSearch(value);

  const handleExportAll = () => {
    // Export all visible reports as a combined summary
    if (reports.length === 0) return;
    const blob = new Blob(
      [JSON.stringify(reports, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `prism-lens-reports-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <h2>Validation Reports</h2>
        <button className="btn btn-primary" onClick={() => navigate("/validate")}>
          Validate New Plugin
        </button>
      </div>

      <div className="filter-bar">
        <SearchBar
          initialValue=""
          onSearch={handleSearch}
          placeholder="Search by plugin name or report ID…"
          debounceMs={300}
        />
        {reports.length > 0 && (
          <button className="btn btn-sm" onClick={handleExportAll}>
            Export CSV
          </button>
        )}
      </div>

      {loading && <div className="loading">Loading reports…</div>}

      {error && <div className="error-state">{error}</div>}

      {!loading && !error && reports.length === 0 && (
        <div className="empty-state">
          <p>No reports yet. Upload a plugin to get started.</p>
          <Link to="/validate" className="btn">
            Validate a Plugin
          </Link>
        </div>
      )}

      {!loading && !error && reports.length > 0 && (
        <ul className="report-list">
          {reports.map((report) => (
            <li key={report.report_id} className="report-item">
              <div className="report-meta">
                <StatusBadge status={report.status} />
                <span style={{ fontWeight: 600 }}>{report.plugin_name}</span>
                {report.plugin_version && (
                  <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                    v{report.plugin_version}
                  </span>
                )}
              </div>
              <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                {new Date(report.started_at).toLocaleString()}
              </div>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <span className="tag">{report.error_count} errors</span>
                <span className="tag">{report.warning_count} warnings</span>
                <span className="tag">{report.info_count} info</span>
                <Link
                  to={`/reports/${report.report_id}`}
                  className="btn btn-sm"
                >
                  View
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}