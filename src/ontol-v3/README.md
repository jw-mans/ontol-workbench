# Ontol v3

Ontol v3 - Python-пакет для описания UML-диаграмм классов на языке TDL
(Text Diagram Language), проверки полученной модели и генерации SVG.

Пакет можно использовать отдельно, через командную строку, через демонстрационное
приложение Streamlit (устаревший способ) или как движок рендера `.tdl`-файлов внутри общего
приложения workbench.

## Документация

- [Технический отчет по рендеру TDL в SVG](TDL_TO_SVG_RENDERING.md) описывает
  текущий пайплайн от текста TDL до итогового SVG.
- [Проектный отчет за апрель 2026](PROJECT_REPORT_APRIL_2026.md) сохраняет
  отчетную часть проекта и исторические заметки по реализации.

## Возможности

- Лексер, парсер, AST и сборка модели из TDL.
- Pydantic-модель UML для классов, атрибутов, операций и отношений.
- Семантическая валидация диаграммы.
- Генерация SVG через системный Graphviz `dot`.
- SVG data-атрибуты для обратного парсинга.
- Обратный парсер SVG в UML-модель.
- Демонстрационное приложение Streamlit.
- Опциональный экспорт SVG в PNG/JPG.
- Анализ планарности v3-диаграмм, включая диагностику K5/K3,3.
- CSS-темы SVG: `light` и `yellow`.

## Требования

- Python 3.9 или новее.
- Graphviz должен быть установлен как системная программа; команда `dot` должна
  быть доступна в `PATH`.

Python-зависимости объявлены в `pyproject.toml`.

## Установка

Из папки `src/ontol-v3`:

```bash
pip install -e .
```

Для Streamlit-приложения:

```bash
pip install -e ".[app]"
```

Для экспорта в PNG/JPG:

```bash
pip install -e ".[export]"
```

Для полной автономной разработки:

```bash
pip install -e ".[app,export]"
```

## Использование из командной строки

Сгенерировать SVG рядом с исходным `.tdl`-файлом:

```bash
python -m uml_dsl.tdl_run examples/tdl/basic/example.tdl
```

Записать результат в явный путь:

```bash
python -m uml_dsl.tdl_run examples/tdl/basic/example.tdl out.svg
```

Вывод PNG/JPG требует дополнительных зависимостей `export`:

```bash
python -m uml_dsl.tdl_run examples/tdl/basic/example.tdl out.png
```

## Streamlit-приложение

Запуск из папки `src/ontol-v3`:

```bash
streamlit run uml_dsl/app.py
```

В приложении есть две вкладки:

- рендер TDL в SVG;
- проверка SVG и парсинг обратно в UML-модель.

Примеры для приложения лежат в `examples/app/`.

## Python API

```python
from uml_dsl.tdl_run import tdl_to_svg

tdl = """
КЛАСС A
КОНЕЦ КЛАСС
"""

svg = tdl_to_svg(tdl, theme="light")
```

Рендер с диагностикой планарности:

```python
from uml_dsl.tdl_run import tdl_to_svg_analyzed

svg, warnings, planarity = tdl_to_svg_analyzed(tdl)
```

`planarity` равен `None`, если диаграмма планарна. Для непланарной диаграммы
там возвращается тип найденного препятствия, связанные имена классов и сообщение
для пользователя.

## Пайплайн

Рендер TDL:

```text
Текст TDL
-> tdl_lexer.lex
-> tdl_parser.parse_tdl
-> tdl_ast.Document
-> tdl_build.build_diagram
-> ClassDiagram.validate_all
-> анализ планарности
-> graphviz_render.diagram_to_graphviz_svg
-> SVG
```

Обратный парсинг SVG:

```text
SVG
-> svg_parser.parse_svg_to_diagram
-> Pydantic UML-модель
-> ClassDiagram.validate_all
```

## Структура проекта

```text
uml_dsl/
  app.py                  демонстрационное приложение Streamlit
  diagram.py              контейнер ClassDiagram и входная точка валидации
  graphviz_render.py      SVG-рендер
  models.py               UML-классификаторы, атрибуты, операции
  relationships.py        UML-отношения
  svg_parser.py           SVG -> модель
  tdl_*.py                лексер, парсер, AST, сборка модели, CLI для TDL
  styles/                 SVG-темы

examples/
  app/                    примеры для Streamlit-приложения
  tdl/basic/              обычные TDL-примеры и сгенерированные SVG
  tdl/errors/             некорректные TDL-примеры для проверки диагностик
  svg/manual/             вручную подготовленные SVG-примеры

tests/
  fixtures/svg_parser/    фикстуры SVG-парсера
  test_*.py               основной pytest-набор Ontol v3
  scripts/                ручные утилиты генерации фикстур SVG-парсера
```

## Тесты и проверки

Для запуска всех тестов Ontol v3 изолированно от backend и frontend:

```bash
cd src/ontol-v3
python -m pip install -e ".[test]"
python run_tests.py
```

Запускатель `run_tests.py` вызывает только pytest-набор из `src/ontol-v3/tests`.
Аргументы pytest можно передавать дальше:

```bash
python run_tests.py -q
```

Что проверяется:

- лексер, парсер, сборка UML-модели и сообщения об ошибках;
- валидация наследования, типов, композиций и модификаторов атрибутов;
- анализ планарности, включая K5 и K3,3;
- SVG-рендер, темы, маркеры отношений, кратности и data-атрибуты;
- обратный разбор SVG в модель;
- CLI-команда `python -m uml_dsl.tdl_run`.

Ручные утилиты для обновления фикстур SVG-парсера остаются отдельно:

```bash
python tests/scripts/generate_svg_parser_examples.py
python tests/scripts/test_svg_parser.py
```

В общем workbench также есть backend-тесты интеграции v3-рендера:
`v2-service/backend/tests/test_render_v3.py`. Они проверяют, что `.tdl`-файлы
отправляются в v3-движок, а SVG и данные планарности корректно проходят через
границу приложения. Эти backend-тесты не входят в `run_tests.py`.

## Примеры

- `examples/tdl/basic/example.tdl` - самый маленький обычный TDL-пример.
- `examples/tdl/basic/diagram_1_*.tdl` - более крупные примеры диаграмм классов.
- `examples/tdl/errors/` - некорректные примеры для проверки валидации.
- `examples/app/` - примеры, которые показывает Streamlit-приложение.

## Зависимости

Основные зависимости:

- `pydantic`;
- `networkx`;
- системный Graphviz `dot`.

Опциональные extra-зависимости:

- `app`: демонстрационное приложение Streamlit;
- `export`: CairoSVG и Pillow для экспорта в PNG/JPG;
- `test`: pytest для автономного набора тестов Ontol v3.

`pyproject.toml` является единственным источником метаданных пакета,
Python-зависимостей и наборов дополнительных зависимостей.
