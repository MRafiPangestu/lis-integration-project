from __future__ import annotations

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TestGroup(Base):
    __tablename__ = "test_groups"

    id_group: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nama_group: Mapped[str] = mapped_column(String(100), nullable=False)
    urutan_tampil: Mapped[Optional[int]] = mapped_column()

    # Relationships
    tests: Mapped[list[TestCatalog]] = relationship(back_populates="group")

