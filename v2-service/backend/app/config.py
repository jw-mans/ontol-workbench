"""Конфигурация сервиса (pydantic-settings).

Значения читаются из переменных окружения (или `.env`). Имена переменных
совпадают с именами полей в верхнем регистре, напр. поле ``database_url`` ←
переменная ``DATABASE_URL``.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    app_name: str = 'Ontol V2 API'

    # Async-движок SQLAlchemy: схема postgresql+asyncpg.
    database_url: str = 'postgresql+asyncpg://ontol:ontol@localhost:5432/ontol'

    # База URL своего PlantUML-сервера (PNG-эндпоинт), для рендера диаграмм.
    plantuml_url: str = 'http://localhost:8080/png/'

    # Секрет для подписи cookie-сессий (fastapi-users, Фаза 1).
    secret: str = 'change-me-in-production'

    # Источники, которым разрешён CORS (фронтенд на Vite).
    cors_origins: list[str] = ['http://localhost:5173']


settings = Settings()
