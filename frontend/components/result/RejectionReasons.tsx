interface Props { reasons: string[]; }

export default function RejectionReasons({ reasons }: Props) {
  if (!reasons.length) return null;
  return (
    <div>
      <h3>Reasons</h3>
      <ul>
        {reasons.map((reason) => <li key={reason}>{reason}</li>)}
      </ul>
    </div>
  );
}
