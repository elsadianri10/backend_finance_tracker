from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import Base


class Debt(Base):
    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint("kind IN ('DEBT', 'RECEIVABLE')", name="ck_debt_kind"),
        CheckConstraint("principal > 0 AND principal <= 1000000000000", name="ck_debt_principal"),
        CheckConstraint("(interest_type = 'NONE' AND interest_rate = 0) OR (interest_type = 'MONTHLY' AND interest_rate > 0 AND interest_rate <= 100)", name="ck_debt_interest"),
        CheckConstraint("due_date IS NULL OR due_date >= transaction_date", name="ck_debt_due_date"),
        CheckConstraint("installment_count BETWEEN 0 AND 60 AND (installment_count = 0 OR due_date IS NOT NULL)", name="ck_debt_installments"),
        Index("ix_debts_user_id", "user_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    person_name: Mapped[str] = mapped_column(String(255), nullable=False)
    principal: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    source_bank_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("bank_accounts.id", ondelete="SET NULL"))
    source_bank_name: Mapped[str | None] = mapped_column(String(100))
    source_account_number_masked: Mapped[str | None] = mapped_column(String(30))
    installment_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    installment_amounts: Mapped[list] = mapped_column(JSON, nullable=False, server_default=text("'[]'"))
    interest_type: Mapped[str] = mapped_column(String(20), nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    notes: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DebtPayment(Base):
    __tablename__ = "debt_payments"
    __table_args__ = (
        UniqueConstraint("debt_id", "request_id"),
        UniqueConstraint("debt_id", "sequence"),
        CheckConstraint("amount > 0 AND amount <= 9007199254740991", name="ck_debt_payment_amount"),
        CheckConstraint("sequence >= 1", name="ck_debt_payment_sequence"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    debt_id: Mapped[UUID] = mapped_column(ForeignKey("debts.id"), nullable=False)
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
