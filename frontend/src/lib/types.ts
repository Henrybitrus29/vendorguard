export type Role = "admin" | "vendor";
export type Status = "Processing" | "Approved" | "Human_Review" | "Rejected";
export type Stage = "uploaded" | "classified" | "audited" | "decided";

export interface User {
  id: string;
  email: string;
  role: Role;
}

/** What a vendor is allowed to see. */
export interface VendorSubmission {
  id: string;
  title: string;
  status: Status;
  stage: Stage;
  filename: string;
  created_at: string;
}

export interface AuditHistoryItem {
  task_id: string;
  confidence_score: number;
  reasoning_summary: string;
  executed_at: string;
}

export interface OverrideEntry {
  id: string;
  admin_email: string;
  previous_status: string;
  new_status: string;
  reason: string;
  created_at: string;
}

export interface AlertEntry {
  id: string;
  severity: "high" | "medium" | "test";
  status: "sent" | "failed" | "suppressed";
  created_at: string;
}

export interface AdminSubmission extends VendorSubmission {
  vendor_id: string;
  content_type: string;
  file_url: string;
  ai_decision: "APPROVED" | "HUMAN_REVIEW" | "REJECTED" | null;
  ai_confidence: number | null;
  flags: string[];
  checks: Record<string, boolean>;
  extracted_data: {
    vendor_name?: string | null;
    tax_id_value?: string | null;
    reasoning?: string;
    document_type?: string | null;
    extraction?: { method: "digital" | "ocr" | "none"; ocr_pages: number };
  };
  audit_history: AuditHistoryItem[];
  overrides?: OverrideEntry[];
  alerts?: AlertEntry[];
}

export interface Metrics {
  total: number;
  processing: number;
  pending_review: number;
  by_status: Record<string, number>;
  auto_approved_pct: number | null;
  automation_rate_pct: number | null;
  security_flagged: number;
  avg_confidence_pct: number | null;
  ai_agreement_pct: number | null;
  overrides_total: number;
  alerts_configured: boolean;
}
