from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import CHAR, Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Patient(Base):
    __tablename__ = "patients"

    id_pasien: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nomor_rm: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nama_lengkap: Mapped[str] = mapped_column(String(200), nullable=False)
    tanggal_lahir: Mapped[Optional[datetime.date]] = mapped_column(Date)
    jenis_kelamin: Mapped[Optional[str]] = mapped_column(CHAR(1))

    # Relationships
    visits: Mapped[list[Visit]] = relationship(back_populates="patient")

