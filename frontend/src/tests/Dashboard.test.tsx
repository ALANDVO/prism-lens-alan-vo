import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "../pages/Dashboard";

// Mock the API client
const mockGetClient = vi.hoisted(() => ({
  listReports: vi.fn(),
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

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows empty state when no reports", async () => {
    mockGetClient.listReports.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/No reports yet/i)).toBeInTheDocument();
    });
  });

  it("renders reports when data is loaded", async () => {
    const mockReports = [
      {
        report_id: "r_test1",
        plugin_name: "test-plugin",
        plugin_version: "1.0.0",
        status: "passed" as const,
        started_at: "2025-01-01T00:00:00Z",
        error_count: 0,
        warning_count: 2,
        info_count: 1,
      },
    ];
    mockGetClient.listReports.mockResolvedValue(mockReports);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("test-plugin")).toBeInTheDocument();
    });
    expect(screen.getByText("v1.0.0")).toBeInTheDocument();
  });

  it("shows error state on API failure", async () => {
    mockGetClient.listReports.mockRejectedValue(
      new Error("Network error"),
    );

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Failed to load reports/i)).toBeInTheDocument();
    });
  });
});