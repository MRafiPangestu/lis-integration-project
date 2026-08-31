from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, TIMESTAMP, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (
        # Prevent duplicate parameter within a single test run
        UniqueConstraint("id_run", "parameter_tes", name="uk_run_parameter"),
    )

    id_hasil: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_run: Mapped[int] = mapped_column(ForeignKey("test_runs.id_run"), nullable=False)
    parameter_tes: Mapped[str] = mapped_column(String(50), nullable=False)
    nilai_hasil: Mapped[str] = mapped_column(String(50), nullable=False)
    satuan: Mapped[Optional[str]] = mapped_column(String(20))
    flag_abnormalitas: Mapped[Optional[str]] = mapped_column(String(10))
    reference_range_snapshot: Mapped[Optional[str]] = mapped_column(String(100))
    waktu_hasil: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    test_run: Mapped[TestRun] = relationship(back_populates="results")

