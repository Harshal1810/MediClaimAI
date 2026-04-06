export interface AdjudicationResult {
  decision: string;
  approved_amount: number;
  rejection_reasons: string[];
  confidence_score: number;
  deductions?: Record<string, number>;
  flags?: string[];
  notes?: string;
  next_steps?: string;
  rejected_items?: string[];
  cashless_approved?: boolean;
  network_discount?: number;
  confidence_action?: string;
  confidence_flags?: string[];
  confidence_breakdown?: Record<string, any>;
}
