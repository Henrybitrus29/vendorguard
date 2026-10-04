"use client";

import { CheckCircle2, FileText, Flag, UploadCloud, XCircle } from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { PipelineStepper } from "@/components/pipeline-stepper";
import { StatusBadge } from "@/components/status";
import { Button, Card, Input, Label, Skeleton } from "@/components/ui";
import { api, uploadSubmission } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Status, VendorSubmission } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

const MAX_MB = 10;
const ALLOWED = [".pdf", ".txt", ".png", ".jpg", ".jpeg"];

const OUTCOME: Record<Exclude<Status, "Processing">, { text: string; Icon: typeof Flag; cls: string }> = {
  Approved: { text: "Your document passed the automated compliance checks.", Icon: CheckCircle2, cls: "text-success" },
  Human_Review: { text: "A compliance officer is reviewing this document. You do not need to do anything.", Icon: Flag, cls: "text-warning" },
  Rejected: { text: "This document could not be accepted. Please contact support if you think this is a mistake.", Icon: XCircle, cls: "text-danger" },
};

export default function VendorPage() {
  const user = useSession("vendor");
  const [items, setItems] = useState<VendorSubmission[] | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setItems(await api<VendorSubmission[]>("/submissions"));
    } catch {
      /* the session hook handles auth problems */
    }
  }, []);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  // Poll while anything is still processing, so the stepper updates live.
  const anyProcessing = items?.some((s) => s.status === "Processing");
  useEffect(() => {
    if (!anyProcessing) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [anyProcessing, load]);

  const pick = (f: File | undefined) => {
    setError("");
    if (!f) return;
    const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED.includes(ext)) return setError("Only PDF, PNG, JPEG and plain-text (.txt) files are accepted.");
    if (f.size > MAX_MB * 1024 * 1024) return setError(`File is larger than ${MAX_MB} MB.`);
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, "").slice(0, 120));
  };

  const submit = async () => {
    if (!file) return;
    setError("");
    setProgress(0);
    try {
      await uploadSubmission(title.trim(), file, setProgress);
      setFile(null);
      setTitle("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setProgress(null);
    }
  };

  if (!user) return <div className="min-h-screen" />;
  const uploading = progress !== null;

  return (
    <AppShell user={user}>
      <div className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight">My documents</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Upload a vendor document (SLA, MSA, tax certificate, insurance certificate). You will see the result within moments.
        </p>

        <Card className="mt-6 p-5">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              pick(e.dataTransfer.files[0]);
            }}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Choose a file to upload"
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-10 text-center transition-colors",
              dragging ? "border-primary bg-primary/5" : "hover:bg-muted",
            )}
          >
            {file ? (
              <>
                <FileText className="h-8 w-8 text-primary" aria-hidden />
                <p className="mt-2 text-sm font-medium">{file.name}</p>
                <p className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(0)} KB · click to change</p>
              </>
            ) : (
              <>
                <UploadCloud className="h-8 w-8 text-muted-foreground" aria-hidden />
                <p className="mt-2 text-sm font-medium">Drag a file here, or click to browse</p>
                <p className="text-xs text-muted-foreground">PDF, PNG, JPG or TXT, up to {MAX_MB} MB. Scans are read automatically.</p>
              </>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.txt,.png,.jpg,.jpeg,application/pdf,text/plain,image/png,image/jpeg"
              className="hidden"
              onChange={(e) => pick(e.target.files?.[0])}
            />
          </div>

          {file && (
            <div className="mt-4 space-y-3">
              <div>
                <Label htmlFor="title">Document title</Label>
                <Input id="title" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} disabled={uploading} />
              </div>
              {uploading && (
                <div aria-live="polite">
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">Uploading… {progress}%</p>
                </div>
              )}
              <Button onClick={submit} disabled={uploading || title.trim().length < 3} className="w-full">
                {uploading ? "Uploading…" : "Submit for review"}
              </Button>
            </div>
          )}
          {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
        </Card>

        <h2 className="mb-3 mt-8 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Submissions</h2>
        {items === null ? (
          <div className="space-y-3">
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </div>
        ) : items.length === 0 ? (
          <Card className="px-4 py-10 text-center text-sm text-muted-foreground">
            Nothing here yet. Your uploaded documents and their results will appear here.
          </Card>
        ) : (
          <div className="space-y-3">
            {items.map((s) => {
              const outcome = s.status === "Processing" ? null : OUTCOME[s.status];
              return (
                <Card key={s.id} className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="truncate font-semibold">{s.title}</h3>
                      <p className="text-xs text-muted-foreground">
                        {s.filename} · {timeAgo(s.created_at)}
                      </p>
                    </div>
                    <StatusBadge status={s.status} />
                  </div>
                  <div className="mt-4">
                    <PipelineStepper stage={s.stage} status={s.status} />
                  </div>
                  {outcome && (
                    <p className={cn("mt-4 flex items-start gap-2 text-sm", outcome.cls)}>
                      <outcome.Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                      <span className="text-foreground">{outcome.text}</span>
                    </p>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
