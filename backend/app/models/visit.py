from __future__ import annotations

import datetime

from sqlalchemy import ForeignKey, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Visit(Base):
    __tablename__ = "visits"

    id_visit: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_pasien: Mapped[int] = mapped_column(ForeignKey("patients.id_pasien"), nullable=False)
    no_registrasi: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    waktu_kunjungan: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    patient: Mapped[Patient] = relationship(back_populates="visits")
    orders: Mapped[list[Order]] = relationship(back_populates="visit")

