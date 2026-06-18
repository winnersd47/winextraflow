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
  const [myCourses, setMyCourses] = useState<any[]>([]);
  const [purchasing, setPurchasing] = useState<string | null>(null);
  const [purchaseMsg, setPurchaseMsg] = useState("");
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
    const safe = (p: Promise<Response>) => p.then(r => r.ok ? r.json() : null).catch(() => null);
    const load = async () => {
      const [plans, keys, rp, edu, tg, ps, ph] = await Promise.all([
        safe(fetch("/api/v1/products/api-keys/plans", { headers })),
        safe(fetch("/api/v1/products/api-keys", { headers })),
        safe(fetch("/api/v1/products/reports/providers", { headers })),
        safe(fetch("/api/v1/products/education", { headers })),
        safe(fetch("/api/v1/products/telegram-premium", { headers })),
        safe(fetch("/api/v1/premium/status", { headers })),
        safe(fetch("/api/v1/payments/history", { headers })),
      ]);
      setApiPlans(plans?.plans || []);
      setApiKeys(keys?.keys || []);
      setReportProviders(rp?.providers || []);
      setCourses(edu?.courses || []);
      // Load my courses
      const mc = await safe(fetch("/api/v1/products/education/my-courses", { headers }));
      setMyCourses(mc?.courses || []);
      if (tg) setTgInfo(tg);
      if (ps) setPremiumStatus(ps);
      setPayments(ph?.items || []);
      setLoading(false);
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
        await fetch(`/api/v1/payments/complete-demo?payment_id=${result.payment_id}`, { method: "POST", headers });
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
    { key: "telegram", label: isRu ? "Каналы" : "Channels" },
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

          {/* Pricing cards with payment method selector */}
          {!premiumStatus?.is_premium && (
            <PaymentSection isRu={isRu} buying={buying} onBuy={handleBuyPremium} headers={headers} />
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
            <div className="mt-3 flex flex-wrap gap-2">
              {["WELCOME7", "TRIAL3", "AIGROWTH14", "LAUNCH30", "VIP3"].map(code => (
                <button key={code} onClick={() => setPromo(code)}
                  className="rounded bg-surface-hover px-2 py-1 text-xs text-text-muted hover:text-text-primary transition">
                  {code}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-text-muted">
              {isRu ? "Нажмите на код, чтобы вставить его в поле" : "Click a code to paste it"}
            </p>
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

          {/* MAX Messenger */}
          <div className="rounded-xl border border-border bg-surface-card p-6">
            <div className="flex items-center gap-3 mb-3">
              <h3 className="text-lg font-bold text-text-primary">MAX</h3>
              <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-bold text-blue-400">{isRu ? "Российский мессенджер" : "Russian messenger"}</span>
            </div>
            <p className="text-sm text-text-secondary">
              {isRu
                ? "Мессенджер MAX от VK — национальный мессенджер России. Те же сигналы, что и в Telegram, дублируются в MAX для пользователей, предпочитающих российскую платформу."
                : "MAX messenger by VK — Russia's national messenger. Same signals as Telegram are mirrored to MAX for users who prefer the Russian platform."}
            </p>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-surface p-3 text-center">
                <p className="text-xs text-text-muted">{isRu ? "Бесплатный канал" : "Free channel"}</p>
                <p className="mt-1 text-sm font-medium text-text-primary">{tgInfo.max_free_channel_name || "WinExtraFlow Signals"}</p>
              </div>
              <div className="rounded-lg bg-surface p-3 text-center">
                <p className="text-xs text-text-muted">VIP ({isRu ? "Premium" : "Premium"})</p>
                <p className="mt-1 text-sm font-medium text-brand-500">{tgInfo.max_vip_channel_name || "WinExtraFlow VIP"}</p>
              </div>
            </div>
          </div>

          {/* How it works */}
          <div className="rounded-lg bg-surface px-4 py-3 text-xs text-text-muted">
            {isRu
              ? `Как это работает: новый сигнал → VIP-каналы (Telegram + MAX) получают полные данные мгновенно → бесплатные каналы получают только направление через ${tgInfo.delay_minutes || 120} минут.`
              : `How it works: new signal → VIP channels (Telegram + MAX) get full details instantly → free channels get direction only after ${tgInfo.delay_minutes || 120} minutes.`}
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
                <div className="flex flex-col items-end gap-2">
                  {c.is_free ? (
                    <span className="text-lg font-bold text-green-400">{isRu ? "Бесплатно" : "Free"}</span>
                  ) : (
                    <span className="text-lg font-bold text-brand-500">{isRu ? (c.price_usd > 0 ? `${(c.price_usd * 90).toLocaleString("ru-RU")} ₽` : "") : (c.price_usd > 0 ? `$${c.price_usd}` : "")}</span>
                  )}
                  {(() => {
                    const purchased = myCourses.some((mc: any) => mc.course_id === c.id);
                    if (purchased) return (
                      <span className="rounded bg-green-500/20 px-3 py-1 text-xs font-bold text-green-400">{isRu ? "Доступ открыт" : "Purchased"}</span>
                    );
                    return (
                      <button onClick={async () => {
                        setPurchasing(c.id); setPurchaseMsg("");
                        try {
                          const token = localStorage.getItem("token");
                          const resp = await fetch(`/api/v1/products/education/${c.id}/purchase`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
                          const d = await resp.json();
                          if (resp.ok) {
                            setPurchaseMsg(isRu ? `Курс "${d.title}" получен!` : `Course "${d.title}" purchased!`);
                            const mc = await fetch("/api/v1/products/education/my-courses", { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json());
                            setMyCourses(mc?.courses || []);
                          } else { setPurchaseMsg(d.detail || "Error"); }
                        } catch { setPurchaseMsg("Error"); }
                        finally { setPurchasing(null); }
                      }} disabled={purchasing === c.id}
                        className="rounded-lg bg-brand-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50">
                        {purchasing === c.id ? "..." : (isRu ? "Заказать" : "Order")}
                      </button>
                    );
                  })()}
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
              {!c.is_accessible && !myCourses.some((mc: any) => mc.course_id === c.id) && (
                <div className="mt-4 rounded-lg bg-yellow-500/10 px-3 py-2 text-xs text-yellow-400">
                  {isRu ? "Требуется Premium подписка" : "Premium subscription required"}
                </div>
              )}
            </div>
          ))}

          {/* My Courses */}
          {myCourses.length > 0 && (
            <div className="mt-6 rounded-xl border border-brand-500/30 bg-brand-500/5 p-6">
              <h3 className="mb-4 font-bold text-text-primary">{isRu ? "Мои курсы" : "My Courses"} ({myCourses.length})</h3>
              <div className="space-y-3">
                {myCourses.map((mc: any) => (
                  <div key={mc.course_id} className="rounded-lg bg-surface p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <span className="font-medium text-text-primary">{isRu ? mc.title_ru : mc.title_en}</span>
                        <span className="ml-2 rounded bg-surface-hover px-1.5 py-0.5 text-xs text-text-muted">{mc.level}</span>
                      </div>
                      <span className="text-sm font-bold text-brand-500">{mc.progress_pct}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-surface-card">
                      <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${mc.progress_pct}%` }} />
                    </div>
                    <p className="mt-1 text-xs text-text-muted">{mc.lessons_completed}/{mc.total_lessons} {isRu ? "уроков" : "lessons"}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {purchaseMsg && (
            <div className="mt-4 rounded-lg bg-green-500/10 p-3 text-sm text-green-400">{purchaseMsg}</div>
          )}
        </div>
      )}
    </div>
  );
}

/* ═══ PAYMENT SECTION — auto-detect jurisdiction ═══ */

type PayMethod = "yookassa" | "crypto" | "international";

const METHODS: { key: PayMethod; ru: string; en: string; desc_ru: string; desc_en: string; icon: string }[] = [
  { key: "yookassa", ru: "Карты РФ / СБП", en: "RU Cards / SBP", desc_ru: "ЮKassa: МИР, Visa, MC, СБП, SberPay, ЮMoney", desc_en: "YooKassa: MIR, Visa, MC, SBP, SberPay", icon: "🇷🇺" },
  { key: "international", ru: "Карты USD/EUR", en: "Cards USD/EUR", desc_ru: "Prodamus: Visa, MasterCard в долларах и евро", desc_en: "Prodamus: Visa, MasterCard in USD/EUR", icon: "🌍" },
  { key: "crypto", ru: "Криптовалюта", en: "Crypto (USDT/BTC)", desc_ru: "CryptoCloud: USDT, BTC, ETH, SOL — комиссия 0.4%", desc_en: "CryptoCloud: USDT, BTC, ETH, SOL — 0.4% fee", icon: "🪙" },
];

const PLANS: { key: string; tier: string; ru: string; en: string; rub: number; usd: number; eur: number; days: number; badge?: string; features_ru: string[]; features_en: string[] }[] = [
  { key: "pro_monthly", tier: "pro", ru: "Pro / Месяц", en: "Pro / Monthly", rub: 1490, usd: 16, eur: 15, days: 30,
    features_ru: ["Все сигналы без лимита", "Бэктест без ограничений", "AI чат + Скринер", "Торговый журнал", "Оповещения"],
    features_en: ["Unlimited signals", "Unlimited backtesting", "AI Chat + Screener", "Trade Journal", "Price Alerts"] },
  { key: "monthly", tier: "premium", ru: "Premium / Месяц", en: "Premium / Monthly", rub: 2990, usd: 33, eur: 30, days: 30, badge: "TOP",
    features_ru: ["Всё из Pro +", "Копитрейдинг", "Исполнение на 9 биржах", "Маркетплейс стратегий", "VIP Telegram канал", "PDF отчёты"],
    features_en: ["Everything in Pro +", "Copy Trading", "Execution on 9 exchanges", "Strategy Marketplace", "VIP Telegram channel", "PDF Reports"] },
  { key: "yearly", tier: "premium", ru: "Premium / Год", en: "Premium / Year", rub: 23900, usd: 264, eur: 240, days: 365, badge: "-33%",
    features_ru: ["Всё из Premium", "Экономия 33%", "12 месяцев по цене 8"],
    features_en: ["Everything in Premium", "Save 33%", "12 months for the price of 8"] },
];

function PaymentSection({ isRu, buying, onBuy, headers }: {
  isRu: boolean; buying: string;
  onBuy: (plan: string) => void;
  headers: Record<string, string>;
}) {
  const [method, setMethod] = useState<PayMethod>(isRu ? "yookassa" : "international");
  const [processing, setProcessing] = useState("");

  const handlePay = async (plan: string) => {
    setProcessing(plan);
    try {
      let endpoint = "/api/v1/payments/checkout";
      let body: any = { plan };

      if (method === "crypto") {
        endpoint = "/api/v1/payments/checkout/crypto";
        body = { plan, return_url: window.location.href };
      } else if (method === "international") {
        endpoint = "/api/v1/payments/checkout/international";
        body = { plan, currency: "usd", return_url: window.location.href };
      } else {
        body = { plan, return_url: window.location.href };
      }

      const resp = await fetch(endpoint, {
        method: "POST", headers,
        body: JSON.stringify(body),
      });
      const result = await resp.json();

      if (result.demo) {
        // Demo mode — auto-complete
        const completeUrl = method === "yookassa"
          ? `/api/v1/payments/complete-demo?payment_id=${result.payment_id}`
          : `/api/v1/payments/complete-demo?payment_id=${result.payment_id}`;
        await fetch(completeUrl, { method: "POST", headers });
        window.location.reload();
      } else if (result.payment_url) {
        window.location.href = result.payment_url;
      }
    } catch (err) {
      console.error("Payment error:", err);
    } finally {
      setProcessing("");
    }
  };

  return (
    <div className="space-y-4">
      {/* Method selector */}
      <div className="rounded-xl border border-border bg-surface-card p-4">
        <h3 className="mb-3 text-sm font-bold text-text-muted">{isRu ? "Способ оплаты" : "Payment Method"}</h3>
        <div className="grid gap-2 sm:grid-cols-3">
          {METHODS.map(m => (
            <button key={m.key} onClick={() => setMethod(m.key)}
              className={`rounded-xl border-2 p-3 text-left transition ${method === m.key ? "border-brand-500 bg-brand-500/5" : "border-border hover:border-brand-500/30"}`}>
              <div className="flex items-center gap-2">
                <span className="text-lg">{m.icon}</span>
                <span className="text-sm font-bold text-text-primary">{isRu ? m.ru : m.en}</span>
              </div>
              <p className="mt-1 text-xs text-text-muted">{isRu ? m.desc_ru : m.desc_en}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Plans — 3 tier cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        {PLANS.map(plan => {
          const price = method === "yookassa" ? plan.rub : plan.usd;
          const currency = method === "yookassa" ? "₽" : "$";
          const isPremium = plan.tier === "premium" && plan.key !== "yearly";
          const isYearly = plan.key === "yearly";
          const period = plan.days === 365 ? (isRu ? "год" : "yr") : (isRu ? "мес" : "mo");

          return (
            <div key={plan.key} className={`rounded-xl p-6 flex flex-col ${isPremium ? "border-2 border-brand-500 bg-surface-card shadow-lg shadow-brand-500/10" : "border border-border bg-surface-card"}`}>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-text-primary">{isRu ? plan.ru : plan.en}</h3>
                {plan.badge && (
                  <span className={`rounded px-2 py-0.5 text-xs font-bold ${plan.badge === "TOP" ? "bg-brand-500/20 text-brand-500" : "bg-yellow-500/20 text-yellow-400"}`}>
                    {plan.badge}
                  </span>
                )}
              </div>
              <p className={`mt-1 text-3xl font-extrabold ${isPremium ? "text-brand-500" : "text-text-primary"}`}>
                {method === "yookassa" ? price.toLocaleString("ru-RU") : price}
                <span className="text-base font-normal text-text-muted"> {currency}/{period}</span>
              </p>
              <p className="mt-1 text-xs text-text-muted">
                {plan.days} {isRu ? "дней" : "days"}
                {method === "yookassa" ? ` (~$${plan.usd})` : ""}
              </p>

              {/* Features list */}
              <ul className="mt-3 flex-1 space-y-1.5">
                {(isRu ? plan.features_ru : plan.features_en).map(f => (
                  <li key={f} className="flex items-center gap-2 text-xs text-text-secondary">
                    <span className="text-brand-500">~</span>{f}
                  </li>
                ))}
              </ul>

              <button onClick={() => handlePay(plan.key)} disabled={!!processing}
                className={`mt-4 w-full rounded-lg py-3 text-sm font-medium transition disabled:opacity-50 ${
                  isPremium
                    ? "bg-brand-600 text-white hover:bg-brand-700"
                    : "border border-brand-500 text-brand-500 hover:bg-brand-500/10"
                }`}>
                {processing === plan.key ? "..." : (isRu ? "Оплатить" : "Pay")}
              </button>
            </div>
          );
        })}
      </div>

      {/* Commission info */}
      <p className="text-center text-xs text-text-muted">
        {method === "yookassa" && (isRu ? "Обработка: ЮKassa. Комиссия: карты 2.8%, СБП 0.7%. Чек формируется автоматически." : "Processed by YooKassa. Fee: cards 2.8%, SBP 0.7%. Receipt generated automatically.")}
        {method === "crypto" && (isRu ? "Обработка: CryptoCloud. Комиссия: 0.4-1%. Автоконверсия в рубли." : "Processed by CryptoCloud. Fee: 0.4-1%. Auto-conversion to RUB.")}
        {method === "international" && (isRu ? "Обработка: Prodamus. Комиссия: 3.5-5%. Visa/MasterCard в USD и EUR." : "Processed by Prodamus. Fee: 3.5-5%. Visa/MasterCard in USD and EUR.")}
      </p>
    </div>
  );
}
