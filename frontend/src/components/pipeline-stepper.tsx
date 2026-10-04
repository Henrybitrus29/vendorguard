import { Check } from "lucide-react";
import type { Stage, Status } from "@/lib/types";
import { cn } from "@/lib/utils";

const STEPS: { key: Stage; label: string }[] = [
  { key: "uploaded", label: "Uploaded" },
  { key: "classified", label: "Classified" },
  { key: "audited", label: "Audited" },
  { key: "decided", label: "Decision" },
];

/** `stage` is the LAST COMPLETED step. While status is Processing, the next step is shown as in progress. */
export function PipelineStepper({ stage, status }: { stage: Stage; status: Status }) {
  const done = STEPS.findIndex((s) => s.key === stage);
  const processing = status === "Processing";
  return (
    <ol className="flex items-center" aria-label="Processing progress">
      {STEPS.map((step, i) => {
        const complete = i <= done;
        const active = processing && i === done + 1;
        return (
          <li key={step.key} className="flex flex-1 items-center last:flex-none">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full border text-xs font-semibold",
                  complete && "border-primary bg-primary text-primary-foreground",
                  active && "animate-pulse border-primary text-primary",
                  !complete && !active && "text-muted-foreground",
                )}
              >
                {complete ? <Check className="h-3.5 w-3.5" aria-hidden /> : i + 1}
              </span>
              <span className={cn("hidden text-xs sm:inline", complete || active ? "font-medium" : "text-muted-foreground")}>
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <span className={cn("mx-2 h-px flex-1", i < done ? "bg-primary" : "bg-border")} aria-hidden />
            )}
          </li>
        );
      })}
    </ol>
  );
}
