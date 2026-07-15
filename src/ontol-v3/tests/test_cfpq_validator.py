import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from uml_dsl.diagram import ClassDiagram
from uml_dsl.models import Class
from uml_dsl.enums import DependencyStereotype

def test_cfpq_clean_diagram_passes():
    """Тест: Корректная диаграмма должна проходить валидацию без ошибок."""
    d = ClassDiagram()
    d.add_classifier(Class(name="Base"))
    d.add_classifier(Class(name="Derived"))
    
    d.add_generalization(specific="Derived", general="Base")
    d.validate_all()


def test_cfpq_abab_antipattern_warns():
    """Антипаттерн ABAB — предупреждение (не ошибка): validate_all не бросает,
    а возвращает его в списке предупреждений даже в строгом режиме."""
    d = ClassDiagram()
    d.add_classifier(Class(name="ServiceAbstract"))
    d.add_classifier(Class(name="ServiceConcrete"))
    d.add_classifier(Class(name="RepositoryAbstract"))
    d.add_classifier(Class(name="RepositoryConcrete"))

    d.add_generalization(specific="ServiceConcrete", general="ServiceAbstract")
    d.add_generalization(specific="RepositoryConcrete", general="RepositoryAbstract")

    d.add_dependency(client="ServiceAbstract", supplier="RepositoryConcrete", stereotype=DependencyStereotype.USE)
    d.add_dependency(client="RepositoryAbstract", supplier="ServiceConcrete", stereotype=DependencyStereotype.USE)

    warnings = d.validate_all()
    assert any("антипаттерн" in w.lower() for w in warnings)
