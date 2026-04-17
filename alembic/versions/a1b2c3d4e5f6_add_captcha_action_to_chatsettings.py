"""Add captcha_action to chatsettings

Revision ID: a1b2c3d4e5f6
Revises: d8e5270ca9c5
Create Date: 2026-04-17 18:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "d8e5270ca9c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add captchaAction column to chatsettings table
    op.add_column(
        "chatsettings",
        sa.Column(
            "captchaAction",
            sa.String(length=50),
            server_default=sa.text("'ban'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove captchaAction column from chatsettings table
    op.drop_column("chatsettings", "captchaAction")
