"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function RefundPage() {
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
        {locale === "ru" ? <RefundRU /> : <RefundEN />}
      </div>
    </div>
  );
}

function RefundRU() {
  return (
    <article className="prose prose-invert max-w-none">
      <h1 className="text-3xl font-bold text-text-primary">Политика возврата средств</h1>
      <p className="text-text-muted">Последнее обновление: 13 мая 2026 г.</p>

      <p className="text-text-secondary">Настоящая Политика возврата средств (далее -- «Политика») регулирует порядок возврата денежных средств за подписку на платформе WinExtraFlow (далее -- «Платформа») в соответствии с Законом РФ от 07.02.1992 N 2300-1 «О защите прав потребителей» (ЗоЗПП).</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">1. Описание услуги</h2>
      <p className="text-text-secondary">1.1. Платформа предоставляет цифровые услуги в формате подписки Premium, включающей расширенный доступ к торговым сигналам, AI-рейтингу, бэктестингу, копитрейдингу и маркетплейсу стратегий.</p>
      <p className="text-text-secondary">1.2. Подписка Premium является цифровой услугой, предоставляемой дистанционно.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">2. Право на возврат</h2>
      <div className="rounded-xl border-2 border-brand-500/50 bg-brand-500/5 p-6 my-4">
        <p className="text-text-secondary"><strong>Возврат в течение 14 дней.</strong> В соответствии со ст. 32 ЗоЗПП потребитель вправе отказаться от исполнения договора о выполнении работ (оказании услуг) в любое время при условии оплаты исполнителю фактически понесенных расходов.</p>
      </div>
      <p className="text-text-secondary">2.1. Вы можете запросить полный возврат средств в течение 14 календарных дней с момента оплаты подписки, если услуга не была фактически использована.</p>
      <p className="text-text-secondary">2.2. Услуга считается использованной, если вы получили доступ к Premium-функциям: просмотр сигналов Premium-уровня, запуск бэктестов, активация копитрейдинга или подписка на стратегии маркетплейса.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">3. Случаи, когда возврат невозможен</h2>
      <p className="text-text-secondary">3.1. Если услуга была фактически оказана (вы использовали Premium-функции Платформы), возврат средств не производится.</p>
      <p className="text-text-secondary">3.2. Возврат невозможен по истечении 14 календарных дней с момента оплаты.</p>
      <p className="text-text-secondary">3.3. Возврат не производится, если аккаунт был заблокирован за нарушение Пользовательского соглашения.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">4. Порядок обращения</h2>
      <p className="text-text-secondary">4.1. Для запроса возврата направьте заявление на <a href="mailto:support@winextraflow.com" className="text-brand-500">support@winextraflow.com</a> с указанием:</p>
      <ul className="list-disc pl-5 text-text-secondary space-y-2">
        <li>Email аккаунта, привязанного к подписке.</li>
        <li>Дата оплаты и сумма.</li>
        <li>Причина запроса на возврат.</li>
      </ul>
      <p className="text-text-secondary">4.2. Вы также можете обратиться через форму обратной связи в личном кабинете.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">5. Сроки рассмотрения и возврата</h2>
      <p className="text-text-secondary">5.1. Заявление на возврат рассматривается в течение 5 рабочих дней.</p>
      <p className="text-text-secondary">5.2. В случае одобрения возврат средств осуществляется в течение 10 рабочих дней на платежное средство, использованное при оплате.</p>
      <p className="text-text-secondary">5.3. Возврат производится через платежную систему Stripe.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">6. Спорные ситуации</h2>
      <p className="text-text-secondary">6.1. В случае технических сбоев Платформы, повлекших невозможность использования оплаченных услуг, возврат производится пропорционально периоду недоступности.</p>
      <p className="text-text-secondary">6.2. Если вы считаете, что списание произведено ошибочно, свяжитесь с нами в кратчайшие сроки. Мы рассмотрим каждый случай индивидуально.</p>
      <p className="text-text-secondary">6.3. При невозможности урегулирования спора в досудебном порядке вы вправе обратиться в суд по месту жительства или в Роспотребнадзор.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">7. Контакты</h2>
      <p className="text-text-secondary">По вопросам возврата средств: <a href="mailto:support@winextraflow.com" className="text-brand-500">support@winextraflow.com</a></p>

      <div className="mt-8 rounded-xl border border-border bg-surface-card p-4 text-center">
        <p className="text-sm text-text-muted">Оплачивая подписку WinExtraFlow Premium, вы подтверждаете, что ознакомлены с настоящей Политикой возврата средств.</p>
      </div>
    </article>
  );
}

