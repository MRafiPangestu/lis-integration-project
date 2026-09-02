"""Legacy baseline

Revision ID: 4a24240f8c32
Revises: b1f9dbe772fa
Create Date: 2026-09-02 09:23:43.071549

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a24240f8c32'
down_revision: Union[str, None] = 'b1f9dbe772fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
