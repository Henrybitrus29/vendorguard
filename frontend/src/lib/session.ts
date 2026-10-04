"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "./api";
import type { Role, User } from "./types";

/** Loads the signed-in user. Redirects to /login, or to the right home page if the role is wrong. */
export function useSession(required: Role) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<User>("/auth/me")
      .then((u) => {
        if (cancelled) return;
        if (u.role !== required) router.replace(u.role === "admin" ? "/admin" : "/vendor");
        else setUser(u);
      })
      .catch(() => !cancelled && router.replace("/login"));
    return () => {
      cancelled = true;
    };
  }, [required, router]);

  return user;
}
