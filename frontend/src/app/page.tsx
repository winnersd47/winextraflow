"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";

const FEATURES = [
  { icon: "🤖", titleKey: "landing.feature1Title", descKey: "landing.feature1Desc" },
  { icon: "📡", titleKey: "landing.feature2Title", descKey: "landing.feature2Desc" },
  { icon: "🧪", titleKey: "landing.feature3Title", descKey: "landing.feature3Desc" },
  { icon: "📋", titleKey: "landing.feature4Title", descKey: "landing.feature4Desc" },
  { icon: "🛒", titleKey: "landing.feature5Title", descKey: "landing.feature5Desc" },
  { icon: "⚡", titleKey: "landing.feature6Title", descKey: "landing.feature6Desc" },
];

const STEPS = [
  { num: "01", titleKey: "landing.step1Title", descKey: "landing.step1Desc" },
  { num: "02", titleKey: "landing.step2Title", descKey: "landing.step2Desc" },
  { num: "03", titleKey: "landing.step3Title", descKey: "landing.step3Desc" },
];

export default function LandingPage() {
  const { t, locale, setLocale } = useI18n();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="min-h-screen bg-surface">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 lg:px-16">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold text-brand-500">WinExtra</span>
          <span className="text-2xl font-bold text-text-primary">Flow</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            <button onClick={() => setLocale("ru")} className={`rounded px-2 py-1 text-xs font-bold ${locale === "ru" ? "bg-brand-500 text-white" : "bg-surface-hover text-text-muted"}`}>RUS</button>
            <button onClick={() => setLocale("en")} className={`rounded px-2 py-1 text-xs font-bold ${locale === "en" ? "bg-brand-500 text-white" : "bg-surface-hover text-text-muted"}`}>ENG</button>
          </div>
          <button onClick={toggleTheme} className="rounded p-1.5 text-text-secondary hover:bg-surface-hover">
            {theme === "dark" ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            )}
          </button>
          <Link href="/login" className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-primary transition hover:bg-surface-hover">{t("landing.ctaLogin")}</Link>
          <Link href="/register" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700">{t("landing.ctaStart")}</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="px-6 py-20 text-center lg:px-16 lg:py-32">
        <div className="mx-auto max-w-3xl">
          <h1 className="bg-gradient-to-r from-brand-500 to-emerald-300 bg-clip-text text-4xl font-extrabold text-transparent sm:text-5xl lg:text-6xl">
            {t("landing.heroTitle")}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary">
            {t("landing.heroSubtitle")}
          </p>
          <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link href="/register" className="rounded-xl bg-brand-600 px-8 py-3.5 text-lg font-semibold text-white transition hover:bg-brand-700 hover:shadow-lg hover:shadow-brand-500/25">
              {t("landing.ctaStart")}
            </Link>
            <Link href="/login" className="rounded-xl border border-border px-8 py-3.5 text-lg font-semibold text-text-primary transition hover:bg-surface-hover">
              {t("landing.ctaLogin")}
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-16 lg:px-16">
        <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">{t("landing.featuresTitle")}</h2>
        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.titleKey} className="rounded-xl border border-border bg-surface-card p-6 transition hover:border-brand-500/50 hover:shadow-lg">
              <span className="text-3xl">{f.icon}</span>
              <h3 className="mt-4 text-lg font-semibold text-text-primary">{t(f.titleKey)}</h3>
              <p className="mt-2 text-sm text-text-secondary">{t(f.descKey)}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="px-6 py-16 lg:px-16">
        <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">{t("landing.howTitle")}</h2>
        <div className="mx-auto flex max-w-4xl flex-col gap-8 lg:flex-row lg:gap-12">
          {STEPS.map((s) => (
            <div key={s.num} className="flex-1 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-brand-500/10 text-2xl font-bold text-brand-500">{s.num}</div>
              <h3 className="mt-4 text-xl font-semibold text-text-primary">{t(s.titleKey)}</h3>
              <p className="mt-2 text-sm text-text-secondary">{t(s.descKey)}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="px-6 py-16 lg:px-16">
        <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">{t("landing.pricingTitle")}</h2>
        <div className="mx-auto grid max-w-3xl grid-cols-1 gap-6 sm:grid-cols-2">
          {/* Free */}
          <div className="rounded-xl border border-border bg-surface-card p-8">
            <h3 className="text-xl font-bold text-text-primary">{t("landing.free")}</h3>
            <p className="mt-2 text-4xl font-extrabold text-text-primary">{t("landing.freePrice")}</p>
            <ul className="mt-6 space-y-3 text-sm text-text-secondary">
              {["freeFeature1", "freeFeature2", "freeFeature3", "freeFeature4"].map((k) => (
                <li key={k} className="flex items-center gap-2"><span className="text-brand-500">✓</span>{t(`landing.${k}`)}</li>
              ))}
            </ul>
            <Link href="/register" className="mt-8 block rounded-lg border border-border py-3 text-center font-medium text-text-primary transition hover:bg-surface-hover">{t("landing.ctaStart")}</Link>
          </div>
          {/* Premium */}
          <div className="rounded-xl border-2 border-brand-500 bg-surface-card p-8 shadow-lg shadow-brand-500/10">
            <div className="flex items-center gap-2">
              <h3 className="text-xl font-bold text-text-primary">{t("landing.premiumLabel")}</h3>
              <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">PRO</span>
            </div>
            <p className="mt-2 text-4xl font-extrabold text-brand-500">{t("landing.premiumPrice")}</p>
            <p className="text-xs text-text-muted">{t("landing.premiumPriceNote")}</p>
            <ul className="mt-6 space-y-3 text-sm text-text-secondary">
              {["premiumFeature1", "premiumFeature2", "premiumFeature3", "premiumFeature4", "premiumFeature5"].map((k) => (
                <li key={k} className="flex items-center gap-2"><span className="text-brand-500">✓</span>{t(`landing.${k}`)}</li>
              ))}
            </ul>
            <Link href="/register" className="mt-8 block rounded-lg bg-brand-600 py-3 text-center font-medium text-white transition hover:bg-brand-700">{t("landing.ctaStart")}</Link>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="px-6 py-16 lg:px-16">
        <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">{t("landing.statsTitle")}</h2>
        <div className="mx-auto grid max-w-3xl grid-cols-2 gap-6 sm:grid-cols-4">
          {[
            { value: "50K+", label: t("landing.statSignals") },
            { value: "200+", label: t("landing.statProviders") },
            { value: "10K+", label: t("landing.statUsers") },
            { value: "99.9%", label: t("landing.statUptime") },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-3xl font-extrabold text-brand-500">{s.value}</p>
              <p className="mt-1 text-sm text-text-secondary">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border px-6 py-8 lg:px-16">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="flex items-center gap-2">
            <span className="font-bold text-brand-500">WinExtra</span>
            <span className="font-bold text-text-primary">Flow</span>
          </div>
          <div className="flex gap-6 text-sm text-text-secondary">
            <Link href="/api-docs" className="hover:text-text-primary">{t("landing.footerApi")}</Link>
            <Link href="/login" className="hover:text-text-primary">{t("landing.ctaLogin")}</Link>
            <Link href="/register" className="hover:text-text-primary">{t("landing.ctaStart")}</Link>
          </div>
          <p className="text-xs text-text-muted">&copy; 2026 WinExtraFlow. {t("landing.footerRights")}</p>
        </div>
      </footer>
    </div>
  );
}
