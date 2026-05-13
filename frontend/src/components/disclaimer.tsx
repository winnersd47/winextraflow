"use client";

import { useI18n } from "@/lib/i18n";
import Link from "next/link";

/**
 * Legal disclaimer shown at the bottom of dashboard pages.
 * Required for legal compliance per Russian financial regulations.
 */
export function Disclaimer() {
  const { locale } = useI18n();
  const isRu = locale === "ru";

  return (
    <div className="mt-8 border-t border-border pt-4">
      <p className="text-xs leading-relaxed text-text-muted">
        {isRu ? (
          <>
            WinExtraFlow предоставляет информационно-аналитические услуги. Информация на платформе{" "}
            <strong>НЕ является индивидуальной инвестиционной рекомендацией</strong>.
            Торговля на финансовых рынках сопряжена с риском потери капитала.
            Прошлые результаты не гарантируют будущую доходность.
            Перед принятием инвестиционных решений проконсультируйтесь с квалифицированным финансовым советником.{" "}
            <Link href="/terms" className="text-brand-500 hover:underline">Условия использования</Link>{" | "}
            <Link href="/privacy" className="text-brand-500 hover:underline">Конфиденциальность</Link>{" | "}
            <Link href="/refund" className="text-brand-500 hover:underline">Возврат</Link>
          </>
        ) : (
          <>
            WinExtraFlow provides informational and analytical services. Information on the platform{" "}
            <strong>is NOT an individual investment recommendation</strong>.
            Trading in financial markets involves the risk of capital loss.
            Past performance does not guarantee future results.
            Consult a qualified financial advisor before making investment decisions.{" "}
            <Link href="/terms" className="text-brand-500 hover:underline">Terms</Link>{" | "}
            <Link href="/privacy" className="text-brand-500 hover:underline">Privacy</Link>{" | "}
            <Link href="/refund" className="text-brand-500 hover:underline">Refund</Link>
          </>
        )}
      </p>
    </div>
  );
}
