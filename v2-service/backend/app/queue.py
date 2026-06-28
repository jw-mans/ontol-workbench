"""Очередь фоновых задач (arq поверх Redis).

Здесь только настройки подключения и фабрика пула — сами задачи в app/worker.py.
API кладёт задачи в очередь по имени (``enqueue_job('render_build', ...)``) и не
импортирует код воркера, поэтому тяжёлый стек ontol в процесс API не тянется.
"""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import settings

RENDER_BUILD = 'render_build'


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def create_redis_pool() -> ArqRedis:
    return await create_pool(redis_settings())
