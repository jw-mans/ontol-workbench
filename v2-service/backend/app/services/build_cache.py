"""Кэш сборок по контенту (MinIO): meta рядом с артефактами.

Ключ meta content-addressed: ``cache/{digest}.json`` (digest уже включает движок,
точку входа и контент — см. ``render.content_digest``). Meta хранит поля
``BuildResult``, но presigned-URL (они истекают) занулены — на кэш-хите ссылка на
артефакт (PNG/SVG) генерируется заново из детерминированного ключа.

Все обращения к S3 «мягкие»: недоступность MinIO → промах кэша (``load`` вернёт
None) или тихий пропуск записи (``store``), сборка при этом не ломается.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from app.services import storage
from app.services.render import BuildResult, content_digest


def _engine(entry: str) -> str:
    return 'v3' if entry.endswith('.tdl') else 'v1'


def _digest(entry: str, files: dict[str, str]) -> str:
    return content_digest(_engine(entry), entry, files)


def _meta_key(digest: str) -> str:
    return f'cache/{digest}.json'


def load(entry: str, files: dict[str, str]) -> dict | None:
    """Готовый ответ сборки из кэша (со свежей presigned-ссылкой) или None.

    Промах и любая ошибка S3 → None (вызывающий просто отрендерит заново).
    """
    try:
        digest = _digest(entry, files)
        raw = storage.get_bytes(_meta_key(digest))
        if raw is None:
            return None
        meta = json.loads(raw)
        # Перегенерируем presigned-ссылку на артефакт из детерминированного ключа
        # (сам meta пишем только при успешной заливке артефакта — см. store()).
        if _engine(entry) == 'v3':
            meta['svg_url'] = storage.presigned_get(
                storage.artifact_key(digest, 'svg')
            )
        else:
            meta['png_url'] = storage.presigned_get(
                storage.artifact_key(digest, 'png')
            )
        return meta
    except Exception:  # noqa: BLE001 — кэш не критичен: промах вместо падения
        return None


def store(entry: str, files: dict[str, str], result: BuildResult) -> None:
    """Записать meta в кэш. Только для «чистых» сборок, где артефакт реально в S3.

    Не кэшируем: неуспешные сборки; v1 без PNG; v3 с инлайн-фолбэком (заливка SVG
    не удалась) — иначе кэш-хит отдал бы результат без диаграммы.
    """
    if not result.ok:
        return
    if _engine(entry) == 'v3' and not result.svg_url:
        return  # инлайн-фолбэк: артефакта в S3 нет
    if _engine(entry) == 'v1' and not result.png_url:
        return  # PNG не отрисовался/не залился
    try:
        meta = asdict(result)
        # presigned-URL истекают — не храним; на хите генерируем заново.
        meta['png_url'] = None
        meta['svg_url'] = None
        storage.put_bytes(
            _meta_key(_digest(entry, files)),
            json.dumps(meta, ensure_ascii=False).encode('utf-8'),
            'application/json',
        )
    except Exception:  # noqa: BLE001 — запись кэша не критична
        pass
