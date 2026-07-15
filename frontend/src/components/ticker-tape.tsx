"use client";

import { useEffect, useRef } from "react";

/**
 * TradingView Ticker Tape — live scrolling prices.
 * Free widget, no API key needed.
 * Shows: MOEX stocks + Crypto + Forex + US Stocks
 */
export function TickerTape() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js";
    script.async = true;
    script.type = "text/javascript";
    script.innerHTML = JSON.stringify({
      symbols: [
        { proName: "MOEX:SBER", title: "Sber" },
        { proName: "MOEX:GAZP", title: "Gazprom" },
        { proName: "MOEX:LKOH", title: "Lukoil" },
        { proName: "BINANCE:BTCUSDT", title: "Bitcoin" },
        { proName: "BINANCE:ETHUSDT", title: "Ethereum" },
        { proName: "BINANCE:SOLUSDT", title: "Solana" },
        { proName: "FX:EURUSD", title: "EUR/USD" },
        { proName: "FX:USDRUB", title: "USD/RUB" },
        { proName: "NASDAQ:AAPL", title: "Apple" },
        { proName: "NASDAQ:NVDA", title: "NVIDIA" },
        { proName: "NASDAQ:TSLA", title: "Tesla" },
        { proName: "TVC:GOLD", title: "Gold" },
      ],
      showSymbolLogo: true,
      isTransparent: true,
      displayMode: "adaptive",
      colorTheme: "dark",
      locale: "ru",
    });

    const wrapper = document.createElement("div");
    wrapper.className = "tradingview-widget-container";
    wrapper.appendChild(script);
    containerRef.current.appendChild(wrapper);

    return () => {
      if (containerRef.current) containerRef.current.innerHTML = "";
    };
  }, []);

  return <div ref={containerRef} className="w-full border-b border-border/30" />;
}
