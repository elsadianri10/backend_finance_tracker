from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        CheckConstraint("admin_fee BETWEEN 0 AND 1000000000000 AND others_fee BETWEEN 0 AND 1000000000000", name="ck_bank_account_fees"),
        Index("ix_bank_accounts_user_id", "user_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform_id: Mapped[int] = mapped_column(ForeignKey("wallet_providers.id"), nullable=False)
    account_number_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    card_number_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    valid_thru: Mapped[str] = mapped_column(String(7), nullable=False)
    admin_fee: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    others_fee: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
