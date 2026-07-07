from __future__ import annotations

import asyncio
from contextlib import suppress

from ..arch.actor_driver import ActorDriver
from ..arch.drivable import Drivable
from ..arch.step_limits import validate_step_limit


class AsyncReadyActors:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._ready: asyncio.Queue[Drivable] = asyncio.Queue()
        self._scheduled: set[int] = set()
        self._inflight = 0

    def schedule(self, actor: Drivable) -> bool:
        actor_id = id(actor)
        if actor_id in self._scheduled:
            return False
        self._scheduled.add(actor_id)
        self._ready.put_nowait(actor)
        return True

    async def pop(self) -> Drivable:
        actor = await self._ready.get()
        self._scheduled.discard(id(actor))
        self._inflight += 1
        return actor

    def complete(self, actor: Drivable) -> bool:
        self._inflight -= 1
        return actor.pending > 0

    def is_idle(self) -> bool:
        return not self._scheduled and self._ready.qsize() == 0 and self._inflight == 0

    def queue_size(self) -> int:
        return self._ready.qsize() + self._inflight


class AsyncioActorDriver(ActorDriver):
    def __init__(
            self,
            step_limit: int | None = 1,
            *,
            loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._step_limit = validate_step_limit(step_limit)
        self._loop = loop or asyncio.get_running_loop()
        self._ready_actors = AsyncReadyActors(self._loop)
        self._closing = False
        self._worker_task: asyncio.Task[None] | None = None
        self._idle_event = asyncio.Event()
        self._idle_event.set()

    def attach(self, actor: Drivable) -> None:
        del actor

    def schedule(self, actor: Drivable) -> None:
        if self._closing:
            raise RuntimeError("driver is closing")
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self._loop:
            self._schedule_now(actor)
            return
        self._loop.call_soon_threadsafe(self._schedule_now, actor)

    def is_idle(self) -> bool:
        return self._ready_actors.is_idle()

    def queue_size(self) -> int:
        return self._ready_actors.queue_size()

    async def join(self) -> None:
        while not self.is_idle():
            await self._idle_event.wait()

    async def aclose(self) -> None:
        self._closing = True
        await self.join()
        if self._worker_task is not None:
            self._worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker_task

    def close(self) -> None:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self._loop:
            self._request_close()
            return
        self._loop.call_soon_threadsafe(self._request_close)

    def _request_close(self) -> None:
        self._closing = True
        if self.is_idle():
            if self._worker_task is not None:
                self._worker_task.cancel()
            self._idle_event.set()

    def _schedule_now(self, actor: Drivable) -> None:
        if not self._ready_actors.schedule(actor):
            return
        self._idle_event.clear()
        if self._worker_task is None:
            self._worker_task = self._loop.create_task(self._run())

    async def _run(self) -> None:
        try:
            while not self._closing or not self.is_idle():
                actor = await self._ready_actors.pop()
                try:
                    actor.step(self._step_limit)
                finally:
                    if self._ready_actors.complete(actor):
                        self._ready_actors.schedule(actor)
                    if self.is_idle():
                        self._idle_event.set()
        finally:
            self._worker_task = None
            if self.is_idle():
                self._idle_event.set()
