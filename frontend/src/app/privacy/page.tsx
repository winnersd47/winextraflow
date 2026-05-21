"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function PrivacyPage() {
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
        {locale === "ru" ? <PrivacyRU /> : <PrivacyEN />}
      </div>
    </div>
  );
}

function PrivacyRU() {
  return (
    <article className="prose prose-invert max-w-none">
      <h1 className="text-3xl font-bold text-text-primary">Политика конфиденциальности</h1>
      <p className="text-text-muted">Последнее обновление: 13 мая 2026 г.</p>

      <p className="text-text-secondary">Настоящая Политика конфиденциальности (далее -- «Политика») описывает порядок сбора, обработки и защиты персональных данных пользователей платформы WinExtraFlow (далее -- «Платформа») в соответствии с Федеральным законом от 27.07.2006 N 152-ФЗ «О персональных данных».</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">1. Оператор персональных данных</h2>
      <p className="text-text-secondary">1.1. Оператором персональных данных является WinExtraFlow (далее -- «Оператор»).</p>
      <p className="text-text-secondary">1.2. Контактный адрес для вопросов по обработке данных: <a href="mailto:privacy@winextraflow.com" className="text-brand-500">privacy@winextraflow.com</a></p>

      <h2 className="text-xl font-bold text-text-primary mt-8">2. Какие данные мы собираем</h2>
      <p className="text-text-secondary">2.1. <strong>Регистрационные данные:</strong> адрес электронной почты, имя пользователя (логин), реферальный код (уникальный идентификатор).</p>
      <p className="text-text-secondary">2.1.1. <strong>Данные мессенджеров (при подключении):</strong> идентификатор чата Telegram (telegram_chat_id), идентификатор чата MAX (max_chat_id). Собираются только при добровольном подключении мессенджера пользователем.</p>
      <p className="text-text-secondary">2.2. <strong>Данные KYC-верификации:</strong> фотография документа, удостоверяющего личность (паспорт), фамилия и имя.</p>
      <p className="text-text-secondary">2.3. <strong>Технические данные:</strong> IP-адрес, тип и версия браузера, данные cookies и localStorage.</p>
      <p className="text-text-secondary">2.4. <strong>Данные об использовании:</strong> торговая активность, настройки стратегий, история бэктестов.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">3. Цели обработки данных</h2>
      <p className="text-text-secondary">3.1. Регистрация и аутентификация пользователя на Платформе.</p>
      <p className="text-text-secondary">3.2. Прохождение KYC-верификации в соответствии с требованиями законодательства.</p>
      <p className="text-text-secondary">3.3. Исполнение торговых сигналов и копитрейдинг через подключенные биржевые аккаунты.</p>
      <p className="text-text-secondary">3.4. Отправка уведомлений о сигналах, состоянии подписки и обновлениях Платформы.</p>
      <p className="text-text-secondary">3.5. Улучшение качества сервиса и персонализация пользовательского опыта.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">4. Правовые основания обработки</h2>
      <p className="text-text-secondary">4.1. <strong>Согласие пользователя</strong> -- предоставляется при регистрации и прохождении KYC.</p>
      <p className="text-text-secondary">4.2. <strong>Исполнение договора</strong> -- обработка данных необходима для предоставления услуг Платформы согласно Пользовательскому соглашению.</p>
      <p className="text-text-secondary">4.3. <strong>Законный интерес</strong> -- обеспечение безопасности, предотвращение мошенничества, аналитика использования.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">5. Передача данных третьим лицам</h2>
      <p className="text-text-secondary">5.1. <strong>Stripe</strong> -- для обработки платежей за подписку Premium. Stripe получает платежные данные напрямую; Платформа не хранит номера банковских карт.</p>
      <p className="text-text-secondary">5.2. <strong>Биржи (Binance, Bybit)</strong> -- для исполнения торговых ордеров через API. Передаются только торговые команды.</p>
      <p className="text-text-secondary">5.3. Данные не передаются иным третьим лицам, за исключением случаев, предусмотренных законодательством РФ.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">6. Хранение данных</h2>
      <p className="text-text-secondary">6.1. Персональные данные хранятся на серверах, расположенных на территории Российской Федерации и Европейского Союза.</p>
      <p className="text-text-secondary">6.2. Срок хранения данных -- в течение всего периода действия аккаунта пользователя. При удалении аккаунта все персональные данные удаляются немедленно и безвозвратно: ордера, подписки, уведомления, KYC-фотографии, данные мессенджеров.</p>
      <p className="text-text-secondary">6.3. Анонимизированная запись пользователя сохраняется для обеспечения целостности реферальной системы, но не содержит персональных данных.</p>
      <p className="text-text-secondary">6.4. <strong>Журналирование:</strong> системные журналы содержат только анонимные идентификаторы (UUID) и не включают имена пользователей, email или другие персональные данные. Журналы хранятся 30 дней.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">7. Права пользователя</h2>
      <p className="text-text-secondary">В соответствии с 152-ФЗ вы имеете право:</p>
      <ul className="list-disc pl-5 text-text-secondary space-y-2">
        <li>Получить информацию об обработке ваших персональных данных.</li>
        <li>Потребовать исправления неточных или неполных данных.</li>
        <li>Потребовать удаления персональных данных.</li>
        <li>Отозвать согласие на обработку персональных данных.</li>
        <li>Обжаловать действия Оператора в Роскомнадзор.</li>
      </ul>
      <p className="text-text-secondary mt-2">Для реализации указанных прав направьте запрос на <a href="mailto:privacy@winextraflow.com" className="text-brand-500">privacy@winextraflow.com</a>. Срок ответа -- не более 30 дней.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">8. Безопасность данных</h2>
      <p className="text-text-secondary">8.1. Все данные передаются по защищенному протоколу HTTPS.</p>
      <p className="text-text-secondary">8.2. API-ключи бирж шифруются с использованием алгоритма Fernet (AES-256).</p>
      <p className="text-text-secondary">8.3. Пароли хранятся в виде bcrypt-хэшей.</p>
      <p className="text-text-secondary">8.4. Доступ к серверам и базам данных ограничен и контролируется.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">9. Контакты</h2>
      <p className="text-text-secondary">По вопросам обработки персональных данных обращайтесь:</p>
      <p className="text-text-secondary">Email: <a href="mailto:privacy@winextraflow.com" className="text-brand-500">privacy@winextraflow.com</a></p>
      <p className="text-text-secondary">Общая поддержка: <a href="mailto:support@winextraflow.com" className="text-brand-500">support@winextraflow.com</a></p>

      <div className="mt-8 rounded-xl border border-border bg-surface-card p-4 text-center">
        <p className="text-sm text-text-muted">Используя платформу WinExtraFlow, вы подтверждаете, что ознакомлены с настоящей Политикой конфиденциальности и согласны с порядком обработки ваших персональных данных.</p>
      </div>
    </article>
  );
}

