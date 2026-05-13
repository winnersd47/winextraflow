"""Compliance API — admin dashboard for legal documents, licenses, warnings.

Provides:
- GET /compliance/status — full compliance checklist with warnings
- POST /compliance/{doc_type}/upload — upload a license/document file
- PATCH /compliance/{doc_type}/status — update status (verified, not_required, etc.)
- GET /compliance/warnings — critical warnings for admin dashboard
"""

import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.compliance import (
    ComplianceDocType,
    ComplianceDocument,
    ComplianceStatus,
)
from app.models.user import User, UserRole

router = APIRouter()

COMPLIANCE_UPLOAD_DIR = "uploads/compliance"
os.makedirs(COMPLIANCE_UPLOAD_DIR, exist_ok=True)

# ─── Compliance checklist (progressive: самозанятый → ИП → ООО) ──
COMPLIANCE_CHECKLIST = [
    # ═══ ЭТАП 1: Самозанятый (НПД) — старт за 15 минут ═══
    {
        "doc_type": "business_registration",
        "title": "Регистрация самозанятого (НПД)",
        "description": "Регистрация в качестве плательщика налога на профессиональный доход через приложение 'Мой налог' (ФНС) или банк-партнёр. ФЗ-422. Занимает 15 минут. Не требует госпошлины, ОКВЭД и расчётного счёта.",
        "category": "business",
        "is_required": True,
        "warning": "Без регистрации самозанятого приём платежей от пользователей является незаконной предпринимательской деятельностью. Ст. 171 УК РФ.",
    },
    {
        "doc_type": "tax_registration",
        "title": "ИНН (уже есть у всех граждан РФ)",
        "description": "ИНН присваивается автоматически. Проверьте наличие на nalog.gov.ru. Для самозанятого ОГРН не требуется — только ИНН.",
        "category": "business",
        "is_required": True,
        "warning": "ИНН необходим для регистрации в 'Мой налог'. Без него невозможно выдавать чеки клиентам.",
    },
    {
        "doc_type": "okved_extract",
        "title": "Выписка ЕГРИП / ОКВЭД (только для ИП, этап 2)",
        "description": "Для самозанятого ОКВЭД НЕ требуется. При переходе на ИП (доход > 2.4 млн руб/год) потребуются коды: 62.01 (разработка ПО), 63.11 (обработка данных), 62.09 (прочие ИТ-услуги).",
        "category": "business",
        "is_required": False,
        "warning": "Не нужно на этапе самозанятого. Станет обязательным при переходе на ИП.",
    },
    # ═══ ЭТАП 1: Лицензии (самозанятый) ═══
    {
        "doc_type": "investment_advisor",
        "title": "Дисклеймер 'Не является инвестиционной рекомендацией'",
        "description": "КЛЮЧЕВОЙ ДОКУМЕНТ для самозанятого. Платформа позиционируется как ИНФОРМАЦИОННЫЙ СЕРВИС, а не инвестиционный советник. Все страницы содержат дисклеймер. ФЗ-39 ст. 6.1 — статус инвестсоветника требуется ТОЛЬКО при персональных рекомендациях конкретному клиенту. Агрегация публичных сигналов + AI-аналитика = информационная услуга.",
        "category": "licenses",
        "is_required": True,
        "warning": "Дисклеймеры уже реализованы на платформе. Загрузите утверждённый текст дисклеймера как документ для юридической фиксации.",
    },
    {
        "doc_type": "securities_license",
        "title": "Лицензия профучастника РЦБ (этап 3 — ООО)",
        "description": "Для самозанятого и ИП — НЕ требуется, если пользователи сами подключают свои API-ключи бирж. Платформа не хранит средства клиентов и не исполняет сделки от своего имени.",
        "category": "licenses",
        "is_required": False,
        "warning": "Не требуется на текущем этапе. Станет актуально при переходе на ООО и получении лицензии ЦБ.",
    },
    {
        "doc_type": "crypto_license",
        "title": "Уведомление об операциях с криптовалютой",
        "description": "ФЗ-259 'О ЦФА'. Криптовалюта — не средство платежа, но имущество. Самозанятый может оказывать информационные услуги по крипто-рынку. Оплата принимается в рублях через Stripe/банк.",
        "category": "licenses",
        "is_required": False,
        "warning": "Не принимайте оплату в криптовалюте. Принимайте только рубли/доллары через банк или Stripe.",
    },
    # ═══ ЭТАП 1: Персональные данные ═══
    {
        "doc_type": "personal_data_operator",
        "title": "Уведомление Роскомнадзора (ФЗ-152)",
        "description": "Самозанятый ОБЯЗАН уведомить Роскомнадзор об обработке персональных данных при сборе email, ФИО. Подаётся бесплатно через pd.rkn.gov.ru за 10 минут. Штраф за отсутствие: 3 000 — 5 000 руб. для физлица (ст. 13.11 КоАП).",
        "category": "data_protection",
        "is_required": True,
        "warning": "Штраф для физлица/самозанятого: 3 000 — 5 000 руб. Подайте уведомление на pd.rkn.gov.ru.",
    },
    {
        "doc_type": "gdpr_compliance",
        "title": "GDPR (этап 2 — при работе с ЕС)",
        "description": "Для самозанятого в РФ с клиентами только из РФ — не требуется. При масштабировании на ЕС потребуется соответствие GDPR.",
        "category": "data_protection",
        "is_required": False,
        "warning": "Не требуется на этапе самозанятого с клиентами из РФ.",
    },
    # ═══ ЭТАП 1: AML/KYC ═══
    {
        "doc_type": "aml_policy",
        "title": "Политика AML (упрощённая для самозанятого)",
        "description": "Самозанятый НЕ является субъектом 115-ФЗ напрямую (не банк, не ломбард). Однако Stripe как платёжный агент проводит AML-проверки. Создайте документ с описанием: кто может пользоваться платформой, как обрабатываются подозрительные платежи.",
        "category": "aml",
        "is_required": True,
        "warning": "Stripe может заблокировать аккаунт при подозрении на отмывание. Подготовьте базовую AML-политику.",
    },
    {
        "doc_type": "kyc_procedure",
        "title": "Описание процедуры KYC",
        "description": "Документ описывающий процедуру идентификации пользователей: какие данные собираются (email, фото с паспортом), зачем, как хранятся. KYC-модуль уже реализован на платформе. Нужно зафиксировать процедуру документально.",
        "category": "aml",
        "is_required": True,
        "warning": "KYC-модуль работает. Зафиксируйте процедуру в документе.",
    },
    # ═══ ЭТАП 1: Пользовательские документы (все на платформе) ═══
    {
        "doc_type": "terms_of_service",
        "title": "Пользовательское соглашение (оферта)",
        "description": "Публичная оферта по ст. 437 ГК РФ. РЕАЛИЗОВАНО на платформе: /terms. Самозанятый может заключать договоры оферты с физлицами. Загрузите утверждённую копию.",
        "category": "user_docs",
        "is_required": True,
        "warning": "Реализовано на платформе. Загрузите подписанную копию для юридической фиксации.",
    },
    {
        "doc_type": "privacy_policy",
        "title": "Политика конфиденциальности",
        "description": "РЕАЛИЗОВАНО на платформе: /privacy. 9 разделов по ФЗ-152. Загрузите утверждённую копию.",
        "category": "user_docs",
        "is_required": True,
        "warning": "Реализовано на платформе. Загрузите подписанную копию.",
    },
    {
        "doc_type": "risk_disclosure",
        "title": "Уведомление о рисках",
        "description": "РЕАЛИЗОВАНО: дисклеймеры на каждой странице, в Terms of Service, в Бэктесте, в Лидерборде. 'Не является инвестиционной рекомендацией'. Загрузите утверждённый текст.",
        "category": "user_docs",
        "is_required": True,
        "warning": "Дисклеймеры реализованы на всех страницах. Загрузите утверждённый текст.",
    },
    {
        "doc_type": "refund_policy",
        "title": "Политика возврата средств",
        "description": "РЕАЛИЗОВАНО на платформе: /refund. 7 разделов по ст. 32 ЗоЗПП. Самозанятый обязан возвращать деньги за неоказанные услуги. Загрузите утверждённую копию.",
        "category": "user_docs",
        "is_required": True,
        "warning": "Реализовано на платформе. Загрузите подписанную копию.",
    },
    {
        "doc_type": "cookie_policy",
        "title": "Политика использования cookies",
        "description": "РЕАЛИЗОВАНО на платформе: /cookies. 6 разделов по ФЗ-152. Загрузите утверждённую копию.",
        "category": "user_docs",
        "is_required": True,
        "warning": "Реализовано на платформе. Загрузите подписанную копию.",
    },
    # ═══ ЭТАП 1: Финансы (самозанятый) ═══
    {
        "doc_type": "liability_insurance",
        "title": "Страхование ответственности (этап 3 — ООО)",
        "description": "Для самозанятого страхование НЕ обязательно. Рекомендуется при доходе > 500 000 руб/год. Станет обязательным при регистрации инвестсоветника (ООО + лицензия ЦБ).",
        "category": "financial",
        "is_required": False,
        "warning": "Не обязательно для самозанятого. Рекомендуется при масштабировании.",
    },
    {
        "doc_type": "financial_guarantee",
        "title": "Банковский счёт / карта для приёма платежей",
        "description": "Самозанятый принимает платежи на личную карту или через Stripe. Чеки формируются в приложении 'Мой налог'. Расчётный счёт ИП НЕ требуется.",
        "category": "financial",
        "is_required": True,
        "warning": "Настройте приём платежей: Stripe (международные) + банковская карта (РФ). Формируйте чеки в 'Мой налог'.",
    },
]


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin access required")
    return user


