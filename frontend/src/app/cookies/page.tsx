"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function CookiesPage() {
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
        {locale === "ru" ? <CookiesRU /> : <CookiesEN />}
      </div>
    </div>
  );
}

function CookiesRU() {
  return (
    <article className="prose prose-invert max-w-none">
      <h1 className="text-3xl font-bold text-text-primary">Политика использования cookies</h1>
      <p className="text-text-muted">Последнее обновление: 13 мая 2026 г.</p>

      <p className="text-text-secondary">Настоящая Политика использования cookies (далее -- «Политика») описывает, какие технологии хранения данных использует платформа WinExtraFlow (далее -- «Платформа») и для каких целей.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">1. Что такое cookies и localStorage</h2>
      <p className="text-text-secondary">1.1. <strong>Cookies</strong> -- небольшие текстовые файлы, сохраняемые браузером на вашем устройстве при посещении веб-сайтов. Они позволяют сайту запоминать информацию о вашем визите.</p>
      <p className="text-text-secondary">1.2. <strong>localStorage</strong> -- механизм хранения данных в браузере, позволяющий веб-приложениям сохранять информацию локально на устройстве пользователя без передачи на сервер при каждом запросе.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">2. Какие данные мы храним</h2>
      <p className="text-text-secondary">Платформа использует следующие данные в cookies и localStorage:</p>

      <div className="overflow-x-auto my-4">
        <table className="w-full text-text-secondary text-sm border-collapse">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-2 pr-4 text-text-primary">Название</th>
              <th className="text-left py-2 pr-4 text-text-primary">Тип</th>
              <th className="text-left py-2 pr-4 text-text-primary">Назначение</th>
              <th className="text-left py-2 text-text-primary">Срок</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-border">
              <td className="py-2 pr-4">token</td>
              <td className="py-2 pr-4">localStorage</td>
              <td className="py-2 pr-4">JWT-токен для аутентификации пользователя</td>
              <td className="py-2">До выхода из аккаунта</td>
            </tr>
            <tr className="border-b border-border">
              <td className="py-2 pr-4">theme</td>
              <td className="py-2 pr-4">localStorage</td>
              <td className="py-2 pr-4">Сохранение выбранной темы оформления (темная/светлая)</td>
              <td className="py-2">Постоянно</td>
            </tr>
            <tr className="border-b border-border">
              <td className="py-2 pr-4">locale</td>
              <td className="py-2 pr-4">localStorage</td>
              <td className="py-2 pr-4">Сохранение выбранного языка интерфейса (RU/EN)</td>
              <td className="py-2">Постоянно</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2 className="text-xl font-bold text-text-primary mt-8">3. Цели использования</h2>
      <p className="text-text-secondary">3.1. <strong>Аутентификация.</strong> JWT-токен в localStorage обеспечивает поддержание авторизованной сессии без необходимости повторного входа при каждом посещении.</p>
      <p className="text-text-secondary">3.2. <strong>Персонализация.</strong> Сохранение темы оформления и языка интерфейса для удобства пользователя.</p>
      <p className="text-text-secondary">3.3. Платформа не использует сторонние рекламные или аналитические cookies.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">4. Управление cookies и localStorage</h2>
      <p className="text-text-secondary">4.1. Вы можете удалить данные cookies и localStorage через настройки вашего браузера:</p>
      <ul className="list-disc pl-5 text-text-secondary space-y-2">
        <li><strong>Chrome:</strong> Настройки &rarr; Конфиденциальность и безопасность &rarr; Удалить данные браузера.</li>
        <li><strong>Firefox:</strong> Настройки &rarr; Приватность и защита &rarr; Cookies и данные сайтов &rarr; Удалить данные.</li>
        <li><strong>Safari:</strong> Настройки &rarr; Конфиденциальность &rarr; Управление данными сайтов.</li>
      </ul>
      <p className="text-text-secondary">4.2. Вы также можете использовать режим инкогнито (приватного просмотра) -- в этом случае данные будут удалены при закрытии окна браузера.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">5. Последствия отключения</h2>
      <p className="text-text-secondary">5.1. При удалении токена аутентификации вам потребуется повторно войти в аккаунт.</p>
      <p className="text-text-secondary">5.2. При удалении настроек темы и языка будут применены значения по умолчанию.</p>
      <p className="text-text-secondary">5.3. Полное отключение cookies и localStorage в браузере может ограничить функциональность Платформы, в том числе сделать невозможной авторизацию.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">6. Контакты</h2>
      <p className="text-text-secondary">По вопросам, связанным с cookies и хранением данных: <a href="mailto:support@winextraflow.com" className="text-brand-500">support@winextraflow.com</a></p>

      <div className="mt-8 rounded-xl border border-border bg-surface-card p-4 text-center">
        <p className="text-sm text-text-muted">Продолжая использовать платформу WinExtraFlow, вы соглашаетесь с использованием cookies и localStorage в соответствии с настоящей Политикой.</p>
      </div>
    </article>
  );
}

