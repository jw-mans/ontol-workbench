# ONTOL V1 — сборка и запуск (для отчёта)

Записка по результатам Этапа 0 ([../../../V1_PLAN.md](../../../V1_PLAN.md)).

## Зависимости

Зависимости разведены на две части:

| Файл | Назначение |
|---|---|
| `requirements-core.txt` | ядро: парсинг, визуализация, CLI, веб (Streamlit), тесты. Без langchain. |
| `requirements-ai.txt` | опциональный AI-стек (`--gen-hierarchy`, LLM через Ollama/langchain). |
| `requirements.txt` | полный набор (ядро + AI), для обратной совместимости. |

Раньше пакет **не импортировался без langchain** — модуль `ai.py` тянул его на уровне модуля.
Теперь импорт langchain ленивый (внутри `AI.generate_hierarchy`), поэтому ядро, веб и тесты
работают без тяжёлого AI-стека.

## Установка (ядро)

```bash
cd repos/v1
python -m venv .venv
.venv/Scripts/pip install -r requirements-core.txt   # Windows
# source .venv/bin/activate && pip install -r requirements-core.txt  # *nix
```

## Windows: кодировка консоли

Префиксы предупреждений/ошибок содержат эмодзи (🔔/🚨). На стандартной cp1251-консоли
Windows вывод падает с `UnicodeEncodeError`, маскируя реальное сообщение. Перед запуском:

```bash
set PYTHONUTF8=1          # cmd
$env:PYTHONUTF8=1         # PowerShell
export PYTHONUTF8=1       # git-bash
```

## Запуск CLI

Пакет лежит в `src/`, поэтому нужен `PYTHONPATH=src` (или `pip install -e .`):

```bash
PYTHONPATH=src python -m ontol.cli examples/set_theory.ontol
# → examples/set_theory.json + .puml + .png
```

Полезные флаги: `--watch`, `--debug`, `--output-dir <dir>`, `--split-funcs-rels`.

## Тесты

```bash
PYTHONPATH=src python -m pytest tests -q
# 53 passed
```

## Веб — личный кабинет (ЛК)

```bash
pip install -r deploy/requirements.txt   # streamlit + ontol
streamlit run deploy/app.py
```

`deploy/app.py` — многофайловый ЛК поверх слоя `ontol.project`:

- слева: список проектов (создать / переименовать / удалить) и кнопка «Загрузить демо»;
- проект = директория с несколькими `.ontol`; файлы редактируются по вкладкам;
- файлы в пределах проекта импортируют друг друга (`import { ... } from 'other.ontol'`);
- «Собрать» рендерит выбранную точку входа in-process → диаграмма + JSON + `.puml` + zip.

Каталог проектов — `ONTOL_PROJECTS_DIR` (по умолчанию `deploy/projects`).

## AI-фича (опционально)

```bash
pip install -r requirements-ai.txt   # + установленный Ollama с нужной моделью
PYTHONPATH=src python -m ontol.cli examples/set_theory.ontol --gen-hierarchy -m llama3.1
```
