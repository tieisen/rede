from datetime import datetime, timezone, timedelta
from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # sankhya | rede
    sistema: Mapped[str] = mapped_column(String(20), unique=True)

    access_token: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token: Mapped[str] = mapped_column(String, nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone(timedelta(hours=-3))),
        onupdate=lambda: datetime.now(timezone(timedelta(hours=-3))),
    )