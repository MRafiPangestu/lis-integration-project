from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Order(Base):
    __tablename__ = "orders"

    id_order: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_visit: Mapped[int] = mapped_column(ForeignKey("visits.id_visit"), nullable=False)
    id_unit: Mapped[Optional[int]] = mapped_column(ForeignKey("units.id_unit"))
    id_dokter: Mapped[Optional[int]] = mapped_column(ForeignKey("doctors.id_dokter"))
    diagnosa: Mapped[Optional[str]] = mapped_column(Text)
    waktu_order: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.current_timestamp()
    )
    status_order: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="Diproses"
    )

    # Relationships
    visit: Mapped[Visit] = relationship(back_populates="orders")
    unit: Mapped[Optional[Unit]] = relationship(back_populates="orders")
    doctor: Mapped[Optional[Doctor]] = relationship(back_populates="orders")
    test_runs: Mapped[list[TestRun]] = relationship(back_populates="order")

