"""trips table

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("thread_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False, server_default="demo"),
        sa.Column("destination", sa.String(120), nullable=False),
        sa.Column("origin", sa.String(120), nullable=False),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("travellers", sa.JSON(), nullable=False),
        sa.Column("total_inr", sa.Integer(), nullable=False),
        sa.Column("bookings", sa.JSON(), nullable=False),
        sa.Column("itinerary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_trips_thread_id", "trips", ["thread_id"])
    op.create_index("ix_trips_user_id", "trips", ["user_id"])


def downgrade() -> None:
    op.drop_table("trips")
