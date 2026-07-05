"""Диспетчер сборки проекта.

Движок выбирается по расширению точки входа: ``.tdl`` -> ontol-v3
(Graphviz/SVG), иначе — ontol-v1 (PlantUML/JSON/PNG). Сама реализация каждого
движка живёт в отдельном модуле (``render_v1`` / ``render_v3``), импортируется
лениво — чтобы ядро одного движка не тянулось, когда собирают другим.
"""

import hashlib
from dataclasses import dataclass, field


def content_digest(engine: str, entry: str, files: dict[str, str]) -> str:
    """Стабильный хеш идентичности сборки: движок + точка входа + контент файлов.

    Одинаковый набор файлов и точка входа → один и тот же ключ артефакта. Основа
    для content-addressed ключей в MinIO и кэша сборок (шаг 4). Порядок файлов не
    влияет (сортируем по имени); разделители — чтобы склейки не давали коллизий.
    """
    h = hashlib.sha256()
    h.update(engine.encode())
    h.update(b'\x00')
    h.update(entry.encode())
    for name in sorted(files):
        h.update(b'\x00')
        h.update(name.encode())
        h.update(b'\x00')
        h.update(files[name].encode())
    return h.hexdigest()


@dataclass
class BuildResult:
    """Единый результат сборки для обоих движков."""

    ok: bool
    json: str | None = None  # v1
    puml: str | None = None  # v1
    png_url: str | None = None  # v1: presigned-ссылка на PNG в MinIO
    svg_url: str | None = None  # v3: presigned-ссылка на SVG в MinIO
    # v3-фолбэк: инлайн-SVG, если заливка в MinIO не удалась (S3 недоступен).
    svg: str | None = None
    planarity: dict | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def build_project(
    files: dict[str, str], entry: str, plantuml_url: str
) -> BuildResult:
    """Собрать ``entry`` из набора файлов ``{имя: контент}`` нужным движком."""
    if entry not in files:
        return BuildResult(ok=False, error=f'Entry file {entry!r} not found')

    if entry.endswith('.tdl'):
        from app.services.render_v3 import build_tdl

        return build_tdl(files, entry)

    from app.services.render_v1 import build_ontol

    return build_ontol(files, entry, plantuml_url)
