# ONTOL V1 — сборка и запуск (для отчёта)

Записка по результатам Этапа 0 ([../../../V1_PLAN.md](../../../V1_PLAN.md)).

## Зависимости

Зависимости разведены на две части:

Пакет v1 (`ontol`) переехал в `src/ontol-v1/` (свой `pyproject.toml`).

| Файл | Назначение |
|---|---|
| `src/ontol-v1/requirements-core.txt` | ядро: парсинг, визуализация, CLI, веб (Streamlit), тесты. Без langchain. |
| `src/ontol-v1/requirements-ai.txt` | опциональный AI-стек (`--gen-hierarchy`, LLM через Ollama/langchain). |
| `src/ontol-v1/requirements.txt` | полный набор (ядро + AI), для обратной совместимости. |

Раньше пакет **не импортировался без langchain** — модуль `ai.py` тянул его на уровне модуля.
Теперь импорт langchain ленивый (внутри `AI.generate_hierarchy`), поэтому ядро, веб и тесты
работают без тяжёлого AI-стека.

## Установка (ядро)

```bash
python -m venv .venv
.venv/Scripts/pip install -e src/ontol-v1        # Windows (ядро)
# source .venv/bin/activate && pip install -e src/ontol-v1  # *nix
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

После `pip install -e src/ontol-v1` доступна CLI-команда `ontol`:

```bash
ontol src/ontol-v1/examples/set_theory.ontol
# → src/ontol-v1/examples/set_theory.json + .puml + .png
```

Полезные флаги: `--watch`, `--debug`, `--output-dir <dir>`, `--split-funcs-rels`.

## Тесты

```bash
python -m pytest src/ontol-v1/tests -q
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
pip install -e src/ontol-v1[ai]   # + установленный Ollama с нужной моделью
ontol src/ontol-v1/examples/set_theory.ontol --gen-hierarchy -m llama3.1
```
