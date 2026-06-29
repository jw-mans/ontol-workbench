# V2 — multi-user service (FastAPI + React)

Полноценный многопользовательский сервис, который придёт на смену прототипу на
Streamlit ([../v1-streamlit/](../v1-streamlit/)). Оба приложения существуют
**параллельно** и используют общее ядро `src/ontol`. Сборка `.ontol` в диаграммы
(JSON / PlantUML / PNG) выполняется в фоне через очередь.

Полный план реализации, модель данных, API и дорожная карта:
[../docs/V2_PLAN.md](../docs/V2_PLAN.md).

## Архитектура

| Сервис | Что это | Порт (хост) |
|--------|---------|-------------|
| `web` | SPA (Vite-сборка) за nginx, проксирует `/api` на backend | `5173` |
| `api` | FastAPI (gunicorn + uvicorn-воркеры): auth, CRUD, постановка сборок в очередь | `8000` |
| `worker` | arq-воркер: рендерит диаграммы, читая файлы из БД | — |
| `db` | PostgreSQL 16 | `5433` |
| `redis` | брокер очереди arq | — |
| `plantuml` | PlantUML-сервер (PNG) | `8080` |

- **backend/** — FastAPI + SQLAlchemy 2.0 (async) + Alembic + PostgreSQL,
  авторизация на `fastapi-users` (JWT в httpOnly-cookie, stateless).
- **frontend/** — React + Vite + TypeScript + Monaco (своя подсветка Ontol).

Фронт и API на одном origin (`/api` проксируется nginx/Vite), поэтому CORS в
проде не задействован.

## Запуск через Docker (рекомендуется)

Из каталога `v2-service`:

```bash
cp .env.example .env          # затем задать SECRET (см. ниже)
docker compose up --build
```

Открыть **http://localhost:5173** → регистрация → проекты → файлы → «Собрать».

Миграции БД применяются автоматически при старте `api`
(`alembic upgrade head`) — отдельных шагов не нужно.

### Переменные окружения

Compose читает `v2-service/.env` автоматически. Обязательна одна переменная —
`SECRET` (подпись cookie/JWT), остальные имеют дев-дефолты:

```bash
# сгенерировать секрет:
python -c "import secrets; print(secrets.token_hex(32))"
```

| Переменная | Назначение | Дефолт |
|------------|-----------|--------|
| `SECRET` | подпись cookie/JWT (**обязательна**) | — |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | креды Postgres | `ontol` |
| `CORS_ORIGINS` | разрешённые origin (JSON-массив) | `["http://localhost:5173"]` |
| `WEB_CONCURRENCY` | число gunicorn-воркеров у `api` | `2` |

> Контейнер `db` публикуется на хост-порт **5433** (а не 5432), чтобы не
> конфликтовать с локально установленным PostgreSQL. Внутри сети compose сервисы
> ходят к `db:5432`.

## Локальный запуск без Docker (для разработки)

Нужны запущенные Postgres и Redis (можно поднять только их:
`docker compose up -d db redis plantuml`).

**Backend** (из корня репозитория):
```bash
pip install -e .                                   # ядро ontol (без AI-стека)
pip install -r v2-service/backend/requirements.txt

cd v2-service/backend
# .env рядом с backend задаёт DATABASE_URL / REDIS_URL / SECRET
alembic upgrade head
uvicorn app.main:app --reload                      # http://localhost:8000 (/docs)

# отдельным процессом — воркер рендера:
arq app.worker.WorkerSettings
```

**Frontend:**
```bash
cd v2-service/frontend
npm install
npm run dev                                        # http://localhost:5173
```
Vite проксирует `/api` на `http://localhost:8000` (переопределяется
`VITE_API_TARGET`).

## Тесты (backend)

```bash
cd v2-service/backend
pip install -r requirements-dev.txt
pytest
```
Гоняются на in-memory SQLite — внешняя БД не нужна.

## Замечания

- AI-стек (langchain) сервису не нужен и в образ не ставится (ядро ontol — без
  экстры `[ai]`).
- Для PNG нужен контейнер `plantuml`; без него JSON и PlantUML-исходник всё равно
  возвращаются, а PNG уходит в `warnings`.
