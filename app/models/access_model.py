from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base


class AccountAccess(Base):
    __tablename__ = 'account_access'
    __table_args__ = (CheckConstraint("subscription_plan IN ('FREE','PRO')", name='ck_access_plan'),
                     CheckConstraint('version > 0', name='ck_access_version'),
                     CheckConstraint('(trial_started_at IS NULL AND trial_until IS NULL) OR (trial_started_at IS NOT NULL AND trial_until IS NOT NULL AND trial_until > trial_started_at)', name='ck_access_trial_dates'))
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    subscription_plan: Mapped[str] = mapped_column(String(10), default='FREE', server_default='FREE')
    subscription_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    complimentary: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    complimentary_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1, server_default='1')


class AccessAudit(Base):
    __tablename__ = 'access_audit'
    __table_args__ = (CheckConstraint("action IN ('GRANT','REVOKE')", name='ck_access_audit_action'),
                     Index('ix_access_audit_target', 'user_id', 'created_at'))
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    action: Mapped[str] = mapped_column(String(10))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
