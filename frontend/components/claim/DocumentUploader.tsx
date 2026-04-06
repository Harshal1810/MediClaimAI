"use client";

import { useState } from "react";
import { uploadDocument } from "@/lib/api";

interface Props {
  claimId: string;
  onUploaded?: (info: { document_id: string; filename: string; document_type?: string }) => void;
}

type DocTypeOption = "auto" | "prescription" | "bill" | "pharmacy_bill" | "report";

interface PendingFile {
  id: string;
  file: File;
  docType: DocTypeOption;
  status: "pending" | "uploaded" | "failed";
  message?: string;
}

export default function DocumentUploader({ claimId, onUploaded }: Props) {
  const [pending, setPending] = useState<PendingFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addFiles(files: FileList | null) {
    if (!files?.length) return;
    const next: PendingFile[] = Array.from(files).map((f) => ({
      id: crypto.randomUUID(),
      file: f,
      docType: "auto",
      status: "pending",
    }));
    setPending((prev) => [...prev, ...next]);
  }

  async function handleUpload() {
    setError(null);
    setLoading(true);
    try {
      if (!pending.length) throw new Error("Please add at least one document.");
      for (const item of pending) {
        if (item.status === "uploaded") continue;
        try {
          const type = item.docType === "auto" ? undefined : item.docType;
          const res = await uploadDocument(claimId, item.file, type);
          setPending((prev) => prev.map((p) => (p.id === item.id ? { ...p, status: "uploaded", message: "Uploaded" } : p)));
          onUploaded?.({ document_id: res.document_id, filename: res.filename, document_type: type });
        } catch (e: any) {
          setPending((prev) => prev.map((p) => (p.id === item.id ? { ...p, status: "failed", message: e?.message || "Upload failed" } : p)));
        }
      }
    } catch (e: any) {
      setError(e?.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <h3>Upload Documents</h3>
      <p className="help">Add one or more documents. If you’re unsure, keep type as Auto-detect.</p>

      <div className="field" style={{ marginTop: 10 }}>
        <label>Add documents</label>
        <input type="file" multiple accept="image/*,application/pdf,.docx" onChange={(e) => addFiles(e.target.files)} />
      </div>

      {pending.length ? (
        <div style={{ marginTop: 10, display: "grid", gap: 10 }}>
          {pending.map((p) => (
            <div key={p.id} className="card" style={{ padding: 12, background: "var(--card-2)" }}>
              <div style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
                <div>
                  <div style={{ fontWeight: 700 }}>{p.file.name}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{Math.round(p.file.size / 1024)} KB • {p.status}</div>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  <select
                    value={p.docType}
                    onChange={(e) => setPending((prev) => prev.map((x) => (x.id === p.id ? { ...x, docType: e.target.value as DocTypeOption } : x)))}
                    disabled={p.status === "uploaded"}
                  >
                    <option value="auto">Auto-detect</option>
                    <option value="prescription">Prescription</option>
                    <option value="bill">Hospital Bill</option>
                    <option value="pharmacy_bill">Pharmacy Bill</option>
                    <option value="report">Lab Report</option>
                  </select>
                  <button
                    className="btn"
                    type="button"
                    disabled={loading}
                    onClick={() => setPending((prev) => prev.filter((x) => x.id !== p.id))}
                  >
                    Remove
                  </button>
                </div>
              </div>
              {p.message ? <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>{p.message}</div> : null}
            </div>
          ))}
        </div>
      ) : null}

      {error ? <div className="alert" style={{ marginTop: 10 }}>{error}</div> : null}

      <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <button className="btn" type="button" disabled={loading} onClick={handleUpload}>
          {loading ? "Uploading..." : "Upload"}
        </button>
        <span className="muted" style={{ fontSize: 12 }}>Claim: {claimId}</span>
      </div>
    </div>
  );
}
