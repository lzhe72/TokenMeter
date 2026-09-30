"""Initial user, revocable session, audit and login throttle schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("username", sa.String(64), nullable=False, unique=True),
                    sa.Column("password_hash", sa.String(255), nullable=False),
                    sa.Column("role", sa.String(16), nullable=False),
                    sa.Column("is_active", sa.Boolean(), nullable=False),
                    sa.Column("must_change_password", sa.Boolean(), nullable=False),
                    sa.Column("credential_version", sa.Integer(), nullable=False),
                    sa.CheckConstraint("role IN ('admin', 'member')", name="user_role"))
    op.create_table("sessions", sa.Column("token_hash", sa.String(64), primary_key=True),
                    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("credential_version", sa.Integer(), nullable=False),
                    sa.Column("expires_at", sa.BigInteger(), nullable=False))
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_table("audit", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id")),
                    sa.Column("target_id", sa.String(36), sa.ForeignKey("users.id")),
                    sa.Column("action", sa.String(64), nullable=False),
                    sa.Column("occurred_at", sa.BigInteger(), nullable=False))
    op.create_index("ix_audit_occurred_at", "audit", ["occurred_at"])
    op.create_table("login_buckets", sa.Column("key", sa.String(80), primary_key=True),
                    sa.Column("failures", sa.Integer(), nullable=False),
                    sa.Column("window_start", sa.BigInteger(), nullable=False))


def downgrade():
    raise RuntimeError("Account data is not destructively downgraded; restore a verified backup")
