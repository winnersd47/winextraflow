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

# ─── Compliance checklist definition (Russian law focus) ──
COMPLIANCE_CHECKLIST = [
    # Категория: Регистрация бизнеса
    {
        "doc_type": "business_registration",
        "title": "Регистрация юридического лица",
        "description": "Свидетельство о регистрации ИП или ООО. Необходимо для любой коммерческой деятельности на территории РФ. Статья 23 ГК РФ.",
        "category": "business",
        "is_required": True,
        "warning": "БЕЗ РЕГИСТРАЦИИ БИЗНЕСА коммерческая эксплуатация платформы является НЕЗАКОННОЙ. Статья 171 УК РФ — незаконное предпринимательство.",
    },
    {
        "doc_type": "tax_registration",
        "title": "Постановка на налоговый учёт (ИНН/ОГРН)",
        "description": "Свидетельство ИНН и ОГРН. Выдаётся ФНС при регистрации. Необходимо для приёма платежей и налоговой отчётности.",
        "category": "business",
        "is_required": True,
        "warning": "Отсутствие налоговой регистрации влечёт административную и уголовную ответственность. Статья 116 НК РФ.",
    },
    {
        "doc_type": "okved_extract",
        "title": "Выписка из ЕГРЮЛ/ЕГРИП с кодами ОКВЭД",
        "description": "Коды ОКВЭД должны включать: 66.12 (посредничество по операциям с ценными бумагами), 66.19 (прочая вспомогательная деятельность в сфере финансовых услуг), 63.11 (обработка данных).",
        "category": "business",
        "is_required": True,
        "warning": "Несоответствие ОКВЭД фактической деятельности может повлечь отказ в обслуживании банками и налоговые проверки.",
    },
    # Категория: Лицензии и разрешения
    {
        "doc_type": "investment_advisor",
        "title": "Статус инвестиционного советника (реестр ЦБ РФ)",
        "description": "Включение в единый реестр инвестиционных советников ЦБ РФ. ОБЯЗАТЕЛЬНО если платформа предоставляет инвестиционные рекомендации (AI-рейтинг сигналов). Федеральный закон № 39-ФЗ 'О рынке ценных бумаг', ст. 6.1.",
        "category": "licenses",
        "is_required": True,
        "warning": "AI-рейтинг сигналов с рекомендациями BUY/SELL квалифицируется как инвестиционное консультирование. Без статуса инвестсоветника это НАРУШЕНИЕ закона. Штраф до 50 000 руб. (ст. 15.29 КоАП).",
    },
    {
        "doc_type": "securities_license",
        "title": "Лицензия профессионального участника РЦБ",
        "description": "Лицензия ЦБ РФ на брокерскую/дилерскую деятельность. Требуется если платформа исполняет ордера на фондовом рынке (MOEX) через Tinkoff Invest, Interactive Brokers и др.",
        "category": "licenses",
        "is_required": False,
        "warning": "Если платформа САМОСТОЯТЕЛЬНО исполняет сделки на бирже от имени клиентов — требуется лицензия. При подключении через API клиента (пользователь сам даёт ключи) — лицензия НЕ требуется.",
    },
    {
        "doc_type": "crypto_license",
        "title": "Разрешение на операции с ЦФА / криптовалютой",
        "description": "Федеральный закон № 259-ФЗ 'О цифровых финансовых активах'. С 01.09.2024 — ФЗ о майнинге. Операции с криптовалютой в РФ регулируются, но не лицензируются напрямую.",
        "category": "licenses",
        "is_required": False,
        "warning": "Криптовалюта НЕ является законным средством платежа в РФ (ст. 14 ФЗ-259). Платформа не должна принимать криптовалюту как оплату. Торговля на крипто-биржах разрешена как имущественная операция.",
    },
    # Категория: Персональные данные
    {
        "doc_type": "personal_data_operator",
        "title": "Регистрация оператора персональных данных (Роскомнадзор)",
        "description": "Уведомление Роскомнадзора об обработке персональных данных по ФЗ-152. ОБЯЗАТЕЛЬНО при сборе email, ФИО, паспортных данных (KYC). Подаётся через портал pd.rkn.gov.ru.",
        "category": "data_protection",
        "is_required": True,
        "warning": "Обработка персональных данных без уведомления Роскомнадзора — нарушение ФЗ-152. Штраф для юрлиц: от 60 000 до 100 000 руб. (ст. 13.11 КоАП). Повторное нарушение — до 300 000 руб.",
    },
    {
        "doc_type": "gdpr_compliance",
        "title": "Соответствие GDPR (для пользователей из ЕС)",
        "description": "Если платформа обслуживает пользователей из Евросоюза — требуется соответствие Общему регламенту по защите данных (GDPR). Включает: DPA, право на удаление, портирование данных.",
        "category": "data_protection",
        "is_required": False,
        "warning": "Штрафы за нарушение GDPR — до 20 млн EUR или 4% годового оборота. Рекомендуется ограничить доступ из ЕС до получения GDPR-compliance.",
    },
    # Категория: AML/KYC
    {
        "doc_type": "aml_policy",
        "title": "Правила внутреннего контроля ПОД/ФТ (115-ФЗ)",
        "description": "Федеральный закон № 115-ФЗ 'О противодействии легализации доходов'. Если платформа принимает платежи — необходимы правила внутреннего контроля. Включает: идентификацию клиентов, мониторинг операций, сообщение о подозрительных операциях.",
        "category": "aml",
        "is_required": True,
        "warning": "Приём платежей без AML/KYC процедур — нарушение 115-ФЗ. Банки могут заблокировать расчётный счёт при выявлении нарушений.",
    },
    {
        "doc_type": "kyc_procedure",
        "title": "Утверждённая процедура идентификации клиентов (KYC)",
        "description": "Документ, описывающий процедуру идентификации: какие данные собираются, как верифицируются, где хранятся. Платформа уже имеет KYC-модуль (фото с паспортом).",
        "category": "aml",
        "is_required": True,
        "warning": "KYC-модуль платформы реализован. Необходимо утвердить документ-процедуру и назначить ответственное лицо.",
    },
    # Категория: Пользовательские документы
    {
        "doc_type": "terms_of_service",
        "title": "Пользовательское соглашение (оферта)",
        "description": "Публичная оферта по ст. 437 ГК РФ. Определяет условия использования платформы, ответственность сторон, порядок оплаты.",
        "category": "user_docs",
        "is_required": True,
        "warning": "Реализовано на платформе (/terms). Рекомендуется заверить юристом.",
    },
    {
        "doc_type": "privacy_policy",
        "title": "Политика конфиденциальности",
        "description": "Описание обработки персональных данных: какие данные, цели, сроки хранения, третьи лица. Требуется по ФЗ-152 и ФЗ-149.",
        "category": "user_docs",
        "is_required": True,
        "warning": "ОТСУТСТВУЕТ на платформе. Необходимо создать и опубликовать.",
    },
    {
        "doc_type": "risk_disclosure",
        "title": "Уведомление о рисках",
        "description": "Предупреждение пользователей о рисках торговли на финансовых рынках. Должно включать: риск потери капитала, волатильность, отсутствие гарантий.",
        "category": "user_docs",
        "is_required": True,
        "warning": "Частично реализовано в Terms of Service. Рекомендуется выделить в отдельный документ.",
    },
    {
        "doc_type": "refund_policy",
        "title": "Политика возврата средств",
        "description": "Условия возврата оплаты за Premium-подписку. Требуется по Закону о защите прав потребителей (ст. 32). Для цифровых услуг — описание условий возврата.",
        "category": "user_docs",
        "is_required": True,
        "warning": "ОТСУТСТВУЕТ. Без политики возврата Stripe может заблокировать аккаунт при спорах (chargebacks).",
    },
    {
        "doc_type": "cookie_policy",
        "title": "Политика использования cookies",
        "description": "Описание файлов cookie, используемых на сайте. Требуется для соответствия ФЗ-152 и рекомендациям Роскомнадзора. Для ЕС — обязательно по ePrivacy Directive.",
        "category": "user_docs",
        "is_required": True,
        "warning": "ОТСУТСТВУЕТ. Необходимо добавить баннер cookies и политику.",
    },
    # Категория: Финансовые гарантии
    {
        "doc_type": "liability_insurance",
        "title": "Страхование профессиональной ответственности",
        "description": "Полис страхования ответственности инвестиционного советника. Минимальная сумма — 2 млн руб. (для реестра ЦБ). Рекомендуется даже без обязательного требования.",
        "category": "financial",
        "is_required": False,
        "warning": "Для включения в реестр инвестиционных советников ЦБ — страхование ОБЯЗАТЕЛЬНО.",
    },
    {
        "doc_type": "financial_guarantee",
        "title": "Финансовая гарантия / уставный капитал",
        "description": "Подтверждение минимального капитала. Для брокерской лицензии — от 3 млн руб. Для инвестиционного советника (ООО) — не менее 10 000 руб. уставного капитала.",
        "category": "financial",
        "is_required": False,
        "warning": "Требования зависят от типа лицензии. При работе как ИП — нет требований к капиталу.",
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
