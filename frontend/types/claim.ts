import { LLMConfig } from "./provider";

export interface ClaimFormData {
  session_id: string;
  member_id: string;
  member_name: string;
  treatment_date: string;
  submission_date: string;
  claim_amount: number;
  hospital_name?: string;
  cashless_requested: boolean;
  use_llm: boolean;
  llm_config?: LLMConfig;
}
