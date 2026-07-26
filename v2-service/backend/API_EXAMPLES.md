# Примеры использования API (ontol-v3)

## Рендер файла

### Запрос

```bash
curl -X POST http://localhost:8000/projects/abc-123/build \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "entry": "models/domain.tdl"
  }'
```

### Ответ (успешный)

```json
{
  "ok": true,
  "svg": "<svg>...</svg>",
  "warnings": [],
  "planarity": null,
  "error": null
}
```

### Ответ (с предупреждением о цикле)

```json
{
  "ok": true,
  "svg": "<svg>...</svg>",
  "warnings": ["Обнаружен цикл наследования: А -> Б -> А"],
  "planarity": null,
  "error": null
}
```

---

## Создание онтологии

### Запрос

```bash
curl -X POST http://localhost:8000/projects/abc-123/ontologies/build \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "directory_id": "def-456",
    "concepts": [
      {
        "name": "Animal",
        "type": "class",
        "is_abstract": true,
        "attributes": ["+ name: String"],
        "operations": ["+ eat(food: Food): Boolean"]
      },
      {
        "name": "Dog",
        "type": "class",
        "attributes": ["+ breed: String"],
        "operations": ["+ bark(): Void"]
      },
      {
        "name": "Owner",
        "type": "class",
        "attributes": ["+ name: String"]
      }
    ],
    "relations": [
      {
        "relation_type": "generalization",
        "from_concept": "Dog",
        "to_concept": "Animal"
      },
      {
        "relation_type": "association",
        "from_concept": "Dog",
        "to_concept": "Owner",
        "name": "has",
        "multiplicity_from": "[0..*]",
        "multiplicity_to": "[1]"
      }
    ],
    "file_name": "animals.tdl",
    "template": "from_relations"
  }'
```

### Ответ (успешный)

```json
{
  "is_valid": true,
  "warnings": [],
  "planarity": null,
  "error": null
}
```

### Ответ (с ошибкой)

```json
{
  "is_valid": false,
  "warnings": [],
  "planarity": null,
  "error": "Failed to create file: File with this name already exists"
}
```

---

## Проверка TDL-контента

### Запрос

```bash
curl -X POST http://localhost:8000/projects/abc-123/ontologies/check \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "directory_id": "def-456",
    "file_name": "test.tdl",
    "content": "КЛАСС A\nКОНЕЦ КЛАСС\nКЛАСС B\nКОНЕЦ КЛАСС\nОБОБЩЕНИЕ B -> A\n"
  }'
```

### Ответ (валидно)

```json
{
  "is_valid": true,
  "warnings": [],
  "planarity": null,
  "error": null
}
```

### Ответ (с ошибкой)

```json
{
  "is_valid": false,
  "warnings": [],
  "planarity": null,
  "error": "Ошибка модели: Unknown classifier 'C' in Generalization"
}
```

---

## Проверка директории

### Запрос

```bash
curl -X POST "http://localhost:8000/projects/abc-123/ontologies/check_directory?directory_id=def-456" \
  -H "Authorization: Bearer token"
```

### Ответ (успешно)

```json
{
  "is_valid": true,
  "warnings": [],
  "planarity": null,
  "error": null
}
```

### Ответ (с предупреждениями)

```json
{
  "is_valid": false,
  "warnings": [
    "Граф диаграммы не планарен: содержит полный граф на 5 вершинах (K5). Классы-нарушители: A, B, C, D, E. Диаграмма построена как есть (возможны пересечения рёбер)."
  ],
  "planarity": {
    "kind": "K5",
    "labels": ["A", "B", "C", "D", "E"],
    "message": "Граф диаграммы не планарен: содержит полный граф на 5 вершинах (K5). Классы-нарушители: A, B, C, D, E. Диаграмма построена как есть (возможны пересечения рёбер).",
    "subgraphs": [
      {
        "kind": "K5",
        "labels": ["A", "B", "C", "D", "E"]
      }
    ],
    "count": 1
  },
  "error": null
}
```

---

## Получение понятий из TDL

### Запрос (через прямой вызов)

```python
from app.services.render_v3 import get_concepts_from_tdl

text = """
КЛАСС Animal АБСТРАКТНЫЙ
  АТРИБУТЫ
    + name: String
  ОПЕРАЦИИ
    + eat(food: Food): Boolean
КОНЕЦ КЛАСС

КЛАСС Dog
  АТРИБУТЫ
    + breed: String
  ОПЕРАЦИИ
    + bark(): Void
КОНЕЦ КЛАСС

ОБОБЩЕНИЕ Dog -> Animal
"""

concepts = get_concepts_from_tdl(text)
print(concepts)
```

### Ответ

```json
[
  {
    "name": "Animal",
    "type": "class",
    "is_abstract": true,
    "attributes": ["+ name: String"],
    "operations": ["+ eat(food: Food): Boolean"]
  },
  {
    "name": "Dog",
    "type": "class",
    "is_abstract": false,
    "attributes": ["+ breed: String"],
    "operations": ["+ bark(): Void"]
  }
]
```

---

## Работа с несколькими файлами в директории

### Сценарий: Проверка семантической целостности всей директории

