"""New file to collect manually imported SVG→model examples.

Keep this file for examples you want to develop iteratively from SVG inputs.
Run as: `python -m imported_examples` to generate interactive SVG files.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pathlib import Path

from uml_dsl import (
    Class,
    ClassDiagram,
    ClassPosition,
    Attribute,
    Operation,
    Parameter,
    MultiplicityRange,
    Association,
    AssociationEnd,
    DependencyStereotype,
    svg_to_png,
    svg_to_jpg,
    export_available,
)


OUT_DIR = Path(__file__).parent / "09_02" / "imported_svg"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def save(diagram: ClassDiagram, filename: str, export_raster: bool = True) -> None:
    """Сохраняет интерактивный SVG и при возможности — PNG/JPG."""
    svg_content = diagram.to_svg(width=900, height=500, interactive=True)
    svg_path = OUT_DIR / filename
    svg_path.write_text(svg_content, encoding="utf-8")
    print(f"  ✓ {svg_path}")

    if export_raster and export_available() and svg_to_png and svg_to_jpg:
        try:
            base = Path(filename).stem
            png_path = OUT_DIR / f"{base}.png"
            jpg_path = OUT_DIR / f"{base}.jpg"
            svg_to_png(svg_content, output=png_path)
            svg_to_jpg(svg_content, output=jpg_path)
            print(f"  ✓ {png_path}")
            print(f"  ✓ {jpg_path}")
        except Exception as e:
            print(f"  ⚠ экспорт PNG/JPG: {e}")


def example_from_svg_01():
    """Manual mapping of the provided SVG into UML model objects.

    This example reconstructs the diagram as three classifier boxes A/B/C
    and three instance boxes ": A", ": B", ": C". Each instance is
    modeled as a `Dependency` (instanceOf) pointing to its classifier.
    The resulting diagram is saved as both SVG and interactive HTML.
    """
    A = Class(name="A")
    B = Class(name="B")
    C = Class(name="C")

    instA = Class(name=": A")
    instB = Class(name=": B")
    instC = Class(name=": C")

    d = ClassDiagram(title="imported_svg_01 — manual")
    for c in (A, B, C, instA, instB, instC):
        d.add_classifier(c)

    # represent «instance Of» as dependencies: instance -> classifier
    # Instance is supplier (source of dependency arrow), classifier is client (target).
    # Semantically: instances depend on their classifiers (types).
    # Visually: arrow goes from instance (supplier) to classifier (client).
    d.add_dependency(client=": A", supplier="A", stereotype=DependencyStereotype.INSTANCE_OF)
    d.add_dependency(client=": B", supplier="B", stereotype=DependencyStereotype.INSTANCE_OF)
    d.add_dependency(client=": C", supplier="C", stereotype=DependencyStereotype.INSTANCE_OF)

    # add inheritance: B inherits from A, C inherits from B
    d.add_generalization(specific="B", general="A")
    d.add_generalization(specific="C", general="B")

    d.positions = {
        # Swapped positions: classifiers moved below, instances moved above
        "A": ClassPosition(classifier_name="A", x=86.843573, y=158.50967, width=84.658836, height=35.69226),
        "B": ClassPosition(classifier_name="B", x=237.1706, y=158.50967, width=84.658836, height=35.69226),
        "C": ClassPosition(classifier_name="C", x=387.4976, y=158.50968, width=84.658836, height=35.69226),
        ": A": ClassPosition(classifier_name=": A", x=86.843574, y=44.474173, width=84.658836, height=35.69226),
        ": B": ClassPosition(classifier_name=": B", x=237.1706, y=44.474175, width=84.658836, height=35.69226),
        ": C": ClassPosition(classifier_name=": C", x=387.4976, y=44.474176, width=84.658836, height=35.69226),
    }

    save(d, "imported_svg_01.svg")


def main():
    print("Генерация интерактивных SVG...")
    example_from_svg_01()


if __name__ == "__main__":
    main()
