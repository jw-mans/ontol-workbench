"""Сборка проекта движком ontol-v1 (Ontol DSL -> JSON / PlantUML / PNG).

Файлы проекта хранятся в БД. Чтобы межфайловые импорты ``ontol`` (которые
резолвятся по файловой системе) работали без изменений ядра, материализуем все
файлы во временный каталог и рендерим оттуда.
"""

import os
import re
import shutil
import tempfile

from ontol import JSONSerializer, Parser, PlantUML, Project

from app.config import settings
from app.services import storage
from app.services.render import BuildResult, content_digest

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def _clean(warnings: list[str]) -> list[str]:
    return [_ANSI_RE.sub('', w) for w in warnings]


def build_ontol(
    files: dict[str, str], entry: str, plantuml_url: str
) -> BuildResult:
    """Собрать ``.ontol``-проект."""
    tmp_dir = tempfile.mkdtemp(prefix='ontol_build_')
    try:
        project = Project(tmp_dir)
        for name, content in files.items():
            project.write_file(name, content)
        return _render(project, entry, plantuml_url, files)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _render(
    project: Project, entry: str, plantuml_url: str, files: dict[str, str]
) -> BuildResult:
    entry_path = project.file_path(entry)
    try:
        content = project.read_file(entry)
        ontology, warnings = Parser().parse(content, entry_path)
    except Exception as error:  # noqa: BLE001
        return BuildResult(ok=False, error=str(error))

    json_text = JSONSerializer().serialize(ontology)
    plantuml = PlantUML(
        url=plantuml_url, timeout=settings.plantuml_timeout_seconds
    )
    puml_text = plantuml.generate(ontology)

    png_url: str | None = None
    puml_path = os.path.join(project.root, '_build.puml')
    with open(puml_path, 'w', encoding='utf-8') as f:
        f.write(puml_text)
    try:
        plantuml.processes_puml_to_png(puml_path)
        png_path = os.path.splitext(puml_path)[0] + '.png'
        with open(png_path, 'rb') as f:
            png_bytes = f.read()
        # PNG → MinIO (content-addressed), в ответ — presigned-ссылка вместо
        # тяжёлого base64 в JSON/Redis.
        key = storage.artifact_key(content_digest('v1', entry, files), 'png')
        storage.put_bytes(key, png_bytes, 'image/png')
        png_url = storage.presigned_get(key)
    except Exception as error:  # noqa: BLE001
        warnings.append(f'PNG rendering/upload failed: {error}')

    return BuildResult(
        ok=True,
        json=json_text,
        puml=puml_text,
        png_url=png_url,
        warnings=_clean(warnings),
    )
