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
  const [activeTab, setActiveTab] = useState("api");
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
        const [plans, keys, rp, edu, tg] = await Promise.all([
          fetch("/api/v1/products/api-keys/plans", { headers }).then(r => r.json()),
          fetch("/api/v1/products/api-keys", { headers }).then(r => r.json()),
          fetch("/api/v1/products/reports/providers", { headers }).then(r => r.json()),
          fetch("/api/v1/products/education", { headers }).then(r => r.json()),
          fetch("/api/v1/products/telegram-premium", { headers }).then(r => r.json()),
        ]);
        setApiPlans(plans.plans || []);
        setApiKeys(keys.keys || []);
        setReportProviders(rp.providers || []);
        setCourses(edu.courses || []);
        setTgInfo(tg);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    };
    load();
  }, []);

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

      {/* ── API Access ── */}
      {activeTab === "api" && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            {apiPlans.map((p: any) => (
              <div key={p.key} className="rounded-xl border border-border bg-surface-card p-6">
                <h3 className="text-lg font-bold text-text-primary">{p.name}</h3>
                <p className="mt-1 text-3xl font-bold text-brand-500">${p.price_usd}<span className="text-sm text-text-muted">/{isRu ? "мес" : "mo"}</span></p>
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
                <option value="basic">Basic ($49/mo)</option>
                <option value="pro">Pro ($99/mo)</option>
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
                  {generatingReport === p.id ? "..." : "$9.99"}
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

      {/* ── Telegram VIP ── */}
      {activeTab === "telegram" && tgInfo && (
        <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
          <h2 className="text-2xl font-bold text-text-primary">{tgInfo.channel_name}</h2>
          <p className="mt-2 text-4xl font-bold text-brand-500">${tgInfo.price_usd}<span className="text-lg text-text-muted">/{isRu ? "мес" : "mo"}</span></p>
          <p className="mt-1 text-sm text-text-muted">{tgInfo.price_rub} {isRu ? "руб" : "RUB"}</p>
          <ul className="mx-auto mt-6 max-w-md space-y-2 text-left text-sm text-text-secondary">
            {(isRu ? tgInfo.features_ru : tgInfo.features)?.map((f: string, i: number) => (
              <li key={i} className="flex items-center gap-2"><span className="text-green-400">+</span> {f}</li>
            ))}
          </ul>
          <p className="mt-6 text-sm text-brand-400">{isRu ? tgInfo.access_ru : tgInfo.access}</p>
          {tgInfo.is_subscribed ? (
            <p className="mt-4 rounded-lg bg-green-500/10 px-4 py-2 text-sm text-green-400">{isRu ? "Доступ активен (Premium)" : "Access active (Premium)"}</p>
          ) : (
            <a href="/dashboard/premium" className="mt-4 inline-block rounded-lg bg-brand-600 px-8 py-3 text-sm font-medium text-white hover:bg-brand-700">
              {isRu ? "Подключить Premium" : "Get Premium"}
            </a>
          )}
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
                    <span className="text-lg font-bold text-brand-500">${c.price_usd}</span>
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
