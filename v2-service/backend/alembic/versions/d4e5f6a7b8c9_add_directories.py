"""add_directories_and_parent_id

Revision ID: d4e5f6a7b8c9
Revises: e5bae891668a
Create Date: 2026-07-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import fastapi_users_db_sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'e5bae891668a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем parent_id для подпроектов (если еще не добавлен)
    try:
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
    except Exception:
        # parent_id уже добавлен, пропускаем
        pass

    # Добавляем engine для выбора языка проекта (если еще не добавлен)
    try:
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
    except Exception:
        # engine уже добавлен, пропускаем
        pass

    op.create_table(
        'directory',
        sa.Column('id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('project_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=False),
        sa.Column('parent_directory_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_directory_id'], ['directory.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'parent_directory_id', 'name', name='uq_directory_project_parent_name'),
    )
    op.create_index(op.f('ix_directory_project_id'), 'directory', ['project_id'], unique=False)
    op.create_index(op.f('ix_directory_parent_directory_id'), 'directory', ['parent_directory_id'], unique=False)

    # Обновляем таблицу file для поддержки directory_id
    op.add_column('file', sa.Column('directory_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True))
    op.create_foreign_key('fk_file_directory_id', 'file', 'directory', ['directory_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_file_directory_id'), 'file', ['directory_id'], unique=False)

    # Удаляем старый уникальный констрейнт на project_id + name
    op.drop_constraint('uq_file_project_name', 'file', type_='unique')
    
    # Создаем новый уникальный констрейнт на project_id + directory_id + name
    op.create_unique_constraint('uq_file_project_directory_name', 'file', ['project_id', 'directory_id', 'name'])

    # Миграция существующих файлов в корневую директорию
    # Создаем корневую директорию для каждого проекта
    op.execute(
        """
        INSERT INTO directory (id, project_id, parent_directory_id, name, created_at)
        SELECT gen_random_uuid(), p.id, NULL, '.', NOW()
        FROM project p
        WHERE NOT EXISTS (
            SELECT 1 FROM directory d WHERE d.project_id = p.id
        )
        """
    )
    
    # Переносим файлы в корневую директорию (directory_id = NULL будет заменен на реальный ID)
    op.execute(
        """
        UPDATE file f
        SET directory_id = (
            SELECT d.id FROM directory d WHERE d.project_id = f.project_id AND d.parent_directory_id IS NULL AND d.name = '.'
        )
        WHERE f.directory_id IS NULL
        """
    )


def downgrade() -> None:
    # Возврат к старому уникальному констрейнту
    op.drop_constraint('uq_file_project_directory_name', 'file', type_='unique')
    op.create_unique_constraint('uq_file_project_name', 'file', ['project_id', 'name'])
    
    op.drop_index(op.f('ix_file_directory_id'), table_name='file')
    op.drop_constraint('fk_file_directory_id', 'file', type_='foreignkey')
    op.drop_column('file', 'directory_id')

    op.drop_index(op.f('ix_directory_parent_directory_id'), table_name='directory')
    op.drop_index(op.f('ix_directory_project_id'), table_name='directory')
    op.drop_table('directory')

    # Удаляем parent_id (если он был добавлен)
    try:
        op.drop_constraint('uq_project_owner_parent_name', 'project', type_='unique')
        op.create_unique_constraint(
            'uq_project_owner_name', 'project', ['owner_id', 'name']
        )
        op.drop_constraint('fk_project_parent_id', 'project', type_='foreignkey')
        op.drop_index(op.f('ix_project_parent_id'), table_name='project')
        op.drop_column('project', 'parent_id')
    except Exception:
        # parent_id уже удален, пропускаем
        pass

    # Удаляем engine (если он был добавлен)
    try:
        op.drop_column('project', 'engine')
    except Exception:
        # engine уже удален, пропускаем
        pass
