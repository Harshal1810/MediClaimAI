interface Props { decision: string; }

function variant(decision: string) {
  const d = (decision || "").toUpperCase();
  if (d === "APPROVED") return "good";
  if (d === "PARTIAL") return "warn";
  if (d === "MANUAL_REVIEW") return "warn";
  return "bad";
}

export default function DecisionBadge({ decision }: Props) {
  const v = variant(decision);
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
      <span className={`pill ${v}`}>Decision: <strong>{decision}</strong></span>
    </div>
  );
}
