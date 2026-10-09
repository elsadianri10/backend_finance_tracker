from datetime import date, datetime
from uuid import UUID, uuid4
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base


class RoutinePlan(Base):
    __tablename__ = 'routine_plans'
    __table_args__ = (
        Index('ix_routine_owner', 'user_id'),
        CheckConstraint("kind IN ('SUBSCRIPTION','CONTRIBUTION','TRANSFER')", name='ck_routine_kind'),
        CheckConstraint("status IN ('ACTIVE','NOTE','STOPPED')", name='ck_routine_status'),
        CheckConstraint("amount BETWEEN 0 AND 1000000000000 AND (status <> 'ACTIVE' OR amount > 0)", name='ck_routine_amount'),
        CheckConstraint('interval_months BETWEEN 1 AND 12', name='ck_routine_interval'),
        CheckConstraint('total_cycles BETWEEN 0 AND 60 AND initial_paid >= 0 AND (total_cycles = 0 OR initial_paid <= total_cycles)', name='ck_routine_cycles'),
        CheckConstraint('version > 0', name='ck_routine_version'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(20))
    recipient: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(12))
    first_due_date: Mapped[date]
    interval_months: Mapped[int] = mapped_column(Integer)
    total_cycles: Mapped[int] = mapped_column(Integer)
    initial_paid: Mapped[int] = mapped_column(Integer)
    destination_bank_id: Mapped[UUID | None] = mapped_column(ForeignKey('bank_accounts.id', ondelete='SET NULL'))
    billing_transaction_id: Mapped[UUID | None] = mapped_column(ForeignKey('billing_transactions.id', ondelete='SET NULL'))
    debt_id: Mapped[UUID | None] = mapped_column(ForeignKey('debts.id', ondelete='SET NULL'))
    saving_id: Mapped[UUID | None] = mapped_column(ForeignKey('savings.id'))
    notes: Mapped[str] = mapped_column(String(2000))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoutinePayment(Base):
    __tablename__ = 'routine_payments'
    __table_args__ = (
        Index('uq_routine_payment_sequence', 'plan_id', 'sequence', unique=True, postgresql_where=text('voided_at IS NULL'), sqlite_where=text('voided_at IS NULL')),
        UniqueConstraint('plan_id', 'request_id', name='uq_routine_payment_request'),
        CheckConstraint('sequence > 0', name='ck_routine_payment_sequence'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey('routine_plans.id'))
    request_id: Mapped[UUID]
    sequence: Mapped[int]
    due_date: Mapped[date]
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LedgerTransaction(Base):
    __tablename__ = 'ledger_transactions'
    __table_args__ = (
        Index('ix_ledger_owner_date', 'user_id', 'transaction_date'),
        UniqueConstraint('user_id', 'legacy_id', name='uq_ledger_legacy'),
        Index('uq_ledger_billing_installment', 'billing_installment_id', unique=True, postgresql_where=text('voided_at IS NULL'), sqlite_where=text('voided_at IS NULL')),
        UniqueConstraint('debt_payment_id', name='uq_ledger_debt_payment'),
        UniqueConstraint('saving_movement_id', name='uq_ledger_saving_movement'),
        UniqueConstraint('user_id', 'request_id', name='uq_ledger_request'),
        CheckConstraint("kind IN ('income','expense','transfer')", name='ck_ledger_kind'),
        CheckConstraint('amount > 0 AND amount <= 1000000000000', name='ck_ledger_amount'),
        CheckConstraint('source_bank_id IS NULL OR destination_bank_id IS NULL OR source_bank_id <> destination_bank_id', name='ck_ledger_distinct_banks'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(323))
    amount: Mapped[int] = mapped_column(BigInteger)
    transaction_date: Mapped[date]
    source_bank_id: Mapped[UUID | None] = mapped_column(ForeignKey('bank_accounts.id', ondelete='SET NULL'))
    destination_bank_id: Mapped[UUID | None] = mapped_column(ForeignKey('bank_accounts.id', ondelete='SET NULL'))
    source_label: Mapped[str] = mapped_column(String(150))
    destination_label: Mapped[str] = mapped_column(String(150))
    notes: Mapped[str] = mapped_column(String(2000))
    routine_payment_id: Mapped[UUID | None] = mapped_column(ForeignKey('routine_payments.id'), unique=True)
    billing_installment_id: Mapped[UUID | None] = mapped_column(ForeignKey('billing_installments.id', ondelete='SET NULL'))
    debt_payment_id: Mapped[UUID | None] = mapped_column(ForeignKey('debt_payments.id', ondelete='SET NULL'))
    saving_movement_id: Mapped[UUID | None] = mapped_column(ForeignKey('saving_movements.id'))
    request_id: Mapped[UUID | None]
    request_hash: Mapped[str | None] = mapped_column(String(64))
    legacy_id: Mapped[str | None] = mapped_column(String(200))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransactionImport(Base):
    __tablename__ = 'transaction_imports'
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
