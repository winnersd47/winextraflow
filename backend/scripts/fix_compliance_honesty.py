"""Correct falsely 'verified' compliance items.

Earlier in the session every item was set to VERIFIED via the API, including
legal obligations that were never actually discharged. Verified must mean
"a document exists and was checked", not "we reasoned it was probably fine".

Corrections:
  personal_data_operator  VERIFIED -> IN_PROGRESS  (no notification filed with RKN;
                          a published privacy policy is not a filing under 152-FZ)
  aml_policy              VERIFIED -> IN_PROGRESS  (delegating AML to YooKassa is
                          outsourcing, not having internal control rules per 115-FZ)
  kyc_procedure           VERIFIED -> IN_PROGRESS  (a KYC module exists; a documented
                          identification procedure does not)
  financial_guarantee     VERIFIED -> NOT_REQUIRED (no bank guarantee exists; it is
                          not required for an information service — mark it honestly
                          instead of claiming it is done)

Kept VERIFIED (a real artefact backs each one):
  business_registration / tax_registration — KND 1122035, INN 250715201810
  terms_of_service, privacy_policy, refund_policy, cookie_policy — published pages
  risk_disclosure, investment_advisor — disclaimers on every page and every post

Usage: python scripts/fix_compliance_honesty.py [--apply]
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session
from app.models.compliance import ComplianceDocument, ComplianceStatus

CORRECTIONS = {
    "personal_data_operator": (
        ComplianceStatus.IN_PROGRESS,
        "Уведомление в Роскомнадзор об обработке ПДн НЕ подано. "
        "Опубликованная политика конфиденциальности не заменяет уведомление (152-ФЗ).",
    ),
    "aml_policy": (
        ComplianceStatus.IN_PROGRESS,
        "Правила внутреннего контроля (115-ФЗ) не разработаны. "
        "AML выполняет платёжный провайдер — это передача функции, а не исполнение обязанности.",
    ),
    "kyc_procedure": (
        ComplianceStatus.IN_PROGRESS,
        "Реализован технический модуль KYC. Регламент идентификации клиентов не оформлен.",
    ),
    "financial_guarantee": (
        ComplianceStatus.NOT_REQUIRED,
        "Банковская гарантия отсутствует и не требуется для информационно-аналитического "
        "сервиса без хранения средств клиентов.",
    ),
}


async def main():
    apply = "--apply" in sys.argv
    async with async_session() as db:
        rows = (await db.execute(select(ComplianceDocument))).scalars().all()
        by_type = {}
        for r in rows:
            key = r.doc_type.value if hasattr(r.doc_type, "value") else str(r.doc_type)
            by_type[key] = r

        changed = 0
        for key, (new_status, note) in CORRECTIONS.items():
            doc = by_type.get(key)
            if not doc:
                print(f"  [skip] {key}: не найден в БД")
                continue
            old = doc.status.value if hasattr(doc.status, "value") else str(doc.status)
            if old == new_status.value:
                print(f"  [ok]   {key}: уже {old}")
                continue
            print(f"  [FIX]  {key}: {old} -> {new_status.value}")
            print(f"         {note}")
            if apply:
                doc.status = new_status
                doc.notes = note
                changed += 1
        if apply:
            await db.commit()

        # Recount
        rows = (await db.execute(select(ComplianceDocument))).scalars().all()
        done = sum(1 for r in rows if (r.status.value if hasattr(r.status, "value") else r.status)
                   in ("verified", "not_required"))
        print(f"\n{'Применено' if apply else 'ПРЕДПРОСМОТР (нужен --apply)'}: изменено {changed}")
        print(f"Соответствие: {done}/{len(rows)} = {round(done / max(len(rows), 1) * 100)}%")
        if not apply:
            print("\nЗапустите с --apply, чтобы сохранить.")


asyncio.run(main())
