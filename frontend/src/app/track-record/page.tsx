"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";

interface Summary {
  enough_data: boolean;
  closed_trades: number;
  min_sample?: number;
  notice_ru?: string;
  notice_en?: string;
  win_rate_pct?: number;
  wins?: number;
  losses?: number;
  avg_win_pct?: number;
  avg_loss_pct?: number;
  profit_factor?: number | null;
  expectancy_pct?: number;
  best_pct?: number;
  worst_pct?: number;
  disclaimer_ru?: string;
}

interface Row {
  id: string;
  ticker: string;
  market: string;
  action: string;
  entry: number;
  take_profit: number | null;
  stop_loss: number | null;
  outcome: "tp" | "sl";
  result_pct: number;
  wef_score: number | null;
  closed_at: string | null;
}

const MARKET_LABEL: Record<string, string> = {
  moex: "🇷🇺 MOEX", stocks: "🇺🇸 Акции", binance: "₿ Крипто",
  forex: "💱 Форекс", futures: "🛢 Фьючерсы",
};

export default function TrackRecordPage() {
  const { locale } = useI18n();
  const isRu = locale === "ru";
  const [sum, setSum] = useState<Summary | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [s, l] = await Promise.all([
          fetch("/api/v1/track-record/summary").then((r) => r.json()),
          fetch("/api/v1/track-record/signals?limit=100").then((r) => r.json()),
        ]);
        setSum(s);
        setRows(l.items || []);
      } catch { }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <Link href="/" className="text-sm text-brand-500 hover:underline">
        {isRu ? "← На главную" : "← Home"}
      </Link>

      <h1 className="mt-4 text-3xl font-bold text-text-primary">
        {isRu ? "Track Record" : "Track Record"}
      </h1>
      <p className="mt-2 max-w-2xl text-text-secondary">
        {isRu
          ? "Полный журнал закрытых сигналов — построчно, с результатом каждой сделки. Демо-данные в статистику не входят."
          : "Full log of closed signals — row by row, with each outcome. Demo data is excluded."}
      </p>

      {loading ? (
        <p className="mt-8 text-text-muted">{isRu ? "Загрузка..." : "Loading..."}</p>
      ) : !sum ? (
        <p className="mt-8 text-text-muted">{isRu ? "Данные недоступны" : "Data unavailable"}</p>
      ) : (
        <>
          {/* Aggregate stats — hidden until the sample is meaningful */}
          {sum.enough_data ? (
            <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                [isRu ? "Сделок закрыто" : "Closed trades", String(sum.closed_trades)],
                [isRu ? "Win Rate" : "Win rate", `${sum.win_rate_pct}%`],
                [isRu ? "Profit Factor" : "Profit factor", String(sum.profit_factor ?? "—")],
                [isRu ? "Ожидание/сделку" : "Expectancy", `${sum.expectancy_pct}%`],
                [isRu ? "Средний плюс" : "Avg win", `+${sum.avg_win_pct}%`],
                [isRu ? "Средний минус" : "Avg loss", `−${sum.avg_loss_pct}%`],
                [isRu ? "Лучшая" : "Best", `+${sum.best_pct}%`],
                [isRu ? "Худшая" : "Worst", `${sum.worst_pct}%`],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-border bg-surface-card p-4">
                  <div className="text-xs text-text-muted">{label}</div>
                  <div className="mt-1 text-xl font-bold text-text-primary">{value}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-8 rounded-xl border border-yellow-500/25 bg-yellow-500/5 p-5">
              <div className="text-sm font-bold text-text-primary">
                {isRu ? "Статистики пока нет" : "No statistics yet"}
              </div>
              <p className="mt-2 text-sm text-text-secondary">
                {isRu ? sum.notice_ru : sum.notice_en}
              </p>
              <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-surface">
                <div
                  className="h-full bg-brand-500"
                  style={{ width: `${Math.min(100, (sum.closed_trades / (sum.min_sample || 30)) * 100)}%` }}
                />
              </div>
              <div className="mt-1 text-xs text-text-muted">
                {sum.closed_trades} / {sum.min_sample || 30}
              </div>
            </div>
          )}

          {/* Auditable log */}
          <h2 className="mt-10 text-xl font-bold text-text-primary">
            {isRu ? "Журнал сделок" : "Trade log"} ({rows.length})
          </h2>
          {rows.length === 0 ? (
            <p className="mt-3 text-sm text-text-muted">
              {isRu ? "Закрытых сделок пока нет." : "No closed trades yet."}
            </p>
          ) : (
            <div className="mt-3 overflow-x-auto rounded-xl border border-border bg-surface-card">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead className="border-b border-border text-xs text-text-muted">
                  <tr>
                    <th className="px-4 py-3">{isRu ? "Инструмент" : "Instrument"}</th>
                    <th className="px-4 py-3">{isRu ? "Рынок" : "Market"}</th>
                    <th className="px-4 py-3">{isRu ? "Сторона" : "Side"}</th>
                    <th className="px-4 py-3">{isRu ? "Вход" : "Entry"}</th>
                    <th className="px-4 py-3">WEF</th>
                    <th className="px-4 py-3">{isRu ? "Исход" : "Outcome"}</th>
                    <th className="px-4 py-3">{isRu ? "Результат" : "Result"}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td className="px-4 py-3 font-medium text-text-primary">{r.ticker}</td>
                      <td className="px-4 py-3 text-text-secondary">{MARKET_LABEL[r.market] || r.market}</td>
                      <td className={`px-4 py-3 font-medium ${r.action === "buy" ? "text-green-400" : "text-red-400"}`}>
                        {r.action.toUpperCase()}
                      </td>
                      <td className="px-4 py-3 text-text-secondary">{r.entry}</td>
                      <td className="px-4 py-3 text-text-secondary">{r.wef_score ? `${r.wef_score}%` : "—"}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded px-1.5 py-0.5 text-xs font-bold ${
                          r.outcome === "tp" ? "bg-green-500/15 text-green-400" : "bg-red-500/15 text-red-400"
                        }`}>
                          {r.outcome === "tp" ? "TP" : "SL"}
                        </span>
                      </td>
                      <td className={`px-4 py-3 font-bold ${r.result_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {r.result_pct >= 0 ? "+" : ""}{r.result_pct}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-6 rounded-lg border border-border bg-surface-card p-4 text-xs leading-relaxed text-text-muted">
            {isRu
              ? "Результат каждой сделки считается по уровню, на котором она закрылась (TP или SL), без учёта комиссий и проскальзывания. Демо- и тестовые сигналы исключены. Прошлые результаты не гарантируют будущих. Не является индивидуальной инвестиционной рекомендацией."
              : "Each result is measured at the level that closed the trade (TP or SL), excluding commissions and slippage. Demo and test signals are excluded. Past results do not guarantee future performance. Not personalized investment advice."}
          </div>
        </>
      )}
    </div>
  );
}
