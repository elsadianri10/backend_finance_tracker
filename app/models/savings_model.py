from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base


class Saving(Base):
    __tablename__ = 'savings'
    __table_args__ = (
        CheckConstraint("kind IN ('CASH','GOLD','DEPOSIT')", name='ck_saving_kind'),
        CheckConstraint('opening_amount > 0', name='ck_saving_opening'),
        CheckConstraint("(kind = 'GOLD' AND metal_type IS NOT NULL AND metal_type IN ('GOLD','SILVER')) OR (kind <> 'GOLD' AND metal_type IS NULL)", name='ck_saving_metal_type'),
        Index('ix_savings_user_id', 'user_id'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    metal_type: Mapped[str | None] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    opening_amount: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    bank_account_id: Mapped[UUID | None] = mapped_column(ForeignKey('bank_accounts.id', ondelete='SET NULL'))
    bank_name: Mapped[str | None] = mapped_column(String(100))
    bank_account_masked: Mapped[str | None] = mapped_column(String(30))
    weight_per_piece: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    pieces: Mapped[int | None]
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 0))
    price_per_gram: Mapped[Decimal | None] = mapped_column(Numeric(18, 0))
    price_date: Mapped[date | None] = mapped_column(Date)
    maturity_date: Mapped[date | None] = mapped_column(Date)
    interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    notes: Mapped[str] = mapped_column(String(2000), nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SavingMovement(Base):
    __tablename__ = 'saving_movements'
    __table_args__ = (
        UniqueConstraint('saving_id', 'request_id'),
        UniqueConstraint('saving_id', 'sequence'),
        CheckConstraint("direction IN ('ADD','REMOVE') AND amount > 0", name='ck_saving_movement'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    saving_id: Mapped[UUID] = mapped_column(ForeignKey('savings.id'), nullable=False)
    request_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(String(2000), nullable=False, default='')
