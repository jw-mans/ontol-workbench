from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "engine" / "src"))

from relation_templates import TemplateRelationClassifier, load_templates  # noqa: E402


def test_load_templates_has_all_nine_labels() -> None:
    templates = load_templates(str(ROOT / "templates.yaml"))
    expected = {
        "generalization", "aggregation", "composition", "association",
        "dependency", "input", "output", "instance", "manifest",
    }
    assert set(templates) == expected
    for label, phrases in templates.items():
        assert phrases, f"{label} has no template phrases"


def test_classifier_matches_aggregation_phrase() -> None:
    clf = TemplateRelationClassifier(str(ROOT / "templates.yaml"), str(ROOT / "config" / "formats"))
    text = (
        "Если, то подмножество носителя называется замкнутым относительно операции. "
        "Если замкнуто относительно всех, то называется подалгеброй, где."
    )
    assert clf.predict("множество", "алгебра", text) == "aggregation"


def test_classifier_matches_composition_phrase() -> None:
    clf = TemplateRelationClassifier(str(ROOT / "templates.yaml"), str(ROOT / "config" / "formats"))
    text = (
        "Если — отношение эквивалентности на множестве, то множество классов "
        "эквивалентности называется фактормножеством множества относительно "
        "эквивалентности и обозначается: Фактормножество является подмножеством булеана."
    )
    assert clf.predict("класс эквивалентности", "фактормножество", text) == "composition"


def test_classifier_falls_back_to_generalization_when_nothing_matches() -> None:
    clf = TemplateRelationClassifier(str(ROOT / "templates.yaml"), str(ROOT / "config" / "formats"))
    text = "Функция является функцией на множестве."
    assert clf.predict("формула", "булева функция", text) == "generalization"


def test_classifier_handles_empty_chunk() -> None:
    clf = TemplateRelationClassifier(str(ROOT / "templates.yaml"), str(ROOT / "config" / "formats"))
    assert clf.predict("a", "b", "") == "generalization"


def test_input_output_are_not_distinguishable_by_template_on_identical_text() -> None:
    # см. отчёт: Input/Output различаются только порядком concept_a/concept_b
    clf = TemplateRelationClassifier(str(ROOT / "templates.yaml"), str(ROOT / "config" / "formats"))
    text = (
        "Арифметика, изучаемая в начальной школе, — это алгебра, включающая операции "
        "сложения, умножения, вычитания и деления с остатком, причём носителем "
        "является множество натуральных чисел и ноль."
    )
    forward = clf.predict("деление с остатком", "натуральное число", text)
    backward = clf.predict("натуральное число", "деление с остатком", text)
    assert forward == backward
