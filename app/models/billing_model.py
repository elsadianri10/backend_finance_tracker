from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import Base


class WalletProvider(Base):
    __tablename__ = "wallet_providers"
    __table_args__ = (CheckConstraint("bank_f IN (0, 1)", name="ck_wallet_provider_bank_f"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    bank_f: Mapped[int] = mapped_column(Integer, server_default=text("0"))


# Preserve internal imports and the /billing/platforms API while sharing providers.
BillingPlatform = WalletProvider


class BillingAccount(Base):
    __tablename__ = "billing_accounts"
    __table_args__ = (
        CheckConstraint("platform_type IN ('CREDIT_CARD', 'PAY_LATER')", name="ck_billing_account_type"),
        CheckConstraint("(platform_type = 'CREDIT_CARD' AND account_type IS NOT NULL AND account_number_encrypted IS NOT NULL AND valid_thru IS NOT NULL) OR (platform_type = 'PAY_LATER' AND account_type IS NULL AND account_number_encrypted IS NULL AND valid_thru IS NULL)", name="ck_billing_card_fields"),
        CheckConstraint("(has_fixed_bill_date = TRUE AND billing_date BETWEEN 1 AND 31 AND due_date BETWEEN 1 AND 31 AND billing_date IS NOT NULL AND due_date IS NOT NULL) OR (has_fixed_bill_date = FALSE AND billing_date IS NULL AND due_date IS NULL)", name="ck_billing_fixed_dates"),
        Index("ix_billing_accounts_user_id", "user_id"),
        CheckConstraint("monthly_fee BETWEEN 0 AND 1000000000000 AND payment_fee BETWEEN 0 AND 1000000000000", name="ck_billing_account_fees"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform_id: Mapped[int] = mapped_column(ForeignKey("wallet_providers.id"), nullable=False)
    platform_type: Mapped[str] = mapped_column(String(20), nullable=False)
    account_type: Mapped[str | None] = mapped_column(String(100))
    account_number_encrypted: Mapped[str | None] = mapped_column(Text)
    valid_thru: Mapped[str | None] = mapped_column(String(7))
    has_fixed_bill_date: Mapped[bool] = mapped_column(Boolean, nullable=False)
    billing_date: Mapped[int | None] = mapped_column(Integer)
    due_date: Mapped[int | None] = mapped_column(Integer)
    monthly_fee: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False, default=0, server_default=text("0"))
    payment_fee: Mapped[int] = mapped_column(Numeric(18, 0), nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

