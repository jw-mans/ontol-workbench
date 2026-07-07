# DiGr engine

DSL для запросов к тексту: разбор документа в AST и исполнение запросов
FIND/CONTEXT/DISTANCE по единой грамматике (`dsl_grammar.rbnf`). Используется
без изменений в [`../relation-classifier`](../relation-classifier) и
[`../ontology-pipeline`](../ontology-pipeline). Отчёт о выводе единой
грамматики — [`../docs/dsl_unification_report.pdf`](../docs/dsl_unification_report.pdf).

- `src/actor` — акторный рантайм (FSM, драйверы, почтовые ящики).
- `src/document_ast` — парсинг документа в AST.
- `src/dsl` — DSL: лексер, парсер, единая модель запроса и его исполнение.
- `main.py` — CLI: строит AST документа, даёт интерактивный DSL-запрос.
- `tests/` — тесты движка и CLI.
- `config/formats/`, `text.txt`, `GA_1_2025.tex` — тестовые данные и конфигурация
  форматов.

Другие каталоги подключают движок через `PYTHONPATH=../engine/src` (см. их
README). `config/formats/*.yaml` и `requirements.txt` там свои — это
конфигурация запуска, а не код.

## Запуск

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=src .venv/Scripts/python -m pytest -q
```

Единственный ожидаемый непройденный тест — `test_cli_noninteractive_smoke_outputs_ast_json`:
падает из-за кодировки консоли Windows (`cp1252`) при выводе кириллицы в `main.py`,
не связано с DSL.
