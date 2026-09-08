"""M8.4 add order overview query indexes

Revision ID: 4aff9e134f16
Revises: c5465739f048
Create Date: 2026-09-08 14:45:44.162436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4aff9e134f16'
down_revision: Union[str, None] = 'c5465739f048'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Additive query-performance indexes for the M8.4 instrument order overview.

    No columns, tables, constraints or existing indexes are touched. The
    optional fifth index on ``test_runs (id_order, is_final DESC, run_sequence
    DESC)`` is deliberately NOT created: the existing UNIQUE
    ``uk_order_run_sequence`` plus per-order cardinality make the effective-run
    LIMIT-1 ordering cheap, and no EXPLAIN evidence showed a dedicated index is
    needed.
    """
    # instrument scope: EXISTS / semi-join and the effective-run LATERAL
    op.create_index(
        "ix_test_runs_id_instrument_id_order",
        "test_runs",
        ["id_instrument", "id_order"],
    )
    # Order -> Visit join
    op.create_index("ix_orders_id_visit", "orders", ["id_visit"])
    # Visit -> Patient join
    op.create_index("ix_visits_id_pasien", "visits", ["id_pasien"])
    # final output ordering + date-range scan on the worklist
    op.create_index(
        "ix_orders_waktu_order_id_order",
        "orders",
        [sa.text("waktu_order DESC"), sa.text("id_order DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_orders_waktu_order_id_order", table_name="orders")
    op.drop_index("ix_visits_id_pasien", table_name="visits")
    op.drop_index("ix_orders_id_visit", table_name="orders")
    op.drop_index("ix_test_runs_id_instrument_id_order", table_name="test_runs")
