# V1 — Streamlit personal workspace (личный кабинет)

Текущий «тяжёлый» ЛК на Streamlit: проекты из нескольких `.ontol`-файлов,
авторизация, редактор с автосохранением, сборка в JSON + PlantUML + PNG.
Рендер выполняется **in-process** через пакет `ontol`.

Существует **параллельно** с новым сервисом в [../v2-service/](../v2-service/)
(см. план: [../docs/V2_PLAN.md](../docs/V2_PLAN.md)). Общее ядро — `src/ontol`.

## Запуск

```bash
# 1) поставить ядро ontol из корня репозитория (editable):
pip install -e .
# 2) зависимости ЛК:
pip install -r v1-streamlit/requirements.txt
# 3) запустить:
streamlit run v1-streamlit/app.py
```

## Конфигурация (env)

- `ONTOL_PROJECTS_DIR` — каталог проектов (по умолчанию `v1-streamlit/projects`).
- `ONTOL_USERS_FILE` — файл учёток (по умолчанию `<projects_dir>/users.json`).

## Статус

Прототип. Ограничения (сессии в памяти, учётки в JSON, гонки при конкуренции)
описаны в [../docs/REPORT.md](../docs/REPORT.md). «Настоящий» многопользовательский
вариант реализуется в `v2-service` по [../docs/V2_PLAN.md](../docs/V2_PLAN.md).
