"""Схемы запроса опциональной AI-генерации связей."""

from pydantic import BaseModel


class AIHierarchyRequest(BaseModel):
    # Точка входа; если не задана — сервер выберет main.ontol/первый.
    entry: str | None = None
    # Модель Ollama; если не задана — берётся settings.ai_model.
    model: str | None = None
