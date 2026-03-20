from datetime import datetime, timezone, timedelta
from sqlalchemy import String, DateTime, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

class Token(Base):
    __tablename__ = "tokens"
    __table_args__ = (
        CheckConstraint("sistema IN ('sankhya', 'rede')", name='ck_tokens_sistema'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sistema: Mapped[str] = mapped_column(String(20), unique=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone(timedelta(hours=-3))),
        onupdate=lambda: datetime.now(timezone(timedelta(hours=-3))),
    )