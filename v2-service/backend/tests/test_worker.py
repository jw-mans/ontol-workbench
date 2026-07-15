"""Юнит-тест задачи воркера render_build: читает файлы проекта из БД и выбирает
точку входа. Сам рендер (build_project) подменяется заглушкой — PlantUML не нужен.
"""

import uuid

import app.worker as worker_mod
from app.models.file import File
from app.models.project import Project
from app.services.render import BuildResult


async def _seed_project(session_maker, files: dict[str, str]) -> str:
    async with session_maker() as session:
        project = Project(id=uuid.uuid4(), owner_id=uuid.uuid4(), name='W')
        session.add(project)
        for name, content in files.items():
            session.add(File(project_id=project.id, name=name, content=content))
        await session.commit()
        return str(project.id)


async def test_render_build_reads_files_and_picks_entry(session_maker, monkeypatch):
    pid = await _seed_project(
        session_maker, {'main.ontol': 'x', 'other.ontol': 'y'}
    )
    monkeypatch.setattr(worker_mod, 'async_session_maker', session_maker)

    captured = {}

    def fake_build(files, entry, url):
        captured['files'] = files
        captured['entry'] = entry
        return BuildResult(ok=True, json='{}', puml='@startuml', png_url=None)

    monkeypatch.setattr(worker_mod, 'build_project', fake_build)

    result = await worker_mod.render_build({}, pid, None)

    assert result['ok'] is True
    # воркер сам прочитал оба файла проекта из БД
    assert set(captured['files']) == {'main.ontol', 'other.ontol'}
    assert captured['files']['main.ontol'] == 'x'
    # дефолтная точка входа — main.ontol
    assert captured['entry'] == 'main.ontol'


async def test_render_build_empty_project(session_maker, monkeypatch):
    pid = await _seed_project(session_maker, {})
    monkeypatch.setattr(worker_mod, 'async_session_maker', session_maker)

    result = await worker_mod.render_build({}, pid, None)

    assert result['ok'] is False
    assert 'no files' in (result['error'] or '').lower()


async def test_render_build_tdl_merges_subtree(session_maker, monkeypatch):
    # проект с .tdl + подпроект с .tdl → сборка v3 собирает всё поддерево
    async with session_maker() as session:
        owner = uuid.uuid4()
        root = Project(id=uuid.uuid4(), owner_id=owner, name='root')
        child = Project(
            id=uuid.uuid4(), owner_id=owner, parent_id=root.id, name='sub'
        )
        session.add_all([root, child])
        session.add(File(project_id=root.id, name='a.tdl', content='КЛАСС A\nКОНЕЦ КЛАСС'))
        session.add(File(project_id=child.id, name='b.tdl', content='КЛАСС B\nКОНЕЦ КЛАСС'))
        await session.commit()
        pid = str(root.id)

    monkeypatch.setattr(worker_mod, 'async_session_maker', session_maker)

    captured = {}

    def fake_build(files, entry, url):
        captured['files'] = files
        captured['entry'] = entry
        return BuildResult(ok=True, svg='<svg/>')

    monkeypatch.setattr(worker_mod, 'build_project', fake_build)

    result = await worker_mod.render_build({}, pid, None)

    assert result['ok'] is True
    # оба .tdl (проекта и подпроекта) попали в сборку
    contents = set(captured['files'].values())
    assert 'КЛАСС A\nКОНЕЦ КЛАСС' in contents
    assert 'КЛАСС B\nКОНЕЦ КЛАСС' in contents
    assert captured['entry'].endswith('.tdl')
