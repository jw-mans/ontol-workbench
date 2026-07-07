from __future__ import annotations

from actor import Actor, ActorHandle

from ...config.parser_config import ParserConfig
from ...source.source_reader_registry import SourceReaderRegistry
from ..messages import DocumentLoaded, ReadDocumentRequest, ReaderMessage
from ..states import WorkerState


class SourceReaderActor(Actor[WorkerState, ReaderMessage, ReaderMessage]):
    def __init__(
            self,
            config: ParserConfig,
            reply_to: ActorHandle[object] | None = None,
    ) -> None:
        super().__init__(WorkerState, WorkerState.IDLE)
        self._config = config
        self._reply_to = reply_to
        self._registry = SourceReaderRegistry()

    def set_reply_to(self, handle: ActorHandle[object]) -> None:
        self._reply_to = handle

    def on_idle_read_document_request(self, message: ReadDocumentRequest) -> WorkerState:
        if self._config.format_name != message.format_name:
            raise ValueError(
                f"Runtime config is for format '{self._config.format_name}', "
                f"got request for '{message.format_name}'"
            )
        if self._reply_to is None:
            raise RuntimeError("reply_to handle is not configured")
        document = self._registry.read(
            message.path,
            message.format_name,
            self._config.format_config.reader,
        )
        self._reply_to.tell(DocumentLoaded(document))
        return WorkerState.IDLE


DocumentReaderActor = SourceReaderActor
