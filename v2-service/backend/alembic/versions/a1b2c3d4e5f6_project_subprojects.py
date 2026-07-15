"""project subprojects (parent_id)

Revision ID: a1b2c3d4e5f6
Revises: e5bae891668a
Create Date: 2026-07-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import fastapi_users_db_sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e5bae891668a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'project',
        sa.Column(
            'parent_id',
            fastapi_users_db_sqlalchemy.generics.GUID(),
            nullable=True,
        ),
    )
    op.create_index(
        op.f('ix_project_parent_id'), 'project', ['parent_id'], unique=False
    )
    op.create_foreign_key(
        'fk_project_parent_id',
        'project',
        'project',
        ['parent_id'],
        ['id'],
        ondelete='CASCADE',
    )
    # Имя теперь уникально среди соседей (одного родителя), а не глобально.
    op.drop_constraint('uq_project_owner_name', 'project', type_='unique')
    op.create_unique_constraint(
        'uq_project_owner_parent_name',
        'project',
        ['owner_id', 'parent_id', 'name'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_project_owner_parent_name', 'project', type_='unique')
    op.create_unique_constraint(
        'uq_project_owner_name', 'project', ['owner_id', 'name']
    )
    op.drop_constraint('fk_project_parent_id', 'project', type_='foreignkey')
    op.drop_index(op.f('ix_project_parent_id'), table_name='project')
    op.drop_column('project', 'parent_id')
