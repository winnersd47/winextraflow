"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

/**
 * Contacts & legal details page.
 * Required by payment providers (YooKassa) — must show the seller's INN,
 * status, contact channels and links to the legal documents.
 */
export default function ContactsPage() {
  const { locale } = useI18n();
  const isRu = locale === "ru";

  const rows = isRu
    ? [
        ["Исполнитель", "Сердюк Виктор Николаевич"],
        ["Статус", "Самозанятый (плательщик НПД)"],
        ["ИНН", "250715201810"],
        ["Дата постановки на учёт", "07.03.2026"],
        ["Регистрирующий орган", "Межрайонная ИФНС России №9 по Приморскому краю"],
        ["Email", "winnersd47@gmail.com"],
        ["Telegram", "@winnersd95"],
        ["Сайт", "winextraflow.pages.dev"],
      ]
    : [
        ["Provider", "Viktor Serdyuk"],
        ["Status", "Self-employed (NPD taxpayer, Russia)"],
        ["Tax ID (INN)", "250715201810"],
        ["Registered", "2026-03-07"],
        ["Tax authority", "Interdistrict IFTS of Russia No. 9, Primorsky Krai"],
        ["Email", "winnersd47@gmail.com"],
        ["Telegram", "@winnersd95"],
        ["Website", "winextraflow.pages.dev"],
      ];

  const docs = isRu
    ? [
        ["/terms", "Пользовательское соглашение"],
        ["/privacy", "Политика конфиденциальности (ФЗ-152)"],
        ["/refund", "Политика возврата"],
        ["/cookies", "Политика использования cookies"],
      ]
    : [
        ["/terms", "Terms of Service"],
        ["/privacy", "Privacy Policy (FZ-152)"],
        ["/refund", "Refund Policy"],
        ["/cookies", "Cookie Policy"],
      ];

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <Link href="/" className="text-sm text-brand-500 hover:underline">
        {isRu ? "← На главную" : "← Home"}
      </Link>

      <h1 className="mt-4 text-3xl font-bold text-text-primary">
        {isRu ? "Контакты и реквизиты" : "Contacts & Legal Details"}
      </h1>
      <p className="mt-2 text-text-secondary">
        {isRu
          ? "Реквизиты исполнителя услуг и способы связи."
          : "Service provider details and contact information."}
      </p>

      <div className="mt-8 overflow-hidden rounded-xl border border-border bg-surface-card">
        <table className="w-full text-sm">
          <tbody>
            {rows.map(([k, v], i) => (
              <tr key={k} className={i % 2 ? "bg-surface/40" : ""}>
                <td className="w-1/2 px-4 py-3 text-text-secondary">{k}</td>
                <td className="px-4 py-3 font-medium text-text-primary">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="mt-10 text-xl font-bold text-text-primary">
        {isRu ? "Услуга" : "Service"}
      </h2>
      <p className="mt-2 text-sm text-text-secondary">
        {isRu
          ? "Предоставление доступа к информационно-аналитическому сервису WinExtraFlow: агрегация торговых сигналов, AI-оценка качества (WEF Score), аналитика рынков. Доступ предоставляется по подписке, активация — сразу после оплаты."
          : "Access to the WinExtraFlow information and analytics service: trading-signal aggregation, AI quality scoring (WEF Score), market analytics. Subscription-based; access is activated immediately after payment."}
      </p>

      <h2 className="mt-10 text-xl font-bold text-text-primary">
        {isRu ? "Правовые документы" : "Legal Documents"}
      </h2>
      <ul className="mt-3 space-y-2 text-sm">
        {docs.map(([href, label]) => (
          <li key={href}>
            <Link href={href} className="text-brand-500 hover:underline">
              {label}
            </Link>
          </li>
        ))}
      </ul>

      <div className="mt-10 rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-4 text-sm text-text-secondary">
        {isRu
          ? "⚠️ WinExtraFlow не является инвестиционным советником и не оказывает услуг по управлению активами. Публикуемая информация носит аналитический характер и не является индивидуальной инвестиционной рекомендацией. Торговля на финансовых рынках сопряжена с риском потери капитала."
          : "⚠️ WinExtraFlow is not an investment adviser and does not manage assets. All published information is analytical and does not constitute personalized investment advice. Trading involves risk of capital loss."}
      </div>
    </div>
  );
}
