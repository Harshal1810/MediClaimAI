interface Props { deductions?: Record<string, number>; }

export default function DeductionBreakdown({ deductions }: Props) {
  if (!deductions) return null;
  return (
    <div>
      <h3>Deductions</h3>
      <ul>
        {Object.entries(deductions).map(([key, value]) => <li key={key}>{key}: {value}</li>)}
      </ul>
    </div>
  );
}
