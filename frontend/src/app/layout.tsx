import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import { ThemeProvider } from "@/lib/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "WinExtraFlow — Trading Signals with AI Rating",
    template: "%s | WinExtraFlow",
  },
  description: "Aggregate trading signals from TradingView & Telegram, rate with AI, auto-trade on exchanges. Free to start.",
  keywords: ["trading signals", "AI rating", "copy trading", "backtesting", "crypto signals", "TradingView", "Telegram signals"],
  authors: [{ name: "WinExtraFlow" }],
  openGraph: {
    title: "WinExtraFlow — Trading Signals with AI Rating",
    description: "Aggregate signals, rate with AI, auto-trade. Free to start.",
    url: "https://winextraflow.com",
    siteName: "WinExtraFlow",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "WinExtraFlow — Trading Signals with AI Rating",
    description: "Aggregate signals, rate with AI, auto-trade. Free to start.",
  },
  robots: { index: true, follow: true },
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
