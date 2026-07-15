"use client";

import { useEffect, useRef } from "react";

/**
 * TradingView Advanced Chart — full interactive chart with indicators.
 */
export function TVAdvancedChart({ symbol = "MOEX:SBER", height = 500 }: { symbol?: string; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol,
      interval: "D",
      timezone: "Europe/Moscow",
      theme: "dark",
      style: "1",
      locale: "ru",
      allow_symbol_change: true,
      support_host: "https://www.tradingview.com",
      height,
    });

    const wrapper = document.createElement("div");
    wrapper.className = "tradingview-widget-container";
    wrapper.style.height = `${height}px`;
    wrapper.appendChild(script);
    ref.current.appendChild(wrapper);

    return () => { if (ref.current) ref.current.innerHTML = ""; };
  }, [symbol, height]);

  return <div ref={ref} className="rounded-xl overflow-hidden border border-border" style={{ height }} />;
}

/**
 * TradingView Market Overview — indices + forex + crypto in tabs.
 */
export function TVMarketOverview({ height = 450 }: { height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js";
    script.async = true;
    script.innerHTML = JSON.stringify({
      colorTheme: "dark",
      dateRange: "1M",
      showChart: true,
      locale: "ru",
      isTransparent: true,
      showSymbolLogo: true,
      showFloatingTooltip: true,
      width: "100%",
      height,
      tabs: [
        {
          title: "MOEX",
          symbols: [
            { s: "MOEX:SBER", d: "Сбер" },
            { s: "MOEX:GAZP", d: "Газпром" },
            { s: "MOEX:LKOH", d: "Лукойл" },
            { s: "MOEX:ROSN", d: "Роснефть" },
            { s: "MOEX:GMKN", d: "Норникель" },
            { s: "MOEX:YNDX", d: "Яндекс" },
          ],
        },
        {
          title: "Crypto",
          symbols: [
            { s: "BINANCE:BTCUSDT", d: "Bitcoin" },
            { s: "BINANCE:ETHUSDT", d: "Ethereum" },
            { s: "BINANCE:SOLUSDT", d: "Solana" },
            { s: "BINANCE:BNBUSDT", d: "BNB" },
          ],
        },
        {
          title: "Forex",
          symbols: [
            { s: "FX:EURUSD", d: "EUR/USD" },
            { s: "FX:GBPUSD", d: "GBP/USD" },
            { s: "FX:USDJPY", d: "USD/JPY" },
            { s: "FX:USDRUB", d: "USD/RUB" },
          ],
        },
        {
          title: "US Stocks",
          symbols: [
            { s: "NASDAQ:AAPL", d: "Apple" },
            { s: "NASDAQ:NVDA", d: "NVIDIA" },
            { s: "NASDAQ:TSLA", d: "Tesla" },
            { s: "NASDAQ:MSFT", d: "Microsoft" },
          ],
        },
      ],
    });

    const wrapper = document.createElement("div");
    wrapper.className = "tradingview-widget-container";
    wrapper.appendChild(script);
    ref.current.appendChild(wrapper);

    return () => { if (ref.current) ref.current.innerHTML = ""; };
  }, [height]);

  return <div ref={ref} className="rounded-xl overflow-hidden border border-border" />;
}

/**
 * TradingView Economic Calendar — upcoming NFP, CPI, rates.
 */
export function TVEconomicCalendar({ height = 400 }: { height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-events.js";
    script.async = true;
    script.innerHTML = JSON.stringify({
      colorTheme: "dark",
      isTransparent: true,
      width: "100%",
      height,
      locale: "ru",
      importanceFilter: "0,1",
      countryFilter: "ru,us,eu,gb,jp,cn",
    });

    const wrapper = document.createElement("div");
    wrapper.className = "tradingview-widget-container";
    wrapper.appendChild(script);
    ref.current.appendChild(wrapper);

    return () => { if (ref.current) ref.current.innerHTML = ""; };
  }, [height]);

  return <div ref={ref} className="rounded-xl overflow-hidden border border-border" />;
}

/**
 * TradingView Mini Chart — small chart for cards/tables.
 */
export function TVMiniChart({ symbol = "MOEX:SBER", width = 350, height = 220 }: { symbol?: string; width?: number; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js";
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbol,
      width,
      height,
      locale: "ru",
      dateRange: "1M",
      colorTheme: "dark",
      isTransparent: true,
      autosize: false,
      chartOnly: false,
    });

    const wrapper = document.createElement("div");
    wrapper.className = "tradingview-widget-container";
    wrapper.appendChild(script);
    ref.current.appendChild(wrapper);

    return () => { if (ref.current) ref.current.innerHTML = ""; };
  }, [symbol]);

  return <div ref={ref} className="rounded-xl overflow-hidden" />;
}
