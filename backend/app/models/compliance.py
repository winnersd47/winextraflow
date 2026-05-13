"""Compliance model — tracks legal documents, licenses, admin confirmations."""

import enum
import uuid

from sqlalchemy import String, Enum, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ComplianceDocType(str, enum.Enum):
    """Types of compliance documents an admin can upload/confirm."""
    # Регистрация бизнеса
    BUSINESS_REGISTRATION = "business_registration"    # ИП/ООО свидетельство
    TAX_REGISTRATION = "tax_registration"              # ИНН/ОГРН
    OKVЕД_EXTRACT = "okved_extract"                    # Выписка с ОКВЭД

    # Лицензии / Разрешения
    INVESTMENT_ADVISOR = "investment_advisor"           # Статус инвестиционного советника (ЦБ)
    SECURITIES_LICENSE = "securities_license"           # Лицензия профучастника РЦБ
    CRYPTO_LICENSE = "crypto_license"                   # Лицензия на операции с ЦФА

    # Персональные данные
    PERSONAL_DATA_OPERATOR = "personal_data_operator"  # Регистрация в Роскомнадзор (152-ФЗ)
    GDPR_COMPLIANCE = "gdpr_compliance"                # GDPR соответствие (для ЕС)

    # AML / KYC
    AML_POLICY = "aml_policy"                          # Правила внутреннего контроля (115-ФЗ)
    KYC_PROCEDURE = "kyc_procedure"                    # Процедура идентификации клиентов

    # Пользовательские документы
    TERMS_OF_SERVICE = "terms_of_service"              # Пользовательское соглашение
    PRIVACY_POLICY = "privacy_policy"                  # Политика конфиденциальности
    RISK_DISCLOSURE = "risk_disclosure"                # Уведомление о рисках
    REFUND_POLICY = "refund_policy"                    # Политика возврата
    COOKIE_POLICY = "cookie_policy"                    # Политика cookies

    # Страхование / Финансовые гарантии
    LIABILITY_INSURANCE = "liability_insurance"         # Страхование ответственности
    FINANCIAL_GUARANTEE = "financial_guarantee"         # Банковская гарантия


class ComplianceStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    UPLOADED = "uploaded"
    VERIFIED = "verified"
    EXPIRED = "expired"
    NOT_REQUIRED = "not_required"


class ComplianceDocument(Base):
    __tablename__ = "compliance_documents"

    doc_type: Mapped[ComplianceDocType] = mapped_column(Enum(ComplianceDocType), unique=True)
    status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus), default=ComplianceStatus.NOT_STARTED
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(String(50), default="general")
