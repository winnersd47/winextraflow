"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function TermsPage() {
  const { locale, setLocale } = useI18n();

  return (
    <div className="min-h-screen bg-surface">
      <nav className="flex items-center justify-between border-b border-border px-6 py-4 lg:px-16">
        <Link href="/" className="flex items-center gap-2">
          <span className="text-xl font-bold text-brand-500">WinExtra</span>
          <span className="text-xl font-bold text-text-primary">Flow</span>
        </Link>
        <div className="flex gap-1">
          <button onClick={() => setLocale("ru")} className={`rounded px-2 py-1 text-xs font-bold ${locale === "ru" ? "bg-brand-500 text-white" : "bg-surface-hover text-text-muted"}`}>RUS</button>
          <button onClick={() => setLocale("en")} className={`rounded px-2 py-1 text-xs font-bold ${locale === "en" ? "bg-brand-500 text-white" : "bg-surface-hover text-text-muted"}`}>ENG</button>
        </div>
      </nav>

      <div className="mx-auto max-w-3xl px-6 py-12">
        {locale === "ru" ? <TermsRU /> : <TermsEN />}
      </div>
    </div>
  );
}

function TermsRU() {
  return (
    <article className="prose prose-invert max-w-none">
      <h1 className="text-3xl font-bold text-text-primary">Пользовательское соглашение</h1>
      <p className="text-text-muted">Последнее обновление: 6 мая 2026 г.</p>

      <p className="text-text-secondary">Настоящее Пользовательское соглашение (далее — «Соглашение») регулирует использование платформы WinExtraFlow (далее — «Платформа», «Сервис»). Регистрируясь и используя Платформу, вы подтверждаете согласие с условиями данного Соглашения.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">1. Общие положения</h2>
      <p className="text-text-secondary">1.1. WinExtraFlow — платформа агрегации торговых сигналов с AI-рейтингом, бэктестингом, копитрейдингом и маркетплейсом стратегий.</p>
      <p className="text-text-secondary">1.2. Платформа НЕ является инвестиционным советником, брокером или финансовой организацией.</p>
      <p className="text-text-secondary">1.3. Для использования Платформы пользователь должен быть старше 18 лет.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">2. Предупреждение о рисках</h2>
      <div className="rounded-xl border-2 border-red-500/50 bg-red-500/5 p-6 my-4">
        <h3 className="text-lg font-bold text-red-400">ВАЖНО: Торговля финансовыми инструментами связана с высоким риском</h3>
        <ul className="list-disc pl-5 text-text-secondary space-y-2 mt-3">
          <li><strong>Риск потери капитала.</strong> Вы можете потерять часть или весь вложенный капитал. Торгуйте только теми средствами, потерю которых можете позволить.</li>
          <li><strong>Прошлая доходность не гарантирует будущую.</strong> Исторические результаты сигналов, провайдеров и стратегий не являются гарантией будущей прибыли.</li>
          <li><strong>AI-рейтинг не является рекомендацией.</strong> Оценка сигналов системой искусственного интеллекта носит информационный характер и не является инвестиционной рекомендацией.</li>
          <li><strong>Риск автоматического исполнения.</strong> При использовании копитрейдинга и авто-исполнения сделки совершаются автоматически. Убедитесь, что настройки risk-management соответствуют вашему уровню допустимого риска.</li>
          <li><strong>Риски крипторынка.</strong> Криптовалюты чрезвычайно волатильны. Цена может измениться на десятки процентов за минуты.</li>
          <li><strong>Технические сбои.</strong> Платформа, биржи и сети могут испытывать задержки, сбои и перебои, которые могут привести к неисполнению или некорректному исполнению ордеров.</li>
          <li><strong>Риск третьих сторон.</strong> Платформа интегрируется с биржами (Binance, Bybit) и Telegram. Мы не контролируем работу этих сервисов и не несём ответственности за их сбои.</li>
          <li><strong>Риск провайдеров сигналов.</strong> Качество и точность сигналов зависит от провайдеров. Платформа агрегирует, но не гарантирует точность сигналов.</li>
        </ul>
      </div>

      <h2 className="text-xl font-bold text-text-primary mt-8">3. Ответственность</h2>
      <p className="text-text-secondary">3.1. <strong>Платформа предоставляется «как есть» (as is).</strong> Мы не даём гарантий доходности, бесперебойной работы или отсутствия ошибок.</p>
      <p className="text-text-secondary">3.2. Все торговые решения принимаются пользователем самостоятельно. Платформа не несёт ответственности за финансовые убытки.</p>
      <p className="text-text-secondary">3.3. Максимальная ответственность Платформы ограничена суммой, уплаченной пользователем за подписку за последние 3 месяца.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">4. API-ключи и безопасность</h2>
      <p className="text-text-secondary">4.1. API-ключи бирж хранятся в зашифрованном виде (Fernet/AES-256).</p>
      <p className="text-text-secondary">4.2. Рекомендуется создавать API-ключи только с разрешениями на торговлю, без права на вывод средств.</p>
      <p className="text-text-secondary">4.3. Пользователь несёт полную ответственность за безопасность своих учётных данных и API-ключей.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">5. Подписка и оплата</h2>
      <p className="text-text-secondary">5.1. Бесплатный план имеет ограничения по количеству сигналов, бэктестов и функций.</p>
      <p className="text-text-secondary">5.2. Premium подписка оплачивается через Stripe. Возврат возможен в течение 7 дней с момента оплаты.</p>
      <p className="text-text-secondary">5.3. Платформа оставляет за собой право изменять тарифы с уведомлением за 30 дней.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">6. Маркетплейс стратегий</h2>
      <p className="text-text-secondary">6.1. Авторы стратегий получают 70% от подписок. Платформа удерживает 30%.</p>
      <p className="text-text-secondary">6.2. Авторы стратегий не являются лицензированными финансовыми советниками.</p>
      <p className="text-text-secondary">6.3. Платформа не проверяет и не сертифицирует стратегии. Используйте бэктестинг для оценки.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">7. Персональные данные</h2>
      <p className="text-text-secondary">7.1. Мы собираем: email, имя пользователя, IP-адрес, данные о торговой активности.</p>
      <p className="text-text-secondary">7.2. Данные не передаются третьим лицам, кроме случаев, предусмотренных законом.</p>
      <p className="text-text-secondary">7.3. Пользователь может запросить удаление аккаунта и данных.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">8. Запрещённые действия</h2>
      <p className="text-text-secondary">Запрещается: манипулирование рынком через сигналы, создание множественных аккаунтов для злоупотребления реферальной программой, попытки взлома или DDoS платформы, публикация заведомо ложных сигналов.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">9. Изменение условий</h2>
      <p className="text-text-secondary">Платформа оставляет за собой право вносить изменения в настоящее Соглашение. Уведомление об изменениях направляется на email и через уведомления в системе за 14 дней.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">10. Контакты</h2>
      <p className="text-text-secondary">По всем вопросам: <a href="mailto:support@winextraflow.com" className="text-brand-500">support@winextraflow.com</a></p>

      <div className="mt-8 rounded-xl border border-border bg-surface-card p-4 text-center">
        <p className="text-sm text-text-muted">Регистрируясь на платформе WinExtraFlow, вы подтверждаете, что прочитали, поняли и согласны со всеми условиями данного Соглашения, включая предупреждения о рисках.</p>
      </div>
    </article>
  );
}

