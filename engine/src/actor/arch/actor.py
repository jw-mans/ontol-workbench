from __future__ import annotations

from abc import ABC
from enum import Enum
from typing import TYPE_CHECKING, Iterable, Self, TypeVar

from .fsm import Fsm
from .mailbox import Mailbox
from .mailbox_like import MailboxLike

if TYPE_CHECKING:
    from .actor_driver import ActorDriver
    from ..handles.actor_handle import ActorHandle

State = TypeVar("State", bound=Enum)
QueueItem = TypeVar("QueueItem")
Message = TypeVar("Message")


class Actor(Fsm[State, QueueItem, Message], ABC):
    def __init__(
            self,
            state_type: type[State],
            initial_state: State,
            mailbox: MailboxLike[QueueItem] | None = None,
            driver: ActorDriver | None = None,
    ) -> None:
        self._mailbox: MailboxLike[QueueItem] = mailbox or Mailbox[QueueItem]()
        self._driver: ActorDriver | None = None
        super().__init__(state_type, initial_state, self._mailbox)
        if driver is not None:
            self.bind(driver)

    @property
    def mailbox(self) -> MailboxLike[QueueItem]:
        return self._mailbox

    @property
    def driver(self) -> ActorDriver | None:
        return self._driver

    def bind(self, driver: ActorDriver) -> Self:
        if self._driver is not None and self._driver is not driver:
            raise RuntimeError("actor is already bound to another driver")
        self._driver = driver
        driver.attach(self)
        if self.pending > 0:
            driver.schedule(self)
        return self

    def put(self, item: QueueItem) -> None:
        self._mailbox.put(item)
        if self._driver is not None:
            self._driver.schedule(self)

    def send(self, item: QueueItem) -> None:
        self.put(item)

    def extend(self, items: Iterable[QueueItem]) -> None:
        for item in items:
            self.put(item)

    @property
    def pending(self) -> int:
        return len(self._mailbox)

    def as_handle(self) -> ActorHandle[QueueItem]:
        from ..handles.actor_handle import ActorHandle

        return ActorHandle(self)
