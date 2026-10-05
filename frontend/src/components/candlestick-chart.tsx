"use client";

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";

/**
 * Candlestick chart on Apache ECharts.
 *
 * Migrated off lightweight-charts. That library is Apache-2.0, but its terms
 * additionally require a visible link to tradingview.com on a user-facing page, and
 * it satisfies that by drawing a TradingView logo on every chart (`attributionLogo`,
 * on by default). ECharts' Apache-2.0 has no such user-facing requirement — the
 * NOTICE obligation is satisfied in the project's licence notices, not by a badge
 * over the price.
 *
 * Same public props as before, so call sites did not change.
 */

interface CandleData {
  time: string; // "2026-01-15"
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface MarkerData {
  time: string;
  position: "aboveBar" | "belowBar";
  color: string;
  shape: "arrowUp" | "arrowDown" | "circle";
  text: string;
}

interface Props {
  data: CandleData[];
  markers?: MarkerData[];
  entryPrice?: number;
  takeProfit?: number;
  stopLoss?: number;
  height?: number;
  ticker?: string;
}

const UP = "#10b981";
const DOWN = "#ef4444";
const GRID = "rgba(255,255,255,0.04)";
const AXIS = "rgba(255,255,255,0.1)";

export default function CandlestickChart({
  data, markers, entryPrice, takeProfit, stopLoss, height = 400, ticker,
}: Props) {
  const option = useMemo(() => {
    const dates = data.map(d => d.time);
    // ECharts candlestick order is [open, close, low, high] — not OHLC.
    const ohlc = data.map(d => [d.open, d.close, d.low, d.high]);
    const hasVolume = data.some(d => d.volume);
    const volume = data.map(d => ({
      value: d.volume ?? 0,
      itemStyle: { color: d.close >= d.open ? `${UP}30` : `${DOWN}30` },
    }));

    const priceLines = [
      entryPrice ? { y: entryPrice, color: "#3b82f6", label: "Вход", dash: [6, 4] } : null,
      takeProfit ? { y: takeProfit, color: UP, label: "Цель", dash: [2, 4] } : null,
      stopLoss ? { y: stopLoss, color: DOWN, label: "Стоп", dash: [2, 4] } : null,
    ].filter(Boolean) as { y: number; color: string; label: string; dash: number[] }[];

    const markPoints = (markers || []).map(m => {
      const i = dates.indexOf(m.time);
      const bar = data[i];
      if (i < 0 || !bar) return null;
      const above = m.position === "aboveBar";
      return {
        name: m.text,
        coord: [i, above ? bar.high : bar.low],
        symbol: m.shape === "arrowDown" ? "arrow" : "pin",
        symbolRotate: m.shape === "arrowDown" ? 180 : 0,
        symbolSize: 18,
        itemStyle: { color: m.color },
        label: { show: !!m.text, formatter: m.text, fontSize: 10, color: "#e2e8f0",
                 position: above ? "top" : "bottom" },
      };
    }).filter(Boolean);

    return {
      animation: false,
      backgroundColor: "transparent",
      textStyle: { color: "#9ca3af" },
      grid: hasVolume
        ? [{ left: 52, right: 16, top: 16, height: "62%" },
           { left: 52, right: 16, top: "76%", height: "16%" }]
        : [{ left: 52, right: 16, top: 16, bottom: 48 }],
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        backgroundColor: "rgba(10,22,40,0.95)",
        borderColor: AXIS,
        textStyle: { color: "#e2e8f0", fontSize: 11 },
      },
      xAxis: hasVolume
        ? [{ type: "category", data: dates, gridIndex: 0, axisLine: { lineStyle: { color: AXIS } },
             axisLabel: { show: false }, splitLine: { show: false } },
           { type: "category", data: dates, gridIndex: 1, axisLine: { lineStyle: { color: AXIS } },
             axisLabel: { fontSize: 10 }, splitLine: { show: false } }]
        : [{ type: "category", data: dates, axisLine: { lineStyle: { color: AXIS } },
             axisLabel: { fontSize: 10 }, splitLine: { show: false } }],
      yAxis: hasVolume
        ? [{ scale: true, gridIndex: 0, position: "right",
             axisLine: { lineStyle: { color: AXIS } }, axisLabel: { fontSize: 10 },
             splitLine: { lineStyle: { color: GRID } } },
           { gridIndex: 1, position: "right", axisLabel: { show: false },
             axisLine: { show: false }, splitLine: { show: false } }]
        : [{ scale: true, position: "right", axisLine: { lineStyle: { color: AXIS } },
             axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: GRID } } }],
      dataZoom: [
        { type: "inside", xAxisIndex: hasVolume ? [0, 1] : [0] },
      ],
      series: [
        {
          type: "candlestick",
          data: ohlc,
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: { color: UP, color0: DOWN, borderColor: UP, borderColor0: DOWN },
          markPoint: markPoints.length ? { data: markPoints } : undefined,
          markLine: priceLines.length
            ? {
                symbol: "none",
                label: { formatter: (p: any) => p.name, position: "insideEndTop",
                         fontSize: 10, color: "#e2e8f0" },
                data: priceLines.map(l => ({
                  name: `${l.label} ${l.y}`,
                  yAxis: l.y,
                  lineStyle: { color: l.color, width: 1.5, type: l.dash },
                })),
              }
            : undefined,
        },
        ...(hasVolume
          ? [{ type: "bar", data: volume, xAxisIndex: 1, yAxisIndex: 1, barWidth: "60%" }]
          : []),
      ],
    };
  }, [data, markers, entryPrice, takeProfit, stopLoss]);

  if (!data.length) {
    return (
      <div className="rounded-xl border border-border bg-surface-card p-8 text-center text-sm text-text-muted">
        Нет данных для графика
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface-card">
      {ticker && (
        <div className="border-b border-border px-4 py-2">
          <span className="text-sm font-bold text-text-primary">{ticker}</span>
          <span className="ml-2 text-xs text-text-muted">{data.length} свечей</span>
        </div>
      )}
      <ReactECharts
        option={option}
        style={{ height }}
        notMerge
        lazyUpdate
        opts={{ renderer: "canvas" }}
      />
    </div>
  );
}
