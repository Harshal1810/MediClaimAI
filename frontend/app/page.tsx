import Link from "next/link";

export default function HomePage() {
  return (
    <main className="grid" style={{ gap: 16 }}>
      <section className="hero">
        <h2>AI-Assisted OPD Claims Adjudication</h2>
        <p>
          Upload a prescription + bill, optionally use LLM-assisted extraction, and get a deterministic adjudication decision
          with confidence breakdown and audit-friendly metadata.
        </p>
        <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link className="btn primary" href="/submit-claim">Start a New Claim</Link>
        </div>
      </section>

      <section className="grid two">
        <div className="card">
          <h3>What you submit</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            Prescription and bill are required for the MVP pipeline. Optional: reports/pharmacy bills (supported via classification).
          </p>
          <ul className="muted" style={{ margin: "10px 0 0", paddingLeft: 18, lineHeight: 1.6 }}>
            <li>Prescription: doctor reg, diagnosis, tests/medicines</li>
            <li>Bill: category amounts, totals, provider name</li>
            <li>Policy rules: limits, exclusions, timeline, copay, discounts</li>
          </ul>
        </div>
        <div className="card">
          <h3>How decisions are made</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            LLMs can help read documents, but the final approval/rejection/payout is always computed by deterministic code.
          </p>
          <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
            <span className="pill good">Deterministic rule engine</span>
            <span className="pill">Optional LLM-assisted extraction</span>
            <span className="pill warn">Fallbacks if LLM fails</span>
          </div>
        </div>
      </section>
    </main>
  );
}
