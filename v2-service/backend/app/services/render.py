"""
Диспетчер сборки проекта.

Движок выбирается по расширению точки входа: 
- ``.tdl`` -> ontol-v3 (Graphviz/SVG), 
- иначе — ontol-v1 (PlantUML/JSON/PNG). 
Сама реализация каждого движка живёт в отдельном модуле 
(``render_v1`` / ``render_v3``), импортируется лениво — 
чтобы ядро одного движка не тянулось, когда собирают другим.
"""

from dataclasses import dataclass, field


@dataclass
class BuildResult:
    """
    Единый результат сборки для обоих движков.
    :param ok: True = сборка успешна, False = ошибка
    :param json: JSON-результат (v1)
    :param puml: PlantUML-результат (v1)
    :param png_url: URL PNG (v1)
    :param svg: SVG-результат (v3)
    :param planarity: планарность (v3)
    :param warnings: список предупреждений (v3)
    :param error: текст ошибки (v1/v3)
    """

    ok: bool
    json: str | None = None  # v1
    puml: str | None = None  # v1
    png_url: str | None = None  # v1
    svg: str | None = None  # v3 (TDL => Graphviz)
    planarity: dict | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def build_project(
    files: dict[str, str], entry: str, plantuml_url: str
) -> BuildResult:
    """
    Собрать ``entry`` из набора файлов ``{имя: контент}`` нужным движком.

    :param files: словарь имя -> текст Ontol DSL / TDL
    :param entry: имя файла, с которого начинать сборку
    :param plantuml_url: URL сервиса PlantUML (для рендера PNG)
    
    :return: BuildResult
    """
    if entry not in files:
        return BuildResult(ok=False, error=f'Entry file {entry!r} not found')

    if entry.endswith('.tdl'):
        from app.services.render_v3 import build_tdl

        return build_tdl(files, entry)

    from app.services.render_v1 import build_ontol

    return build_ontol(files, entry, plantuml_url)
