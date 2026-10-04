import { CheckCircle2, Clock, Flag, Loader2, XCircle } from "lucide-react";
import type { Status } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge } from "./ui";

const META: Record<Status, { label: string; tone: "success" | "warning" | "danger" | "info"; Icon: typeof Clock }> = {
  Processing: { label: "Processing", tone: "info", Icon: Loader2 },
  Approved: { label: "Approved", tone: "success", Icon: CheckCircle2 },
  Human_Review: { label: "Needs review", tone: "warning", Icon: Flag },
  Rejected: { label: "Rejected", tone: "danger", Icon: XCircle },
};

export const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  Object.entries(META).map(([k, v]) => [k, v.label]),
);

export function StatusBadge({ status }: { status: Status }) {
  const { label, tone, Icon } = META[status] ?? { label: status, tone: "info" as const, Icon: Clock };
  return (
    <Badge tone={tone}>
      <Icon className={cn("h-3 w-3", status === "Processing" && "animate-spin")} aria-hidden />
      {label}
    </Badge>
  );
}

export function ConfidenceBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-muted-foreground">Not scored</span>;
  const pct = Math.round(value <= 1 ? value * 100 : value);
  const tone = pct >= 85 ? "bg-success" : pct >= 60 ? "bg-warning" : "bg-danger";
  return (
    <div className="flex items-center gap-2" title={`AI confidence ${pct}%`}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div className={cn("h-full", tone)} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-9 text-xs tabular-nums text-muted-foreground">{pct}%</span>
    </div>
  );
}
