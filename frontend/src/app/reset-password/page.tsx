"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>}>
      <ResetPasswordInner />
    </Suspense>
  );
}

function ResetPasswordInner() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { t } = useI18n();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setError(t("auth.passwordsMismatch")); return; }
    if (password.length < 6) { setError(t("auth.passwordTooShort")); return; }
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      if (res.ok) setDone(true);
      else { const d = await res.json(); setError(d.detail || "Failed"); }
    } catch { setError("Network error"); }
    finally { setLoading(false); }
  };

  if (!token) return <div className="flex min-h-screen items-center justify-center text-text-secondary">Invalid reset link</div>;

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-brand-500">WinExtraFlow</h1>
          <p className="mt-2 text-text-secondary">{t("auth.newPassword")}</p>
        </div>

        {done ? (
          <div className="rounded-xl bg-surface-card p-8 text-center">
            <p className="text-2xl mb-3">✅</p>
            <p className="text-text-primary font-semibold">{t("auth.passwordChanged")}</p>
            <Link href="/login" className="mt-4 inline-block rounded-lg bg-brand-600 px-6 py-2.5 text-white hover:bg-brand-700">{t("auth.signIn")}</Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 rounded-xl bg-surface-card p-8">
            {error && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
            <div>
              <label className="mb-1 block text-sm text-text-secondary">{t("auth.newPassword")}</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-text-secondary">{t("auth.confirmPassword")}</label>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500" />
            </div>
            <button type="submit" disabled={loading} className="w-full rounded-lg bg-brand-600 py-2.5 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
              {loading ? "..." : t("auth.resetPassword")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
