from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base


class Passkey(Base):
    __tablename__ = 'user_passkeys'
    __table_args__ = (Index('ix_passkeys_user_id', 'user_id'), CheckConstraint('sign_count >= 0', name='ck_passkey_counter'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    credential_id: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary)
    name: Mapped[str] = mapped_column(String(80))
    rp_id: Mapped[str] = mapped_column(String(253))
    sign_count: Mapped[int] = mapped_column(BigInteger, default=0)
    backed_up: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasskeyChallenge(Base):
    __tablename__ = 'passkey_challenges'
    __table_args__ = (
        Index('ix_passkey_challenges_user', 'user_id'),
        CheckConstraint("purpose IN ('LOGIN','REGISTER','MANAGE')", name='ck_passkey_purpose'),
        CheckConstraint('attempts BETWEEN 0 AND 5', name='ck_passkey_attempts'),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    purpose: Mapped[str] = mapped_column(String(10))
    challenge: Mapped[bytes] = mapped_column(LargeBinary)
    auth_version: Mapped[int] = mapped_column(BigInteger)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0)


class RecoveryCode(Base):
    __tablename__ = 'passkey_recovery_codes'
    __table_args__ = (Index('ix_recovery_user', 'user_id'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
