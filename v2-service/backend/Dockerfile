FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
# По умолчанию ядро ontol ставится БЕЗ AI-экстры (тяжёлый langchain вынесен в
# optional-extra `[ai]`). Опциональная AI-фича включается build-arg INSTALL_AI=true
# (см. docker-compose.ai.yml) — тогда ставим `.[ai]`.
ARG INSTALL_AI=false
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN if [ "$INSTALL_AI" = "true" ]; then \
        pip install --no-cache-dir -e ".[ai]"; \
    else \
        pip install --no-cache-dir -e .; \
    fi

COPY v2-service/backend/requirements.txt ./backend-requirements.txt
RUN pip install --no-cache-dir -r backend-requirements.txt

COPY v2-service/backend ./backend
WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:8000"]
