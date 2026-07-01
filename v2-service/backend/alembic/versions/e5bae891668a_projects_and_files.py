"""projects and files

Revision ID: e5bae891668a
Revises: e168b259fbb3
Create Date: 2026-06-27 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import fastapi_users_db_sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'e5bae891668a'
down_revision: Union[str, None] = 'e168b259fbb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project',
        sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('owner_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_id', 'name', name='uq_project_owner_name'),
    )
    op.create_index(op.f('ix_project_owner_id'), 'project', ['owner_id'], unique=False)

    op.create_table(
        'file',
        sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('project_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_file_project_name'),
    )
    op.create_index(op.f('ix_file_project_id'), 'file', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_file_project_id'), table_name='file')
    op.drop_table('file')
    op.drop_index(op.f('ix_project_owner_id'), table_name='project')
    op.drop_table('project')
