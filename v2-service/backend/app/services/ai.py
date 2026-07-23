"""
Опциональная AI-генерация связей (раздел ``hierarchy``) через ontol.AI + Ollama.

Включается флагом ``settings.ai_enabled``. Тяжёлый стек (langchain) и Ollama нужны
только при включённой фиче, поэтому ``ontol.AI`` и сама генерация вызываются
лениво — если экстра ``[ai]`` не установлена, вернётся понятная ошибка, а не падёж.

Возвращаем не мутированный файл, а **предложение**: список связей + готовый
к вставке фрагмент на языке Ontol. Решение, вставлять ли его, — за пользователем.

Блокирующая функция: вызывать из async-кода через ``run_in_threadpool``/``to_thread``.
"""

import os
import shutil
import tempfile
from dataclasses import dataclass, field

from ontol import Parser, Project, RelationshipDirection


@dataclass
class AIHierarchyResult:
    """
    Результат генерации связей (раздел ``hierarchy``) через LLM (Ollama).
    :param ok: True = успешно, False = ошибка
    :param relationships: список предложенных связей 
                          (parent/child/relationship/title/bidirectional/comment)
    :param snippet: фрагмент Ontol DSL (раздел hierarchy) — можно вставить в файл
    :param error: текст ошибки (например, нет langchain / недоступен Ollama)
    """
    ok: bool
    relationships: list[dict] = field(default_factory=list)
    # Фрагмент `.ontol` (раздел hierarchy) — можно вставить в файл.
    snippet: str | None = None
    error: str | None = None


def generate_hierarchy(
    files: dict[str, str],
    entry: str,
    model: str,
    base_url: str,
    temperature: float = 0.0,
) -> AIHierarchyResult:
    """
    Предложить связи для точки входа на основе её терминов и функций.

    :param files: словарь имя -> текст Ontol DSL
    :param entry: имя файла, с которого начинать сборку
    :param model: имя модели Ollama (например, "llama2")
    :param base_url: URL базового сервера Ollama
    :param temperature: температура генерации

    :return: AIHierarchyResult
    """
    if entry not in files:
        return AIHierarchyResult(ok=False, error=f'Entry file {entry!r} not found')

    tmp_dir = tempfile.mkdtemp(prefix='ontol_ai_')
    try:
        project = Project(tmp_dir)
        for name, content in files.items():
            project.write_file(name, content)
        return _run(project, entry, model, base_url, temperature)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _run(
    project: Project, entry: str, model: str, base_url: str, temperature: float
) -> AIHierarchyResult:
    entry_path = os.path.join(project.root, entry)
    try:
        # Читаем файл напрямую, минуя project.read_file(), так как entry может быть полным путем
        with open(entry_path, 'r', encoding='utf-8') as f:
            content = f.read()
        ontology, _ = Parser().parse(content, entry_path)
    except Exception as error:  # noqa: BLE001 — ошибка парсинга/импорта
        return AIHierarchyResult(ok=False, error=str(error))

    try:
        from ontol import AI  # noqa: PLC0415 — ленивый импорт AI-стека

        relationships, comments = AI().generate_hierarchy(
            ontology, model=model, temperature=temperature, base_url=base_url
        )
    except Exception as error:  # noqa: BLE001 — нет langchain / недоступен Ollama
        return AIHierarchyResult(ok=False, error=f'AI generation failed: {error}')

    rels: list[dict] = []
    lines: list[str] = []
    for rel, comment in zip(relationships, comments):
        parent = rel.parent.name
        child = rel.children[0].name
        rtype = rel.relationship.value
        title = rel.attributes.title or None
        bidirectional = (
            rel.attributes.direction == RelationshipDirection.BIDIRECTIONAL
        )
        rels.append(
            {
                'parent': parent,
                'child': child,
                'relationship': rtype,
                'title': title,
                'bidirectional': bidirectional,
                'comment': comment,
            }
        )
        attrs: list[str] = []
        if title:
            attrs.append(f"title: '{title}'")
        if bidirectional:
            attrs.append("direction: 'bidirectional'")
        attr_str = f", {{ {', '.join(attrs)} }}" if attrs else ''
        if comment:
            lines.append(f'  # {comment}')
        lines.append(f'  {parent} {rtype} {child}{attr_str}')

    snippet = 'hierarchy:\n' + '\n'.join(lines) if rels else None
    return AIHierarchyResult(ok=True, relationships=rels, snippet=snippet)
