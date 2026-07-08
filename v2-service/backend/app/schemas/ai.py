"""Схемы запроса опциональной AI-генерации связей."""

from pydantic import BaseModel


class AIHierarchyRequest(BaseModel):
    """
    Параметры запроса на генерацию связей (раздел hierarchy) через LLM.
    
    :param entry: точка входа (имя файла) — если не задана
    :param model: модель Ollama (например, "llama2") — если не задана, берётся settings.ai_model
    """
    # Точка входа; если не задана — сервер выберет main.ontol/первый.
    entry: str | None = None
    # Модель Ollama; если не задана — берётся settings.ai_model.
    model: str | None = None
