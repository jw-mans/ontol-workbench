#!/usr/bin/env python3
"""
Тест парсера SVG -> Pydantic
"""
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from uml_dsl.svg_parser import parse_svg_to_diagram


def test_parser():
    """Тестирует парсер на сгенерированных SVG файлах."""
    
    # Путь к папке с SVG (созданной generate_svg_parser_examples.py)
    svg_dir = TESTS_ROOT / "fixtures" / "svg_parser"
    
    if not svg_dir.exists():
        print(f"Папка не найдена: {svg_dir}")
        print("Сначала запустите: python tests/scripts/generate_svg_parser_examples.py")
        return
    
    # Находим все SVG файлы
    svg_files = list(svg_dir.glob("*.svg"))
    
    if not svg_files:
        print("Нет SVG файлов для тестирования")
        return
    
    print(f"Найдено {len(svg_files)} SVG файлов\n")
    
    for svg_file in svg_files:
        print(f"Тестируем: {svg_file.name}")
        print("-" * 50)
        
        try:
            # Читаем SVG
            with open(svg_file, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # Парсим обратно в модель
            parse_result = parse_svg_to_diagram(svg_content)
            
            if not parse_result.success:
                print("ERROR Ошибки парсинга:")
                for error in parse_result.errors:
                    print(f"  - {error}")
                print("Парсинг не удался")
                continue
            
            diagram = parse_result.diagram
            
            # Показываем предупреждения, если есть
            if parse_result.warnings:
                print("WARN Предупреждения:")
                for warning in parse_result.warnings:
                    print(f"  - {warning}")
            
            # Проверяем, что получилось
            print(f"  Заголовок: {diagram.title}")
            print(f"  Классов: {len(diagram.classifiers)}")
            print(f"  Ассоциаций: {len(diagram.associations)}")
            print(f"  Зависимостей: {len(diagram.dependencies)}")
            print(f"  Обобщений: {len(diagram.generalizations)}")
            print(f"  Реализаций: {len(diagram.realizations)}")
            
            # Пробуем валидировать
            try:
                diagram.validate_all()
                print("OK Валидация пройдена")
            except Exception as e:
                print(f"ERROR Ошибка валидации: {e}")
            
            # Проверяем позиции
            if diagram.positions:
                print(f"  Позиций классов: {len(diagram.positions)}")
                # Показываем первые 3 для примера
                for i, (name, pos) in enumerate(list(diagram.positions.items())[:3]):
                    print(f"    {name}: ({pos.x:.0f}, {pos.y:.0f})")
            
            print("OK Парсинг успешен")
            
        except Exception as e:
            print(f"Ошибка парсинга: {e}")
            import traceback
            traceback.print_exc()
        
        print()


def test_roundtrip():
    """
    Тест полного цикла: Pydantic -> SVG -> Pydantic
    """
    print("Тест полного цикла (roundtrip)")
    print("=" * 50)
    
    # Сначала запускаем генерацию примеров
    print("Генерируем примеры...")
    import generate_svg_parser_examples
    generate_svg_parser_examples.main()

    # Берём первый SVG
    svg_dir = TESTS_ROOT / "fixtures" / "svg_parser"
    svg_files = list(svg_dir.glob("*.svg"))
    
    if not svg_files:
        print("Нет SVG файлов")
        return
    
    test_file = svg_files[0]
    print(f"Тестовый файл: {test_file.name}")
    
    # Читаем SVG
    with open(test_file, 'r', encoding='utf-8') as f:
        svg_content = f.read()
    
    # Парсим
    parse_result = parse_svg_to_diagram(svg_content)
    if not parse_result.success or parse_result.diagram is None:
        print("Парсинг не удался:")
        for error in parse_result.errors:
            print(f"  - {error}")
        return

    diagram = parse_result.diagram
    
    # Генерируем новый SVG из распарсенной модели
    new_svg = diagram.to_svg(interactive=True)
    
    # Сохраняем для сравнения
    output_file = svg_dir / "roundtrip_test.svg"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(new_svg)
    
    print(f"Новый SVG сохранён: {output_file}")
    print("Сравните оригинал и новый файл (должны быть похожи)")


if __name__ == "__main__":
    print("ТЕСТ ПАРСЕРА SVG -> PYDANTIC\n")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--roundtrip":
        test_roundtrip()
    else:
        test_parser()
