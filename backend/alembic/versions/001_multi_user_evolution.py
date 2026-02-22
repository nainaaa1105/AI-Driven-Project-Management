"""multi-user workspace evolution

Revision ID: 001_multi_user
Revises: None
Create Date: 2026-02-22

This migration evolves the backend from single-user to multi-user,
workspace-based architecture. It:
  - Adds columns to existing tables (users, tasks, messages, alerts)
  - Creates new tables (workspaces, workspace_members, channels,
    message_task_map, ai_events)
  - All new columns are nullable to preserve existing data
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_multi_user"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New tables ───────────────────────────────────────────────────

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True, default=""),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workspaces_id", "workspaces", ["id"])

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
    )
    op.create_index("ix_workspace_members_id", "workspace_members", ["id"])

    op.create_table(
        "channels",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True, default=""),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_channels_id", "channels", ["id"])

    op.create_table(
        "message_task_map",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=False, default="spawned"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_message_task_map_id", "message_task_map", ["id"])

    op.create_table(
        "ai_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.Text, nullable=True),
        sa.Column("triggered_by_message_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_events_id", "ai_events", ["id"])

    # ── Alter existing tables ────────────────────────────────────────

    # users: add email, password_hash, role, created_at
    op.add_column("users", sa.Column("email", sa.String(255), nullable=True, unique=True))
    op.add_column("users", sa.Column("password_hash", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("role", sa.String(50), nullable=False, server_default="user"))
    op.add_column("users", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_users_email", "users", ["email"])

    # tasks: add workspace_id, channel_id, assigned_user_id
    op.add_column("tasks", sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True))
    op.add_column("tasks", sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="SET NULL"), nullable=True))
    op.add_column("tasks", sa.Column("assigned_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_tasks_workspace_id", "tasks", ["workspace_id"])

    # messages: add sender_id, workspace_id, channel_id
    op.add_column("messages", sa.Column("sender_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("messages", sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True))
    op.add_column("messages", sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_messages_workspace_id", "messages", ["workspace_id"])
    op.create_index("ix_messages_channel_id", "messages", ["channel_id"])

    # alerts: add workspace_id
    op.add_column("alerts", sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_alerts_workspace_id", "alerts", ["workspace_id"])


def downgrade() -> None:
    # ── Remove added columns from existing tables ────────────────────
    op.drop_index("ix_alerts_workspace_id", table_name="alerts")
    op.drop_column("alerts", "workspace_id")

    op.drop_index("ix_messages_channel_id", table_name="messages")
    op.drop_index("ix_messages_workspace_id", table_name="messages")
    op.drop_column("messages", "channel_id")
    op.drop_column("messages", "workspace_id")
    op.drop_column("messages", "sender_id")

    op.drop_index("ix_tasks_workspace_id", table_name="tasks")
    op.drop_column("tasks", "assigned_user_id")
    op.drop_column("tasks", "channel_id")
    op.drop_column("tasks", "workspace_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "created_at")
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")

    # ── Drop new tables ──────────────────────────────────────────────
    op.drop_table("ai_events")
    op.drop_table("message_task_map")
    op.drop_table("channels")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
