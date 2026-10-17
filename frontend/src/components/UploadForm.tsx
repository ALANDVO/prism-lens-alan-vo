import { useState, useRef, type DragEvent, type ChangeEvent } from "react";
import { getClient } from "../api/client";
import { ApiError } from "../api/client";
import type { ValidateResponse } from "../types";

interface UploadFormProps {
  onValidated: (response: ValidateResponse) => void;
}

export function UploadForm({ onValidated }: UploadFormProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    if (!file.name.endsWith(".zip")) {
      setError("Please select a .zip archive");
      return;
    }
    if (file.size > 50_000_000) {
      setError("Archive exceeds 50 MB limit");
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const client = getClient();
      const reportId = await client.validatePlugin(file);
      onValidated({ report_id: reportId });
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`Upload failed (${e.status}): ${e.message}`);
      } else {
        setError("Upload failed — please try again");
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="upload-form">
      <div
        className={`upload-area ${isDragging ? "dragover" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
      >
        <input
          type="file"
          ref={fileInputRef}
          accept=".zip"
          onChange={handleChange}
          disabled={isUploading}
        />
        {isUploading ? (
          <p className="loading">Validating plugin…</p>
        ) : (
          <>
            <p>Drag & drop a .zip plugin archive here, or click to browse</p>
            <p style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
              Supported format: .zip
            </p>
          </>
        )}
      </div>
      {error && <div className="error-state">{error}</div>}
    </div>
  );
}
