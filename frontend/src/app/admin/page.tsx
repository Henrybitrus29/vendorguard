"use client";

import { BellRing, Download, Inbox, RefreshCw, Search } from "lucide-react";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ConfidenceBar, STATUS_LABEL, StatusBadge } from "@/components/status";
import { SubmissionDrawer } from "@/components/submission-drawer";
import { Badge, Button, Card, Input, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { AdminSubmission, Metrics } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

const FILTERS = ["All", "Human_Review", "Approved", "Rejected", "Processing"] as const;

function StatCard({
  label,
  value,
  hint,
  loading,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  loading: boolean;
  tone?: "warning" | "danger";
}) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-20" />
      ) : (
        <p className={cn("mt-1 text-3xl font-semibold tabular-nums tracking-tight", tone === "warning" && "text-warning", tone === "danger" && "text-danger")}>
          {value}
        </p>
      )}
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
    </Card>
  );
}

const pct = (n: number | null) => (n === null ? "n/a" : `${n}%`);

export default function AdminPage() {
  const user = useSession("admin");
  const [items, setItems] = useState<AdminSubmission[] | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All");
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [alertMsg, setAlertMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const sendTestAlert = async () => {
    setTesting(true);
    setAlertMsg(null);
    try {
      await api("/admin/alerts/test", { method: "POST" });
      setAlertMsg({ ok: true, text: "Test alert sent. Check your Slack or Teams channel." });
    } catch (e) {
      setAlertMsg({ ok: false, text: e instanceof Error ? e.message : "Could not send the test alert." });
    } finally {
      setTesting(false);
    }
  };

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [list, m] = await Promise.all([api<AdminSubmission[]>("/submissions"), api<Metrics>("/admin/metrics")]);
      setItems(list);
      setMetrics(m);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load data.");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  const anyProcessing = items?.some((s) => s.status === "Processing");
  useEffect(() => {
    if (!anyProcessing) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [anyProcessing, load]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    items?.forEach((s) => (c[s.status] = (c[s.status] ?? 0) + 1));
    return c;
  }, [items]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (items ?? []).filter(
      (s) =>
        (filter === "All" || s.status === filter) &&
        (!q ||
          s.title.toLowerCase().includes(q) ||
          s.id.toLowerCase().includes(q) ||
          (s.extracted_data.vendor_name ?? "").toLowerCase().includes(q)),
    );
  }, [items, filter, query]);

  if (!user) return <div className="min-h-screen" />;
  const loading = items === null;

  return (
    <AppShell user={user}>
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Review queue</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              The AI decides clear cases. You review exceptions and every override is logged.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {metrics?.alerts_configured && (
              <Button variant="secondary" onClick={sendTestAlert} disabled={testing}>
                <BellRing className="h-4 w-4" aria-hidden /> {testing ? "Sending…" : "Send test alert"}
              </Button>
            )}
            <a
              href="/api/admin/audit-log.csv"
              className="inline-flex h-10 items-center gap-2 rounded-md border bg-card px-4 text-sm font-medium hover:bg-muted"
            >
              <Download className="h-4 w-4" aria-hidden /> Audit log (CSV)
            </a>
            <Button variant="secondary" onClick={load} disabled={refreshing}>
              <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} aria-hidden /> Refresh
            </Button>
          </div>
        </div>

        {alertMsg && (
          <p
            role={alertMsg.ok ? "status" : "alert"}
            className={cn(
              "mt-4 rounded-md border p-3 text-sm",
              alertMsg.ok ? "border-success/30 bg-success/10 text-success" : "border-danger/30 bg-danger/10 text-danger",
            )}
          >
            {alertMsg.text}
          </p>
        )}

        {/* Stat cards */}
        <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
          <StatCard label="Pending review" value={String(metrics?.pending_review ?? 0)} hint="Waiting for a person" loading={loading} tone={metrics && metrics.pending_review > 0 ? "warning" : undefined} />
          <StatCard label="Auto-approved" value={pct(metrics?.auto_approved_pct ?? null)} hint="Approved with no human help" loading={loading} />
          <StatCard label="Security flags" value={String(metrics?.security_flagged ?? 0)} hint="Suspicious or unverifiable" loading={loading} tone={metrics && metrics.security_flagged > 0 ? "danger" : undefined} />
          <StatCard label="Avg confidence" value={pct(metrics?.avg_confidence_pct ?? null)} hint="Across all audited files" loading={loading} />
          <StatCard label="AI agreement" value={pct(metrics?.ai_agreement_pct ?? null)} hint={`Auto decisions kept by humans · ${metrics?.overrides_total ?? 0} overrides`} loading={loading} />
        </div>

        {/* Filters */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <div role="tablist" aria-label="Filter by status" className="flex flex-wrap gap-1.5">
            {FILTERS.map((f) => {
              const n = f === "All" ? items?.length ?? 0 : counts[f] ?? 0;
              return (
                <button
                  key={f}
                  role="tab"
                  aria-selected={filter === f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium",
                    filter === f ? "bg-foreground text-background" : "border bg-card text-muted-foreground hover:bg-muted",
                  )}
                >
                  {f === "All" ? "All" : STATUS_LABEL[f]} <span className="tabular-nums opacity-70">{n}</span>
                </button>
              );
            })}
          </div>
          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" aria-hidden />
            <Input
              type="search"
              aria-label="Search submissions"
              placeholder="Search title, ID or vendor"
              className="pl-9"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>

        {error && (
          <p role="alert" className="mt-4 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
            {error}
          </p>
        )}

        {/* Table */}
        <Card className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Submission</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">AI confidence</th>
                <th className="px-4 py-3 font-medium">Flags</th>
                <th className="px-4 py-3 font-medium">Submitted</th>
              </tr>
            </thead>
            <tbody>
              {loading &&
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b last:border-0">
                    <td className="px-4 py-4" colSpan={5}>
                      <Skeleton className="h-5 w-full" />
                    </td>
                  </tr>
                ))}

              {!loading && visible.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-14 text-center text-muted-foreground">
                    <Inbox className="mx-auto mb-2 h-8 w-8" aria-hidden />
                    {items!.length === 0
                      ? "No submissions yet. They appear here as soon as a vendor uploads a document."
                      : "No submissions match this filter."}
                  </td>
                </tr>
              )}

              {visible.map((s) => (
                <tr
                  key={s.id}
                  tabIndex={0}
                  onClick={() => setOpenId(s.id)}
                  onKeyDown={(e) => e.key === "Enter" && setOpenId(s.id)}
                  className="cursor-pointer border-b last:border-0 hover:bg-muted/50"
                >
                  <td className="px-4 py-3">
                    <p className="font-medium">{s.title}</p>
                    <p className="font-mono text-xs text-muted-foreground">
                      {s.id.slice(0, 8)}
                      {s.extracted_data.vendor_name ? ` · ${s.extracted_data.vendor_name}` : ""}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="px-4 py-3">
                    <ConfidenceBar value={s.ai_confidence} />
                  </td>
                  <td className="px-4 py-3">
                    {s.flags.length > 0 ? <Badge tone="warning">{s.flags.length} flagged</Badge> : <span className="text-muted-foreground">None</span>}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{timeAgo(s.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <SubmissionDrawer
        submissionId={openId}
        onClose={() => setOpenId(null)}
        onChanged={(updated) => {
          setItems((prev) => prev?.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)) ?? prev);
          load();
        }}
      />
    </AppShell>
  );
}
