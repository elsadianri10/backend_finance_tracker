from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base

class AccountDeletion(Base):
    __tablename__ = 'account_deletions'
    __table_args__ = (CheckConstraint("status IN ('PENDING','REVIEWING','CANCELLED','CLEANUP','COMPLETED')",name='ck_deletion_status'),Index('ix_deletion_status_created','status','created_at'))
    id: Mapped[UUID] = mapped_column(primary_key=True,default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    subject_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(12),default='PENDING')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'))

class DeletionBlob(Base):
    __tablename__ = 'account_deletion_blobs'
    id: Mapped[UUID] = mapped_column(primary_key=True,default=uuid4)
    request_id: Mapped[UUID] = mapped_column(ForeignKey('account_deletions.id',ondelete='CASCADE'),index=True)
    url: Mapped[str] = mapped_column(String(2048))
