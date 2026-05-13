"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

interface RevenueReport {
  revenue: { year: number; total_usd: number; total_rub: number; transaction_count: number; monthly: { month: number; amount_usd: number; amount_rub: number; count: number }[]; usd_to_rub_rate: number };
  stage: { key: string; name_ru: string; name_en: string; max_revenue_rub: number; tax_rate: string; description_ru: string; description_en: string; usage_pct: number; remaining_rub: number };
  alerts: { level: string; title_ru: string; title_en: string; message_ru: string; message_en: string; action_ru: string; action_en: string }[];
  stages: { key: string; name_ru: string; name_en: string; max_revenue_rub: number; tax_rate: string; is_current: boolean }[];
}

const MONTH_RU = ["", "Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"];
const MONTH_EN = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function RevenuePage() {
  const [data, setData] = useState<RevenueReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { locale } = useI18n();
  const isRu = locale === "ru";

  useEffect(() => {
    const load = async () => {
      try {
        const token = localStorage.getItem("token");
        const resp = await fetch("/api/v1/admin/revenue", { headers: { Authorization: `Bearer ${token}` } });
        if (!resp.ok) throw new Error("Access denied");
        setData(await resp.json());
      } catch (err: any) { setError(err.message); }
      finally { setLoading(false); }
    };
    load();
  }, []);

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (error) return <div className="mx-auto max-w-4xl rounded-xl bg-red-500/10 p-6 text-red-400">{error}</div>;
  if (!data) return null;

  const { revenue, stage, alerts, stages } = data;
  const months = isRu ? MONTH_RU : MONTH_EN;

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">
        {isRu ? "Доходы и налоги" : "Revenue & Taxes"}
      </h1>
      <p className="mb-6 text-sm text-text-secondary">
        {isRu ? `Фиксация прибыли за ${revenue.year} год. Законодательство РФ.` : `Profit tracking for ${revenue.year}. Russian law.`}
      </p>

      {/* Alerts */}
      {alerts.map((a, i) => (
        <div key={i} className={`mb-4 rounded-xl border-2 p-4 ${a.level === "critical" ? "border-red-500 bg-red-500/5" : a.level === "warning" ? "border-yellow-500 bg-yellow-500/5" : "border-blue-500 bg-blue-500/5"}`}>
          <h3 className={`font-bold ${a.level === "critical" ? "text-red-400" : a.level === "warning" ? "text-yellow-400" : "text-blue-400"}`}>
            {isRu ? a.title_ru : a.title_en}
          </h3>
          <p className="mt-1 text-sm text-text-secondary">{isRu ? a.message_ru : a.message_en}</p>
          <p className="mt-2 text-sm font-semibold text-text-primary">{isRu ? a.action_ru : a.action_en}</p>
        </div>
      ))}

      {/* Current stage + revenue bar */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-text-muted">{isRu ? "Текущий статус" : "Current Status"}</p>
            <p className="text-xl font-bold text-brand-500">{isRu ? stage.name_ru : stage.name_en}</p>
            <p className="text-xs text-text-muted">{isRu ? stage.description_ru : stage.description_en}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-muted">{isRu ? "Ставка налога" : "Tax Rate"}</p>
            <p className="text-2xl font-bold text-text-primary">{stage.tax_rate}</p>
          </div>
        </div>
        <div className="mb-2 flex justify-between text-xs text-text-muted">
          <span>{revenue.total_rub.toLocaleString("ru-RU")} {isRu ? "руб" : "RUB"}</span>
          <span>{stage.usage_pct}% / {stage.max_revenue_rub.toLocaleString("ru-RU")} {isRu ? "руб" : "RUB"}</span>
        </div>
        <div className="h-4 overflow-hidden rounded-full bg-surface">
          <div
            className={`h-full rounded-full transition-all ${stage.usage_pct >= 90 ? "bg-red-500" : stage.usage_pct >= 70 ? "bg-yellow-500" : "bg-green-500"}`}
            style={{ width: `${Math.min(100, stage.usage_pct)}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-text-muted">
          {isRu ? `Осталось до лимита: ${stage.remaining_rub.toLocaleString("ru-RU")} руб` : `Remaining to limit: ${stage.remaining_rub.toLocaleString("ru-RU")} RUB`}
        </p>
      </div>

      {/* Revenue cards */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MC label={isRu ? "Доход (USD)" : "Revenue (USD)"} value={`$${revenue.total_usd.toLocaleString()}`} />
        <MC label={isRu ? "Доход (RUB)" : "Revenue (RUB)"} value={`${revenue.total_rub.toLocaleString("ru-RU")} R`} />
        <MC label={isRu ? "Транзакций" : "Transactions"} value={String(revenue.transaction_count)} />
        <MC label={isRu ? "Курс USD/RUB" : "USD/RUB Rate"} value={String(revenue.usd_to_rub_rate)} />
      </div>

      {/* Monthly breakdown */}
      {revenue.monthly.length > 0 && (
        <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
          <h2 className="mb-4 text-lg font-bold text-text-primary">{isRu ? "По месяцам" : "Monthly Breakdown"}</h2>
          <div className="space-y-2">
            {revenue.monthly.map((m) => (
              <div key={m.month} className="flex items-center justify-between rounded-lg bg-surface p-3">
                <span className="w-12 text-sm font-medium text-text-primary">{months[m.month]}</span>
                <div className="flex-1 mx-4">
                  <div className="h-2 overflow-hidden rounded-full bg-surface-card">
                    <div className="h-full rounded-full bg-brand-500" style={{ width: `${(m.amount_rub / Math.max(stage.max_revenue_rub * 0.1, 1)) * 100}%` }} />
                  </div>
                </div>
                <span className="text-sm font-medium text-text-primary">${m.amount_usd.toLocaleString()}</span>
                <span className="ml-4 text-xs text-text-muted">({m.count})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Progressive stages */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
        <h2 className="mb-4 text-lg font-bold text-text-primary">
          {isRu ? "План масштабирования бизнеса" : "Business Scaling Plan"}
        </h2>
        <div className="space-y-3">
          {stages.map((s) => (
            <div key={s.key} className={`flex items-center justify-between rounded-lg p-4 ${s.is_current ? "border-2 border-brand-500 bg-brand-500/5" : "bg-surface"}`}>
              <div className="flex items-center gap-3">
                {s.is_current && <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">{isRu ? "ТЕКУЩИЙ" : "CURRENT"}</span>}
                <div>
                  <h3 className="font-semibold text-text-primary">{isRu ? s.name_ru : s.name_en}</h3>
                  <p className="text-xs text-text-muted">{isRu ? "до" : "up to"} {s.max_revenue_rub.toLocaleString("ru-RU")} {isRu ? "руб/год" : "RUB/year"}</p>
                </div>
              </div>
              <span className="text-sm font-bold text-text-primary">{s.tax_rate}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Tax tips */}
      <div className="rounded-xl border border-border bg-surface-card p-6 text-xs text-text-muted">
        {isRu ? (
          <div className="space-y-2">
            <p><strong>Самозанятый (НПД):</strong> Регистрация в приложении "Мой налог". Налог 4% от физлиц, 6% от юрлиц. Чеки формируются автоматически. Лимит 2.4 млн руб/год.</p>
            <p><strong>ИП (УСН 6%):</strong> Регистрация в ФНС. Налог 6% от дохода. Страховые взносы ~45 842 руб/год (2024). Лимит 150 млн руб/год.</p>
            <p><strong>ООО:</strong> Регистрация в ФНС. Уставный капитал от 10 000 руб. Налог УСН 6% или ОСНО. Без лимита дохода. Можно нанимать сотрудников.</p>
            <p className="text-yellow-400/70">Данная информация носит справочный характер и НЕ является налоговой консультацией. Проконсультируйтесь с бухгалтером.</p>
          </div>
        ) : (
          <div className="space-y-2">
            <p><strong>Self-Employed (NPD):</strong> Register in "My Tax" app. Tax 4% from individuals, 6% from legal entities. Receipts auto-generated. Limit 2.4M RUB/year.</p>
            <p><strong>Individual Entrepreneur (USN 6%):</strong> Register with FNS. Tax 6% of income. Insurance contributions ~45,842 RUB/year. Limit 150M RUB/year.</p>
            <p><strong>LLC (OOO):</strong> Register with FNS. Charter capital from 10,000 RUB. Tax USN 6% or OSNO. No income limit. Can hire employees.</p>
            <p className="text-yellow-400/70">This information is for reference only and is NOT tax advice. Consult an accountant.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function MC({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-border bg-surface-card p-4"><p className="text-xs text-text-muted">{label}</p><p className="mt-1 text-2xl font-bold text-text-primary">{value}</p></div>;
}
