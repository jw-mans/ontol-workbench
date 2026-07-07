from __future__ import annotations

from actor import Actor, ActorHandle

from ...config.parser_config import ParserConfig
from ..ast_builder import AstBuilder
from ..messages import BuildSubtreeRequest, SubtreeCompleted, WorkerMessage
from ..states import WorkerState


class SubtreeBuilderWorkerActor(Actor[WorkerState, WorkerMessage, WorkerMessage]):
    def __init__(
            self,
            config: ParserConfig,
            reply_to: ActorHandle[object] | None = None,
    ) -> None:
        super().__init__(WorkerState, WorkerState.IDLE)
        self._builder = AstBuilder(config)
        self._reply_to = reply_to

    def set_reply_to(self, handle: ActorHandle[object]) -> None:
        self._reply_to = handle

    def on_idle_build_subtree_request(self, message: BuildSubtreeRequest) -> WorkerState:
        if self._reply_to is None:
            raise RuntimeError("reply_to handle is not configured")
        node = self._builder.build_entity_node(message.entity_name, message.segment)
        self._reply_to.tell(SubtreeCompleted(
            segment_index=message.segment_index,
            node=node,
        ))
        return WorkerState.IDLE


SubtreeWorkerActor = SubtreeBuilderWorkerActor
