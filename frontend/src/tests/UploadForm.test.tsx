import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UploadForm } from "../components/UploadForm";

const mockGetClient = vi.hoisted(() => ({
  validatePlugin: vi.fn(),
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

describe("UploadForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows file selection prompt initially", () => {
    render(<UploadForm onValidated={() => {}} />);

    expect(screen.getByText(/Drag & drop/i)).toBeInTheDocument();
  });

  it("rejects non-zip files", async () => {
    render(<UploadForm onValidated={() => {}} />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["hello"], "plugin.txt", { type: "text/plain" });

    await fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/Please select a .zip archive/i)).toBeInTheDocument();
    });
  });

  it("submits a zip file and calls onValidated", async () => {
    const user = userEvent.setup();
    const onValidated = vi.fn();
    mockGetClient.validatePlugin.mockResolvedValue("r_new_report");

    render(<UploadForm onValidated={onValidated} />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["zip content"], "plugin.zip", { type: "application/zip" });

    await fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(mockGetClient.validatePlugin).toHaveBeenCalledWith(file);
    });
    await waitFor(() => {
      expect(onValidated).toHaveBeenCalledWith({ report_id: "r_new_report" });
    });
  });
});