function TermsEN() {
  return (
    <article className="prose prose-invert max-w-none">
      <h1 className="text-3xl font-bold text-text-primary">Terms of Service</h1>
      <p className="text-text-muted">Last updated: May 6, 2026</p>

      <p className="text-text-secondary">These Terms of Service ("Terms") govern the use of the WinExtraFlow platform ("Platform", "Service"). By registering and using the Platform, you agree to these Terms.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">1. General Provisions</h2>
      <p className="text-text-secondary">1.1. WinExtraFlow is a trading signal aggregation platform with AI rating, backtesting, copy trading, and strategy marketplace.</p>
      <p className="text-text-secondary">1.2. The Platform is NOT an investment advisor, broker, or financial institution.</p>
      <p className="text-text-secondary">1.3. Users must be at least 18 years old.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">2. Risk Disclosure</h2>
      <div className="rounded-xl border-2 border-red-500/50 bg-red-500/5 p-6 my-4">
        <h3 className="text-lg font-bold text-red-400">IMPORTANT: Trading financial instruments carries high risk</h3>
        <ul className="list-disc pl-5 text-text-secondary space-y-2 mt-3">
          <li><strong>Capital loss risk.</strong> You may lose part or all of your invested capital. Only trade with funds you can afford to lose.</li>
          <li><strong>Past performance does not guarantee future results.</strong> Historical results of signals, providers, and strategies are not a guarantee of future profits.</li>
          <li><strong>AI rating is not financial advice.</strong> AI-based signal scoring is informational only and does not constitute investment advice.</li>
          <li><strong>Auto-execution risk.</strong> Copy trading and auto-execution place trades automatically. Ensure risk management settings match your risk tolerance.</li>
          <li><strong>Cryptocurrency risks.</strong> Cryptocurrencies are extremely volatile. Prices can change by tens of percent within minutes.</li>
          <li><strong>Technical failures.</strong> The Platform, exchanges, and networks may experience delays, outages, and interruptions that may result in failed or incorrect order execution.</li>
          <li><strong>Third-party risk.</strong> The Platform integrates with exchanges (Binance, Bybit) and Telegram. We do not control these services and are not responsible for their failures.</li>
          <li><strong>Signal provider risk.</strong> Signal quality depends on providers. The Platform aggregates but does not guarantee signal accuracy.</li>
        </ul>
      </div>

      <h2 className="text-xl font-bold text-text-primary mt-8">3. Liability</h2>
      <p className="text-text-secondary">3.1. The Platform is provided "as is." We make no guarantees of profitability, uptime, or error-free operation.</p>
      <p className="text-text-secondary">3.2. All trading decisions are made by the user. The Platform is not responsible for financial losses.</p>
      <p className="text-text-secondary">3.3. Maximum liability is limited to the subscription amount paid in the last 3 months.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">4. API Keys & Security</h2>
      <p className="text-text-secondary">4.1. Exchange API keys are stored encrypted (Fernet/AES-256).</p>
      <p className="text-text-secondary">4.2. We recommend creating API keys with trading permissions only, without withdrawal rights.</p>
      <p className="text-text-secondary">4.3. Users are fully responsible for the security of their credentials and API keys.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">5. Subscription & Payment</h2>
      <p className="text-text-secondary">5.1. Free plan has limits on signals, backtests, and features.</p>
      <p className="text-text-secondary">5.2. Premium is processed via Stripe. Refunds available within 7 days of payment.</p>
      <p className="text-text-secondary">5.3. The Platform reserves the right to change pricing with 30 days notice.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">6. Strategy Marketplace</h2>
      <p className="text-text-secondary">6.1. Strategy authors receive 70% of subscription revenue. The Platform retains 30%.</p>
      <p className="text-text-secondary">6.2. Strategy authors are not licensed financial advisors.</p>
      <p className="text-text-secondary">6.3. The Platform does not verify or certify strategies. Use backtesting to evaluate.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">7. Personal Data</h2>
      <p className="text-text-secondary">7.1. We collect: email, username, IP address, trading activity data.</p>
      <p className="text-text-secondary">7.2. Data is not shared with third parties except as required by law.</p>
      <p className="text-text-secondary">7.3. Users may request account and data deletion.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">8. Prohibited Actions</h2>
      <p className="text-text-secondary">Prohibited: market manipulation via signals, creating multiple accounts for referral abuse, hacking or DDoS attempts, publishing deliberately false signals.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">9. Changes to Terms</h2>
      <p className="text-text-secondary">The Platform reserves the right to modify these Terms. Users will be notified via email and in-app notifications 14 days in advance.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">10. Contact</h2>
      <p className="text-text-secondary">For all inquiries: <a href="mailto:support@winextraflow.com" className="text-brand-500">support@winextraflow.com</a></p>

      <div className="mt-8 rounded-xl border border-border bg-surface-card p-4 text-center">
        <p className="text-sm text-text-muted">By registering on WinExtraFlow, you confirm that you have read, understood, and agree to all Terms, including the Risk Disclosure.</p>
      </div>
    </article>
  );
}
