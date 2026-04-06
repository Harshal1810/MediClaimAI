"use client";

import { useRouter } from "next/navigation";
import ClaimForm from "@/components/claim/ClaimForm";
import DocumentUploader from "@/components/claim/DocumentUploader";
import { useSessionId } from "@/hooks/useSessionId";
import { adjudicateStoredClaim, createClaim, processDocuments } from "@/lib/api";
import { useState } from "react";

export default function SubmitClaimPage() {
  const sessionId = useSessionId();
  const router = useRouter();
  const [claimId, setClaimId] = useState<string | null>(null);
  const [processingConfig, setProcessingConfig] = useState<any>(null);
  const [uploads, setUploads] = useState(0);
  const [processed, setProcessed] = useState<any>(null);
  const [processing, setProcessing] = useState(false);
  const [adjudicating, setAdjudicating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(data: any) {
    setError(null);
    const response = await createClaim(data);
    setClaimId(response.claim_id);
    setProcessingConfig({ use_llm: !!data.use_llm, llm_config: data.use_llm ? data.llm_config : null });
  }

  async function handleAdjudicate() {
    if (!claimId) return;
    setError(null);
    setAdjudicating(true);
    try {
      await adjudicateStoredClaim(claimId, processingConfig);
      router.push(`/result/${claimId}`);
    } catch (e: any) {
      setError(e?.message || "Adjudication failed");
    } finally {
      setAdjudicating(false);
    }
  }

  async function handleProcessDocs() {
    if (!claimId) return;
    setError(null);
    setProcessing(true);
    try {
      const res = await processDocuments(claimId, processingConfig);
      setProcessed(res);
    } catch (e: any) {
      setError(e?.message || "Processing failed");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <main className="grid" style={{ gap: 14 }}>
      <div className="hero">
        <h2>Submit a Claim</h2>
        <p>Step 1: enter claim details. Step 2: upload documents. Step 3: run adjudication and view the decision.</p>
      </div>

      {!claimId ? (
        <ClaimForm sessionId={sessionId} onSubmit={handleSubmit} />
      ) : (
        <div className="grid two">
          <div className="card">
            <h3>Claim Created</h3>
            <div className="pill good">Claim ID: <strong>{claimId}</strong></div>
            <p className="help" style={{ marginTop: 10 }}>
              Upload documents, then click “Process & Preview” to review extracted metadata before running adjudication.
            </p>
            {error ? <div className="alert" style={{ marginTop: 10 }}>{error}</div> : null}
            <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button className="btn" type="button" disabled={uploads < 1 || processing} onClick={handleProcessDocs}>
                {processing ? "Processing..." : "Process & Preview"}
              </button>
              <button className="btn success" type="button" disabled={!processed || adjudicating} onClick={handleAdjudicate}>
                {adjudicating ? "Running..." : "Run Adjudication"}
              </button>
              <div className="muted" style={{ fontSize: 12, alignSelf: "center" }}>
                Uploaded: {uploads}
              </div>
            </div>
            <div style={{ marginTop: 12 }}>
              <div className="progress" aria-label="Upload progress">
                <div style={{ width: `${Math.min(100, uploads * 33)}%` }} />
              </div>
            </div>
            {processed ? (
              <div style={{ marginTop: 14 }} className="card">
                <h3>Extracted Metadata Preview</h3>
                <p className="help">Review the detected document types and extracted fields. If something looks wrong, remove/reupload with a fixed type.</p>
                <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
                  {(processed.documents || []).map((d: any) => (
                    <div key={d.document_id} className="card" style={{ padding: 12, background: "rgba(255,255,255,0.04)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                        <div>
                          <div style={{ fontWeight: 800 }}>{d.filename}</div>
                          <div className="muted" style={{ fontSize: 12 }}>
                            Type: <strong>{d.document_type || "unknown"}</strong>
                          </div>
                        </div>
                        {d.flags?.length ? <span className="pill warn">flags: {d.flags.length}</span> : null}
                      </div>
                      <pre style={{ marginTop: 10, whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 12, color: "rgba(255,255,255,0.86)" }}>
                        {JSON.stringify(d.extracted, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          <DocumentUploader claimId={claimId} onUploaded={() => setUploads((x) => x + 1)} />
        </div>
      )}
    </main>
  );
}
