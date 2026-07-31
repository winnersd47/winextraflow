"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";
import { IconWave, IconCompass, IconAnchor, IconHelm, IconShip, IconBolt } from "@/components/sea-icons";

const FEATURES = [
  { Icon: IconWave, titleKey: "landing.feature1Title", descKey: "landing.feature1Desc" },
  { Icon: IconCompass, titleKey: "landing.feature2Title", descKey: "landing.feature2Desc" },
  { Icon: IconAnchor, titleKey: "landing.feature3Title", descKey: "landing.feature3Desc" },
  { Icon: IconHelm, titleKey: "landing.feature4Title", descKey: "landing.feature4Desc" },
  { Icon: IconShip, titleKey: "landing.feature5Title", descKey: "landing.feature5Desc" },
  { Icon: IconBolt, titleKey: "landing.feature6Title", descKey: "landing.feature6Desc" },
];

const STEPS = [
  { num: "01", titleKey: "landing.step1Title", descKey: "landing.step1Desc" },
  { num: "02", titleKey: "landing.step2Title", descKey: "landing.step2Desc" },
  { num: "03", titleKey: "landing.step3Title", descKey: "landing.step3Desc" },
];

function WaveDivider({ flip = false }: { flip?: boolean }) {
  return (
    <div className={`w-full overflow-hidden leading-none ${flip ? "rotate-180" : ""}`}>
      <svg viewBox="0 0 1440 60" preserveAspectRatio="none" className="w-full h-[40px] lg:h-[60px]">
        <path fill="var(--color-wave-1)" fillOpacity="0.08" d="M0,30 C240,50 480,10 720,30 C960,50 1200,10 1440,30 L1440,60 L0,60 Z"/>
        <path fill="var(--color-wave-2)" fillOpacity="0.05" d="M0,35 C360,15 720,55 1080,35 C1260,25 1350,45 1440,35 L1440,60 L0,60 Z"/>
      </svg>
    </div>
  );
}

/* Animated counter */
function AnimatedNumber({ target, suffix = "" }: { target: number; suffix?: string }) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target <= 0) return;
    const duration = 1500;
    const steps = 40;
    const increment = target / steps;
    let current = 0;
    const interval = setInterval(() => {
      current += increment;
      if (current >= target) { setValue(target); clearInterval(interval); }
      else setValue(Math.floor(current));
    }, duration / steps);
    return () => clearInterval(interval);
  }, [target]);
  return <>{value.toLocaleString()}{suffix}</>;
}

/* Signal confidence color */
function confidenceColor(c: number) {
  if (c >= 0.8) return "text-green-400";
  if (c >= 0.6) return "text-yellow-400";
  return "text-red-400";
}

function confidenceBg(c: number) {
  if (c >= 0.8) return "bg-green-500/20 border-green-500/30";
  if (c >= 0.6) return "bg-yellow-500/20 border-yellow-500/30";
  return "bg-red-500/20 border-red-500/30";
}

