from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base


class BillingTransaction(Base):
    __tablename__ = "billing_transactions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("billing_accounts.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    tenor: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_date: Mapped[date | None] = mapped_column(Date)
    first_installment: Mapped[date] = mapped_column(Date, nullable=False)
    last_installment: Mapped[date | None] = mapped_column(Date, nullable=True)
    transaction_kind: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ONE_TIME'"))
    stopped_on: Mapped[date | None] = mapped_column(Date)
    recurring_billing_day: Mapped[int | None] = mapped_column(Integer)
    recurring_due_day: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    notes: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("tenor IN (0, 3, 6, 9, 12, 18, 24)"),
        CheckConstraint("amount > 0"),
        CheckConstraint("(transaction_kind = 'ONE_TIME' AND tenor = 0 AND last_installment IS NOT NULL AND stopped_on IS NULL) OR (transaction_kind = 'INSTALLMENT' AND tenor > 0 AND last_installment IS NOT NULL AND stopped_on IS NULL) OR (transaction_kind = 'SUBSCRIPTION' AND tenor = 0 AND last_installment IS NULL)", name="ck_billing_transaction_kind"),
        Index("ix_billing_transactions_account", "account_id"),
    )


class BillingInstallment(Base):
    __tablename__ = "billing_installments"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("billing_transactions.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    charged_on: Mapped[date | None] = mapped_column(Date)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint("transaction_id", "sequence"),
        CheckConstraint("sequence >= 1", name="ck_billing_installment_sequence"),
        CheckConstraint("amount > 0"),
    )
