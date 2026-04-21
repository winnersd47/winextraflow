"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import React from "react";

export type Locale = "ru" | "en";

const translations: Record<Locale, Record<string, string>> = {
  ru: {
    // Auth
    "auth.signIn": "Войти",
    "auth.signingIn": "Вход...",
    "auth.signInTitle": "Вход в аккаунт",
    "auth.register": "Регистрация",
    "auth.registering": "Создание...",
    "auth.createAccount": "Создать аккаунт",
    "auth.email": "Email",
    "auth.password": "Пароль",
    "auth.username": "Имя пользователя",
    "auth.referralCode": "Реферальный код (необязательно)",
    "auth.noAccount": "Нет аккаунта?",
    "auth.haveAccount": "Уже есть аккаунт?",
    "auth.logout": "Выйти",

    // Sidebar
    "nav.signals": "Сигналы",
    "nav.leaderboard": "Лидерборд",
    "nav.backtest": "Бэктест",
    "nav.marketplace": "Маркетплейс",
    "nav.copyTrading": "Копитрейдинг",
    "nav.execution": "Исполнение",
    "nav.referrals": "Рефералы",
    "nav.profile": "Профиль",

    // Signals
    "signals.title": "Лента сигналов",
    "signals.total": "сигналов",
    "signals.live": "В реальном времени",
    "signals.reconnecting": "Переподключение...",
    "signals.filterTicker": "Фильтр по тикеру...",
    "signals.all": "Все",
    "signals.active": "Активные",
    "signals.tpHit": "TP",
    "signals.slHit": "SL",
    "signals.expired": "Истекшие",
    "signals.empty": "Сигналов не найдено",
    "signals.emptyHint": "Сигналы появятся здесь при получении от TradingView или Telegram",
    "signals.entry": "Вход",
    "signals.status": "Статус",
    "signals.back": "Назад",
    "signals.aiRating": "AI рейтинг",
    "signals.result": "Результат",
    "signals.closedAt": "Закрыт по цене",

    // Signal statuses
    "status.active": "Активный",
    "status.closed_tp": "TP",
    "status.closed_sl": "SL",
    "status.closed_manual": "Закрыт",
    "status.expired": "Истёк",

    // Providers
    "providers.leaderboard": "Лидерборд провайдеров",
    "providers.subtitle": "Топ провайдеров по AI рейтингу",
    "providers.empty": "Нет оценённых провайдеров",
    "providers.emptyHint": "Провайдеры появятся после закрытия сигналов с AI рейтингом",
    "providers.winRate": "Винрейт",
    "providers.sharpe": "Шарп",
    "providers.drawdown": "Просадка",
    "providers.aiScore": "AI рейтинг",
    "providers.signals": "сигналов",

    // Backtest
    "backtest.title": "Бэктестинг",
    "backtest.subtitle": "Тестирование сигналов на исторических данных",
    "backtest.run": "Запустить",
    "backtest.running": "Анализ...",
    "backtest.providerId": "ID провайдера (необязательно)",
    "backtest.ticker": "Тикер (необязательно)",
    "backtest.capital": "Капитал",
    "backtest.totalReturn": "Общая доходность",
    "backtest.winRate": "Винрейт",
    "backtest.sharpe": "Коэффициент Шарпа",
    "backtest.maxDrawdown": "Макс. просадка",
    "backtest.details": "Детали",
    "backtest.closedTrades": "Закрытые сделки",
    "backtest.activeSignals": "Активные сигналы",
    "backtest.expiredLabel": "Истекшие",
    "backtest.avgWin": "Ср. выигрыш",
    "backtest.avgLoss": "Ср. убыток",
    "backtest.bestTrade": "Лучшая сделка",
    "backtest.worstTrade": "Худшая сделка",
    "backtest.profitFactor": "Профит-фактор",
    "backtest.maxWinStreak": "Макс. серия побед",
    "backtest.maxLossStreak": "Макс. серия убытков",
    "backtest.equityCurve": "Кривая капитала",
    "backtest.trades": "Сделки",

    // Marketplace
    "marketplace.title": "Маркетплейс стратегий",
    "marketplace.available": "стратегий доступно",
    "marketplace.filterTags": "Фильтр по тегам...",
    "marketplace.free": "Бесплатные",
    "marketplace.premium": "Премиум",
    "marketplace.paid": "Платные",
    "marketplace.sortScore": "AI рейтинг",
    "marketplace.sortPopular": "Популярные",
    "marketplace.sortNew": "Новые",
    "marketplace.empty": "Стратегий не найдено",
    "marketplace.emptyHint": "Опубликуйте стратегию, чтобы увидеть её здесь",
    "marketplace.subscribe": "Подписаться",
    "marketplace.unsubscribe": "Отписаться",
    "marketplace.subscribers": "Подписчики",
    "marketplace.pricing": "Стоимость",
    "marketplace.priceFree": "Бесплатно",
    "marketplace.pricePremium": "Только Premium",
    "marketplace.backTo": "Назад к маркетплейсу",

    // Copy Trading
    "copyTrading.title": "Копитрейдинг",
    "copyTrading.subtitle": "Автоматическое копирование сигналов подписанных стратегий",
    "copyTrading.active": "Копитрейдинг активен",
    "copyTrading.inactive": "Копитрейдинг неактивен",
    "copyTrading.howToEnable": "Для активации: подпишитесь на стратегию с авто-исполнением и добавьте биржевой аккаунт с авто-исполнением.",
    "copyTrading.howTitle": "Как работает копитрейдинг",
    "copyTrading.step1": "1. Подпишитесь на стратегию в Маркетплейсе",
    "copyTrading.step2": "2. Включите авто-исполнение на подписке",
    "copyTrading.step3": "3. Добавьте биржевой аккаунт в разделе Исполнение с авто-исполнением",
    "copyTrading.step4": "4. Новые сигналы автоматически торгуются на вашем аккаунте",
    "copyTrading.autoSubs": "Авто-подписки",
    "copyTrading.autoAccounts": "Авто-аккаунты",
    "copyTrading.successful": "Успешные",
    "copyTrading.failed": "Неудачные",
    "copyTrading.history": "История копитрейдинга",
    "copyTrading.noTrades": "Скопированных сделок пока нет",

    // Execution
    "execution.title": "Исполнение",
    "execution.subtitle": "Управление биржевыми аккаунтами и исполнение сигналов",
    "execution.addAccount": "+ Добавить аккаунт",
    "execution.cancel": "Отмена",
    "execution.exchange": "Биржа",
    "execution.label": "Название",
    "execution.apiKey": "API ключ",
    "execution.apiSecret": "API секрет",
    "execution.autoExecute": "Включить авто-исполнение для высококачественных сигналов",
    "execution.add": "Добавить аккаунт",
    "execution.accounts": "Биржевые аккаунты",
    "execution.noAccounts": "Нет аккаунтов. Добавьте Demo для бумажной торговли.",
    "execution.manual": "Ручной",
    "execution.autoOn": "Авто ВКЛ",
    "execution.orders": "История ордеров",
    "execution.noOrders": "Ордеров пока нет. Исполните сигнал, чтобы увидеть сделки.",
    "execution.symbol": "Символ",
    "execution.side": "Сторона",
    "execution.qty": "Кол-во",
    "execution.price": "Цена",
    "execution.time": "Время",

    // Referrals
    "referrals.title": "Реферальная программа",
    "referrals.subtitle": "Приглашайте друзей и получайте дни Premium",
    "referrals.yourLink": "Ваша реферальная ссылка",
    "referrals.copy": "Копировать",
    "referrals.copied": "Скопировано!",
    "referrals.code": "Код",
    "referrals.total": "Всего рефералов",
    "referrals.direct": "Прямые (L1)",
    "referrals.indirect": "Косвенные (L2)",
    "referrals.rewards": "Награды",
    "referrals.days": "дней",
    "referrals.howTitle": "Как это работает",
    "referrals.level1": "Уровень 1 — Прямое приглашение: вы получаете 7 дней Premium",
    "referrals.level2": "Уровень 2 — Ваш реферал приглашает кого-то: вы получаете 3 дня Premium",
    "referrals.yourReferrals": "Ваши рефералы",
    "referrals.empty": "Рефералов пока нет",
    "referrals.emptyHint": "Поделитесь ссылкой, чтобы начать получать награды",

    // Profile
    "profile.level": "Уровень",
    "profile.achievements": "достижений",
    "profile.xpToNext": "XP до следующего уровня",
    "profile.all": "Все",
    "profile.trading": "Трейдинг",
    "profile.social": "Социальные",
    "profile.learning": "Обучение",
    "profile.milestone": "Этапы",
    "profile.unlocked": "Открыто",
    "profile.hidden": "Секретное достижение",
    "profile.progress": "Прогресс",

    // Common
    "common.sort": "Сортировка",
  },
  en: {
    "auth.signIn": "Sign In",
    "auth.signingIn": "Signing in...",
    "auth.signInTitle": "Sign in to your account",
    "auth.register": "Register",
    "auth.registering": "Creating account...",
    "auth.createAccount": "Create your account",
    "auth.email": "Email",
    "auth.password": "Password",
    "auth.username": "Username",
    "auth.referralCode": "Referral Code (optional)",
    "auth.noAccount": "No account?",
    "auth.haveAccount": "Already have an account?",
    "auth.logout": "Logout",

    "nav.signals": "Signals",
    "nav.leaderboard": "Leaderboard",
    "nav.backtest": "Backtest",
    "nav.marketplace": "Marketplace",
    "nav.copyTrading": "Copy Trading",
    "nav.execution": "Execution",
    "nav.referrals": "Referrals",
    "nav.profile": "Profile",

    "signals.title": "Signal Feed",
    "signals.total": "signals",
    "signals.live": "Live",
    "signals.reconnecting": "Reconnecting...",
    "signals.filterTicker": "Filter by ticker...",
    "signals.all": "All",
    "signals.active": "Active",
    "signals.tpHit": "TP Hit",
    "signals.slHit": "SL Hit",
    "signals.expired": "Expired",
    "signals.empty": "No signals found",
    "signals.emptyHint": "Signals will appear here when received from TradingView or Telegram",
    "signals.entry": "Entry",
    "signals.status": "Status",
    "signals.back": "Back",
    "signals.aiRating": "AI Rating Breakdown",
    "signals.result": "Result",
    "signals.closedAt": "Closed at",

    "status.active": "Active",
    "status.closed_tp": "TP Hit",
    "status.closed_sl": "SL Hit",
    "status.closed_manual": "Closed",
    "status.expired": "Expired",

    "providers.leaderboard": "Provider Leaderboard",
    "providers.subtitle": "Top signal providers ranked by AI score",
    "providers.empty": "No rated providers yet",
    "providers.emptyHint": "Providers appear here after they have closed signals with an AI score",
    "providers.winRate": "Win Rate",
    "providers.sharpe": "Sharpe",
    "providers.drawdown": "Drawdown",
    "providers.aiScore": "AI Score",
    "providers.signals": "signals",

    "backtest.title": "Backtesting",
    "backtest.subtitle": "Test signal performance on historical data",
    "backtest.run": "Run Backtest",
    "backtest.running": "Running...",
    "backtest.providerId": "Provider ID (optional)",
    "backtest.ticker": "Ticker (optional)",
    "backtest.capital": "Capital",
    "backtest.totalReturn": "Total Return",
    "backtest.winRate": "Win Rate",
    "backtest.sharpe": "Sharpe Ratio",
    "backtest.maxDrawdown": "Max Drawdown",
    "backtest.details": "Performance Details",
    "backtest.closedTrades": "Closed Trades",
    "backtest.activeSignals": "Active Signals",
    "backtest.expiredLabel": "Expired",
    "backtest.avgWin": "Avg Win",
    "backtest.avgLoss": "Avg Loss",
    "backtest.bestTrade": "Best Trade",
    "backtest.worstTrade": "Worst Trade",
    "backtest.profitFactor": "Profit Factor",
    "backtest.maxWinStreak": "Max Win Streak",
    "backtest.maxLossStreak": "Max Loss Streak",
    "backtest.equityCurve": "Equity Curve",
    "backtest.trades": "Trades",

    "marketplace.title": "Strategy Marketplace",
    "marketplace.available": "strategies available",
    "marketplace.filterTags": "Filter by tags...",
    "marketplace.free": "Free",
    "marketplace.premium": "Premium",
    "marketplace.paid": "Paid",
    "marketplace.sortScore": "AI Score",
    "marketplace.sortPopular": "Popular",
    "marketplace.sortNew": "Newest",
    "marketplace.empty": "No strategies found",
    "marketplace.emptyHint": "Publish a strategy to see it here",
    "marketplace.subscribe": "Subscribe",
    "marketplace.unsubscribe": "Unsubscribe",
    "marketplace.subscribers": "Subscribers",
    "marketplace.pricing": "Pricing",
    "marketplace.priceFree": "Free",
    "marketplace.pricePremium": "Premium Only",
    "marketplace.backTo": "Back to Marketplace",

    "copyTrading.title": "Copy Trading",
    "copyTrading.subtitle": "Automatically copy signals from strategies you subscribe to",
    "copyTrading.active": "Copy Trading Active",
    "copyTrading.inactive": "Copy Trading Inactive",
    "copyTrading.howToEnable": "To enable: subscribe to a strategy with auto-execute ON, and have an exchange account with auto-execute enabled.",
    "copyTrading.howTitle": "How Copy Trading Works",
    "copyTrading.step1": "1. Subscribe to a strategy in the Marketplace",
    "copyTrading.step2": "2. Enable auto-execute on the subscription",
    "copyTrading.step3": "3. Add an exchange account in Execution with auto-execute ON",
    "copyTrading.step4": "4. New signals are automatically traded on your account",
    "copyTrading.autoSubs": "Auto Subscriptions",
    "copyTrading.autoAccounts": "Auto Accounts",
    "copyTrading.successful": "Successful",
    "copyTrading.failed": "Failed",
    "copyTrading.history": "Copy Trade History",
    "copyTrading.noTrades": "No copied trades yet",

    "execution.title": "Execution",
    "execution.subtitle": "Manage exchange accounts and execute signals",
    "execution.addAccount": "+ Add Account",
    "execution.cancel": "Cancel",
    "execution.exchange": "Exchange",
    "execution.label": "Label",
    "execution.apiKey": "API Key",
    "execution.apiSecret": "API Secret",
    "execution.autoExecute": "Enable auto-execution for high-confidence signals",
    "execution.add": "Add Account",
    "execution.accounts": "Exchange Accounts",
    "execution.noAccounts": "No accounts. Add a Demo account to start paper trading.",
    "execution.manual": "Manual",
    "execution.autoOn": "Auto ON",
    "execution.orders": "Order History",
    "execution.noOrders": "No orders yet. Execute a signal to see trades here.",
    "execution.symbol": "Symbol",
    "execution.side": "Side",
    "execution.qty": "Qty",
    "execution.price": "Price",
    "execution.time": "Time",

    "referrals.title": "Referral Program",
    "referrals.subtitle": "Invite friends and earn Premium days",
    "referrals.yourLink": "Your Referral Link",
    "referrals.copy": "Copy",
    "referrals.copied": "Copied!",
    "referrals.code": "Code",
    "referrals.total": "Total Referrals",
    "referrals.direct": "Direct (L1)",
    "referrals.indirect": "Indirect (L2)",
    "referrals.rewards": "Rewards Earned",
    "referrals.days": "days",
    "referrals.howTitle": "How it works",
    "referrals.level1": "Level 1 — Direct invite: you get 7 days of Premium",
    "referrals.level2": "Level 2 — Your referral invites someone: you get 3 days of Premium",
    "referrals.yourReferrals": "Your Referrals",
    "referrals.empty": "No referrals yet",
    "referrals.emptyHint": "Share your link to start earning rewards",

    "profile.level": "Level",
    "profile.achievements": "achievements",
    "profile.xpToNext": "XP to next level",
    "profile.all": "All",
    "profile.trading": "Trading",
    "profile.social": "Social",
    "profile.learning": "Learning",
    "profile.milestone": "Milestone",
    "profile.unlocked": "Unlocked",
    "profile.hidden": "Hidden Achievement",
    "profile.progress": "Progress",

    "common.sort": "Sort",
  },
};

interface I18nContextType {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextType>({
  locale: "ru",
  setLocale: () => {},
  t: (key) => key,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("locale") as Locale) || "ru";
    }
    return "ru";
  });

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    if (typeof window !== "undefined") {
      localStorage.setItem("locale", l);
    }
  }, []);

  const t = useCallback(
    (key: string) => translations[locale]?.[key] || translations.en[key] || key,
    [locale]
  );

  return React.createElement(
    I18nContext.Provider,
    { value: { locale, setLocale, t } },
    children
  );
}

export function useI18n() {
  return useContext(I18nContext);
}
