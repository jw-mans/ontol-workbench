"""project engine (v1/v3)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 00:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'project',
        sa.Column(
            'engine', sa.String(length=2), nullable=False, server_default='v1'
        ),
    )
    # Существующим проектам проставляем язык по файлам: есть .tdl -> v3.
    op.execute(
        "UPDATE project SET engine='v3' WHERE id IN ("
        "SELECT DISTINCT project_id FROM file WHERE name LIKE '%.tdl')"
    )
    op.alter_column('project', 'engine', server_default=None)


def downgrade() -> None:
    op.drop_column('project', 'engine')
