"use client";

import { useEffect, useRef } from "react";

interface CandleData {
  time: string; // "2024-01-15"
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

export default function CandlestickChart({
  data, markers, entryPrice, takeProfit, stopLoss, height = 400, ticker,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    let disposed = false;

    import("lightweight-charts").then(({ createChart, CrosshairMode, LineStyle }) => {
      if (disposed || !containerRef.current) return;

      // Clean previous
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }

      const chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height,
        layout: {
          background: { color: "transparent" } as any,
          textColor: "#9ca3af",
        },
        grid: {
          vertLines: { color: "rgba(255,255,255,0.04)" },
          horzLines: { color: "rgba(255,255,255,0.04)" },
        },
        crosshair: { mode: CrosshairMode.Normal },
        rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
        timeScale: {
          borderColor: "rgba(255,255,255,0.1)",
          timeVisible: true,
        },
      });

      chartRef.current = chart;

      // Candlestick series
      const candleSeries = chart.addCandlestickSeries({
        upColor: "#10b981",
        downColor: "#ef4444",
        borderUpColor: "#10b981",
        borderDownColor: "#ef4444",
        wickUpColor: "#10b981",
        wickDownColor: "#ef4444",
      });

      candleSeries.setData(data as any);

      // Entry/TP/SL price lines
      if (entryPrice) {
        candleSeries.createPriceLine({
          price: entryPrice,
          color: "#3b82f6",
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: "Entry",
        });
      }
      if (takeProfit) {
        candleSeries.createPriceLine({
          price: takeProfit,
          color: "#10b981",
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: true,
          title: "TP",
        });
      }
      if (stopLoss) {
        candleSeries.createPriceLine({
          price: stopLoss,
          color: "#ef4444",
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: true,
          title: "SL",
        });
      }

      // Markers (buy/sell signals)
      if (markers && markers.length > 0) {
        candleSeries.setMarkers(markers as any);
      }

      // Volume
      if (data.some(d => d.volume)) {
        const volumeSeries = chart.addHistogramSeries({
          color: "#10b98140",
          priceFormat: { type: "volume" },
          priceScaleId: "",
        } as any);
        volumeSeries.priceScale().applyOptions({
          scaleMargins: { top: 0.8, bottom: 0 },
        });
        volumeSeries.setData(
          data.filter(d => d.volume).map(d => ({
            time: d.time,
            value: d.volume!,
            color: d.close >= d.open ? "#10b98130" : "#ef444430",
          })) as any
        );
      }

      chart.timeScale().fitContent();

      // Resize observer
      const resizeObserver = new ResizeObserver(() => {
        if (containerRef.current && chartRef.current) {
          chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
        }
      });
      resizeObserver.observe(containerRef.current);

      return () => {
        resizeObserver.disconnect();
      };
    });

    return () => {
      disposed = true;
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [data, markers, entryPrice, takeProfit, stopLoss, height]);

  return (
    <div className="rounded-xl border border-border bg-surface-card overflow-hidden">
      {ticker && (
        <div className="px-4 py-2 border-b border-border">
          <span className="text-sm font-bold text-text-primary">{ticker}</span>
          <span className="ml-2 text-xs text-text-muted">{data.length} candles</span>
        </div>
      )}
      <div ref={containerRef} style={{ height }} />
    </div>
  );
}