export default function LandingPage() {
  const { t, locale, setLocale } = useI18n();
  const { theme, toggleTheme } = useTheme();
  const isRu = locale === "ru";

  const [stats, setStats] = useState<any>(null);
  const [sample, setSample] = useState<any>(null);
  const [promoCopied, setPromoCopied] = useState(false);

  useEffect(() => {
    fetch("/api/v1/public/stats").then(r => r.ok ? r.json() : null).then(setStats).catch(() => {});
    fetch("/api/v1/public/sample-signal").then(r => r.ok ? r.json() : null).then(setSample).catch(() => {});
  }, []);

  const copyPromo = () => {
    navigator.clipboard.writeText("AIGROWTH14");
    setPromoCopied(true);
    setTimeout(() => setPromoCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-surface">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 lg:px-16">
        <div className="flex items-center gap-2">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" className="text-brand-500">
            <path d="M2 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
            <path d="M2 17c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity=".4"/>
            <path d="M2 7c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity=".2"/>
          </svg>
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
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            )}
          </button>
          <Link href="/login" className="hidden sm:inline-block rounded-lg border border-border px-4 py-2 text-sm font-medium text-text-primary transition hover:bg-surface-hover">{t("landing.ctaLogin")}</Link>
          <Link href="/register" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700">{t("landing.ctaStart")}</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="hero-ocean relative px-6 py-24 text-center lg:px-16 lg:py-36">
        <div className="relative z-10 mx-auto max-w-3xl">
          <h1 className="bg-gradient-to-r from-brand-500 to-cyan-300 bg-clip-text text-4xl font-extrabold text-transparent sm:text-5xl lg:text-6xl drop-shadow-lg">
            {t("landing.heroTitle")}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-gray-300 drop-shadow">
            {t("landing.heroSubtitle")}
          </p>

          {/* Live stat ticker in hero */}
          {stats && (
            <div className="mt-8 flex flex-wrap justify-center gap-6 text-sm">
              <div className="rounded-lg bg-white/10 backdrop-blur px-4 py-2">
                <span className="font-bold text-brand-400"><AnimatedNumber target={stats.signals} /></span>
                <span className="ml-1.5 text-gray-300">{isRu ? "сигналов" : "signals"}</span>
              </div>
              <div className="rounded-lg bg-white/10 backdrop-blur px-4 py-2">
                <span className="font-bold text-brand-400"><AnimatedNumber target={stats.strategies} /></span>
                <span className="ml-1.5 text-gray-300">{isRu ? "стратегий" : "strategies"}</span>
              </div>
              <div className="rounded-lg bg-white/10 backdrop-blur px-4 py-2">
                <span className="font-bold text-brand-400"><AnimatedNumber target={stats.evo_components} /></span>
                <span className="ml-1.5 text-gray-300">{isRu ? "AI компонентов" : "AI components"}</span>
              </div>
              <div className="rounded-lg bg-white/10 backdrop-blur px-4 py-2">
                <span className="font-bold text-brand-400">{stats.exchanges}</span>
                <span className="ml-1.5 text-gray-300">{isRu ? "бирж" : "exchanges"}</span>
              </div>
            </div>
          )}

          <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link href="/register" className="rounded-xl bg-brand-600 px-8 py-3.5 text-lg font-semibold text-white transition hover:bg-brand-700 hover:shadow-lg hover:shadow-brand-500/25">
              {t("landing.ctaStart")}
            </Link>
            <Link href="/login" className="rounded-xl border border-white/30 bg-white/10 backdrop-blur px-8 py-3.5 text-lg font-semibold text-white transition hover:bg-white/20">
              {t("landing.ctaLogin")}
            </Link>
          </div>
        </div>
      </section>

      {/* Exchange logos — trust bar */}
      <section className="border-y border-border/30 bg-surface-card/50 px-6 py-6 lg:px-16">
        <p className="mb-4 text-center text-xs font-medium uppercase tracking-widest text-text-muted">
          {isRu ? "Подключено к ведущим биржам" : "Connected to leading exchanges"}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-6 opacity-60">
          {["Binance", "Bybit", "OKX", "Kraken", "MT5", "Tinkoff", "IBKR", "Exante", "Demo"].map(ex => (
            <span key={ex} className="text-sm font-bold text-text-muted tracking-wide">{ex}</span>
          ))}
        </div>
      </section>

      <WaveDivider />

      {/* Sample Signal — Social Proof */}
      {sample && (
        <section className="px-6 py-16 lg:px-16">
          <h2 className="mb-8 text-center text-3xl font-bold text-text-primary">{t("landing.sampleTitle")}</h2>
          <div className="mx-auto max-w-lg">
            <div className={`rounded-2xl border ${confidenceBg(sample.ai_confidence)} p-6`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className={`rounded-lg px-3 py-1.5 text-sm font-bold ${sample.action === "BUY" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                    {sample.action}
                  </span>
                  <span className="text-xl font-bold text-text-primary">{sample.ticker}</span>
                </div>
                <div className="text-right">
                  <div className="text-xs text-text-muted">{t("landing.sampleConfidence")}</div>
                  <div className={`text-2xl font-bold ${confidenceColor(sample.ai_confidence)}`}>
                    {(sample.ai_confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="rounded-lg bg-surface/50 p-3 text-center">
                  <div className="text-xs text-text-muted">{t("landing.sampleEntry")}</div>
                  <div className="text-sm font-bold text-text-primary">{sample.entry_price}</div>
                </div>
                <div className="rounded-lg bg-surface/50 p-3 text-center">
                  <div className="text-xs text-text-muted">{t("landing.sampleTP")}</div>
                  <div className="text-sm font-bold text-green-400">{sample.take_profit || "—"}</div>
                </div>
                <div className="rounded-lg bg-surface/50 p-3 text-center">
                  <div className="text-xs text-text-muted">{t("landing.sampleSL")}</div>
                  <div className="text-sm font-bold text-red-400">{sample.stop_loss || "—"}</div>
                </div>
              </div>

              {sample.ai_reasoning && (
                <div className="rounded-lg bg-surface/50 p-3">
                  <div className="text-xs text-text-muted mb-1">{t("landing.sampleReasoning")}</div>
                  <p className="text-sm text-text-secondary">{sample.ai_reasoning}</p>
                </div>
              )}

              <div className="mt-3 text-xs text-text-muted text-right">
                {t("landing.sampleProvider")}: {sample.provider_name}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Trust Badges */}
      <section className="px-6 py-8 lg:px-16">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-center gap-6">
          {[
            { icon: "🔒", text: isRu ? "HTTPS + Fernet (AES-128-CBC)" : "HTTPS + Fernet (AES-128-CBC)" },
            { icon: "🛡️", text: isRu ? "ФЗ-152 соответствие" : "Data Protection Compliant" },
            { icon: "📜", text: isRu ? "Публичная оферта" : "Terms of Service" },
            { icon: "🔐", text: isRu ? "Ключи бирж зашифрованы" : "Encrypted API Keys" },
            { icon: "⚠️", text: isRu ? "Не инвестрекомендация" : "Not Investment Advice" },
          ].map(b => (
            <div key={b.text} className="flex items-center gap-2 rounded-lg bg-surface-card border border-border px-3 py-2">
              <span>{b.icon}</span>
              <span className="text-xs text-text-muted">{b.text}</span>
            </div>
          ))}
        </div>
      </section>

      <WaveDivider flip />

      {/* Features — with trading floor photo bg */}
      <section className="bg-trading-floor px-6 py-16 lg:px-16">
        <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">{t("landing.featuresTitle")}</h2>
        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.titleKey} className="glass gradient-border rounded-xl p-6 stat-glow">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-brand-500/10 text-brand-500">
                <f.Icon size={24} />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-text-primary">{t(f.titleKey)}</h3>
              <p className="mt-2 text-sm text-text-secondary">{t(f.descKey)}</p>
            </div>
          ))}
        </div>
      </section>

      <WaveDivider />

      {/* How it works — with analytics bg */}
      <section className="bg-analytics particles px-6 py-16 lg:px-16">
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

      <WaveDivider flip />

      {/* Promo Code Banner */}
      <section className="px-6 py-12 lg:px-16">
        <div className="mx-auto max-w-2xl rounded-2xl border-2 border-brand-500/30 mesh-gradient glass p-8 text-center">
          <h2 className="text-2xl font-bold text-text-primary">{t("landing.promoTitle")}</h2>
          <p className="mt-2 text-sm text-text-secondary">{t("landing.promoDesc")}</p>
          <div className="mt-4 flex items-center justify-center gap-3">
            <code className="rounded-xl bg-surface border border-border px-6 py-3 text-xl font-bold tracking-widest text-brand-500">
              AIGROWTH14
            </code>
            <button onClick={copyPromo} className="rounded-lg bg-brand-600 px-4 py-3 text-sm font-medium text-white hover:bg-brand-700 transition">
              {promoCopied ? t("landing.promoCopied") : t("landing.promoCopy")}
            </button>
          </div>
          <p className="mt-3 text-xs text-text-muted">14 {isRu ? "дней Premium бесплатно" : "days Premium free"}</p>
        </div>
      </section>

      <WaveDivider />

      {/* Pricing — 3 tiers */}
      <section className="px-6 py-16 lg:px-16">
        <h2 className="mb-12 text-center text-3xl font-bold text-text-primary">{t("landing.pricingTitle")}</h2>
        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 sm:grid-cols-3">
          {/* Free */}
          <div className="rounded-xl border border-border bg-surface-card p-8 flex flex-col">
            <h3 className="text-xl font-bold text-text-primary">{isRu ? "Free" : "Free"}</h3>
            <p className="mt-2 text-4xl font-extrabold text-text-primary">$0</p>
            <p className="text-xs text-text-muted">{isRu ? "навсегда" : "forever"}</p>
            <ul className="mt-6 flex-1 space-y-3 text-sm text-text-secondary">
              {[
                isRu ? "10 последних сигналов" : "Last 10 signals",
                isRu ? "1 бэктест в день" : "1 backtest per day",
                isRu ? "Лидерборд провайдеров" : "Provider leaderboard",
                isRu ? "Реферальная программа" : "Referral program",
              ].map(f => <li key={f} className="flex items-center gap-2"><span className="text-text-muted">~</span>{f}</li>)}
            </ul>
            <Link href="/register" className="mt-8 block rounded-lg border border-border py-3 text-center font-medium text-text-primary transition hover:bg-surface-hover">
              {isRu ? "Начать бесплатно" : "Get Started"}
            </Link>
          </div>

          {/* Pro */}
          <div className="rounded-xl border border-border bg-surface-card p-8 flex flex-col">
            <div className="flex items-center gap-2">
              <h3 className="text-xl font-bold text-text-primary">Pro</h3>
              <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-bold text-blue-400">NEW</span>
            </div>
            <p className="mt-2 text-4xl font-extrabold text-text-primary">
              {isRu ? "1 490 ₽" : "$16"}<span className="text-base font-normal text-text-muted">/{isRu ? "мес" : "mo"}</span>
            </p>
            <p className="text-xs text-text-muted">{isRu ? "~$16/мес" : "~1,490 RUB/mo"}</p>
            <ul className="mt-6 flex-1 space-y-3 text-sm text-text-secondary">
              {[
                isRu ? "Все сигналы без лимита" : "Unlimited signals",
                isRu ? "Бэктест без ограничений" : "Unlimited backtesting",
                isRu ? "AI чат + Скринер" : "AI Chat + Screener",
                isRu ? "Торговый журнал" : "Trade Journal",
                isRu ? "Ценовые оповещения" : "Price Alerts",
              ].map(f => <li key={f} className="flex items-center gap-2"><span className="text-blue-400">~</span>{f}</li>)}
            </ul>
            <Link href="/register" className="mt-8 block rounded-lg border border-blue-500 py-3 text-center font-medium text-blue-400 transition hover:bg-blue-500/10">
              {isRu ? "Попробовать Pro" : "Try Pro"}
            </Link>
          </div>

          {/* Premium */}
          <div className="rounded-xl border-2 border-brand-500 bg-surface-card p-8 shadow-lg shadow-brand-500/10 flex flex-col">
            <div className="flex items-center gap-2">
              <h3 className="text-xl font-bold text-text-primary">Premium</h3>
              <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">TOP</span>
            </div>
            <p className="mt-2 text-4xl font-extrabold text-brand-500">
              {isRu ? "2 990 ₽" : "$33"}<span className="text-base font-normal text-text-muted">/{isRu ? "мес" : "mo"}</span>
            </p>
            <p className="text-xs text-text-muted">{isRu ? "~$33/мес · Год: 23 900 ₽ (−33%)" : "~2,990 RUB/mo · Yearly: $264 (−33%)"}</p>
            <ul className="mt-6 flex-1 space-y-3 text-sm text-text-secondary">
              {[
                isRu ? "Всё из Pro +" : "Everything in Pro +",
                isRu ? "Копитрейдинг" : "Copy Trading",
                isRu ? "Исполнение на 9 биржах" : "Execution on 9 exchanges",
                isRu ? "Маркетплейс стратегий" : "Strategy Marketplace",
                isRu ? "VIP Telegram канал" : "VIP Telegram channel",
                isRu ? "PDF отчёты" : "PDF Reports",
              ].map(f => <li key={f} className="flex items-center gap-2"><span className="text-brand-500">~</span>{f}</li>)}
            </ul>
            <Link href="/register" className="mt-8 block rounded-lg bg-brand-600 py-3 text-center font-medium text-white transition hover:bg-brand-700">
              {isRu ? "Подключить Premium" : "Get Premium"}
            </Link>
          </div>
        </div>
      </section>

      <WaveDivider flip />

      {/* Live Stats — with city skyline bg */}
      <section className="bg-city-skyline px-6 py-16 lg:px-16">
        <h2 className="mb-2 text-center text-3xl font-bold text-text-primary">{t("landing.statsTitle")}</h2>
        <p className="mb-12 text-center text-sm text-text-muted">{t("landing.liveStats")}</p>
        <div className="mx-auto grid max-w-4xl grid-cols-2 gap-6 sm:grid-cols-4">
          {[
            { value: stats?.signals || 0, suffix: "+", label: t("landing.statSignals") },
            { value: stats?.strategies || 0, suffix: "+", label: t("landing.statStrategies") },
            { value: stats?.evo_components || 0, suffix: "", label: t("landing.statComponents") },
            { value: stats?.exchanges || 9, suffix: "", label: t("landing.statExchanges") },
          ].map((s) => (
            <div key={s.label} className="glass gradient-border rounded-xl p-4 text-center stat-glow">
              <p className="text-3xl font-extrabold text-brand-500">
                {stats ? <AnimatedNumber target={s.value} suffix={s.suffix} /> : "..."}
              </p>
              <p className="mt-1 text-sm text-text-secondary">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ COMPARISON TABLE ═══ */}
      <section className="bg-crypto-dark px-6 py-16 lg:px-16">
        <h2 className="mb-8 text-center text-3xl font-bold text-text-primary">
          {isRu ? "Сравнение с конкурентами" : "How We Compare"}
        </h2>
        <div className="mx-auto max-w-4xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-text-muted">
                <th className="p-3">{isRu ? "Функция" : "Feature"}</th>
                <th className="p-3 text-center">WinExtraFlow</th>
                <th className="p-3 text-center">TradingView</th>
                <th className="p-3 text-center">Token Metrics</th>
                <th className="p-3 text-center">3Commas</th>
              </tr>
            </thead>
            <tbody className="text-text-secondary">
              {[
                { f: isRu ? "AI-оценка сигналов" : "AI Signal Rating", us: true, tv: false, tm: true, tc: false },
                { f: "MOEX Live", us: true, tv: true, tm: false, tc: false },
                { f: isRu ? "Крипто" : "Crypto", us: true, tv: true, tm: true, tc: true },
                { f: "Forex", us: true, tv: true, tm: false, tc: false },
                { f: isRu ? "Копитрейдинг" : "Copy Trading", us: true, tv: false, tm: false, tc: true },
                { f: isRu ? "Бэктестинг" : "Backtesting", us: true, tv: true, tm: false, tc: false },
                { f: isRu ? "Торговый журнал" : "Trade Journal", us: true, tv: false, tm: false, tc: false },
                { f: isRu ? "Оплата в рублях" : "RUB Payments", us: true, tv: false, tm: false, tc: false },
                { f: isRu ? "Бесплатный тариф" : "Free Tier", us: true, tv: true, tm: false, tc: false },
              ].map(row => (
                <tr key={row.f} className="border-b border-border/30">
                  <td className="p-3 font-medium text-text-primary">{row.f}</td>
                  <td className="p-3 text-center text-lg">{row.us ? "✅" : "—"}</td>
                  <td className="p-3 text-center text-lg">{row.tv ? "✅" : "—"}</td>
                  <td className="p-3 text-center text-lg">{row.tm ? "✅" : "—"}</td>
                  <td className="p-3 text-center text-lg">{row.tc ? "✅" : "—"}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-brand-500/30">
                <td className="p-3 font-bold text-text-primary">{isRu ? "Цена/мес" : "Price/mo"}</td>
                <td className="p-3 text-center font-bold text-brand-500">$0–33</td>
                <td className="p-3 text-center text-text-muted">$13–200</td>
                <td className="p-3 text-center text-text-muted">$29–99</td>
                <td className="p-3 text-center text-text-muted">$29–99</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <WaveDivider />

      {/* ═══ TESTIMONIALS ═══ */}
      <section className="px-6 py-16 lg:px-16">
        <h2 className="mb-8 text-center text-3xl font-bold text-text-primary">
          {isRu ? "Что говорят трейдеры" : "What Traders Say"}
        </h2>
        <div className="mx-auto grid max-w-4xl gap-6 sm:grid-cols-3">
          {[
            {
              text: isRu ? "Раньше проверял 5 каналов каждое утро. Теперь открываю WinExtraFlow — и всё в одном месте с AI-оценкой." : "Used to check 5 channels every morning. Now I open WinExtraFlow — everything in one place with AI rating.",
              name: isRu ? "Алексей К." : "Alexey K.",
              role: isRu ? "Крипто-трейдер" : "Crypto Trader",
            },
            {
              text: isRu ? "WEF Score реально помогает отсеивать слабые сигналы. Win rate вырос с 45% до 68% за месяц." : "WEF Score really helps filter weak signals. My win rate grew from 45% to 68% in a month.",
              name: isRu ? "Мария Д." : "Maria D.",
              role: isRu ? "Инвестор MOEX" : "MOEX Investor",
            },
            {
              text: isRu ? "Подключил копитрейдинг на Demo — проверил за неделю. Результат убедил, перешёл на реальный счёт." : "Set up copy trading on Demo — tested for a week. Results convinced me, switched to real account.",
              name: isRu ? "Дмитрий В." : "Dmitry V.",
              role: isRu ? "Начинающий трейдер" : "Beginner Trader",
            },
          ].map(t => (
            <div key={t.name} className="glass gradient-border rounded-xl p-6">
              <p className="text-sm text-text-secondary leading-relaxed">&ldquo;{t.text}&rdquo;</p>
              <div className="mt-4 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-500/20 text-sm font-bold text-brand-500">
                  {t.name[0]}
                </div>
                <div>
                  <p className="text-sm font-medium text-text-primary">{t.name}</p>
                  <p className="text-xs text-text-muted">{t.role}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-4 text-center text-xs text-text-muted">
          {isRu ? "* Отзывы от бета-тестеров платформы" : "* Reviews from platform beta testers"}
        </p>
      </section>

      <WaveDivider flip />

      {/* ═══ FAQ ═══ */}
      <section className="px-6 py-16 lg:px-16">
        <h2 className="mb-8 text-center text-3xl font-bold text-text-primary">
          {isRu ? "Частые вопросы" : "FAQ"}
        </h2>
        <div className="mx-auto max-w-2xl space-y-3">
          {[
            {
              q: isRu ? "Это бесплатно?" : "Is it free?",
              a: isRu ? "Да, бесплатный тариф включает 10 последних сигналов, 1 бэктест в день, лидерборд и реферальную программу. Premium — от 2 490 ₽/мес." : "Yes, the free tier includes 10 latest signals, 1 backtest/day, leaderboard, and referral program. Premium starts at $29/mo.",
            },
            {
              q: isRu ? "Это инвестиционная рекомендация?" : "Is this investment advice?",
              a: isRu ? "Нет. WinExtraFlow — информационный сервис. Все решения принимаются пользователем самостоятельно. Платформа агрегирует публичные сигналы и оценивает их AI." : "No. WinExtraFlow is an informational service. All decisions are made by the user. The platform aggregates public signals and rates them with AI.",
            },
            {
              q: isRu ? "Безопасно ли подключать биржу?" : "Is it safe to connect my exchange?",
              a: isRu ? "API-ключи шифруются Fernet (AES-128-CBC). Платформа не хранит пароли от бирж. Вы контролируете права ключа (можно дать только read + trade, без вывода средств)." : "API keys are encrypted with Fernet (AES-128-CBC). The platform doesn't store exchange passwords. You control key permissions (read + trade only, no withdrawal).",
            },
            {
              q: isRu ? "Какие биржи поддерживаются?" : "Which exchanges are supported?",
              a: isRu ? "9 бирж: Binance, Bybit, OKX, Kraken, MetaTrader 5, Interactive Brokers, Tinkoff Invest, Exante и Demo-режим." : "9 exchanges: Binance, Bybit, OKX, Kraken, MetaTrader 5, Interactive Brokers, Tinkoff Invest, Exante, and Demo mode.",
            },
            {
              q: isRu ? "Как работает WEF Score?" : "How does WEF Score work?",
              a: isRu ? "WEF Score (0–100%) оценивает каждый сигнал по 9 факторам: риск-менеджмент, risk/reward, история провайдера, Sharpe ratio, drawdown и другие. 150+ AI-компонентов из 60 источников." : "WEF Score (0–100%) rates each signal by 9 factors: risk management, risk/reward, provider history, Sharpe ratio, drawdown, and more. 150+ AI components from 60 sources.",
            },
            {
              q: isRu ? "Можно ли вернуть деньги?" : "Can I get a refund?",
              a: isRu ? "Да. Полный возврат в течение 14 дней по ст. 32 ЗоЗПП. Подробности: /refund" : "Yes. Full refund within 14 days. Details: /refund",
            },
          ].map(item => (
            <details key={item.q} className="group rounded-xl border border-border bg-surface-card">
              <summary className="flex cursor-pointer items-center justify-between p-4 font-medium text-text-primary">
                {item.q}
                <span className="text-text-muted transition group-open:rotate-180">▼</span>
              </summary>
              <div className="px-4 pb-4 text-sm text-text-secondary">{item.a}</div>
            </details>
          ))}
        </div>
      </section>

      {/* ═══ URGENCY BANNER ═══ */}
      <section className="px-6 py-8 lg:px-16">
        <div className="mx-auto max-w-2xl rounded-2xl border-2 border-yellow-500/30 bg-yellow-500/5 p-6 text-center">
          <p className="text-sm font-bold text-yellow-400">
            {isRu ? "Промокод AIGROWTH14 — 14 дней Premium бесплатно" : "Promo code AIGROWTH14 — 14 days Premium free"}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {isRu ? "Ограниченное предложение. Действует при регистрации." : "Limited offer. Valid at registration."}
          </p>
          <Link href="/register" className="mt-3 inline-block rounded-lg bg-yellow-500 px-6 py-2.5 text-sm font-bold text-black hover:bg-yellow-400 transition">
            {isRu ? "Забрать 14 дней бесплатно" : "Claim 14 Free Days"}
          </Link>
        </div>
      </section>

      {/* ═══ STICKY CTA ═══ */}
      <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-surface/90 backdrop-blur px-4 py-3 sm:hidden">
        <Link href="/register" className="block w-full rounded-lg bg-brand-600 py-3 text-center text-sm font-bold text-white">
          {isRu ? "Начать бесплатно" : "Get Started Free"}
        </Link>
      </div>

      {/* Footer */}
      <div className="wave-divider" />
      <footer className="border-t border-border px-6 py-8 lg:px-16">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-brand-500">
              <path d="M2 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
            </svg>
            <span className="font-bold text-brand-500">WinExtra</span>
            <span className="font-bold text-text-primary">Flow</span>
          </div>
          <div className="flex flex-wrap justify-center gap-4 text-sm text-text-secondary">
            <Link href="/api-docs" className="hover:text-text-primary">{t("landing.footerApi")}</Link>
            <Link href="/terms" className="hover:text-text-primary">{t("landing.footerTerms")}</Link>
            <Link href="/privacy" className="hover:text-text-primary">{t("landing.footerPrivacy")}</Link>
            <Link href="/refund" className="hover:text-text-primary">{t("landing.footerRefund")}</Link>
            <Link href="/cookies" className="hover:text-text-primary">{t("landing.footerCookies")}</Link>
            <Link href="/track-record" className="hover:text-text-primary">{t("landing.footerTrackRecord")}</Link>
            <Link href="/contacts" className="hover:text-text-primary">{t("landing.footerContacts")}</Link>
            <Link href="/login" className="hover:text-text-primary">{t("landing.ctaLogin")}</Link>
          </div>
          <p className="mt-3 text-center text-xs leading-relaxed text-text-muted">{t("landing.disclaimer")}</p>
          <p className="mt-1 text-xs text-text-muted">
            &copy; 2026 WinExtraFlow. {t("landing.footerRights")}
            {" · "}
            {isRu ? "Самозанятый Сердюк В.Н., ИНН 250715201810" : "Self-employed V. Serdyuk, INN 250715201810"}
          </p>
        </div>
      </footer>
    </div>
  );
}
