"use client";

import { use, useEffect, useState } from "react";
import { getClaimDecision } from "@/lib/api";
import DecisionBadge from "@/components/result/DecisionBadge";
import RejectionReasons from "@/components/result/RejectionReasons";
import DeductionBreakdown from "@/components/result/DeductionBreakdown";

interface Props {
  params: Promise<{ claimId: string }>;
}

export default function ResultPage({ params }: Props) {
  const { claimId } = use(params);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<any>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await getClaimDecision(claimId);
        if (cancelled) return;
        if (!res.found) {
          setDecision(null);
          return;
        }
        setDecision(res.decision);
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || "Failed to load decision");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [claimId]);

  return (
    <main className="grid" style={{ gap: 14 }}>
      <div className="hero">
        <h2>Claim Result</h2>
        <p className="muted">Claim ID: <strong style={{ color: "rgba(255,255,255,0.9)" }}>{claimId}</strong></p>
      </div>

      {loading ? <div className="card">Loading decision…</div> : null}
      {error ? <div className="alert">{error}</div> : null}

      {!loading && !error && !decision ? (
        <p>No decision found yet. Run adjudication from the submit page.</p>
      ) : null}

      {decision ? (
        <div className="grid two">
          <div className="card">
            <h3>Decision</h3>
            <DecisionBadge decision={decision.decision} />
            <div style={{ marginTop: 10, display: "flex", gap: 10, flexWrap: "wrap" }}>
              <span className="pill">Approved Amount: <strong>₹{decision.approved_amount}</strong></span>
              {decision.cashless_approved ? <span className="pill good">Cashless Approved</span> : null}
              {decision.use_llm === false ? <span className="pill">Mode: Rule-based</span> : null}
              {decision.use_llm ? <span className="pill">Mode: LLM-assisted</span> : null}
            </div>

            {decision.decision === "MANUAL_REVIEW" && decision.recommended_decision ? (
              <p className="help" style={{ marginTop: 10 }}>
                <strong>Recommended (deterministic):</strong> {decision.recommended_decision} • ₹{Number(decision.recommended_approved_amount || 0).toFixed(2)}
              </p>
            ) : null}

            {decision.notes ? <p className="help" style={{ marginTop: 10 }}><strong>Notes:</strong> {decision.notes}</p> : null}

            {decision.llm_final_review ? (
              <div style={{ marginTop: 12 }} className="card">
                <h3>LLM Cross-check (Advisory)</h3>
                {decision.llm_final_review.error ? (
                  <p className="muted" style={{ marginTop: 6 }}>LLM cross-check failed: {decision.llm_final_review.error}</p>
                ) : (
                  <>
                    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 6 }}>
                      <span className={`pill ${decision.llm_final_review.agrees_with_deterministic ? "good" : "warn"}`}>
                        {decision.llm_final_review.agrees_with_deterministic ? "Matches deterministic" : "Differs from deterministic"}
                      </span>
                      <span className="pill">LLM: {decision.llm_final_review.recommended_decision}</span>
                      <span className="pill">LLM Amount: ₹{Number(decision.llm_final_review.recommended_approved_amount || 0).toFixed(2)}</span>
                    </div>
                    {decision.llm_final_review.rationale ? (
                      <p className="help" style={{ marginTop: 8 }}>
                        <strong>Rationale:</strong> {decision.llm_final_review.rationale}
                      </p>
                    ) : null}
                    {decision.llm_final_review.disagreements?.length ? (
                      <div style={{ marginTop: 8 }}>
                        <div style={{ fontWeight: 700, marginBottom: 6 }}>Disagreements</div>
                        <ul className="muted" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.6 }}>
                          {decision.llm_final_review.disagreements.map((x: string) => <li key={x}>{x}</li>)}
                        </ul>
                      </div>
                    ) : null}
                    {decision.llm_final_review.warnings?.length ? (
                      <div style={{ marginTop: 8 }}>
                        <div style={{ fontWeight: 700, marginBottom: 6 }}>Warnings</div>
                        <ul className="muted" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.6 }}>
                          {decision.llm_final_review.warnings.map((x: string) => <li key={x}>{x}</li>)}
                        </ul>
                      </div>
                    ) : null}
                    <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>
                      Deterministic rules remain the source of truth; this is only a cross-check.
                    </p>
                  </>
                )}
              </div>
            ) : null}

            {decision.flags?.length ? (
              <div style={{ marginTop: 12 }}>
                <h3>Flags</h3>
                <ul className="muted" style={{ margin: "8px 0 0", paddingLeft: 18, lineHeight: 1.6 }}>
                  {decision.flags.map((x: string) => <li key={x}>{x}</li>)}
                </ul>
              </div>
            ) : null}
          </div>

          <div className="grid" style={{ gap: 12 }}>
            <div className="card">
              <h3>Breakdown</h3>
              <DeductionBreakdown deductions={decision.deductions} />
              <RejectionReasons reasons={decision.rejection_reasons || []} />
              {decision.rejected_items?.length ? (
                <div style={{ marginTop: 10 }}>
                  <h3>Rejected Items</h3>
                  <ul className="muted" style={{ margin: "8px 0 0", paddingLeft: 18, lineHeight: 1.6 }}>
                    {decision.rejected_items.map((x: string) => <li key={x}>{x}</li>)}
                  </ul>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
