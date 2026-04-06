interface Props { value: number; }

export default function ConfidenceMeter({ value }: Props) {
  const pct = Math.max(0, Math.min(100, Math.round((value || 0) * 100)));
  return (
    <div className="card" style={{ padding: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <div style={{ fontWeight: 700 }}>Confidence</div>
        <span className="pill">{pct}%</span>
      </div>
      <div className="progress" style={{ marginTop: 10 }}>
        <div style={{ width: `${pct}%` }} />
      </div>
      <p className="help" style={{ marginTop: 8 }}>Computed from OCR, extraction, consistency, rules, and medical alignment signals.</p>
    </div>
  );
}
