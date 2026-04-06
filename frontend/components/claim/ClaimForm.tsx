"use client";

import { useEffect, useState } from "react";
import ProviderSelector from "./ProviderSelector";
import { ClaimFormData } from "@/types/claim";
import { LLMProvider } from "@/types/provider";
import { DEFAULT_OPENAI_MODEL } from "@/lib/constants";

interface Props {
  sessionId: string | null;
  onSubmit: (data: ClaimFormData) => Promise<void>;
}

export default function ClaimForm({ sessionId, onSubmit }: Props) {
  function todayLocalISO() {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  }

  const [memberId, setMemberId] = useState("");
  const [memberName, setMemberName] = useState("");
  const [treatmentDate, setTreatmentDate] = useState("");
  const [submissionDate, setSubmissionDate] = useState("");
  const [claimAmount, setClaimAmount] = useState("");
  const [hospitalName, setHospitalName] = useState("");
  const [cashlessRequested, setCashlessRequested] = useState(false);
  const [useLlm, setUseLlm] = useState(false);
  const [providerConfig, setProviderConfig] = useState({ provider: "openai" as LLMProvider, api_key: "", model: DEFAULT_OPENAI_MODEL });
  const [error, setError] = useState<string | null>(null);

  // Avoid hydration mismatches due to locale/timezone differences.
  // Set default dates only after the component mounts (client-side).
  useEffect(() => {
    setSubmissionDate((prev) => prev || todayLocalISO());
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!sessionId) {
      setError("Initializing session… please wait a moment and try again.");
      return;
    }
    if (!memberId.trim() || !memberName.trim() || !treatmentDate || !claimAmount) {
      setError("Please fill Member ID, Member Name, Treatment date, and Claim amount.");
      return;
    }
    if (useLlm) {
      if (!providerConfig.provider || !providerConfig.api_key || !providerConfig.model) {
        setError("LLM mode requires provider, API key, and model.");
        return;
      }
    }
    await onSubmit({
      session_id: sessionId,
      member_id: memberId,
      member_name: memberName,
      treatment_date: treatmentDate,
      submission_date: submissionDate,
      claim_amount: Number(claimAmount),
      hospital_name: hospitalName || undefined,
      cashless_requested: cashlessRequested,
      use_llm: useLlm,
      llm_config: useLlm ? providerConfig : undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="form">
      <div className="card">
        <h3>Claim Details</h3>
        <div className="row two">
          <div className="field">
            <label>Member ID</label>
            <input value={memberId} onChange={(e) => setMemberId(e.target.value)} placeholder="e.g. EMP001" />
          </div>
          <div className="field">
            <label>Member Name</label>
            <input value={memberName} onChange={(e) => setMemberName(e.target.value)} placeholder="e.g. Rajesh Kumar" />
          </div>
        </div>

        <div className="row two">
          <div className="field">
            <label>Treatment date</label>
            <p className="help">Date of doctor visit / treatment (used to check eligibility and policy timing).</p>
            <input type="date" value={treatmentDate} onChange={(e) => setTreatmentDate(e.target.value)} />
          </div>
          <div className="field">
            <label>Submission date</label>
            <p className="help">Date you’re submitting the claim (used for the 30‑day submission window).</p>
            <input type="date" value={submissionDate} onChange={(e) => setSubmissionDate(e.target.value)} />
          </div>
        </div>

        <div className="row two">
          <div className="field">
            <label>Claim amount (₹)</label>
            <input type="number" value={claimAmount} onChange={(e) => setClaimAmount(e.target.value)} placeholder="e.g. 1500" min={0} />
          </div>
          <div className="field">
            <label>Hospital/Clinic (optional)</label>
            <input value={hospitalName} onChange={(e) => setHospitalName(e.target.value)} placeholder="e.g. Apollo Hospitals" />
          </div>
        </div>

        <div className="row two">
          <div className="toggle">
            <input type="checkbox" checked={cashlessRequested} onChange={(e) => setCashlessRequested(e.target.checked)} />
            <div>
              <div style={{ fontWeight: 700 }}>Cashless request</div>
              <div className="muted" style={{ fontSize: 12 }}>Only applicable for network providers and within instant approval limit.</div>
            </div>
          </div>
          <div className="toggle">
            <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
            <div>
              <div style={{ fontWeight: 700 }}>Use LLM-assisted processing</div>
              <div className="muted" style={{ fontSize: 12 }}>LLM helps read documents; decisions remain deterministic.</div>
            </div>
          </div>
        </div>
      </div>

      {useLlm ? (
        <div className="card">
          <h3>LLM Settings</h3>
          <ProviderSelector provider={providerConfig.provider} api_key={providerConfig.api_key} model={providerConfig.model} onChange={setProviderConfig} />
          <p className="help" style={{ marginTop: 8 }}>API keys stay in the browser session only and are never stored.</p>
        </div>
      ) : null}

      {error ? <div className="alert">{error}</div> : null}

      <button className="btn primary" type="submit">Create Claim</button>
      <p className="help">
        Session: <span className="muted">{sessionId || "Generating…"}</span>
      </p>
    </form>
  );
}
