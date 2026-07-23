"""
Сборка проекта движком ontol-v1 (Ontol DSL -> JSON / PlantUML / PNG).

Файлы проекта хранятся в БД. Чтобы межфайловые импорты ``ontol`` (которые
резолвятся по файловой системе) работали без изменений ядра, материализуем все
файлы во временный каталог и рендерим оттуда.
"""

import base64
import os
import re
import shutil
import tempfile

from ontol import JSONSerializer, Parser, PlantUML, Project

from app.config import settings
from app.services.render import BuildResult

_ANSI_RE = re.compile(r'\x1b[[0-9;]*m')


def _clean(warnings: list[str]) -> list[str]:
    return [_ANSI_RE.sub('', w) for w in warnings]


def build_ontol(
    files: dict[str, str], entry: str, plantuml_url: str
) -> BuildResult:
    """
    Собрать ``.ontol``-проект (с подпроектами).

    Ключи ``files`` — относительные пути (подпроект = подкаталог), поэтому
    записываем их напрямую с созданием каталогов: так ``import ... from
    "Подпроект/файл.ontol"`` резолвится парсером по относительному пути.

    :param files: словарь относительный_путь -> текст Ontol DSL
    :param entry: файл-точка входа (в корне проекта)
    :param plantuml_url: URL сервиса PlantUML (для рендера PNG)

    :return: BuildResult
    """
    tmp_dir = tempfile.mkdtemp(prefix='ontol_build_')
    try:
        root = os.path.abspath(tmp_dir)
        for relpath, content in files.items():
            dest = os.path.abspath(os.path.join(root, relpath))
            
            # Проверка path traversal
            if os.path.commonpath([root, dest]) != root:
                continue
            
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            
            # Записываем файл как есть - парсер сам разрешит импорты относительно
            # текущего файла (как при локальной сборке через CLI).
            with open(dest, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return _render(Project(tmp_dir), entry, plantuml_url)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _render(project: Project, entry: str, plantuml_url: str) -> BuildResult:
    entry_path = os.path.join(project.root, entry)
    
    try:
        # Читаем файл напрямую, минуя project.read_file(), так как entry может быть полным путем
        with open(entry_path, 'r', encoding='utf-8') as f:
            content = f.read()
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
            encoded = base64.b64encode(f.read()).decode('ascii')
        png_url = f'data:image/png;base64,{encoded}'
    except Exception as error:  # noqa: BLE001
        warnings.append(f'PNG rendering failed: {error}')

    return BuildResult(
        ok=True,
        json=json_text,
        puml=puml_text,
        png_url=png_url,
        warnings=_clean(warnings),
    )
