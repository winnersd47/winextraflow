"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Language toggle */}
        <div className="mb-4 flex justify-center gap-1">
          <button onClick={() => setLocale("ru")} className={`rounded px-3 py-1 text-xs font-bold transition ${locale === "ru" ? "bg-brand-500 text-white" : "bg-gray-700 text-gray-400"}`}>RUS</button>
          <button onClick={() => setLocale("en")} className={`rounded px-3 py-1 text-xs font-bold transition ${locale === "en" ? "bg-brand-500 text-white" : "bg-gray-700 text-gray-400"}`}>ENG</button>
        </div>

        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-brand-500">WinExtraFlow</h1>
          <p className="mt-2 text-gray-400">{t("auth.signInTitle")}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl bg-surface-card p-8">
          {error && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
          <div>
            <label className="mb-1 block text-sm text-gray-400">{t("auth.email")}</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="w-full rounded-lg border border-gray-700 bg-surface px-4 py-2.5 text-white outline-none focus:border-brand-500" placeholder="you@example.com" />
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-400">{t("auth.password")}</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="w-full rounded-lg border border-gray-700 bg-surface px-4 py-2.5 text-white outline-none focus:border-brand-500" />
          </div>
          <button type="submit" disabled={loading} className="w-full rounded-lg bg-brand-600 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:opacity-50">
            {loading ? t("auth.signingIn") : t("auth.signIn")}
          </button>
          <p className="text-center text-sm text-gray-400">
            <Link href="/forgot-password" className="text-brand-500 hover:underline">{t("auth.forgotPassword")}</Link>
          </p>
          <p className="text-center text-sm text-gray-400">
            {t("auth.noAccount")}{" "}
            <Link href="/register" className="text-brand-500 hover:underline">{t("auth.register")}</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
