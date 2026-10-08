"""initial migration

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-22 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="reviewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # 2. cameras table
    op.create_table(
        "cameras",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("stream_url", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. zones table
    op.create_table(
        "zones",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("camera_id", sa.String(length=36), sa.ForeignKey("cameras.id"), nullable=True),
        sa.Column("zone_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("boundary_polygon", sa.JSON(), nullable=False),
        sa.Column("expected_angle_degrees", sa.Float(), nullable=False, server_default="90.0"),
        sa.Column("zone_type", sa.String(length=50), nullable=False, server_default="parking_bay"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zones_zone_id", "zones", ["zone_id"], unique=True)

    # 4. vehicles table
    op.create_table(
        "vehicles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("camera_id", sa.String(length=36), sa.ForeignKey("cameras.id"), nullable=True),
        sa.Column("class_name", sa.String(length=50), nullable=False, server_default="motorcycle"),
        sa.Column("thumbnail_path", sa.String(length=255), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicles_track_id", "vehicles", ["track_id"])

    # 5. parking_events table
    op.create_table(
        "parking_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vehicle_id", sa.String(length=36), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("zone_id", sa.String(length=36), sa.ForeignKey("zones.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dwell_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("ml_label", sa.String(length=50), nullable=True),
        sa.Column("ml_confidence", sa.Float(), nullable=True),
        sa.Column("ml_probabilities", sa.JSON(), nullable=True),
        sa.Column("snapshot_path", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parking_events_vehicle_id", "parking_events", ["vehicle_id"])
    op.create_index("ix_parking_events_zone_id", "parking_events", ["zone_id"])

    # 6. violations table
    op.create_table(
        "violations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("parking_event_id", sa.String(length=36), sa.ForeignKey("parking_events.id"), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("review_status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("confirmed_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_by_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_violations_parking_event_id", "violations", ["parking_event_id"], unique=True)


def downgrade() -> None:
    op.drop_table("violations")
    op.drop_table("parking_events")
    op.drop_table("vehicles")
    op.drop_table("zones")
    op.drop_table("cameras")
    op.drop_table("users")
