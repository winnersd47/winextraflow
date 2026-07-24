"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [referral, setReferral] = useState("");
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreeData, setAgreeData] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.register(email, username, password, referral);
      router.push("/login");
    } catch (err: any) {
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-4 flex justify-center gap-1">
          <button onClick={() => setLocale("ru")} className={`rounded px-3 py-1 text-xs font-bold transition ${locale === "ru" ? "bg-brand-500 text-white" : "bg-gray-700 text-gray-400"}`}>RUS</button>
          <button onClick={() => setLocale("en")} className={`rounded px-3 py-1 text-xs font-bold transition ${locale === "en" ? "bg-brand-500 text-white" : "bg-gray-700 text-gray-400"}`}>ENG</button>
        </div>

        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-brand-500">WinExtraFlow</h1>
          <p className="mt-2 text-gray-400">{t("auth.createAccount")}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl bg-surface-card p-8">
          {error && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
          <div>
            <label className="mb-1 block text-sm text-gray-400">{t("auth.email")}</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="w-full rounded-lg border border-gray-700 bg-surface px-4 py-2.5 text-white outline-none focus:border-brand-500" />
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-400">{t("auth.username")}</label>
            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required className="w-full rounded-lg border border-gray-700 bg-surface px-4 py-2.5 text-white outline-none focus:border-brand-500" />
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-400">{t("auth.password")}</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} className="w-full rounded-lg border border-gray-700 bg-surface px-4 py-2.5 text-white outline-none focus:border-brand-500" />
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-400">{t("auth.referralCodeOptional")}</label>
            <input type="text" value={referral} onChange={(e) => setReferral(e.target.value)} className="w-full rounded-lg border border-gray-700 bg-surface px-4 py-2.5 text-white outline-none focus:border-brand-500" placeholder={t("auth.referralPlaceholder")} />
            <p className="mt-1 text-xs text-text-muted">{locale === "ru" ? "Есть код друга? Введите — оба получите бонусные дни Premium." : "Have a friend's code? Enter it — you both get bonus Premium days."}</p>
          </div>
          <label className="flex items-start gap-2 text-sm text-text-secondary">
            <input type="checkbox" checked={agreeTerms} onChange={e => setAgreeTerms(e.target.checked)} required className="mt-1 rounded" />
            <span>
              {locale === "ru" ? "Я принимаю " : "I accept the "}
              <a href="/terms" target="_blank" className="text-brand-500 hover:underline">{locale === "ru" ? "Условия использования" : "Terms of Service"}</a>
              {locale === "ru" ? " и " : " and "}
              <a href="/refund" target="_blank" className="text-brand-500 hover:underline">{locale === "ru" ? "Политику возврата" : "Refund Policy"}</a>
            </span>
          </label>
          <label className="flex items-start gap-2 text-sm text-text-secondary">
            <input type="checkbox" checked={agreeData} onChange={e => setAgreeData(e.target.checked)} required className="mt-1 rounded" />
            <span>
              {locale === "ru"
                ? "Я даю согласие на обработку персональных данных (email, имя пользователя, реферальный код, данные мессенджеров при подключении) в соответствии с "
                : "I consent to the processing of personal data (email, username, referral code, messenger data when linked) in accordance with the "}
              <a href="/privacy" target="_blank" className="text-brand-500 hover:underline">{locale === "ru" ? "Политикой конфиденциальности" : "Privacy Policy"}</a>
              {locale === "ru" ? " (ФЗ-152)" : " (FZ-152)"}
            </span>
          </label>
          <button type="submit" disabled={loading} className="w-full rounded-lg bg-brand-600 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:opacity-50">
            {loading ? t("auth.registering") : t("auth.register")}
          </button>
          <p className="text-center text-sm text-gray-400">
            {t("auth.haveAccount")}{" "}
            <Link href="/login" className="text-brand-500 hover:underline">{t("auth.signIn")}</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
