from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base


class SplitBillGroup(Base):
    __tablename__ = 'split_bill_groups'
    __table_args__ = (
        Index('ix_split_bill_groups_user_id', 'user_id'),
        CheckConstraint('version > 0', name='ck_split_bill_version'),
        CheckConstraint("length(trim(name)) > 0", name='ck_split_group_name'),
        CheckConstraint("start_date >= '2000-01-01' AND end_date >= start_date", name='ck_split_group_dates'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date]
    end_date: Mapped[date]
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SplitBillParticipant(Base):
    __tablename__ = 'split_bill_participants'
    __table_args__ = (
        UniqueConstraint('group_id', 'position', name='uq_split_participant_position'),
        CheckConstraint('position BETWEEN 0 AND 19', name='ck_split_participant_position'),
        CheckConstraint("length(trim(name)) > 0", name='ck_split_participant_name'),
    )
    group_id: Mapped[UUID] = mapped_column(ForeignKey('split_bill_groups.id', ondelete='CASCADE'), primary_key=True)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    position: Mapped[int]


class SplitBillExpense(Base):
    __tablename__ = 'split_bill_expenses'
    __table_args__ = (
        ForeignKeyConstraint(['group_id', 'paid_by'], ['split_bill_participants.group_id', 'split_bill_participants.id']),
        UniqueConstraint('group_id', 'position', name='uq_split_expense_position'),
        CheckConstraint('position BETWEEN 0 AND 99', name='ck_split_expense_position'),
        CheckConstraint("length(trim(name)) > 0", name='ck_split_expense_name'),
        CheckConstraint("service_mode IN ('AMOUNT','PERCENT') AND service_value >= 0 AND service_value <= 1000000000000 AND (service_mode <> 'PERCENT' OR service_value <= 100) AND (service_mode <> 'AMOUNT' OR service_value = round(service_value))", name='ck_split_service'),
        CheckConstraint("tax_mode IN ('AMOUNT','PERCENT') AND tax_value >= 0 AND tax_value <= 1000000000000 AND (tax_mode <> 'PERCENT' OR tax_value <= 100) AND (tax_mode <> 'AMOUNT' OR tax_value = round(tax_value))", name='ck_split_tax'),
        CheckConstraint("fee_allocation IN ('PROPORTIONAL','EQUAL','MIXED')", name='ck_split_fee_allocation'),
        CheckConstraint('receipt_total IS NULL OR receipt_total BETWEEN 0 AND 1000000000000', name='ck_split_receipt_total'),
    )
    group_id: Mapped[UUID] = mapped_column(ForeignKey('split_bill_groups.id', ondelete='CASCADE'), primary_key=True)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    expense_date: Mapped[date]
    paid_by: Mapped[UUID]
    service_mode: Mapped[str] = mapped_column(String(10))
    service_value: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    tax_mode: Mapped[str] = mapped_column(String(10))
    tax_value: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    tax_includes_service: Mapped[bool] = mapped_column(Boolean)
    fee_allocation: Mapped[str] = mapped_column(String(12))
    receipt_total: Mapped[int | None] = mapped_column(BigInteger)
    notes: Mapped[str] = mapped_column(String(2000))
    position: Mapped[int]


class SplitBillItem(Base):
    __tablename__ = 'split_bill_items'
    __table_args__ = (
        ForeignKeyConstraint(['group_id', 'expense_id'], ['split_bill_expenses.group_id', 'split_bill_expenses.id'], ondelete='CASCADE'),
        UniqueConstraint('group_id', 'expense_id', 'position', name='uq_split_item_position'),
        CheckConstraint('position BETWEEN 0 AND 99', name='ck_split_item_position'),
        CheckConstraint("length(trim(name)) > 0", name='ck_split_item_name'),
        CheckConstraint('amount > 0 AND amount <= 1000000000000', name='ck_split_item_amount'),
        CheckConstraint("split_mode IN ('EQUAL','CUSTOM')", name='ck_split_item_mode'),
    )
    group_id: Mapped[UUID] = mapped_column(primary_key=True)
    expense_id: Mapped[UUID] = mapped_column(primary_key=True)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[int] = mapped_column(BigInteger)
    split_mode: Mapped[str] = mapped_column(String(6))
    position: Mapped[int]


class SplitBillShare(Base):
    __tablename__ = 'split_bill_shares'
    __table_args__ = (
        ForeignKeyConstraint(['group_id', 'expense_id', 'item_id'], ['split_bill_items.group_id', 'split_bill_items.expense_id', 'split_bill_items.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['group_id', 'participant_id'], ['split_bill_participants.group_id', 'split_bill_participants.id']),
        UniqueConstraint('group_id', 'expense_id', 'item_id', 'position', name='uq_split_share_position'),
        CheckConstraint('position BETWEEN 0 AND 19', name='ck_split_share_position'),
        CheckConstraint('amount BETWEEN 0 AND 1000000000000', name='ck_split_share_amount'),
    )
    group_id: Mapped[UUID] = mapped_column(primary_key=True)
    expense_id: Mapped[UUID] = mapped_column(primary_key=True)
    item_id: Mapped[UUID] = mapped_column(primary_key=True)
    participant_id: Mapped[UUID] = mapped_column(primary_key=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    position: Mapped[int]

