"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";

export default function StorePage() {
  const { locale } = useI18n();
  const { user } = useAuth();
  const isRu = locale === "ru";
  const [apiPlans, setApiPlans] = useState<any[]>([]);
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [reportProviders, setReportProviders] = useState<any[]>([]);
  const [courses, setCourses] = useState<any[]>([]);
  const [tgInfo, setTgInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("premium");
  const [premiumStatus, setPremiumStatus] = useState<any>(null);
  const [promo, setPromo] = useState("");
  const [buying, setBuying] = useState("");
  const [premiumError, setPremiumError] = useState("");
  const [premiumSuccess, setPremiumSuccess] = useState("");
  const [payments, setPayments] = useState<any[]>([]);
  const [newKeyPlan, setNewKeyPlan] = useState("basic");
  const [newKeyLabel, setNewKeyLabel] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [generatingReport, setGeneratingReport] = useState<string | null>(null);
  const [report, setReport] = useState<any>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  useEffect(() => {
    const load = async () => {
      try {
        const [plans, keys, rp, edu, tg, ps, ph] = await Promise.all([
          fetch("/api/v1/products/api-keys/plans", { headers }).then(r => r.json()),
          fetch("/api/v1/products/api-keys", { headers }).then(r => r.json()),
          fetch("/api/v1/products/reports/providers", { headers }).then(r => r.json()),
          fetch("/api/v1/products/education", { headers }).then(r => r.json()),
          fetch("/api/v1/products/telegram-premium", { headers }).then(r => r.json()),
          fetch("/api/v1/premium/status", { headers }).then(r => r.json()),
          fetch("/api/v1/payments/history", { headers }).then(r => r.json()),
        ]);
        setApiPlans(plans.plans || []);
        setApiKeys(keys.keys || []);
        setReportProviders(rp.providers || []);
        setCourses(edu.courses || []);
        setTgInfo(tg);
        setPremiumStatus(ps);
        setPayments(ph?.items || []);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    };
    load();
  }, []);

  const handleBuyPremium = async (plan: string) => {
    setPremiumError(""); setBuying(plan);
    try {
      const resp = await fetch("/api/v1/payments/checkout", {
        method: "POST", headers,
        body: JSON.stringify({ plan }),
      });
      const result = await resp.json();
      if (result.demo) {
        await fetch(`/api/v1/payments/complete-demo?session_id=${result.session_id}`, { method: "POST", headers });
        setPremiumSuccess(isRu ? "Premium активирован!" : "Premium activated!");
        const ps = await fetch("/api/v1/premium/status", { headers }).then(r => r.json());
        setPremiumStatus(ps);
      } else {
        window.location.href = result.checkout_url;
      }
    } catch (err: any) { setPremiumError(err.message); }
    finally { setBuying(""); }
  };

  const handlePromo = async () => {
    setPremiumError(""); setPremiumSuccess("");
    try {
      const resp = await fetch(`/api/v1/premium/activate`, {
        method: "POST", headers,
        body: JSON.stringify({ promo_code: promo }),
      });
      if (resp.ok) {
        setPremiumSuccess(isRu ? "Промокод активирован!" : "Promo code activated!");
        setPromo("");
        const ps = await fetch("/api/v1/premium/status", { headers }).then(r => r.json());
        setPremiumStatus(ps);
      } else { const d = await resp.json(); setPremiumError(d.detail || "Error"); }
    } catch (err: any) { setPremiumError(err.message); }
  };

  const createKey = async () => {
    const resp = await fetch("/api/v1/products/api-keys", {
      method: "POST", headers,
      body: JSON.stringify({ plan: newKeyPlan, label: newKeyLabel || "My API Key" }),
    });
    if (resp.ok) {
      const data = await resp.json();
      setCreatedKey(data.key);
      const keys = await fetch("/api/v1/products/api-keys", { headers }).then(r => r.json());
      setApiKeys(keys.keys || []);
    } else {
      const err = await resp.json();
      alert(err.detail || "Error");
    }
  };

  const generateReport = async (providerId: string) => {
    setGeneratingReport(providerId);
    setReport(null);
    try {
      const resp = await fetch(`/api/v1/products/reports/generate/${providerId}`, { method: "POST", headers });
      if (resp.ok) setReport(await resp.json());
      else alert((await resp.json()).detail || "Error");
    } catch { alert("Error"); }
    finally { setGeneratingReport(null); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  const TABS = [
    { key: "premium", label: "Premium" },
    { key: "api", label: isRu ? "API доступ" : "API Access" },
    { key: "reports", label: isRu ? "Отчёты" : "Reports" },
    { key: "telegram", label: "Telegram VIP" },
    { key: "education", label: isRu ? "Обучение" : "Education" },
  ];

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">{isRu ? "Магазин" : "Store"}</h1>
      <p className="mb-6 text-sm text-text-secondary">{isRu ? "Дополнительные продукты и сервисы" : "Additional products and services"}</p>

      {/* Tabs */}
      <div className="mb-6 flex gap-1 rounded-xl border border-border bg-surface-card p-1">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition ${activeTab === t.key ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── PREMIUM (priority) ── */}
      {activeTab === "premium" && (
        <div className="space-y-6">
          {/* Status banner */}
          {premiumStatus && (
            <div className={`rounded-xl border-2 p-6 ${premiumStatus.is_premium ? "border-brand-500 bg-brand-500/5" : "border-yellow-500 bg-yellow-500/5"}`}>
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-text-primary">
                    {premiumStatus.is_premium
                      ? (isRu ? "Premium активен" : "Premium Active")
                      : (isRu ? "Разблокируйте полный доступ" : "Unlock Full Access")}
                  </h2>
                  <p className="mt-1 text-sm text-text-secondary">
                    {premiumStatus.is_premium
                      ? `${premiumStatus.days_left} ${isRu ? "дней осталось" : "days left"}`
                      : (isRu ? "Все сигналы, бэктест без лимита, исполнение, копитрейдинг, аналитика L2" : "All signals, unlimited backtest, execution, copy trading, L2 analytics")}
                  </p>
                </div>
                {premiumStatus.is_premium && (
                  <span className="rounded-lg bg-brand-500/20 px-4 py-2 text-lg font-bold text-brand-500">PRO</span>
                )}
              </div>
            </div>
          )}

          {premiumError && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{premiumError}</div>}
          {premiumSuccess && <div className="rounded-lg bg-green-500/10 p-3 text-sm text-green-400">{premiumSuccess}</div>}

          {/* Pricing cards */}
          {!premiumStatus?.is_premium && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-border bg-surface-card p-6">
                <h3 className="text-lg font-bold text-text-primary">Monthly</h3>
                <p className="mt-1 text-4xl font-extrabold text-text-primary">{isRu ? "2 600 ₽" : "$29"}<span className="text-base font-normal text-text-muted">/{isRu ? "мес" : "mo"}</span></p>
                <p className="mt-1 text-xs text-text-muted">30 {isRu ? "дней" : "days"}{isRu ? " (~$29)" : ""}</p>
                <button onClick={() => handleBuyPremium("monthly")} disabled={!!buying}
                  className="mt-4 w-full rounded-lg bg-brand-600 py-3 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
                  {buying === "monthly" ? "..." : (isRu ? "Подключить" : "Subscribe")}
                </button>
              </div>
              <div className="rounded-xl border-2 border-brand-500 bg-surface-card p-6 shadow-lg shadow-brand-500/10">
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-text-primary">Yearly</h3>
                  <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">{isRu ? "Экономия 30%" : "Save 30%"}</span>
                </div>
                <p className="mt-1 text-4xl font-extrabold text-brand-500">{isRu ? "22 400 ₽" : "$249"}<span className="text-base font-normal text-text-muted">/{isRu ? "год" : "yr"}</span></p>
                <p className="mt-1 text-xs text-text-muted">365 {isRu ? "дней" : "days"}{isRu ? " (~$249)" : ""}</p>
                <button onClick={() => handleBuyPremium("yearly")} disabled={!!buying}
                  className="mt-4 w-full rounded-lg bg-brand-600 py-3 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
                  {buying === "yearly" ? "..." : (isRu ? "Подключить" : "Subscribe")}
                </button>
              </div>
            </div>
          )}

          {/* What's included */}
          <div className="rounded-xl border border-border bg-surface-card p-6">
            <h3 className="mb-4 font-bold text-text-primary">{isRu ? "Что входит в Premium" : "What's Included"}</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { f: isRu ? "Все сигналы без ограничений" : "All signals unlimited", free: "10", pro: isRu ? "Все" : "All" },
                { f: isRu ? "Бэктестинг" : "Backtesting", free: "1/" + (isRu ? "день" : "day"), pro: isRu ? "Без лимита" : "Unlimited" },
                { f: isRu ? "AI-аналитика L2" : "AI Analytics L2", free: "—", pro: "+" },
                { f: isRu ? "Исполнение на биржах" : "Exchange Execution", free: "—", pro: "+" },
                { f: isRu ? "Копитрейдинг" : "Copy Trading", free: "—", pro: "+" },
                { f: isRu ? "Маркетплейс стратегий" : "Strategy Marketplace", free: "—", pro: "+" },
                { f: isRu ? "PDF отчёты" : "PDF Reports", free: "—", pro: "+" },
                { f: isRu ? "Telegram VIP канал" : "Telegram VIP Channel", free: "—", pro: "+" },
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between rounded-lg bg-surface p-3">
                  <span className="text-sm text-text-primary">{item.f}</span>
                  <div className="flex gap-4 text-xs">
                    <span className="w-16 text-center text-text-muted">{item.free}</span>
                    <span className="w-16 text-center font-bold text-brand-500">{item.pro}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Promo code */}
          <div className="rounded-xl border border-border bg-surface-card p-6">
            <h3 className="mb-3 font-bold text-text-primary">{isRu ? "Промокод" : "Promo Code"}</h3>
            <div className="flex gap-2">
              <input type="text" value={promo} onChange={e => setPromo(e.target.value)}
                placeholder={isRu ? "Введите код" : "Enter code"}
                className="flex-1 rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500" />
              <button onClick={handlePromo} disabled={!promo}
                className="rounded-lg bg-brand-600 px-6 py-2.5 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
                {isRu ? "Применить" : "Apply"}
              </button>
            </div>
          </div>

          {/* Payment history */}
          {payments.length > 0 && (
            <div className="rounded-xl border border-border bg-surface-card p-6">
              <h3 className="mb-3 font-bold text-text-primary">{isRu ? "История платежей" : "Payment History"}</h3>
              <div className="space-y-2">
                {payments.map((p: any) => (
                  <div key={p.id} className="flex items-center justify-between rounded-lg bg-surface p-3">
                    <div className="flex items-center gap-3">
                      <span className={`rounded px-2 py-0.5 text-xs font-bold ${p.status === "completed" ? "bg-green-500/20 text-green-400" : "bg-yellow-500/20 text-yellow-400"}`}>{p.status}</span>
                      <span className="text-sm text-text-primary">{p.plan} — ${p.amount}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── API Access ── */}
      {activeTab === "api" && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            {apiPlans.map((p: any) => (
              <div key={p.key} className="rounded-xl border border-border bg-surface-card p-6">
                <h3 className="text-lg font-bold text-text-primary">{p.name}</h3>
                <p className="mt-1 text-3xl font-bold text-brand-500">{isRu ? `${(p.price_usd * 90).toLocaleString("ru-RU")} ₽` : `$${p.price_usd}`}<span className="text-sm text-text-muted">/{isRu ? "мес" : "mo"}</span></p>
                <ul className="mt-4 space-y-2 text-sm text-text-secondary">
                  <li>{isRu ? "Лимит:" : "Rate:"} {p.rate_limit}</li>
                  <li>{isRu ? "Сигналы:" : "Signals:"} {p.signals ? "+" : "-"}</li>
                  <li>{isRu ? "Провайдеры:" : "Providers:"} {p.providers ? "+" : "-"}</li>
                  <li>{isRu ? "Бэктест:" : "Backtest:"} {p.backtest ? "+" : "-"}</li>
                  <li>WebSocket: {p.websocket ? "+" : "-"}</li>
                </ul>
              </div>
            ))}
          </div>

          {/* Create key form */}
          <div className="rounded-xl border border-border bg-surface-card p-6">
            <h3 className="mb-4 font-bold text-text-primary">{isRu ? "Создать API ключ" : "Create API Key"}</h3>
            {createdKey && (
              <div className="mb-4 rounded-lg bg-green-500/10 p-4">
                <p className="text-xs text-text-muted">{isRu ? "Ваш ключ (сохраните!):" : "Your key (save it!):"}</p>
                <code className="mt-1 block break-all text-sm font-mono text-green-400">{createdKey}</code>
              </div>
            )}
            <div className="flex gap-3">
              <select value={newKeyPlan} onChange={e => setNewKeyPlan(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary">
                <option value="basic">Basic ({isRu ? "4 400 ₽/мес" : "$49/mo"})</option>
                <option value="pro">Pro ({isRu ? "8 900 ₽/мес" : "$99/mo"})</option>
              </select>
              <input type="text" placeholder={isRu ? "Название" : "Label"} value={newKeyLabel} onChange={e => setNewKeyLabel(e.target.value)} className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" />
              <button onClick={createKey} className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700">{isRu ? "Создать" : "Create"}</button>
            </div>
          </div>

          {/* Existing keys */}
          {apiKeys.length > 0 && (
            <div className="rounded-xl border border-border bg-surface-card p-6">
              <h3 className="mb-3 font-bold text-text-primary">{isRu ? "Мои ключи" : "My Keys"} ({apiKeys.length})</h3>
              <div className="space-y-2">
                {apiKeys.map((k: any) => (
                  <div key={k.id} className="flex items-center justify-between rounded-lg bg-surface p-3">
                    <div>
                      <code className="text-sm text-text-primary">{k.key_preview}</code>
                      <span className="ml-2 text-xs text-text-muted">{k.label} ({k.plan})</span>
                    </div>
                    <span className={`text-xs ${k.is_active ? "text-green-400" : "text-red-400"}`}>{k.is_active ? (isRu ? "Активен" : "Active") : (isRu ? "Отозван" : "Revoked")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Reports ── */}
      {activeTab === "reports" && (
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            {isRu ? "Генерация аналитического отчёта по провайдеру. Включает: метрики, бэктест, распределение сигналов." : "Generate analytics report per provider. Includes: metrics, backtest, signal distribution."}
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {reportProviders.map((p: any) => (
              <div key={p.id} className="flex items-center justify-between rounded-xl border border-border bg-surface-card p-4">
                <div>
                  <p className="font-medium text-text-primary">{p.name}</p>
                  <p className="text-xs text-text-muted">{p.total_signals} {isRu ? "сигналов" : "signals"} | AI: {p.ai_score ? (p.ai_score * 100).toFixed(0) + "%" : "—"}</p>
                </div>
                <button onClick={() => generateReport(p.id)} disabled={generatingReport === p.id}
                  className="rounded-lg bg-brand-600 px-4 py-2 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50">
                  {generatingReport === p.id ? "..." : isRu ? "899 ₽" : "$9.99"}
                </button>
              </div>
            ))}
          </div>

          {report && (
            <div className="rounded-xl border border-border bg-surface-card p-6">
              <h3 className="mb-2 font-bold text-text-primary">{report.provider?.name}</h3>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div><span className="text-text-muted">{isRu ? "Доходность" : "Return"}</span><p className={`font-bold ${report.performance?.total_return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>{report.performance?.total_return_pct?.toFixed(1)}%</p></div>
                <div><span className="text-text-muted">Win Rate</span><p className="font-bold text-text-primary">{(report.performance?.win_rate * 100)?.toFixed(0)}%</p></div>
                <div><span className="text-text-muted">Sharpe</span><p className="font-bold text-text-primary">{report.performance?.sharpe_ratio?.toFixed(2)}</p></div>
              </div>
              <p className="mt-3 text-xs text-text-muted">{report.disclaimer}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Telegram Channels ── */}
      {activeTab === "telegram" && tgInfo && (
        <div className="space-y-6">
          {/* Two columns: Free vs VIP */}
          <div className="grid gap-4 sm:grid-cols-2">
            {/* Free channel */}
            <div className="rounded-xl border border-border bg-surface-card p-6">
              <h3 className="text-lg font-bold text-text-primary">{tgInfo.free_channel_name || "@WinExtraFlowSignals"}</h3>
              <p className="mt-1 text-2xl font-bold text-green-400">{isRu ? "Бесплатно" : "Free"}</p>
              <ul className="mt-4 space-y-2 text-sm text-text-secondary">
                {(isRu ? tgInfo.free_features_ru : tgInfo.free_features)?.map((f: string, i: number) => (
                  <li key={i} className="flex items-center gap-2"><span className="text-text-muted">-</span> {f}</li>
                ))}
              </ul>
              <a href={tgInfo.free_channel_link || "https://t.me/WinExtraFlowSignals"} target="_blank" rel="noopener"
                className="mt-4 block w-full rounded-lg border border-border py-2.5 text-center text-sm font-medium text-text-primary hover:bg-surface-hover">
                {isRu ? "Подписаться" : "Subscribe"}
              </a>
            </div>
            {/* VIP channel */}
            <div className="rounded-xl border-2 border-brand-500 bg-surface-card p-6 shadow-lg shadow-brand-500/10">
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-text-primary">{tgInfo.vip_channel_name || "@WinExtraFlowVIP"}</h3>
                <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">VIP</span>
              </div>
              <p className="mt-1 text-2xl font-bold text-brand-500">{isRu ? `${tgInfo.price_rub} ₽` : `$${tgInfo.price_usd}`}<span className="text-sm text-text-muted">/{isRu ? "мес" : "mo"}</span></p>
              <ul className="mt-4 space-y-2 text-sm text-text-secondary">
                {(isRu ? tgInfo.features_ru : tgInfo.features)?.map((f: string, i: number) => (
                  <li key={i} className="flex items-center gap-2"><span className="text-green-400">+</span> {f}</li>
                ))}
              </ul>
              {tgInfo.is_subscribed ? (
                <a href={tgInfo.vip_channel_link || "#"} target="_blank" rel="noopener"
                  className="mt-4 block w-full rounded-lg bg-brand-600 py-2.5 text-center text-sm font-medium text-white hover:bg-brand-700">
                  {isRu ? "Войти в VIP-канал" : "Enter VIP Channel"}
                </a>
              ) : (
                <button onClick={() => setActiveTab("premium")}
                  className="mt-4 w-full rounded-lg bg-brand-600 py-2.5 text-sm font-medium text-white hover:bg-brand-700">
                  {isRu ? "Подключить Premium" : "Get Premium"}
                </button>
              )}
            </div>
          </div>

          {/* Community */}
          <div className="rounded-xl border border-border bg-surface-card p-6 text-center">
            <h3 className="text-lg font-bold text-text-primary">AI Growth Club</h3>
            <p className="mt-1 text-sm text-text-secondary">
              {isRu
                ? "Открытое сообщество: обсуждения рынка, AI-аналитика, обмен опытом"
                : "Open community: market discussions, AI analytics, experience sharing"}
            </p>
            <a href={tgInfo.community_link || "https://t.me/+HEyibcuonz00NTI6"} target="_blank" rel="noopener"
              className="mt-4 inline-block rounded-lg border border-border px-6 py-2.5 text-sm font-medium text-text-primary hover:bg-surface-hover">
              {isRu ? "Присоединиться" : "Join Community"}
            </a>
          </div>

          {/* How it works */}
          <div className="rounded-lg bg-surface px-4 py-3 text-xs text-text-muted">
            {isRu
              ? `Как это работает: при появлении нового сигнала на платформе → VIP-канал получает полные данные мгновенно → бесплатный канал получает только направление (BUY/SELL) через ${tgInfo.delay_minutes || 120} минут.`
              : `How it works: when a new signal appears → VIP channel gets full details instantly → free channel gets direction only (BUY/SELL) after ${tgInfo.delay_minutes || 120} minutes.`}
          </div>
        </div>
      )}

      {/* ── Education ── */}
      {activeTab === "education" && (
        <div className="space-y-4">
          {courses.map((c: any) => (
            <div key={c.id} className="rounded-xl border border-border bg-surface-card p-6">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-text-primary">{isRu ? c.title_ru : c.title_en}</h3>
                    {c.is_free && <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-bold text-green-400">FREE</span>}
                    <span className="rounded bg-surface-hover px-2 py-0.5 text-xs text-text-muted">{c.level}</span>
                  </div>
                  <p className="mt-1 text-sm text-text-secondary">{isRu ? c.description_ru : c.description_en}</p>
                  <p className="mt-2 text-xs text-text-muted">{c.lessons} {isRu ? "уроков" : "lessons"} / {c.duration_min} {isRu ? "мин" : "min"}</p>
                </div>
                <div className="text-right">
                  {c.is_free ? (
                    <span className="text-lg font-bold text-green-400">{isRu ? "Бесплатно" : "Free"}</span>
                  ) : (
                    <span className="text-lg font-bold text-brand-500">{isRu ? (c.price_usd > 0 ? `${(c.price_usd * 90).toLocaleString("ru-RU")} ₽` : "") : (c.price_usd > 0 ? `$${c.price_usd}` : "")}</span>
                  )}
                </div>
              </div>
              <div className="mt-4">
                <p className="mb-2 text-xs font-bold text-text-muted">{isRu ? "Темы:" : "Topics:"}</p>
                <div className="grid grid-cols-2 gap-1 text-xs text-text-secondary">
                  {(isRu ? c.topics_ru : c.topics_en)?.map((t: string, i: number) => (
                    <div key={i} className="flex items-center gap-1"><span className="text-brand-500">{i + 1}.</span> {t}</div>
                  ))}
                </div>
              </div>
              {!c.is_accessible && (
                <div className="mt-4 rounded-lg bg-yellow-500/10 px-3 py-2 text-xs text-yellow-400">
                  {isRu ? "Требуется Premium подписка" : "Premium subscription required"}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
