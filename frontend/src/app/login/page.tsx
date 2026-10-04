"use client";

import { ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import React, { useState } from "react";
import { Button, Card, Input, Label } from "@/components/ui";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const DEMO_ADMIN = { email: "admin@demo.vendorguard.dev", password: "DemoAdmin#2026" };
const DEMO_VENDOR = { email: "vendor@demo.vendorguard.dev", password: "DemoVendor#2026" };

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const go = async (path: string, creds: { email: string; password: string }) => {
    setBusy(true);
    setError("");
    try {
      const user = await api<User>(path, { method: "POST", body: JSON.stringify(creds) });
      router.replace(user.role === "admin" ? "/admin" : "/vendor");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setPassword("");
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    go(mode === "login" ? "/auth/login" : "/auth/register", { email, password });
  };

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2">
          <ShieldCheck className="h-7 w-7 text-primary" aria-hidden />
          <span className="text-2xl font-semibold tracking-tight">VendorGuard</span>
        </div>

        <Card className="p-6">
          <h1 className="text-lg font-semibold">{mode === "login" ? "Sign in" : "Create a vendor account"}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === "login" ? "Welcome back." : "Upload documents for compliance review."}
          </p>

          {error && (
            <p role="alert" className="mt-4 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
              {error}
            </p>
          )}

          <form onSubmit={onSubmit} className="mt-4 space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                required
                minLength={mode === "register" ? 10 : 1}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {mode === "register" && <p className="mt-1 text-xs text-muted-foreground">At least 10 characters.</p>}
            </div>
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <button
            type="button"
            className="mt-4 w-full text-center text-sm text-primary hover:underline"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
          >
            {mode === "login" ? "New vendor? Create an account" : "Already have an account? Sign in"}
          </button>
        </Card>

        {DEMO && (
          <Card className="mt-4 border-dashed p-4">
            <p className="text-sm font-medium">Portfolio demo</p>
            <p className="mt-1 text-xs text-muted-foreground">
              This site only holds fabricated sample data. Explore either role with one click.
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Button variant="secondary" size="sm" disabled={busy} onClick={() => go("/auth/login", DEMO_ADMIN)}>
                Demo admin
              </Button>
              <Button variant="secondary" size="sm" disabled={busy} onClick={() => go("/auth/login", DEMO_VENDOR)}>
                Demo vendor
              </Button>
            </div>
          </Card>
        )}
      </div>
    </main>
  );
}
