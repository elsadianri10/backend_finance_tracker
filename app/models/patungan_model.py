from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import Base


class SharedSubscription(Base):
    __tablename__ = 'shared_subscriptions'
    __table_args__ = (
        Index('ix_shared_subscriptions_owner', 'user_id'),
        CheckConstraint('monthly_amount BETWEEN 1 AND 1000000000', name='ck_shared_subscription_amount'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(150))
    monthly_amount: Mapped[int] = mapped_column(BigInteger)


class SubscriptionMember(Base):
    __tablename__ = 'shared_subscription_members'
    __table_args__ = (
        Index('ix_shared_subscription_members_group', 'subscription_id'),
        CheckConstraint('left_on IS NULL OR left_on >= joined_on', name='ck_shared_member_dates'),
        CheckConstraint('version > 0', name='ck_shared_member_version'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    subscription_id: Mapped[UUID] = mapped_column(ForeignKey('shared_subscriptions.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(150))
    joined_on: Mapped[date]
    left_on: Mapped[date | None]
    pay_at_year_end: Mapped[bool]
    version: Mapped[int] = mapped_column(default=1, server_default='1')


class SubscriptionWaiver(Base):
    __tablename__ = 'shared_subscription_waivers'

    member_id: Mapped[UUID] = mapped_column(ForeignKey('shared_subscription_members.id', ondelete='CASCADE'), primary_key=True)
    month: Mapped[date] = mapped_column(primary_key=True)


class SubscriptionReceipt(Base):
    __tablename__ = 'shared_subscription_receipts'
    __table_args__ = (
        Index('ix_shared_subscription_receipts_member', 'member_id'),
        CheckConstraint('amount BETWEEN 1 AND 1000000000000', name='ck_shared_receipt_amount'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    member_id: Mapped[UUID] = mapped_column(ForeignKey('shared_subscription_members.id', ondelete='CASCADE'))
    transaction_id: Mapped[UUID | None] = mapped_column(ForeignKey('ledger_transactions.id', ondelete='CASCADE'), unique=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    paid_on: Mapped[date]
    start_month: Mapped[date | None]
    notes: Mapped[str] = mapped_column(String(1000))