async def _ensure_checklist_seeded(db: AsyncSession):
    """Seed compliance checklist if not already done."""
    existing = (await db.execute(
        select(ComplianceDocument).limit(1)
    )).scalar_one_or_none()
    if existing:
        return

    for item in COMPLIANCE_CHECKLIST:
        doc = ComplianceDocument(
            doc_type=ComplianceDocType(item["doc_type"]),
            title=item["title"],
            description=item["description"],
            category=item["category"],
            is_required=item["is_required"],
            status=ComplianceStatus.NOT_STARTED,
        )
        db.add(doc)
    await db.commit()


@router.get("/level")
async def compliance_level(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Public endpoint — returns compliance % for feature gating.

    Available to ALL authenticated users (not just admin).
    Returns only the percentage, not the full checklist details.
    """
    await _ensure_checklist_seeded(db)

    result = await db.execute(
        select(ComplianceDocument).where(ComplianceDocument.is_required == True)
    )
    docs = result.scalars().all()
    total = len(docs)
    completed = sum(
        1 for d in docs
        if d.status in (ComplianceStatus.VERIFIED, ComplianceStatus.UPLOADED, ComplianceStatus.NOT_REQUIRED)
    )
    pct = round(completed / total * 100) if total > 0 else 0

    return {"compliance_pct": pct, "total_required": total, "total_completed": completed}


@router.get("/status")
async def compliance_status(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Full compliance checklist with statuses and warnings (admin only)."""
    await _ensure_checklist_seeded(db)

    result = await db.execute(
        select(ComplianceDocument).order_by(ComplianceDocument.category)
    )
    docs = result.scalars().all()

    # Build response with warnings
    items = []
    total_required = 0
    total_completed = 0
    critical_warnings = []

    checklist_map = {item["doc_type"]: item for item in COMPLIANCE_CHECKLIST}

    for doc in docs:
        meta = checklist_map.get(doc.doc_type.value, {})
        is_done = doc.status in (ComplianceStatus.VERIFIED, ComplianceStatus.UPLOADED, ComplianceStatus.NOT_REQUIRED)

        if doc.is_required:
            total_required += 1
            if is_done:
                total_completed += 1
            else:
                critical_warnings.append({
                    "doc_type": doc.doc_type.value,
                    "title": doc.title,
                    "warning": meta.get("warning", ""),
                    "severity": "critical" if doc.is_required else "warning",
                })

        items.append({
            "id": str(doc.id),
            "doc_type": doc.doc_type.value,
            "title": doc.title,
            "description": doc.description,
            "category": doc.category,
            "status": doc.status.value,
            "is_required": doc.is_required,
            "file_name": doc.file_name,
            "admin_note": doc.admin_note,
            "warning": meta.get("warning", ""),
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        })

    return {
        "total_required": total_required,
        "total_completed": total_completed,
        "compliance_pct": round(total_completed / total_required * 100) if total_required > 0 else 0,
        "critical_warnings": critical_warnings,
        "items": items,
    }


@router.get("/warnings")
async def compliance_warnings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get only critical compliance warnings for admin dashboard banner."""
    await _ensure_checklist_seeded(db)

    result = await db.execute(
        select(ComplianceDocument).where(
            ComplianceDocument.is_required == True,
            ComplianceDocument.status.in_([
                ComplianceStatus.NOT_STARTED,
                ComplianceStatus.IN_PROGRESS,
                ComplianceStatus.EXPIRED,
            ]),
        )
    )
    docs = result.scalars().all()
    checklist_map = {item["doc_type"]: item for item in COMPLIANCE_CHECKLIST}

    warnings = []
    for doc in docs:
        meta = checklist_map.get(doc.doc_type.value, {})
        warnings.append({
            "doc_type": doc.doc_type.value,
            "title": doc.title,
            "warning": meta.get("warning", ""),
            "category": doc.category,
        })

    return {"count": len(warnings), "warnings": warnings}


@router.post("/{doc_type}/upload")
async def upload_compliance_doc(
    doc_type: ComplianceDocType,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Upload a compliance document file."""
    # Validate file type
    ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/jpg",
                     "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Допустимые форматы: PDF, JPG, PNG, DOC, DOCX")

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(400, "Максимальный размер файла: 20 МБ")

    # Save file
    ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "doc", "docx"}
    ext = (file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "pdf")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Расширение .{ext} не допускается")

    filename = f"{doc_type.value}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(os.path.abspath(COMPLIANCE_UPLOAD_DIR), filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    # Update document
    doc = (await db.execute(
        select(ComplianceDocument).where(ComplianceDocument.doc_type == doc_type)
    )).scalar_one_or_none()

    if not doc:
        raise HTTPException(404, "Document type not found in checklist")

    doc.file_path = filepath
    doc.file_name = file.filename or filename
    doc.status = ComplianceStatus.UPLOADED
    doc.uploaded_by = admin.id
    await db.commit()

    return {"status": "uploaded", "file_name": doc.file_name, "doc_type": doc_type.value}


@router.patch("/{doc_type}/status")
async def update_compliance_status(
    doc_type: ComplianceDocType,
    status: ComplianceStatus,
    note: str = "",
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update compliance document status."""
    doc = (await db.execute(
        select(ComplianceDocument).where(ComplianceDocument.doc_type == doc_type)
    )).scalar_one_or_none()

    if not doc:
        raise HTTPException(404, "Document type not found")

    doc.status = status
    if note:
        doc.admin_note = note
    await db.commit()

    return {"doc_type": doc_type.value, "status": status.value, "note": note}
