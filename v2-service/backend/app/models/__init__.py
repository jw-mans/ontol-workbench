"""ORM-модели.

Импортируем модели здесь, чтобы они регистрировались на ``Base.metadata`` и
попадали в автогенерацию миграций Alembic.
"""

from app.models.file import File
from app.models.project import Project
from app.models.user import User

__all__ = ['User', 'Project', 'File']