function CookiesEN() {
  return (
    <article className="prose prose-invert max-w-none">
      <h1 className="text-3xl font-bold text-text-primary">Cookie Policy</h1>
      <p className="text-text-muted">Last updated: May 13, 2026</p>

      <p className="text-text-secondary">This Cookie Policy ("Policy") describes what data storage technologies the WinExtraFlow platform ("Platform") uses and for what purposes.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">1. What Are Cookies and localStorage</h2>
      <p className="text-text-secondary">1.1. <strong>Cookies</strong> are small text files stored by your browser on your device when you visit websites. They allow the site to remember information about your visit.</p>
      <p className="text-text-secondary">1.2. <strong>localStorage</strong> is a browser data storage mechanism that allows web applications to store information locally on the user's device without transmitting it to the server with each request.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">2. What Data We Store</h2>
      <p className="text-text-secondary">The Platform uses the following cookies and localStorage data:</p>

      <div className="overflow-x-auto my-4">
        <table className="w-full text-text-secondary text-sm border-collapse">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-2 pr-4 text-text-primary">Name</th>
              <th className="text-left py-2 pr-4 text-text-primary">Type</th>
              <th className="text-left py-2 pr-4 text-text-primary">Purpose</th>
              <th className="text-left py-2 text-text-primary">Duration</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-border">
              <td className="py-2 pr-4">token</td>
              <td className="py-2 pr-4">localStorage</td>
              <td className="py-2 pr-4">JWT token for user authentication</td>
              <td className="py-2">Until logout</td>
            </tr>
            <tr className="border-b border-border">
              <td className="py-2 pr-4">theme</td>
              <td className="py-2 pr-4">localStorage</td>
              <td className="py-2 pr-4">Stores selected theme preference (dark/light)</td>
              <td className="py-2">Persistent</td>
            </tr>
            <tr className="border-b border-border">
              <td className="py-2 pr-4">locale</td>
              <td className="py-2 pr-4">localStorage</td>
              <td className="py-2 pr-4">Stores selected interface language (RU/EN)</td>
              <td className="py-2">Persistent</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2 className="text-xl font-bold text-text-primary mt-8">3. Purposes</h2>
      <p className="text-text-secondary">3.1. <strong>Authentication.</strong> The JWT token in localStorage maintains your authorized session without requiring login on each visit.</p>
      <p className="text-text-secondary">3.2. <strong>Personalization.</strong> Theme and language preferences are saved for your convenience.</p>
      <p className="text-text-secondary">3.3. The Platform does not use third-party advertising or analytics cookies.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">4. Managing Cookies and localStorage</h2>
      <p className="text-text-secondary">4.1. You can delete cookies and localStorage data through your browser settings:</p>
      <ul className="list-disc pl-5 text-text-secondary space-y-2">
        <li><strong>Chrome:</strong> Settings &rarr; Privacy and Security &rarr; Clear browsing data.</li>
        <li><strong>Firefox:</strong> Settings &rarr; Privacy &amp; Security &rarr; Cookies and Site Data &rarr; Clear Data.</li>
        <li><strong>Safari:</strong> Settings &rarr; Privacy &rarr; Manage Website Data.</li>
      </ul>
      <p className="text-text-secondary">4.2. You may also use incognito (private browsing) mode -- data will be deleted when the browser window is closed.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">5. Consequences of Disabling</h2>
      <p className="text-text-secondary">5.1. Deleting the authentication token will require you to log in again.</p>
      <p className="text-text-secondary">5.2. Deleting theme and language settings will reset them to defaults.</p>
      <p className="text-text-secondary">5.3. Completely disabling cookies and localStorage in your browser may limit Platform functionality, including making authentication impossible.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">6. Contact</h2>
      <p className="text-text-secondary">For questions about cookies and data storage: <a href="mailto:support@winextraflow.com" className="text-brand-500">support@winextraflow.com</a></p>

      <div className="mt-8 rounded-xl border border-border bg-surface-card p-4 text-center">
        <p className="text-sm text-text-muted">By continuing to use WinExtraFlow, you agree to the use of cookies and localStorage as described in this Policy.</p>
      </div>
    </article>
  );
}
