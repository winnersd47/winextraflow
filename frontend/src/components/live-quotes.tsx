"use client";

import { useEffect, useState } from "react";

/**
 * Live quotes grid, served by /api/v1/public/ticker-tape.
 *
 * Replaces the TradingView Market Overview widget, whose terms require a visible
 * attribution link. Every quote here already came from a source the platform uses
 * (MOEX ISS, Binance, Yahoo), so the third-party script added nothing but a badge
 * and an external asset that loads unreliably on RU networks.
 *
 * The change column is labelled per instrument because the three sources measure
 * three different things: Binance gives a rolling 24h figure, Yahoo compares with
 * the previous daily close, and MOEX has no change field so it is derived from the
 * session open. Presenting them under one heading would be a quiet lie.
 */

type Item = {
  ticker: string;
  title: string;
  currency: string;
  price: number;
  change_pct: number | null;
  change_window: string | null;
  source: string | null;
};

const WINDOW_RU: Record<string, string> = {
  "24h": "за 24ч",
  prev_close: "к пред. закрытию",
  session: "с открытия",
};

const REFRESH_MS = 60_000;

export function LiveQuotesGrid({ isRu = true }: { isRu?: boolean }) {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await fetch("/api/v1/public/ticker-tape");
        if (!r.ok) return;
        const d = await r.json();
        if (alive) setItems(d.items || []);
      } catch {
        // Keep whatever we had: a blank grid reads as "market closed".
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-10">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  if (!items.length) {
    return (
      <p className="py-8 text-center text-sm text-text-muted">
        {isRu ? "Котировки недоступны — источники не ответили." : "No quotes — sources did not respond."}
      </p>
    );
  }

  return (
    <div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {items.map(it => {
          const up = (it.change_pct ?? 0) >= 0;
          return (
            <div key={it.ticker} className="rounded-lg border border-border bg-surface p-3">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-medium text-text-primary">{it.title}</span>
                <span className="text-xs text-text-muted">{it.ticker}</span>
              </div>
              <div className="mt-1 text-lg font-semibold text-text-primary">
                {it.price.toLocaleString("ru-RU", { maximumFractionDigits: 2 })}
                <span className="ml-0.5 text-sm text-text-muted">{it.currency}</span>
              </div>
              {it.change_pct !== null ? (
                <div className={`text-xs ${up ? "text-green-400" : "text-red-400"}`}>
                  {up ? "+" : ""}
                  {it.change_pct.toFixed(2)}%
                  <span className="ml-1 text-text-muted">
                    {WINDOW_RU[it.change_window || ""] || ""}
                  </span>
                </div>
              ) : (
                <div className="text-xs text-text-muted">
                  {isRu ? "изменение недоступно" : "change unavailable"}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-xs text-text-muted">
        {isRu
          ? "Источники: MOEX ISS, Binance, Yahoo Finance. Период изменения указан у каждой позиции — источники считают его по-разному."
          : "Sources: MOEX ISS, Binance, Yahoo Finance. The change window is stated per row because the sources measure it differently."}
      </p>
    </div>
  );
}
