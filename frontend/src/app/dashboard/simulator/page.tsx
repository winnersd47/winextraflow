"use client";

/**
 * Practice terminal. Chart, order form, open positions, history.
 *
 * Every number here comes from the simulator API, which trades on the platform's
 * own price feed and cannot reach a broker. The disclosure the backend returns is
 * rendered verbatim and not collapsed behind a toggle: a terminal that looks like
 * a real one is exactly where a person would otherwise assume these fills are
 * achievable.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { api, type SimPortfolio, type SimTrade } from "@/lib/api";

const CandlestickChart = dynamic(() => import("@/components/candlestick-chart"), { ssr: false });

type Quote = {
  ticker: string; price: number; source: string; asset_class: string;
  commission_pct: number; delayed: boolean;
};
type Candle = { time: string; open: number; high: number; low: number; close: number; volume?: number };

const PRESETS = ["SBER", "GAZP", "LKOH", "BTCUSDT", "ETHUSDT", "AAPL"];
const POLL_MS = 20_000;

function money(v: number | null | undefined, sign = false): string {
  if (v === null || v === undefined) return "—";
  const s = sign && v > 0 ? "+" : "";
  return s + v.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

function pnlClass(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-gray-400";
  return v > 0 ? "text-green-400" : v < 0 ? "text-red-400" : "text-gray-400";
}

export default function SimulatorPage() {
  const [portfolio, setPortfolio] = useState<SimPortfolio | null>(null);
  const [history, setHistory] = useState<SimTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [ticker, setTicker] = useState("SBER");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [chartErr, setChartErr] = useState<string | null>(null);

  const [action, setAction] = useState<"buy" | "sell">("buy");
  const [sizeMode, setSizeMode] = useState<"risk" | "units">("risk");
  const [units, setUnits] = useState("");
  const [tp, setTp] = useState("");
  const [sl, setSl] = useState("");
  const [busy, setBusy] = useState(false);

  const loadPortfolio = useCallback(async () => {
    try {
      const [p, h] = await Promise.all([api.getSimPortfolio(), api.getSimHistory(undefined, 30)]);
      setPortfolio(p);
      setHistory(h.trades);
      setErr(null);
    } catch (e: any) {
      setErr(e?.message || "Не удалось загрузить счёт");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadInstrument = useCallback(async (t: string) => {
    setChartErr(null);
    const [q, c] = await Promise.allSettled([api.getSimQuote(t), api.getSimCandles(t, 120)]);
    if (q.status === "fulfilled") setQuote(q.value);
    else { setQuote(null); setChartErr(`Нет цены по ${t}`); }
    if (c.status === "fulfilled") {
      setCandles(c.value.candles.map(x => ({
        time: (x.date || x.time || "").slice(0, 10),
        open: x.open, high: x.high, low: x.low, close: x.close, volume: x.volume,
      })));
    } else {
      setCandles([]);
    }
  }, []);

  useEffect(() => { loadPortfolio(); }, [loadPortfolio]);
  useEffect(() => { loadInstrument(ticker); }, [ticker, loadInstrument]);

  // Positions carry live P&L, so the view goes stale on its own.
  useEffect(() => {
    const id = setInterval(() => { loadPortfolio(); loadInstrument(ticker); }, POLL_MS);
    return () => clearInterval(id);
  }, [loadPortfolio, loadInstrument, ticker]);

  // Mirrors the backend's fixed-fractional sizing so the form can show the size
  // before the request. The backend recomputes it and remains the authority.
  const preview = useMemo(() => {
    if (!portfolio || !quote) return null;
    const equity = portfolio.account.balance;
    const stop = parseFloat(sl);
    if (sizeMode === "units") {
      const u = parseFloat(units);
      if (!u || u <= 0) return null;
      const value = u * quote.price;
      return {
        units: u, value,
        risk: stop ? Math.abs(quote.price - stop) * u : null,
        commission: value * quote.commission_pct / 100,
        capped: value > equity * 0.25,
      };
    }
    if (!stop || stop <= 0) return null;
    const stopPct = Math.abs(quote.price - stop) / quote.price;
    if (stopPct <= 0) return null;
    const budget = equity * (portfolio.account.risk_per_trade_pct / 100);
    const full = budget / stopPct;
    const value = Math.min(full, equity * 0.25);
    return {
      units: value / quote.price, value,
      risk: value * stopPct,          // actual, not the budget
      commission: value * quote.commission_pct / 100,
      capped: value < full,
    };
  }, [portfolio, quote, sl, units, sizeMode]);

  async function submit() {
    if (!quote) return;
    setBusy(true); setErr(null); setNotice(null);
    try {
      const r = await api.openSimPosition({
        ticker,
        action,
        units: sizeMode === "units" ? parseFloat(units) : undefined,
        take_profit: tp ? parseFloat(tp) : undefined,
        stop_loss: sl ? parseFloat(sl) : undefined,
      });
      setNotice(
        `Открыто ${r.trade.units.toFixed(4).replace(/\.?0+$/, "")} ${ticker} по ${r.fill_price} ` +
        `(${r.price_source}), комиссия ${money(r.commission)}`
      );
      setUnits(""); setTp(""); setSl("");
      await loadPortfolio();
    } catch (e: any) {
      setErr(e?.message || "Не удалось открыть позицию");
    } finally {
      setBusy(false);
    }
  }

  async function close(id: string) {
    setBusy(true); setErr(null); setNotice(null);
    try {
      const r = await api.closeSimPosition(id);
      setNotice(
        `Закрыто по ${r.close_price}: результат ${money(r.gross_pnl, true)}, ` +
        `комиссия ${money(r.commission)}, итого ${money(r.net_pnl, true)}`
      );
      await loadPortfolio();
    } catch (e: any) {
      setErr(e?.message || "Не удалось закрыть позицию");
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    if (!confirm("Удалить все сделки и вернуть стартовый баланс?")) return;
    setBusy(true);
    try {
      const r = await api.resetSimAccount();
      setNotice(`Счёт сброшен: удалено сделок ${r.deleted_trades}, баланс ${money(r.balance)}`);
      await loadPortfolio();
    } catch (e: any) {
      setErr(e?.message || "Не удалось сбросить счёт");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <div className="p-6 text-gray-400">Загрузка терминала…</div>;
  }

  const acc = portfolio?.account;
  const cur = acc?.currency === "RUB" ? "₽" : "$";

  return (
    <div className="p-4 md:p-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Симулятор</h1>
          <p className="text-sm text-gray-400">
            Тренировочный терминал на котировках платформы. Реальные заявки не отправляются.
          </p>
        </div>
        <button onClick={reset} disabled={busy}
                className="px-3 py-1.5 text-sm rounded-lg border border-white/10 text-gray-300 hover:bg-white/5 disabled:opacity-50">
          Сбросить счёт
        </button>
      </div>

      {/* Rendered as given by the backend, always visible. */}
      {portfolio && (
        <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-3 text-xs text-yellow-200/90 leading-relaxed">
          {portfolio.disclosure_ru}
        </div>
      )}

      {err && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{err}</div>
      )}
      {notice && (
        <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-300">{notice}</div>
      )}

      {/* Account */}
      {acc && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { l: "Баланс", v: `${money(acc.balance)} ${cur}`, c: "text-white" },
            { l: "Средства с позициями", v: `${money(acc.equity)} ${cur}`, c: "text-white" },
            { l: "Нереализованный", v: `${money(portfolio!.unrealised_pnl, true)} ${cur}`, c: pnlClass(portfolio!.unrealised_pnl) },
            { l: "Реализованный", v: `${money(portfolio!.realised_pnl, true)} ${cur}`, c: pnlClass(portfolio!.realised_pnl) },
            { l: "Позиций", v: `${portfolio!.open_count} / ${portfolio!.max_open}`, c: "text-white" },
          ].map(s => (
            <div key={s.l} className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
              <div className="text-[11px] uppercase tracking-wide text-gray-500">{s.l}</div>
              <div className={`text-lg font-semibold ${s.c}`}>{s.v}</div>
            </div>
          ))}
        </div>
      )}

      {/* Win rate is withheld below the sample floor, same rule the platform
          applies to its own record. */}
      {portfolio && !portfolio.enough_data && portfolio.closed_count > 0 && (
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs text-gray-400">
          {portfolio.notice_ru}
        </div>
      )}
      {portfolio?.enough_data && (
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-sm text-gray-300">
          Win rate: <span className="font-semibold text-white">{portfolio.win_rate_pct}%</span>
          {" "}на {portfolio.closed_count} закрытых сделках
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Chart */}
        <div className="lg:col-span-2 rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <input
              value={ticker}
              onChange={e => setTicker(e.target.value.toUpperCase())}
              className="w-28 px-2 py-1.5 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono"
            />
            {PRESETS.map(p => (
              <button key={p} onClick={() => setTicker(p)}
                      className={`px-2 py-1 text-xs rounded-md border ${
                        ticker === p ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-300"
                                     : "border-white/10 text-gray-400 hover:bg-white/5"}`}>
                {p}
              </button>
            ))}
            {quote && (
              <div className="ml-auto text-right">
                <div className="text-lg font-semibold text-white font-mono">{quote.price}</div>
                <div className="text-[11px] text-gray-500">
                  {quote.source}
                  {quote.delayed && <span className="text-yellow-400/80"> · задержка ~15 мин</span>}
                </div>
              </div>
            )}
          </div>
          {chartErr && <div className="text-sm text-red-300 mb-2">{chartErr}</div>}
          {candles.length > 0 ? (
            <CandlestickChart data={candles} height={380} ticker={ticker}
                              entryPrice={quote?.price}
                              takeProfit={tp ? parseFloat(tp) : undefined}
                              stopLoss={sl ? parseFloat(sl) : undefined} />
          ) : (
            <div className="h-[380px] flex items-center justify-center text-gray-500 text-sm">
              Нет свечей по {ticker}
            </div>
          )}
        </div>

        {/* Order form */}
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
          <div className="text-sm font-semibold text-white">Заявка</div>

          <div className="grid grid-cols-2 gap-2">
            {(["buy", "sell"] as const).map(a => (
              <button key={a} onClick={() => setAction(a)}
                      className={`py-2 rounded-lg text-sm font-medium border ${
                        action === a
                          ? a === "buy" ? "border-green-400/40 bg-green-400/10 text-green-300"
                                        : "border-red-400/40 bg-red-400/10 text-red-300"
                          : "border-white/10 text-gray-400 hover:bg-white/5"}`}>
                {a === "buy" ? "Купить" : "Продать"}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-2">
            {([["risk", "От риска"], ["units", "Количеством"]] as const).map(([m, l]) => (
              <button key={m} onClick={() => setSizeMode(m)}
                      className={`py-1.5 rounded-lg text-xs border ${
                        sizeMode === m ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-300"
                                       : "border-white/10 text-gray-400 hover:bg-white/5"}`}>
                {l}
              </button>
            ))}
          </div>

          {sizeMode === "units" && (
            <label className="block">
              <span className="text-[11px] uppercase tracking-wide text-gray-500">Количество</span>
              <input value={units} onChange={e => setUnits(e.target.value)} inputMode="decimal"
                     className="mt-1 w-full px-2 py-1.5 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono" />
            </label>
          )}

          <label className="block">
            <span className="text-[11px] uppercase tracking-wide text-gray-500">
              Стоп-лосс {sizeMode === "risk" && <span className="text-gray-600">— обязателен для расчёта</span>}
            </span>
            <input value={sl} onChange={e => setSl(e.target.value)} inputMode="decimal"
                   className="mt-1 w-full px-2 py-1.5 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono" />
          </label>

          <label className="block">
            <span className="text-[11px] uppercase tracking-wide text-gray-500">Тейк-профит</span>
            <input value={tp} onChange={e => setTp(e.target.value)} inputMode="decimal"
                   className="mt-1 w-full px-2 py-1.5 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono" />
          </label>

          {preview && (
            <div className="rounded-lg border border-white/10 bg-black/20 p-2.5 space-y-1 text-xs">
              <Row l="Количество" v={preview.units.toFixed(preview.units < 1 ? 6 : 0)} />
              <Row l="Объём" v={`${money(preview.value)} ${cur}`} />
              <Row l="Риск при стопе" v={preview.risk !== null ? `${money(preview.risk)} ${cur}` : "не задан"} />
              <Row l="Комиссия входа" v={`${money(preview.commission)} ${cur}`} />
              {preview.capped && (
                <div className="text-yellow-400/90 pt-1">
                  Позиция урезана до 25% счёта — риск поэтому меньше заданного
                </div>
              )}
            </div>
          )}

          <button onClick={submit} disabled={busy || !quote || !preview}
                  className="w-full py-2.5 rounded-lg bg-cyan-500/20 border border-cyan-400/30 text-cyan-200 text-sm font-medium hover:bg-cyan-500/30 disabled:opacity-40">
            {busy ? "…" : `${action === "buy" ? "Купить" : "Продать"} ${ticker}`}
          </button>
          {quote && (
            <p className="text-[11px] text-gray-500 leading-relaxed">
              {portfolio?.commission_note_ru} Исполнение по последней цене — в реальном
              счёте вход был бы хуже на спред.
            </p>
          )}
        </div>
      </div>

      {/* Open positions */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden">
        <div className="px-4 py-3 text-sm font-semibold text-white border-b border-white/5">
          Открытые позиции
        </div>
        {portfolio && portfolio.positions.length === 0 ? (
          <div className="px-4 py-6 text-sm text-gray-500">Открытых позиций нет</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-[11px] uppercase tracking-wide text-gray-500">
                <tr className="border-b border-white/5">
                  {["Инструмент", "Сторона", "Вход", "Текущая", "Кол-во", "Стоп", "Тейк", "P&L", ""]
                    .map(h => <th key={h} className="px-4 py-2 text-left font-medium">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {portfolio?.positions.map(p => (
                  <tr key={p.id} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-2.5 font-mono text-white">{p.ticker}</td>
                    <td className={`px-4 py-2.5 ${p.action === "buy" ? "text-green-400" : "text-red-400"}`}>
                      {p.action === "buy" ? "покупка" : "продажа"}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-gray-300">{p.entry_price}</td>
                    <td className="px-4 py-2.5 font-mono text-gray-300">
                      {p.price_unavailable ? <span className="text-yellow-400/80">нет цены</span> : p.current_price}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-gray-400">
                      {p.units < 1 ? p.units.toFixed(6) : p.units.toFixed(0)}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-gray-500">{p.stop_loss ?? "—"}</td>
                    <td className="px-4 py-2.5 font-mono text-gray-500">{p.take_profit ?? "—"}</td>
                    <td className={`px-4 py-2.5 font-mono ${pnlClass(p.unrealised_pnl)}`}>
                      {money(p.unrealised_pnl, true)}
                      {p.unrealised_pct !== null && p.unrealised_pct !== undefined && (
                        <span className="text-gray-500"> ({p.unrealised_pct > 0 ? "+" : ""}{p.unrealised_pct}%)</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button onClick={() => close(p.id)} disabled={busy}
                              className="px-2.5 py-1 text-xs rounded-md border border-white/10 text-gray-300 hover:bg-white/5 disabled:opacity-50">
                        Закрыть
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* History */}
      {history.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden">
          <div className="px-4 py-3 text-sm font-semibold text-white border-b border-white/5">
            История ({history.length})
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-[11px] uppercase tracking-wide text-gray-500">
                <tr className="border-b border-white/5">
                  {["Инструмент", "Сторона", "Вход", "Выход", "Результат", "Закрыта"]
                    .map(h => <th key={h} className="px-4 py-2 text-left font-medium">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {history.map(t => (
                  <tr key={t.id} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-2 font-mono text-white">{t.ticker}</td>
                    <td className={`px-4 py-2 ${t.action === "buy" ? "text-green-400" : "text-red-400"}`}>
                      {t.action === "buy" ? "покупка" : "продажа"}
                    </td>
                    <td className="px-4 py-2 font-mono text-gray-400">{t.entry_price}</td>
                    <td className="px-4 py-2 font-mono text-gray-400">{t.close_price}</td>
                    <td className={`px-4 py-2 font-mono ${pnlClass(t.result_money)}`}>
                      {money(t.result_money, true)} {cur}
                      <span className="text-gray-500"> ({t.result_pct! > 0 ? "+" : ""}{t.result_pct}%)</span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 text-xs">
                      {t.closed_at ? new Date(t.closed_at).toLocaleString("ru-RU") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ l, v }: { l: string; v: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-gray-500">{l}</span>
      <span className="font-mono text-gray-200">{v}</span>
    </div>
  );
}
