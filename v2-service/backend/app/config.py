"""Конфигурация сервиса (pydantic-settings).

Файл `.env` ищется рядом с пакетом backend (а не в текущей директории запуска),
поэтому конфиг грузится одинаково из-под uvicorn, alembic и тестов.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / '.env'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding='utf-8',
        extra='ignore',
    )

    app_name: str = 'Ontol API'

    # Async-движок SQLAlchemy: схема postgresql+asyncpg.
    database_url: str = 'postgresql+asyncpg://ontol:ontol@localhost:5432/ontol'

    # База URL своего PlantUML-сервера (PNG-эндпоинт), для рендера диаграмм.
    plantuml_url: str = 'http://localhost:8080/png/'

    # Redis для очереди фоновых задач (arq).
    redis_url: str = 'redis://localhost:6379/0'

    # Сколько ждать результат сборки от воркера, прежде чем отдать 504.
    build_timeout_seconds: int = 60

    # --- Опциональная AI-генерация связей (Ollama + langchain) -------------- #
    # Выключена по умолчанию. Включается AI_ENABLED=true; требует образ с экстрой
    # [ai] и доступный Ollama (см. docker-compose.ai.yml).
    ai_enabled: bool = False
    # База URL Ollama-сервера (LLM).
    ollama_url: str = 'http://ollama:11434'
    # Модель Ollama по умолчанию (должна быть заранее `ollama pull`-нута).
    ai_model: str = 'llama3'
    # AI-запрос к LLM дольше сборки — отдельный таймаут ожидания результата.
    ai_timeout_seconds: int = 120

    # Секрет для подписи cookie-сессий и токенов (fastapi-users).
    # В проде ОБЯЗАТЕЛЬНО переопределить; ≥32 байт (для HMAC-SHA256).
    secret: str = 'dev-secret-change-me-in-production-0000'

    # Время жизни токена/cookie авторизации, секунды (по умолчанию 7 дней —
    # рефреша нет, час слишком мал и заставляет часто перелогиниваться).
    access_token_lifetime_seconds: int = 604800

    # Ставить ли флаг Secure у cookie (True — только по HTTPS; для прода).
    cookie_secure: bool = False

    # Источники, которым разрешён CORS (фронтенд на Vite).
    cors_origins: list[str] = ['http://localhost:5173']


settings = Settings()
