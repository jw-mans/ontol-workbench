from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from .inbox_like import InboxLike

QueueItem = TypeVar("QueueItem")


@runtime_checkable
class MailboxLike(InboxLike[QueueItem], Protocol[QueueItem]):
    def put(self, item: QueueItem) -> None: ...

    def __len__(self) -> int: ...
