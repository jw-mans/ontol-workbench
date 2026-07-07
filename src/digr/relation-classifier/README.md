# Синтаксические шаблоны для классификации связей

Замена нейросетевой (RuBERT) классификации отношений между понятиями на
сопоставление с текстовыми шаблонами через DSL-запрос. Отчёт —
[`../docs/relation_classifier_report.pdf`](../docs/relation_classifier_report.pdf).

- `templates.yaml` — шаблоны-фразы на 9 меток онтологии (generalization/aggregation/
  composition/association/dependency/input/output/instance/manifest), выведены из
  `reference_chunk`.
- `relation_templates.py` — `TemplateRelationClassifier`: сопоставляет шаблоны через
  DSL-запрос `CONTEXT ... FOR concept_a, concept_b, template RETURN count`.
- `predict_relations_templates.py` — замена `predict_relations.py`, тот же CLI-контракт.
- `build_chunks_dataset.py` — копия шага A (не изменена), запускается на общем движке
  из [`../engine`](../engine), чтобы проверить, что объединённый движок не ломает этот
  реальный пайплайн. Корпус дискретки — общий, лежит в [`../data`](../data)
  (`--tex ../data/all_lectures.tex --pairs ../data/pairs_w_relation.json`).
- `data/` — эталонные и предсказанные куски (`chunks_ontology_text_*.jsonl`),
  результаты оценки; здесь же используется корпус из `../data`.
- `tests/` — тесты `TemplateRelationClassifier`.

## Итог эксперимента

| Подход | Accuracy | Macro-F1 |
|---|---|---|
| Нейросеть, честная оценка (`holdout_metrics.json`) | 0.302 | 0.250 |
| Всегда `generalization` (majority-class baseline) | 0.505 | ≈0.075 |
| Синтаксические шаблоны (эта задача) | 0.454 | 0.136 |


## Запуск

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
PYTHONPATH=../engine/src PYTHONIOENCODING=utf-8 .venv/Scripts/python predict_relations_templates.py \
    --chunks data/chunks_ontology_text_reference.jsonl --out data/chunks_ontology_text_templates.jsonl
PYTHONIOENCODING=utf-8 .venv/Scripts/python eval_predictions.py --chunks data/chunks_ontology_text_templates.jsonl
PYTHONPATH=../engine/src .venv/Scripts/python -m pytest -q tests/
```

Загрузка в Qdrant (отдельный venv, Python 3.12 — под 3.14 не собирается numpy):

```bash
py -3.12 -m venv .venv312
.venv312/Scripts/pip install --quiet qdrant-client sentence-transformers
.venv312/Scripts/python load_qdrant.py --chunks data/chunks_ontology_text_templates.jsonl \
    --qdrant-path data/qdrant_db --collection concept_pairs_templates
```
