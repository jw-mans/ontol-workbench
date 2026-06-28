"""Pydantic-схемы сборки проекта.

Ответ сборки (ok/json/puml/png_url/warnings/error) отдаётся как dict из
``services.render.BuildResult`` — отдельная response-схема не нужна.
"""

from pydantic import BaseModel


class BuildRequest(BaseModel):
    # Какой файл рендерить. Если не задан — сервер выберет main.ontol/первый.
    entry: str | None = None
