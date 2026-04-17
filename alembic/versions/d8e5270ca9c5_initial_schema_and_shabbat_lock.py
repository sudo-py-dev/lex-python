"""Initial schema and Shabbat Lock

Revision ID: d8e5270ca9c5
Revises: 
Create Date: 2026-04-17 14:36:59.075740

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e5270ca9c5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the new chatshabbatlock table (Safe for existing databases)
    op.create_table('chatshabbatlock',
    sa.Column('chatId', sa.BigInteger(), nullable=False),
    sa.Column('isEnabled', sa.Boolean(), server_default=sa.text('0'), nullable=False),
    sa.Column('lastPermissions', sa.Text(), nullable=True),
    sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['chatId'], ['chatsettings.id'], name=op.f('fk_chatshabbatlock_chatId_chatsettings')),
    sa.PrimaryKeyConstraint('chatId', name=op.f('pk_chatshabbatlock'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('chatshabbatlock')
