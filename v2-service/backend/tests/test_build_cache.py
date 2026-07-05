"""Тесты кэша сборок по контенту. Сеть/boto3 не нужны: storage подменяем
in-memory словарём (put/get/presigned)."""

import pytest

from app.services import build_cache, storage
from app.services.render import BuildResult

FILES = {'d.tdl': 'КЛАСС A\nКОНЕЦ КЛАСС\n'}


@pytest.fixture
def mem_storage(monkeypatch):
    store: dict[str, bytes] = {}
    monkeypatch.setattr(
        storage, 'put_bytes', lambda key, data, ct: store.__setitem__(key, data)
    )
    monkeypatch.setattr(storage, 'get_bytes', lambda key: store.get(key))
    monkeypatch.setattr(
        storage, 'presigned_get', lambda key: f'https://s3.test/{key}?sig=1'
    )
    return store


def test_miss_returns_none(mem_storage):
    assert build_cache.load('d.tdl', FILES) is None


def test_store_then_load_v3_regenerates_link(mem_storage):
    res = BuildResult(
        ok=True, svg_url='https://old/expired', planarity=None, warnings=['w']
    )
    build_cache.store('d.tdl', FILES, res)

    loaded = build_cache.load('d.tdl', FILES)
    assert loaded is not None
    assert loaded['ok'] is True and loaded['warnings'] == ['w']
    # ссылка перегенерирована свежей (не старая истёкшая), ведёт на артефакт .svg
    assert loaded['svg_url'].startswith('https://s3.test/')
    assert 'artifacts/' in loaded['svg_url']
    assert loaded['svg_url'].endswith('.svg?sig=1')
    assert loaded['png_url'] is None


def test_inline_fallback_not_cached(mem_storage):
    # v3 с инлайн-фолбэком (svg_url None) — артефакта в S3 нет, не кэшируем.
    build_cache.store('d.tdl', FILES, BuildResult(ok=True, svg='<svg/>'))
    assert build_cache.load('d.tdl', FILES) is None


def test_v1_without_png_not_cached(mem_storage):
    build_cache.store(
        'm.ontol', FILES, BuildResult(ok=True, json='{}', puml='@startuml')
    )
    assert build_cache.load('m.ontol', FILES) is None


def test_failed_build_not_cached(mem_storage):
    build_cache.store('d.tdl', FILES, BuildResult(ok=False, error='boom'))
    assert build_cache.load('d.tdl', FILES) is None
