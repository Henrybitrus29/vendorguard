"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    api<User>("/auth/me")
      .then((u) => router.replace(u.role === "admin" ? "/admin" : "/vendor"))
      .catch(() => router.replace("/login"));
  }, [router]);
  return <div className="min-h-screen" />;
}
