from __future__ import annotations

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id_instrument: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nama_mesin: Mapped[str] = mapped_column(String(100), nullable=False)
    protokol: Mapped[Optional[str]] = mapped_column(String(50))
    tipe_koneksi: Mapped[Optional[str]] = mapped_column(String(50))

    # Relationships
    messages: Mapped[list[InstrumentMessage]] = relationship(back_populates="instrument")
    test_runs: Mapped[list[TestRun]] = relationship(back_populates="instrument")

