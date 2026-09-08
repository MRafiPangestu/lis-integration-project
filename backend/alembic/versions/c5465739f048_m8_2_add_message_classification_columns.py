"""M8.2 add message classification columns

Revision ID: c5465739f048
Revises: 621889e316b5
Create Date: 2026-09-08 07:52:56.739902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5465739f048'
down_revision: Union[str, None] = '621889e316b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the M8.2 classification axis to instrument_messages.

    Two nullable columns, no backfill. NULL message_class == ingested before
    M8.2 existed; every terminal path populates it from now on.
    """
    op.add_column(
        "instrument_messages",
        sa.Column("message_class", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "instrument_messages",
        sa.Column("classification_rule", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("instrument_messages", "classification_rule")
    op.drop_column("instrument_messages", "message_class")
