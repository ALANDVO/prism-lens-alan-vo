/** Typed API client for the Prism Lens backend. */

import type {
  ExportFormat,
  ReportSummary,
  ValidationReport,
  ValidateResponse,
} from "../types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

class PrismLensClient {
  private baseUrl: string;

  constructor(baseUrl = "/api/v1") {
    this.baseUrl = baseUrl;
  }

  async health(): Promise<{ status: string; version: string }> {
    const resp = await fetch(`${this.baseUrl.replace("/api/v1", "")}/health`);
    if (!resp.ok) throw new ApiError(resp.status, "Health check failed");
    return resp.json();
  }

  async validatePlugin(file: File): Promise<string> {
    const form = new FormData();
    form.append("file", file);

    const resp = await fetch(`${this.baseUrl}/plugins/validate`, {
      method: "POST",
      body: form,
    });

    if (!resp.ok) {
      const detail = await resp.json().catch(() => null);
      throw new ApiError(resp.status, detail?.detail || "Validation failed");
    }

    const data: ValidateResponse = await resp.json();
    return data.report_id;
  }

  async listReports(
    params: {
      limit?: number;
      offset?: number;
      status?: string;
      search?: string;
    } = {},
  ): Promise<ReportSummary[]> {
    const url = new URL(`${this.baseUrl}/reports`, window.location.origin);
    if (params.limit) url.searchParams.set("limit", String(params.limit));
    if (params.offset) url.searchParams.set("offset", String(params.offset));
    if (params.status) url.searchParams.set("status", params.status);
    if (params.search) url.searchParams.set("search", params.search);

    const resp = await fetch(url.toString());
    if (!resp.ok) throw new ApiError(resp.status, "Failed to list reports");
    return resp.json();
  }

  async getReport(reportId: string): Promise<ValidationReport> {
    const resp = await fetch(`${this.baseUrl}/reports/${reportId}`);
    if (!resp.ok) {
      const detail = await resp.json().catch(() => null);
      throw new ApiError(resp.status, detail?.detail || "Report not found");
    }
    return resp.json();
  }

  async exportReport(
    reportId: string,
    format: ExportFormat = "text",
  ): Promise<string> {
    const resp = await fetch(
      `${this.baseUrl}/reports/${reportId}/export?format=${format}`,
    );
    if (!resp.ok) throw new ApiError(resp.status, "Export failed");

    if (format === "json") {
      return await resp.json();
    }
    return await resp.text();
  }

  async requestAdvisory(reportId: string): Promise<ValidationReport> {
    const resp = await fetch(
      `${this.baseUrl}/reports/${reportId}/advisory`,
      { method: "POST" },
    );
    if (!resp.ok) {
      const detail = await resp.json().catch(() => null);
      throw new ApiError(resp.status, detail?.detail || "Advisory failed");
    }
    return resp.json();
  }
}

const client = new PrismLensClient();

export function getClient(): PrismLensClient {
  return client;
}

export default client;