```bash
# 1. Получить все .tdl файлы из директории
curl "http://localhost:8000/projects/abc-123/files?directory_id=def-456" \
  -H "Authorization: Bearer token"

# 2. Проверить семантическую целостность
curl -X POST "http://localhost:8000/projects/abc-123/ontologies/check_directory?directory_id=def-456" \
  -H "Authorization: Bearer token"
```

### Сценарий: Создание онтологии из существующих понятий

```bash
# 1. Получить понятия из одного файла
curl -X POST http://localhost:8000/projects/abc-123/ontologies/check \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "directory_id": "def-456",
    "file_name": "domain.tdl",
    "content": "... содержимое domain.tdl ..."
  }'

# 2. Получить понятия из других файлов (через get_concepts_from_tdl)

# 3. Показать пользователю список всех понятий с поиском

# 4. Пользователь выбирает понятия и связи

# 5. Создать новый файл с выбранными понятиями
curl -X POST http://localhost:8000/projects/abc-123/ontologies/build \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "directory_id": "def-456",
    "concepts": [...],
    "relations": [...],
    "file_name": "new_ontology.tdl",
    "template": "from_relations"
  }'
```

---

## Примеры TDL

### Простой класс

```tdl
КЛАСС User
  АТРИБУТЫ
    + id: Integer
    + name: String
  ОПЕРАЦИИ
    + save(): Boolean
КОНЕЦ КЛАСС
```

### Абстрактный класс

```tdl
КЛАСС Shape АБСТРАКТНЫЙ
  ОПЕРАЦИИ
    + area(): Float
КОНЕЦ КЛАСС
```

### Обобщение

```tdl
КЛАСС Dog
КОНЕЦ КЛАСС

ОБОБЩЕНИЕ Dog -> Animal
```

### Ассоциация с кратностью

```tdl
КЛАСС Order
КОНЕЦ КЛАСС

КЛАСС LineItem
КОНЕЦ КЛАСС

АССОЦИАЦИЯ Order [1] : order -- LineItem [0..*] : items ИМЯ "contains"
```

### Композиция

```tddl
КЛАСС House
КОНЕЦ КЛАСС

КЛАСС Room
КОНЕЦ КЛАСС

КОМПОЗИЦИЯ House [1] : house -- Room [0..*] : rooms
```

---

## Обработка ошибок

### Ошибка синтаксиса

```json
{
  "is_valid": false,
  "warnings": [],
  "planarity": null,
  "error": "Ошибка парсера: Ожидался -- , получен - (строка 5, столбец 20)"
}
```

### Ошибка семантики

```json
{
  "is_valid": false,
  "warnings": [],
  "planarity": null,
  "error": "Ошибка модели: Unknown classifier 'NonExistent' in Association"
}
```

### Ошибка цикла наследования

```json
{
  "is_valid": false,
  "warnings": ["Обнаружен цикл наследования: A -> B -> C -> A"],
  "planarity": null,
  "error": "Ошибка модели: Cycle detected in generalizations: A -> B -> C -> A"
}
```

### Ошибка планарности

```json
{
  "is_valid": true,
  "warnings": [],
  "planarity": {
    "kind": "K5",
    "labels": ["A", "B", "C", "D", "E"],
    "message": "Граф диаграммы не планарен: содержит полный граф на 5 вершинах (K5). Классы-нарушители: A, B, C, D, E. Диаграмма построена как есть (возможны пересечения рёбер).",
    "subgraphs": [
      {
        "kind": "K5",
        "labels": ["A", "B", "C", "D", "E"]
      }
    ],
    "count": 1
  },
  "error": null
}
```

---

## Интеграция с frontend

### Список понятий для выбора

```typescript
interface Concept {
  name: string;
  type: 'class' | 'interface' | 'data_type' | 'enum' | 'template';
  isAbstract: boolean;
  attributes: string[];
  operations: string[];
}

// Получить понятия из всех .tdl файлов в директории
const allConcepts: Concept[] = [];
for (const file of tdlFiles) {
  const concepts = await api.getConcepts(file.content);
  allConcepts.push(...concepts);
}
```

### Создание онтологии

```typescript
interface Relation {
  relationType: 'generalization' | 'association' | 'aggregation' | 
                'composition' | 'dependency' | 'realization';
  fromConcept: string;
  toConcept: string;
  name?: string;
  multiplicityFrom?: string;
  multiplicityTo?: string;
}

// Пользователь выбирает понятия и связи
const selectedConcepts: Concept[] = [...];
const selectedRelations: Relation[] = [...];

// Создать онтологию
const response = await api.buildOntology({
  directoryId,
  concepts: selectedConcepts,
  relations: selectedRelations,
  fileName: 'my_ontology.tdl',
  template: 'from_relations'
});

if (response.isValid) {
  // Успешно создано, обновить список файлов
  refreshFiles();
} else {
  // Показать ошибку
  showError(response.error);
}
```

### Валидация в реальном времени

```typescript
// При редактировании TDL в редакторе
async function validateTDL(content: string) {
  const response = await api.checkTDL(content);
  
  if (!response.isValid) {
    showWarning(response.error);
  } else if (response.planarity) {
    showWarning(response.planarity.message);
  }
  
  return response.isValid;
}

// Вызывать при каждом изменении
editor.on('change', () => {
  validateTDL(editor.getValue());
});
```
