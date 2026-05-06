"use client";

import { useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { t, locale, setLocale } = useI18n();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (res.ok) setSent(true);
      else setError("Request failed");
    } catch { setError("Network error"); }
    finally { setLoading(false); }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-4 flex justify-center gap-1">
          <button onClick={() => setLocale("ru")} className={`rounded px-2 py-1 text-xs font-bold ${locale === "ru" ? "bg-brand-500 text-white" : "bg-surface-hover text-text-muted"}`}>RUS</button>
          <button onClick={() => setLocale("en")} className={`rounded px-2 py-1 text-xs font-bold ${locale === "en" ? "bg-brand-500 text-white" : "bg-surface-hover text-text-muted"}`}>ENG</button>
        </div>
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-brand-500">WinExtraFlow</h1>
          <p className="mt-2 text-text-secondary">{t("auth.forgotPassword")}</p>
        </div>

        {sent ? (
          <div className="rounded-xl bg-surface-card p-8 text-center">
            <p className="text-2xl mb-3">✉️</p>
            <p className="text-text-primary font-semibold">{t("auth.resetSent")}</p>
            <p className="mt-2 text-sm text-text-secondary">{t("auth.resetSentHint")}</p>
            <Link href="/login" className="mt-4 inline-block text-brand-500 hover:underline">{t("auth.signIn")}</Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 rounded-xl bg-surface-card p-8">
            {error && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
            <div>
              <label className="mb-1 block text-sm text-text-secondary">{t("auth.email")}</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500" />
            </div>
            <button type="submit" disabled={loading} className="w-full rounded-lg bg-brand-600 py-2.5 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
              {loading ? "..." : t("auth.sendResetLink")}
            </button>
            <p className="text-center text-sm text-text-secondary">
              <Link href="/login" className="text-brand-500 hover:underline">{t("auth.backToLogin")}</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
