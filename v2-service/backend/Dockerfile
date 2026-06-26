# Образ backend. Контекст сборки — КОРЕНЬ репозитория (см. docker-compose.yml),
# т.к. нужно поставить доменное ядро ontol из src/.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 1) Ядро ontol (editable). pyproject читает README/LICENSE — копируем и их.
#    TODO: ontol тянет langchain как обязательную зависимость (тяжело);
#    при оптимизации образа — вынести AI-стек в optional-extra.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -e .

# 2) Зависимости backend.
COPY v2-service/backend/requirements.txt ./backend-requirements.txt
RUN pip install --no-cache-dir -r backend-requirements.txt

# 3) Код backend.
COPY v2-service/backend ./backend
WORKDIR /app/backend

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
