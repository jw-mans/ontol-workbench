#!/usr/bin/env python
"""accuracy/macro-F1 по chunks-файлу (relation_type vs predicted_relation_type).

python eval_predictions.py --chunks data/chunks_ontology_text_existing.jsonl
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict

# Inheritance -> generalization не опечатка, см. relation_matcher/README.md
LABEL_MAP = {
    "Aggregation": "aggregation",
    "Association": "association",
    "Composition": "composition",
    "Dependency": "dependency",
    "Inheritance": "generalization",
    "Input": "input",
    "Instance": "instance",
    "Manifest": "manifest",
    "Output": "output",
}


def load_rows(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def evaluate(rows: list[dict]) -> None:
    y_true: list[str] = []
    y_pred: list[str] = []
    skipped = 0
    for row in rows:
        true_raw = row.get("relation_type")
        pred = row.get("predicted_relation_type")
        if true_raw is None or pred is None:
            skipped += 1
            continue
        true = LABEL_MAP.get(true_raw)
        if true is None:
            skipped += 1
            continue
        y_true.append(true)
        y_pred.append(pred)

    n = len(y_true)
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / n if n else 0.0

    labels = sorted(set(y_true) | set(y_pred))
    tp: Counter = Counter()
    fp: Counter = Counter()
    fn: Counter = Counter()
    support: Counter = Counter()
    for t, p in zip(y_true, y_pred):
        support[t] += 1
        if t == p:
            tp[t] += 1
        else:
            fp[p] += 1
            fn[t] += 1

    per_class = {}
    f1_values = []
    for label in labels:
        precision = tp[label] / (tp[label] + fp[label]) if (tp[label] + fp[label]) else 0.0
        recall = tp[label] / (tp[label] + fn[label]) if (tp[label] + fn[label]) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[label] = {
            "support": support[label],
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }
        f1_values.append(f1)
    macro_f1 = sum(f1_values) / len(f1_values) if f1_values else 0.0

    print(f"Всего пар с истинной и предсказанной меткой: {n} (пропущено: {skipped})")
    print(f"Accuracy: {correct}/{n} = {accuracy:.4f}")
    print(f"Macro-F1: {macro_f1:.4f}")
    print()
    print(f"{'label':<16}{'support':>8}{'precision':>11}{'recall':>9}{'f1':>7}")
    for label in labels:
        stats = per_class[label]
        print(f"{label:<16}{stats['support']:>8}{stats['precision']:>11.3f}{stats['recall']:>9.3f}{stats['f1']:>7.3f}")

    print()
    print("Порог из ToR (>50% accuracy):", "ПРОЙДЕН" if accuracy > 0.5 else "НЕ ПРОЙДЕН")


def main() -> int:
    parser = argparse.ArgumentParser(description="Метрика классификатора типа связи")
    parser.add_argument("--chunks", default="data/chunks_ontology_text_existing.jsonl")
    args = parser.parse_args()
    rows = load_rows(args.chunks)
    evaluate(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
