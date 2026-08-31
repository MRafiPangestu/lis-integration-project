from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TestCatalog(Base):
    __tablename__ = "tests"

    id_test: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_group: Mapped[Optional[int]] = mapped_column(ForeignKey("test_groups.id_group"))
    kode_tes: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nama_tes: Mapped[str] = mapped_column(String(100), nullable=False)
    satuan_default: Mapped[Optional[str]] = mapped_column(String(20))

    # Relationships
    group: Mapped[Optional[TestGroup]] = relationship(back_populates="tests")