function PrivacyEN() {
  return (
    <article className="prose prose-invert max-w-none">
      <h1 className="text-3xl font-bold text-text-primary">Privacy Policy</h1>
      <p className="text-text-muted">Last updated: May 13, 2026</p>

      <p className="text-text-secondary">This Privacy Policy ("Policy") describes how WinExtraFlow ("Platform") collects, processes, and protects user personal data in accordance with applicable data protection legislation, including Federal Law No. 152-FZ "On Personal Data."</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">1. Data Controller</h2>
      <p className="text-text-secondary">1.1. The data controller is WinExtraFlow ("Operator").</p>
      <p className="text-text-secondary">1.2. Contact for data processing inquiries: <a href="mailto:privacy@winextraflow.com" className="text-brand-500">privacy@winextraflow.com</a></p>

      <h2 className="text-xl font-bold text-text-primary mt-8">2. Data We Collect</h2>
      <p className="text-text-secondary">2.1. <strong>Registration data:</strong> email address, username, referral code (unique identifier).</p>
      <p className="text-text-secondary">2.1.1. <strong>Messenger data (when linked):</strong> Telegram chat ID (telegram_chat_id), MAX Messenger chat ID (max_chat_id). Collected only when user voluntarily links their messenger.</p>
      <p className="text-text-secondary">2.2. <strong>KYC verification data:</strong> photograph of an identity document (passport), full name.</p>
      <p className="text-text-secondary">2.3. <strong>Technical data:</strong> IP address, browser type and version, cookies and localStorage data.</p>
      <p className="text-text-secondary">2.4. <strong>Usage data:</strong> trading activity, strategy settings, backtest history.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">3. Purposes of Data Processing</h2>
      <p className="text-text-secondary">3.1. User registration and authentication on the Platform.</p>
      <p className="text-text-secondary">3.2. KYC verification as required by applicable law.</p>
      <p className="text-text-secondary">3.3. Execution of trading signals and copy trading through connected exchange accounts.</p>
      <p className="text-text-secondary">3.4. Sending notifications about signals, subscription status, and Platform updates.</p>
      <p className="text-text-secondary">3.5. Service quality improvement and personalization.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">4. Legal Basis for Processing</h2>
      <p className="text-text-secondary">4.1. <strong>User consent</strong> -- provided during registration and KYC verification.</p>
      <p className="text-text-secondary">4.2. <strong>Contract performance</strong> -- data processing is necessary to provide Platform services under the Terms of Service.</p>
      <p className="text-text-secondary">4.3. <strong>Legitimate interest</strong> -- security, fraud prevention, usage analytics.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">5. Data Sharing with Third Parties</h2>
      <p className="text-text-secondary">5.1. <strong>Stripe</strong> -- for processing Premium subscription payments. Stripe receives payment data directly; the Platform does not store card numbers.</p>
      <p className="text-text-secondary">5.2. <strong>Exchanges (Binance, Bybit)</strong> -- for executing trading orders via API. Only trading commands are transmitted.</p>
      <p className="text-text-secondary">5.3. Data is not shared with other third parties except as required by law.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">6. Data Storage</h2>
      <p className="text-text-secondary">6.1. Personal data is stored on servers located in the Russian Federation and the European Union.</p>
      <p className="text-text-secondary">6.2. Data is retained for the duration of the active account. Upon account deletion, all personal data is immediately and permanently deleted: orders, subscriptions, notifications, KYC photos, messenger data.</p>
      <p className="text-text-secondary">6.3. An anonymized user record is kept for referral system integrity but contains no personal data.</p>
      <p className="text-text-secondary">6.4. <strong>Logging:</strong> system logs contain only anonymous identifiers (UUID) and do not include usernames, emails, or other personal data. Logs are retained for 30 days.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">7. User Rights</h2>
      <p className="text-text-secondary">Under applicable data protection law, you have the right to:</p>
      <ul className="list-disc pl-5 text-text-secondary space-y-2">
        <li>Request information about how your personal data is processed.</li>
        <li>Request correction of inaccurate or incomplete data.</li>
        <li>Request deletion of your personal data.</li>
        <li>Withdraw consent to data processing.</li>
        <li>File a complaint with the relevant supervisory authority.</li>
      </ul>
      <p className="text-text-secondary mt-2">To exercise these rights, send a request to <a href="mailto:privacy@winextraflow.com" className="text-brand-500">privacy@winextraflow.com</a>. Response time is no more than 30 days.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">8. Data Security</h2>
      <p className="text-text-secondary">8.1. All data is transmitted over HTTPS.</p>
      <p className="text-text-secondary">8.2. Exchange API keys are encrypted using Fernet (AES-256).</p>
      <p className="text-text-secondary">8.3. Passwords are stored as bcrypt hashes.</p>
      <p className="text-text-secondary">8.4. Access to servers and databases is restricted and monitored.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">9. Contact</h2>
      <p className="text-text-secondary">For data processing inquiries:</p>
      <p className="text-text-secondary">Email: <a href="mailto:privacy@winextraflow.com" className="text-brand-500">privacy@winextraflow.com</a></p>
      <p className="text-text-secondary">General support: <a href="mailto:support@winextraflow.com" className="text-brand-500">support@winextraflow.com</a></p>

      <div className="mt-8 rounded-xl border border-border bg-surface-card p-4 text-center">
        <p className="text-sm text-text-muted">By using WinExtraFlow, you confirm that you have read this Privacy Policy and agree to the described data processing practices.</p>
      </div>
    </article>
  );
}
