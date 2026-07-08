"""Pydantic-схемы сборки проекта.

Ответ сборки (ok/json/puml/png_url/warnings/error) отдаётся как dict из
``services.render.BuildResult`` — отдельная response-схема не нужна.
"""

from pydantic import BaseModel


class BuildRequest(BaseModel):
    """
    Параметры запроса на сборку проекта.
    
    :param entry: точка входа (имя файла) — если не задана
    :param plantuml_url: URL сервиса PlantUML (для рендера PNG) — 
                         если не задан, берётся settings.plantuml_url
    """
    # Какой файл рендерить. Если не задан — сервер выберет main.ontol/первый.
    entry: str | None = None
