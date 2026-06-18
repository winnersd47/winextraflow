import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import { ThemeProvider } from "@/lib/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "WinExtraFlow — AI Trading Signals | WEF Score Rating",
    template: "%s | WinExtraFlow",
  },
  description: "AI-платформа торговых сигналов. 200 AI-компонентов оценивают каждый сигнал по 9 факторам (WEF Score). MOEX, крипто, форекс. Бэктест на реальных свечах. Копитрейдинг. Бесплатный тариф.",
  keywords: [
    "trading signals", "AI rating", "WEF Score", "copy trading", "backtesting",
    "crypto signals", "MOEX", "forex signals", "TradingView", "Telegram signals",
    "торговые сигналы", "AI оценка", "копитрейдинг", "бэктестинг", "сигналы крипто",
    "сигналы MOEX", "скринер акций", "тепловая карта",
  ],
  authors: [{ name: "WinExtraFlow" }],
  metadataBase: new URL("https://winextraflow.com"),
  alternates: { canonical: "/" },
  openGraph: {
    title: "WinExtraFlow — AI Trading Signals with WEF Score",
    description: "200 AI components rate every signal by 9 factors. MOEX + Crypto + Forex. Free tier available. Backtest on real candles. Copy trading.",
    url: "https://winextraflow.com",
    siteName: "WinExtraFlow",
    type: "website",
    locale: "ru_RU",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "WinExtraFlow — AI Trading Signals" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "WinExtraFlow — AI Trading Signals",
    description: "200 AI components. 9 factors. WEF Score 0-100. Free to start.",
    images: ["/og-image.png"],
  },
  robots: { index: true, follow: true },
  verification: {
    yandex: "",  // Add Yandex.Webmaster verification code
    google: "",  // Add Google Search Console verification code
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru" className="dark" suppressHydrationWarning>
      <head>
        <link rel="manifest" href="/manifest.json" />
        <link rel="canonical" href="https://winextraflow.com" />
        {/* Yandex.Metrika — replace XXXXXXXX with your counter ID */}
        <script dangerouslySetInnerHTML={{ __html: `
          (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
          m[i].l=1*new Date();
          for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
          k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
          (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
          // ym(XXXXXXXX, "init", { clickmap:true, trackLinks:true, accurateTrackBounce:true, webvisor:true });
        `}} />
        {/* Google Analytics — replace G-XXXXXXXXXX with your Measurement ID */}
        {/* <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX" />
        <script dangerouslySetInnerHTML={{ __html: `
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', 'G-XXXXXXXXXX');
        `}} /> */}
        <meta name="theme-color" content="#10b981" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="WinExtraFlow" />
        <script dangerouslySetInnerHTML={{ __html: `
          try { const t = localStorage.getItem('theme');
            if (t === 'light') document.documentElement.classList.remove('dark');
          } catch(e) {}
          if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').catch(function(){});
          }
        `}} />
      </head>
      <body>
        <I18nProvider>
          <ThemeProvider>
            <AuthProvider>{children}</AuthProvider>
          </ThemeProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
