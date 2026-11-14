from datetime import datetime
from uuid import UUID,uuid4
from sqlalchemy import CheckConstraint,DateTime,ForeignKey,Index,SmallInteger,String,func
from sqlalchemy.orm import Mapped,mapped_column
from app.models.base_model import Base
class UserAdminAudit(Base):
    __tablename__='user_admin_audit'
    __table_args__=(CheckConstraint('previous_f IN (0,1) AND admin_f IN (0,1)',name='ck_admin_audit_flags'),Index('ix_admin_audit_user_created','user_id','created_at'))
    id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    user_id:Mapped[UUID]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    actor_id:Mapped[UUID|None]=mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    previous_f:Mapped[int]=mapped_column(SmallInteger)
    admin_f:Mapped[int]=mapped_column(SmallInteger)
    reason:Mapped[str]=mapped_column(String(500))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
