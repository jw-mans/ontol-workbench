"""Сборка проекта.

Файлы проекта хранятся в БД. Чтобы межфайловые импорты ``ontol`` (которые
резолвятся по файловой системе) работали без изменений ядра, материализуем все
файлы во временный каталог и рендерим оттуда.

Ядро ``ontol`` не модифицируем: повторяем шаги ``ontol.render_project`` (parse →
JSON → PlantUML), но создаём ``PlantUML(url=...)`` со своим сервером вместо
публичного plantuml.com — это единственная причина, по которой не зовём
``render_project`` напрямую (он хардкодит ``PlantUML()``).

Блокирующая функция: вызывать из async-кода через ``run_in_threadpool``.
"""

import base64
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field

from ontol import JSONSerializer, Parser, PlantUML, Project

# Ядро форматирует предупреждения для терминала (ANSI-цвета). В вебе они мусор —
# вырезаем escape-последовательности, текст оставляем как есть.
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def _clean(warnings: list[str]) -> list[str]:
    return [_ANSI_RE.sub('', w) for w in warnings]


@dataclass
class BuildResult:
    ok: bool
    json: str | None = None
    puml: str | None = None
    # PNG отдаём как data-URL (data:image/png;base64,...) — годится прямо в <img>.
    png_url: str | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def build_project(
    files: dict[str, str], entry: str, plantuml_url: str
) -> BuildResult:
    """Собрать ``entry`` из набора файлов ``{имя: контент}``.

    JSON и PlantUML формируются всегда (при успешном парсинге); PNG — по
    возможности (нужен живой PlantUML-сервер), иначе уходит в warnings.
    """
    if entry not in files:
        return BuildResult(ok=False, error=f'Entry file {entry!r} not found')

    tmp_dir = tempfile.mkdtemp(prefix='ontol_build_')
    try:
        project = Project(tmp_dir)
        for name, content in files.items():
            project.write_file(name, content)
        return _render(project, entry, plantuml_url)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _render(project: Project, entry: str, plantuml_url: str) -> BuildResult:
    entry_path = project.file_path(entry)
    try:
        content = project.read_file(entry)
        ontology, warnings = Parser().parse(content, entry_path)
    except Exception as error:  # noqa: BLE001 — отдаём любую ошибку парсинга/импорта
        return BuildResult(ok=False, error=str(error))

    json_text = JSONSerializer().serialize(ontology)
    plantuml = PlantUML(url=plantuml_url)
    puml_text = plantuml.generate(ontology)

    png_url: str | None = None
    puml_path = os.path.join(project.root, '_build.puml')
    with open(puml_path, 'w', encoding='utf-8') as f:
        f.write(puml_text)
    try:
        plantuml.processes_puml_to_png(puml_path)
        png_path = os.path.splitext(puml_path)[0] + '.png'
        with open(png_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('ascii')
        png_url = f'data:image/png;base64,{encoded}'
    except Exception as error:  # noqa: BLE001
        # PNG требует PlantUML-сервера; JSON/puml остаются рабочими без него.
        warnings.append(f'PNG rendering failed: {error}')

    return BuildResult(
        ok=True,
        json=json_text,
        puml=puml_text,
        png_url=png_url,
        warnings=_clean(warnings),
    )
