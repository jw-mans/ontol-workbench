# ontol_v3_students

## Полная документация

📖 **[PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)** — подробное описание проекта, архитектуры, взаимосвязей файлов и итогов работы.

## Краткий обзор

**ontol_v3_students** — система для работы с UML-диаграммами классов:

- **Text Diagram Language (TDL)** → **SVG** через Graphviz
- **Обратный парсинг** SVG → Pydantic-модели
- **Семантическая валидация** диаграмм
- **Веб-интерфейс** на Streamlit

## Быстрый старт

```bash
# Установка зависимостей
pip install -r requirements.txt

# Генерация SVG из TDL
python -m uml_dsl.tdl_run examples/example.tdl

# Запуск веб-интерфейса
streamlit run uml_dsl/app.py
```

## Архитектура

**TDL текст** → Лексер → Парсер → AST → Сборка модели → **Graphviz** → SVG с data-атрибутами ↔ **Обратный парсинг**

### Ключевые компоненты
- `uml_dsl/models.py` — базовые модели UML
- `uml_dsl/diagram.py` — диаграмма и валидация
- `uml_dsl/graphviz_render.py` — генерация SVG
- `uml_dsl/svg_parser.py` — парсинг SVG
- `uml_dsl/app.py` — веб-интерфейс

## Тестирование

```bash
# Генерация тестовых данных
cd examples
python -m imported_examples

# Тестирование парсера
python -m test_parser
```

---

*Подробная документация: [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)*

---

# Список изменений

## Шаг 1: Добавление data-атрибутов в классы
**Файл:** `models.py`
**Метод:** `to_svg()`
**Что сделано:**
- Добавлены data-атрибуты для обратного парсинга:
  - `data-id`, `data-name`, `data-type="class"`
  - `data-stereotype`, `data-abstract`
  - `data-attributes-count`, `data-operations-count`

## Шаг 2: Добавление data-атрибутов в отношения
**Файл:** `diagram.py`
**Методы:** `_render_association_svg()`, `_render_dependency_svg()`, `_render_generalization_svg()`, `_render_realization_svg()`, `_render_nary_association_svg()`
**Что сделано:**
- Для ассоциаций: `data-src`, `data-tgt`, `data-type="association"`, `data-name`, `data-derived`, `data-src-multiplicity`, `data-tgt-multiplicity`, `data-src-role`, `data-tgt-role`, `data-src-navigable`, `data-tgt-navigable`, `data-src-aggregation`, `data-tgt-aggregation`
- Для зависимостей: `data-src`, `data-tgt`, `data-type="dependency"`, `data-stereotype`
- Для обобщений: `data-src`, `data-tgt`, `data-type="generalization"`, `data-substitutable`
- Для реализаций: `data-src`, `data-tgt`, `data-type="realization"`
- Для n-арных ассоциаций: `data-type="nary-association"`, `data-name`, `data-derived`, `data-arity`, `data-participants`

## Шаг 3: Создание парсера SVG → Pydantic
**Новый файл:** `svg_parser.py`
**Функции:**
- `parse_transform()` — извлечение координат из transform="translate(x,y)"
- `parse_svg_to_diagram()` — главная функция парсинга
- `multiplicity_range_from_str()` — парсинг строк кратности

**Что делает:**
- Извлекает классы из `data-type="class"`
- Извлекает ассоциации из `data-type="association"`
- Извлекает зависимости из `data-type="dependency"`
- Извлекает обобщения из `data-type="generalization"`
- Извлекает реализации из `data-type="realization"`
- Восстанавливает позиции классов из transform

## Шаг 4: Тестирование парсера
**Новый файл:** `test_parser.py`
**Функции:**
- `test_parser()` — проверка парсинга всех SVG в папке
- `test_roundtrip()` — проверка полного цикла: Pydantic → SVG → Pydantic → SVG

**Результат:** Roundtrip успешен, файлы идентичны.

## Шаг 5: Streamlit-приложение
**Новый файл:** `app.py`
**Компоненты:**
- Загрузка SVG-файла
- Превью диаграммы
- Кнопка валидации
- Отображение статистики (классы, ассоциации, обобщения, зависимости)
- Детали модели в JSON
- Боковая панель с описанием
- Кнопки для быстрой загрузки примеров

**Запуск:** `streamlit run app.py`

## Итог
Создан работающий прототип с полным циклом:
JSON (через imported_examples.py) → Pydantic → SVG (с тегами) → Parser → Pydantic → Валидация → Интерфейс
