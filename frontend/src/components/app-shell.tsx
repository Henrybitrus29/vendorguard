"use client";

import { FileUp, LayoutDashboard, LogOut, Moon, ShieldCheck, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { Button } from "./ui";

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <Button
      variant="ghost"
      size="sm"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}

export function AppShell({ user, children }: { user: User; children: React.ReactNode }) {
  const router = useRouter();
  const nav =
    user.role === "admin"
      ? { label: "Review queue", Icon: LayoutDashboard }
      : { label: "My documents", Icon: FileUp };

  const signOut = async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      router.replace("/login");
    }
  };

  return (
    <div className="min-h-screen md:grid md:grid-cols-[220px_1fr]">
      <aside className="hidden border-r bg-card md:flex md:flex-col">
        <div className="flex items-center gap-2 px-5 py-5">
          <ShieldCheck className="h-6 w-6 text-primary" aria-hidden />
          <span className="text-lg font-semibold tracking-tight">VendorGuard</span>
        </div>
        <nav className="px-3">
          <span className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-sm font-medium">
            <nav.Icon className="h-4 w-4" aria-hidden />
            {nav.label}
          </span>
        </nav>
        <p className="mt-auto px-5 py-4 text-xs text-muted-foreground">Built by Chidama Tech Partners</p>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="flex items-center justify-between border-b bg-card px-4 py-3 sm:px-8">
          <div className="flex items-center gap-2 md:hidden">
            <ShieldCheck className="h-5 w-5 text-primary" aria-hidden />
            <span className="font-semibold">VendorGuard</span>
          </div>
          <div className="hidden text-sm text-muted-foreground md:block">
            Signed in as <span className="font-medium text-foreground">{user.email}</span>
            <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs uppercase tracking-wide">{user.role}</span>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={signOut}>
              <LogOut className="h-4 w-4" aria-hidden /> Sign out
            </Button>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-8">{children}</main>
      </div>
    </div>
  );
}
