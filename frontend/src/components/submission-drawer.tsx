"use client";

import { AlertTriangle, BellRing, CheckCircle2, ExternalLink, ScanText, XCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AdminSubmission } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { ConfidenceBar, STATUS_LABEL, StatusBadge } from "./status";
import { Badge, Button, Card, Drawer, Label, Skeleton, Textarea } from "./ui";

const CHECK_LABELS: Record<string, string> = {
  tax_id_verified_in_text: "Tax ID found in the document text",
  liability_or_sla_terms: "Liability, indemnity or SLA terms present",
  corporate_vendor: "Corporate vendor entity",
  model_assessment_passed: "AI assessment passed",
};

function flagLabel(flag: string): string {
  if (flag.startsWith("injection_pattern:")) return "Text that looks like instructions to an AI reviewer";
  switch (flag) {
    case "model_flagged_injection":
      return "AI reviewer reported a manipulation attempt";
    case "tax_id_not_found_in_text":
      return "Reported Tax ID does not appear in the document";
    case "empty_text":
      return "No readable text was extracted";
    case "classification_error":
    case "evaluation_error":
    case "processing_error":
      return "Automated processing failed";
    default:
      return flag;
  }
}

const OVERRIDE_OPTIONS = [
  { status: "Approved", label: "Approve", variant: "success" },
  { status: "Human_Review", label: "Flag for review", variant: "warning" },
  { status: "Rejected", label: "Reject", variant: "danger" },
] as const;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

