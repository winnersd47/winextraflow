"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

export default function VerifyEmailPage() {
  const params = useSearchParams();
  const token = params.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (!token) { setStatus("error"); return; }
    fetch(`/api/v1/auth/verify-email?token=${token}`)
      .then(r => {
        if (r.ok) return r.json();
        throw new Error("Invalid token");
      })
      .then(d => { setStatus("success"); setEmail(d.email || ""); })
      .catch(() => setStatus("error"));
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface">
      <div className="w-full max-w-md rounded-2xl border border-border bg-surface-card p-8 text-center">
        {status === "loading" && (
          <>
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
            <p className="text-text-secondary">Verifying...</p>
          </>
        )}
        {status === "success" && (
          <>
            <div className="mb-4 text-5xl">✅</div>
            <h1 className="mb-2 text-2xl font-bold text-text-primary">Email verified!</h1>
            <p className="mb-6 text-sm text-text-secondary">
              {email} successfully verified.
            </p>
            <Link href="/login" className="inline-block rounded-lg bg-brand-600 px-6 py-3 text-sm font-medium text-white hover:bg-brand-700">
              Go to Login
            </Link>
          </>
        )}
        {status === "error" && (
          <>
            <div className="mb-4 text-5xl">❌</div>
            <h1 className="mb-2 text-2xl font-bold text-text-primary">Verification failed</h1>
            <p className="mb-6 text-sm text-text-secondary">
              Invalid or expired verification link.
            </p>
            <Link href="/login" className="inline-block rounded-lg border border-border px-6 py-3 text-sm text-text-secondary hover:bg-surface-hover">
              Go to Login
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
