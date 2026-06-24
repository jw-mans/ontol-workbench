"""Project layer for the Ontol web UI (личный кабинет).

A *project* is a directory that holds several ``.ontol`` files which may import
each other. Because the parser resolves ``import ... from 'other.ontol'`` against
the importing file's directory on disk, keeping all project files in one real
directory makes cross-file imports work for free — we only need to render the
chosen entry file.

This module is UI-agnostic: the Streamlit app (Этап 3) builds on top of it.
"""

import os
import shutil
from dataclasses import dataclass, field
from typing import Optional

from ontol.parser import Parser
from ontol.serializer import JSONSerializer
from ontol.plantuml import PlantUML

ONTOL_EXT = '.ontol'


def _check_flat_name(name: str, kind: str) -> None:
    """Reject empty names and any path separators / traversal."""
    if not name or name in ('.', '..') or name != os.path.basename(name):
        raise ValueError(f'Invalid {kind} name: {name!r}')


@dataclass
class RenderResult:
    ok: bool
    json_path: Optional[str] = None
    puml_path: Optional[str] = None
    png_path: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None


class Project:
    """A directory of ``.ontol`` files that may import one another."""

    def __init__(self, root: str) -> None:
        self.root: str = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    @property
    def name(self) -> str:
        return os.path.basename(self.root)

    def list_files(self) -> list[str]:
        return sorted(
            f for f in os.listdir(self.root) if f.endswith(ONTOL_EXT)
        )

    def file_path(self, filename: str) -> str:
        _check_flat_name(filename, 'file')
        return os.path.join(self.root, filename)

    def read_file(self, filename: str) -> str:
        with open(self.file_path(filename), 'r', encoding='utf-8') as f:
            return f.read()

    def write_file(self, filename: str, content: str) -> str:
        if not filename.endswith(ONTOL_EXT):
            filename += ONTOL_EXT
        path = self.file_path(filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return filename

    def delete_file(self, filename: str) -> None:
        path = self.file_path(filename)
        if os.path.exists(path):
            os.remove(path)


def render_project(
    project: Project, entry: str, output_dir: str
) -> RenderResult:
    """Render an entry file of *project* into ``output_dir``.

    Imports referenced by *entry* are resolved against the project directory,
    so all sibling files must already be written to disk. Produces JSON, a
    PlantUML source and (best-effort, needs network) a PNG.
    """
    entry_path = project.file_path(entry)
    base = os.path.splitext(entry)[0]
    os.makedirs(output_dir, exist_ok=True)

    try:
        content = project.read_file(entry)
        ontology, warnings = Parser().parse(content, entry_path)
    except Exception as error:  # noqa: BLE001 — surface any parse/import error
        return RenderResult(ok=False, error=str(error))

    json_path = os.path.join(output_dir, f'{base}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        f.write(JSONSerializer().serialize(ontology))

    plantuml = PlantUML()
    puml_path = os.path.join(output_dir, f'{base}.puml')
    with open(puml_path, 'w', encoding='utf-8') as f:
        f.write(plantuml.generate(ontology))

    png_path: Optional[str] = os.path.splitext(puml_path)[0] + '.png'
    try:
        plantuml.processes_puml_to_png(puml_path)
    except Exception as error:  # noqa: BLE001
        # PNG needs the PlantUML server; keep JSON/puml usable without it.
        warnings.append(f'PNG rendering failed: {error}')
        png_path = None

    return RenderResult(
        ok=True,
        json_path=json_path,
        puml_path=puml_path,
        png_path=png_path,
        warnings=warnings,
    )


class ProjectStore:
    """Manages projects as subdirectories of a single base directory."""

    def __init__(self, base_dir: str) -> None:
        self.base_dir: str = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def list_projects(self) -> list[str]:
        return sorted(
            d
            for d in os.listdir(self.base_dir)
            if os.path.isdir(os.path.join(self.base_dir, d))
        )

    def exists(self, name: str) -> bool:
        _check_flat_name(name, 'project')
        return os.path.isdir(os.path.join(self.base_dir, name))

    def get(self, name: str) -> Project:
        _check_flat_name(name, 'project')
        return Project(os.path.join(self.base_dir, name))

    def create(self, name: str) -> Project:
        _check_flat_name(name, 'project')
        if self.exists(name):
            raise ValueError(f'Project {name!r} already exists')
        return Project(os.path.join(self.base_dir, name))

    def delete(self, name: str) -> None:
        _check_flat_name(name, 'project')
        path = os.path.join(self.base_dir, name)
        if os.path.isdir(path):
            shutil.rmtree(path)

    def rename(self, old: str, new: str) -> None:
        _check_flat_name(old, 'project')
        _check_flat_name(new, 'project')
        if self.exists(new):
            raise ValueError(f'Project {new!r} already exists')
        os.rename(
            os.path.join(self.base_dir, old),
            os.path.join(self.base_dir, new),
        )