function RefundEN() {
  return (
    <article className="prose prose-invert max-w-none">
      <h1 className="text-3xl font-bold text-text-primary">Refund Policy</h1>
      <p className="text-text-muted">Last updated: May 13, 2026</p>

      <p className="text-text-secondary">This Refund Policy ("Policy") governs the procedure for refunding payments for subscriptions on the WinExtraFlow platform ("Platform") in accordance with applicable consumer protection laws.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">1. Service Description</h2>
      <p className="text-text-secondary">1.1. The Platform provides digital services via Premium subscription, which includes extended access to trading signals, AI rating, backtesting, copy trading, and the strategy marketplace.</p>
      <p className="text-text-secondary">1.2. Premium subscription is a digital service delivered remotely.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">2. Right to Refund</h2>
      <div className="rounded-xl border-2 border-brand-500/50 bg-brand-500/5 p-6 my-4">
        <p className="text-text-secondary"><strong>14-day refund window.</strong> You may cancel and receive a full refund within 14 calendar days of payment, provided the service has not been used.</p>
      </div>
      <p className="text-text-secondary">2.1. You may request a full refund within 14 calendar days from the date of payment if the service has not been actually used.</p>
      <p className="text-text-secondary">2.2. The service is considered used if you have accessed Premium features: viewing Premium-level signals, running backtests, activating copy trading, or subscribing to marketplace strategies.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">3. When Refunds Are Not Available</h2>
      <p className="text-text-secondary">3.1. If the service has been actually provided (you have used Premium features), no refund will be issued.</p>
      <p className="text-text-secondary">3.2. Refunds are not available after 14 calendar days from the date of payment.</p>
      <p className="text-text-secondary">3.3. No refund will be issued if the account was suspended for violation of the Terms of Service.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">4. How to Request a Refund</h2>
      <p className="text-text-secondary">4.1. To request a refund, send an email to <a href="mailto:support@winextraflow.com" className="text-brand-500">support@winextraflow.com</a> with the following information:</p>
      <ul className="list-disc pl-5 text-text-secondary space-y-2">
        <li>Account email associated with the subscription.</li>
        <li>Payment date and amount.</li>
        <li>Reason for the refund request.</li>
      </ul>
      <p className="text-text-secondary">4.2. You may also submit a request through the feedback form in your account dashboard.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">5. Processing Timeline</h2>
      <p className="text-text-secondary">5.1. Refund requests are reviewed within 5 business days.</p>
      <p className="text-text-secondary">5.2. If approved, the refund is processed within 10 business days to the original payment method.</p>
      <p className="text-text-secondary">5.3. Refunds are processed through Stripe.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">6. Dispute Resolution</h2>
      <p className="text-text-secondary">6.1. In the event of Platform technical failures preventing use of paid services, a refund proportional to the downtime period will be issued.</p>
      <p className="text-text-secondary">6.2. If you believe a charge was made in error, contact us as soon as possible. Each case will be reviewed individually.</p>
      <p className="text-text-secondary">6.3. If a dispute cannot be resolved informally, you may pursue resolution through applicable consumer protection authorities or courts.</p>

      <h2 className="text-xl font-bold text-text-primary mt-8">7. Contact</h2>
      <p className="text-text-secondary">For refund inquiries: <a href="mailto:support@winextraflow.com" className="text-brand-500">support@winextraflow.com</a></p>

      <div className="mt-8 rounded-xl border border-border bg-surface-card p-4 text-center">
        <p className="text-sm text-text-muted">By purchasing a WinExtraFlow Premium subscription, you confirm that you have read and understood this Refund Policy.</p>
      </div>
    </article>
  );
}
