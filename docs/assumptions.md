# Assumptions

- Specific ailment waiting period overrides generic PED waiting period.
- MRI and CT may require pre-auth above a threshold (from `shared/policy/derived_rules.json`).
- Per-claim limit is enforced as a hard cap on the approved payout (partial approval up to the cap) and payout is capped to the filed `claim_amount`.
- Fraud indicators can trigger `MANUAL_REVIEW` (confidence is reduced; decision/payout is not auto-approved).
- Consultation co-pay is applied only on consultation fees (not the entire claim total).
- Hospital name mismatch between claim form and bill is treated as a manual-review signal (does not auto-approve).
- If confidence drops below the configured threshold, the system will return `MANUAL_REVIEW` even if the deterministic engine would otherwise approve.
- Decision codes used by the API: `APPROVED`, `PARTIAL`, `REJECTED`, `MANUAL_REVIEW`.
