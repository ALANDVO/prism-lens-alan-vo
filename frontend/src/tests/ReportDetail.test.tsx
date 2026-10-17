import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ReportDetail from "../pages/ReportDetail";

const mockGetClient = vi.hoisted(() => ({
  getReport: vi.fn(),
  exportReport: vi.fn(),
  requestAdvisory: vi.fn(),
}));

vi.mock("../api/client", () => ({
  getClient: () => mockGetClient,
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, msg: string) {
      super(msg);
      this.status = status;
    }
  },
}));

const mockReport = {
  report_id: "r_test123",
  plugin_name: "test-plugin",
  plugin_version: "1.0.0",
  plugin_path: null,
  status: "failed" as const,
  started_at: "2025-01-01T00:00:00Z",
  completed_at: "2025-01-01T00:00:01Z",
  checks: [
    {
      check_id: "manifest_name_invalid",
      category: "manifest",
      severity: "error" as const,
      title: "Invalid name",
      message: "Name has invalid characters",
      file_path: ".cursor-plugin/plugin.json",
      line: 1,
    },
    {
      check_id: "skills_dir_missing",
      category: "skills",
      severity: "warning" as const,
      title: "No skills directory",
      message: "Skills directory not found",
      file_path: null,
      line: null,
    },
  ],
  summary: { error: 1, warning: 1, info: 0 },
  llm_advisory: null,
};

describe("ReportDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("displays report details when loaded", async () => {
    mockGetClient.getReport.mockResolvedValue(mockReport);

    render(
      <MemoryRouter initialEntries={["/reports/r_test123"]}>
        <Routes>
          <Route path="/reports/:reportId" element={<ReportDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("test-plugin")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText(/v1.0.0/)).toBeInTheDocument();
    });
    expect(screen.getByText("Invalid name")).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    mockGetClient.getReport.mockResolvedValue(mockReport);

    render(
      <MemoryRouter initialEntries={["/reports/r_test123"]}>
        <Routes>
          <Route path="/reports/:reportId" element={<ReportDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/Loading report/i)).toBeInTheDocument();
  });

  it("shows error when report not found", async () => {
    mockGetClient.getReport.mockRejectedValue(
      new Error("Request failed with status code 404"),
    );

    render(
      <MemoryRouter initialEntries={["/reports/r_missing"]}>
        <Routes>
          <Route path="/reports/:reportId" element={<ReportDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Failed to load report/i)).toBeInTheDocument();
    });
  });
});