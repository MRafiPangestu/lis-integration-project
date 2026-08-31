from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Unit(Base):
    __tablename__ = "units"

    id_unit: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kode_unit: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nama_unit: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    orders: Mapped[list[Order]] = relationship(back_populates="unit")

