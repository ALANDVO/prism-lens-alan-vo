import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadForm } from "../components/UploadForm";
import type { ValidateResponse } from "../types";

export default function ValidatePage() {
  const [step, setStep] = useState<"form" | "success">("form");
  const [reportId, setReportId] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleValidated = (response: ValidateResponse) => {
    setReportId(response.report_id);
    setStep("success");
  };

  if (step === "success" && reportId) {
    return (
      <section>
        <div className="card">
          <h2>Validation Complete</h2>
          <p>Your plugin has been analyzed. View the detailed report below.</p>
          <div style={{ marginTop: "1rem" }}>
            <button
              className="btn btn-primary"
              onClick={() => navigate(`/reports/${reportId}`)}
            >
              View Report
            </button>
            <button
              className="btn"
              style={{ marginLeft: "0.5rem" }}
              onClick={() => setStep("form")}
            >
              Validate Another
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section>
      <h2>Validate a Cursor Plugin</h2>
      <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
        Upload a .zip archive of your plugin to run the full suite of
        deterministic validation checks covering manifest, skills, agents,
        hooks, MCP servers, path existence, symlinks, and OAuth configuration.
      </p>

      <div className="card">
        <UploadForm onValidated={handleValidated} />
      </div>

      <div className="card">
        <h3 style={{ marginBottom: "0.5rem" }}>What gets checked</h3>
        <ul style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
          <li>• Manifest (plugin.json) schema and name pattern</li>
          <li>• Skill frontmatter (name matches folder, valid YAML, description)</li>
          <li>• Agent definitions</li>
          <li>• Hooks (script path existence)</li>
          <li>• MCP servers (variable declarations, OAuth scopes)</li>
          <li>• All referenced component paths exist</li>
          <li>• Symlinked plugin components (issue #35)</li>
        </ul>
      </div>
    </section>
  );
}

export type { ValidateResponse };