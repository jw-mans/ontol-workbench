FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Graphviz (бинарь `dot`) нужен движку ontol-v3 (TDL → SVG). Ставим всегда.
RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/*

# Два независимых движка, каждый со своим pyproject: v1 (`ontol`) в src/ontol-v1,
# v3 (`uml_dsl`) в src/ontol-v3. Ставим как editable-пакеты. AI-стек (тяжёлый
# langchain) — опциональная экстра `[ai]` у v1, включается build-arg INSTALL_AI=true
# (см. docker-compose.ai.yml).
ARG INSTALL_AI=false
COPY src ./src
RUN if [ "$INSTALL_AI" = "true" ]; then \
        pip install --no-cache-dir -e "./src/ontol-v1[ai]"; \
    else \
        pip install --no-cache-dir -e ./src/ontol-v1; \
    fi \
    && pip install --no-cache-dir -e ./src/ontol-v3

COPY v2-service/backend/requirements.txt ./backend-requirements.txt
RUN pip install --no-cache-dir -r backend-requirements.txt

COPY v2-service/backend ./backend
WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:8000"]