export function SubmissionDrawer({
  submissionId,
  onClose,
  onChanged,
}: {
  submissionId: string | null;
  onClose: () => void;
  onChanged: (s: AdminSubmission) => void;
}) {
  const [detail, setDetail] = useState<AdminSubmission | null>(null);
  const [loadError, setLoadError] = useState("");
  const [choice, setChoice] = useState<string>("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    setDetail(null);
    setLoadError("");
    setChoice("");
    setReason("");
    setFormError("");
    if (!submissionId) return;
    let cancelled = false;
    api<AdminSubmission>(`/submissions/${encodeURIComponent(submissionId)}`)
      .then((d) => !cancelled && setDetail(d))
      .catch((e) => !cancelled && setLoadError(e.message));
    return () => {
      cancelled = true;
    };
  }, [submissionId]);

  const submit = async () => {
    if (!detail || !choice) return;
    setSaving(true);
    setFormError("");
    try {
      const updated = await api<AdminSubmission>(`/submissions/${encodeURIComponent(detail.id)}/override`, {
        method: "PATCH",
        body: JSON.stringify({ new_status: choice, reason: reason.trim() }),
      });
      setDetail(updated);
      onChanged(updated);
      setChoice("");
      setReason("");
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Could not save the override.");
    } finally {
      setSaving(false);
    }
  };

  const canSubmit = !!choice && reason.trim().length >= 10 && !saving;

  return (
    <Drawer open={!!submissionId} onClose={onClose} title={detail?.title ?? "Submission"}>
      {loadError && <p role="alert" className="text-sm text-danger">{loadError}</p>}
      {!detail && !loadError && (
        <div className="space-y-4">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {detail && (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <StatusBadge status={detail.status} />
            <span className="font-mono text-xs text-muted-foreground">{detail.id.slice(0, 8)}</span>
            <span className="text-xs text-muted-foreground">· {formatDate(detail.created_at)}</span>
          </div>

          <Section title="Document">
            {detail.extracted_data.extraction?.method === "ocr" && (
              <Badge tone="info" className="mb-2">
                <ScanText className="h-3 w-3" aria-hidden />
                Read with OCR ({detail.extracted_data.extraction.ocr_pages}{" "}
                {detail.extracted_data.extraction.ocr_pages === 1 ? "page" : "pages"}) · stricter approval threshold
              </Badge>
            )}
            {detail.extracted_data.extraction?.method === "none" && (
              <Badge tone="warning" className="mb-2">No text could be read from this file</Badge>
            )}
            <Card className="overflow-hidden">
              <iframe
                src={detail.file_url}
                title={`Preview of ${detail.filename}`}
                className="h-72 w-full bg-white"
              />
            </Card>
            <a
              href={detail.file_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              Open in a new tab <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          </Section>

          <Section title="AI assessment">
            <Card className="space-y-3 p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">AI decision</span>
                <span className="font-medium">
                  {detail.ai_decision ? STATUS_LABEL[detail.ai_decision === "APPROVED" ? "Approved" : detail.ai_decision === "REJECTED" ? "Rejected" : "Human_Review"] : "Pending"}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Confidence</span>
                <ConfidenceBar value={detail.ai_confidence} />
              </div>
              {(detail.extracted_data.vendor_name || detail.extracted_data.tax_id_value) && (
                <div className="grid grid-cols-2 gap-3 border-t pt-3 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground">Vendor</p>
                    <p className="font-medium">{detail.extracted_data.vendor_name ?? "n/a"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Tax ID</p>
                    <p className="font-mono">{detail.extracted_data.tax_id_value ?? "n/a"}</p>
                  </div>
                </div>
              )}
              {detail.extracted_data.reasoning && (
                <p className="border-t pt-3 text-sm leading-relaxed">{detail.extracted_data.reasoning}</p>
              )}
            </Card>
          </Section>

          {Object.keys(detail.checks).length > 0 && (
            <Section title="Automated checks">
              <ul className="space-y-1.5">
                {Object.entries(detail.checks).map(([key, ok]) => (
                  <li key={key} className="flex items-center gap-2 text-sm">
                    {ok ? (
                      <CheckCircle2 className="h-4 w-4 text-success" aria-label="Passed" />
                    ) : (
                      <XCircle className="h-4 w-4 text-danger" aria-label="Failed" />
                    )}
                    {CHECK_LABELS[key] ?? key}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {detail.flags.length > 0 && (
            <Section title="Security flags">
              <div className="space-y-2">
                {detail.flags.map((f) => (
                  <div key={f} className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/10 p-2.5 text-sm">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
                    <span>{flagLabel(f)}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {detail.alerts && detail.alerts.length > 0 && (
            <Section title="SOC alerts">
              <ul className="space-y-1.5">
                {detail.alerts.map((a) => (
                  <li key={a.id} className="flex items-center gap-2 text-sm">
                    <BellRing className="h-4 w-4 text-muted-foreground" aria-hidden />
                    <Badge tone={a.severity === "high" ? "danger" : "warning"}>{a.severity}</Badge>
                    <span>
                      {a.status === "sent" ? "Alert sent" : a.status === "failed" ? "Alert delivery failed" : "Alert suppressed (hourly cap)"}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">{formatDate(a.created_at)}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {detail.audit_history.length > 0 && (
            <Section title="Audit runs">
              <ol className="space-y-2">
                {detail.audit_history.map((h) => (
                  <li key={h.task_id} className="rounded-md border p-2.5 text-sm">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>{formatDate(h.executed_at)}</span>
                      <span className="tabular-nums">{Math.round(h.confidence_score <= 1 ? h.confidence_score * 100 : h.confidence_score)}% confidence</span>
                    </div>
                    <p className="mt-1">{h.reasoning_summary}</p>
                  </li>
                ))}
              </ol>
            </Section>
          )}

          <Section title="Manual override">
            {detail.status === "Processing" ? (
              <p className="text-sm text-muted-foreground">Available once processing finishes.</p>
            ) : (
              <Card className="space-y-3 p-4">
                <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="New status">
                  {OVERRIDE_OPTIONS.filter((o) => o.status !== detail.status).map((o) => (
                    <Button
                      key={o.status}
                      size="sm"
                      role="radio"
                      aria-checked={choice === o.status}
                      variant={choice === o.status ? o.variant : "secondary"}
                      onClick={() => setChoice(o.status)}
                    >
                      {o.label}
                    </Button>
                  ))}
                </div>
                <div>
                  <Label htmlFor="reason">Reason (required, saved in the audit log)</Label>
                  <Textarea
                    id="reason"
                    rows={3}
                    maxLength={500}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Explain why you are changing this decision (10+ characters)"
                  />
                </div>
                {formError && <p role="alert" className="text-sm text-danger">{formError}</p>}
                <Button onClick={submit} disabled={!canSubmit} className="w-full">
                  {saving ? "Saving…" : "Save override"}
                </Button>
              </Card>
            )}
          </Section>

          {detail.overrides && detail.overrides.length > 0 && (
            <Section title="Override history">
              <ol className="space-y-2">
                {detail.overrides.map((o) => (
                  <li key={o.id} className="rounded-md border p-2.5 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge>{STATUS_LABEL[o.previous_status] ?? o.previous_status}</Badge>
                      <span aria-hidden>→</span>
                      <Badge tone="info">{STATUS_LABEL[o.new_status] ?? o.new_status}</Badge>
                    </div>
                    <p className="mt-1.5">{o.reason}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {o.admin_email} · {formatDate(o.created_at)}
                    </p>
                  </li>
                ))}
              </ol>
            </Section>
          )}
        </>
      )}
    </Drawer>
  );
}
