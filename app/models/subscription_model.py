from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base


class SubscriptionOrder(Base):
    __tablename__ = 'subscription_orders'
    __table_args__ = (
        UniqueConstraint('user_id', 'request_id', name='uq_subscription_request'),
        CheckConstraint("plan IN ('MONTHLY','ANNUAL')", name='ck_subscription_plan'),
        CheckConstraint("environment IN ('sandbox','production')", name='ck_subscription_environment'),
        CheckConstraint('amount > 0', name='ck_subscription_amount'),
        CheckConstraint("state IN ('PENDING','PAID','EXPIRED','CANCELLED','DENIED','REFUNDED','REVIEW')", name='ck_subscription_state'),
        CheckConstraint("renewal_state IN ('NONE','PENDING','CREATING','ACTIVE','REVIEW','CANCELLED','FAILED')", name='ck_subscription_renewal'),
        CheckConstraint('(NOT auto_renew) OR (consented_at IS NOT NULL AND consent_version IS NOT NULL)', name='ck_subscription_consent'),
        Index('ix_subscription_user_created', 'user_id', 'created_at'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    request_id: Mapped[UUID] = mapped_column()
    plan: Mapped[str] = mapped_column(String(10))
    amount: Mapped[int] = mapped_column()
    environment: Mapped[str] = mapped_column(String(10))
    auto_renew: Mapped[bool] = mapped_column(Boolean)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_version: Mapped[str | None] = mapped_column(String(30))
    state: Mapped[str] = mapped_column(String(12), default='PENDING', server_default='PENDING')
    redirect_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    access_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    renewal_state: Mapped[str] = mapped_column(String(12), default='NONE', server_default='NONE')
    provider_subscription_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    next_charge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    setup_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubscriptionPayment(Base):
    __tablename__ = 'subscription_payments'
    __table_args__ = (
        UniqueConstraint('environment', 'transaction_id', name='uq_subscription_transaction'),
        UniqueConstraint('environment', 'provider_order_id', name='uq_subscription_payment_order'),
        CheckConstraint("state IN ('PAID','REFUNDED')", name='ck_subscription_payment_state'),
        CheckConstraint('amount > 0', name='ck_subscription_payment_amount'),
        Index('ix_subscription_payment_order', 'order_id'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey('subscription_orders.id', ondelete='RESTRICT'))
    transaction_id: Mapped[str] = mapped_column(String(100))
    provider_order_id: Mapped[str] = mapped_column(String(100))
    environment: Mapped[str] = mapped_column(String(10))
    amount: Mapped[int] = mapped_column()
    state: Mapped[str] = mapped_column(String(10))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
