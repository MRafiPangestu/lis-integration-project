from __future__ import annotations

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id_dokter: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nama_dokter: Mapped[str] = mapped_column(String(150), nullable=False)
    spesialisasi: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    orders: Mapped[list[Order]] = relationship(back_populates="doctor")

