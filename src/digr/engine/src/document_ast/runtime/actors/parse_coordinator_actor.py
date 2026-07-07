from __future__ import annotations

from actor import Actor, ActorHandle

from ...config.parser_config import ParserConfig
from ...model.ast_document import AstDocument
from ...model.ast_node import AstNode
from ...model.source_document import SourceDocument
from ...segmentation.text_segmenter import TextSegmenter
from ..messages import (
    BuildSubtreeRequest,
    CoordinatorMessage,
    DocumentLoaded,
    ParseCompleted,
    ParseDocumentRequest,
    ReadDocumentRequest,
    SubtreeCompleted,
)
from ..states import CoordinatorState


class ParseCoordinatorActor(Actor[CoordinatorState, CoordinatorMessage, CoordinatorMessage]):
    def __init__(
            self,
            config: ParserConfig,
            reader: ActorHandle[object],
            workers: list[ActorHandle[object]],
            collector: ActorHandle[object],
            segmenter: TextSegmenter | None = None,
    ) -> None:
        super().__init__(CoordinatorState, CoordinatorState.IDLE)
        self._config = config
        self._reader = reader
        self._workers = workers
        self._collector = collector
        self._segmenter = segmenter or TextSegmenter()

        self._pending_count: int = 0
        self._subtree_results: dict[int, AstNode] = {}
        self._document: SourceDocument | None = None

    def on_idle_parse_document_request(self, message: ParseDocumentRequest) -> CoordinatorState:
        format_name = message.format_name
        if format_name is None:
            raise ValueError("format_name must be resolved before sending to coordinator")
        self._reader.tell(ReadDocumentRequest(path=message.path, format_name=format_name))
        return CoordinatorState.WAITING_FOR_DOCUMENT

    def on_waiting_for_document_document_loaded(self, message: DocumentLoaded) -> CoordinatorState:
        doc = message.document
        self._document = doc

        root_entity_name = self._config.format_config.root_entity
        root_entity_config = self._config.get_entity(root_entity_name)
        segments = self._segmenter.segment(doc.text, 0, root_entity_config.segmenter)

        if not segments:
            return self._finalize_with_no_children(doc, root_entity_name)

        self._pending_count = len(segments)
        self._subtree_results = {}

        for i, segment in enumerate(segments):
            worker_index = i % len(self._workers)
            self._workers[worker_index].tell(BuildSubtreeRequest(
                segment_index=i,
                entity_name=root_entity_name,
                segment=segment,
            ))

        return CoordinatorState.BUILDING_SUBTREES

    def on_building_subtrees_subtree_completed(self, message: SubtreeCompleted) -> CoordinatorState:
        self._subtree_results[message.segment_index] = message.node

        if len(self._subtree_results) < self._pending_count:
            return CoordinatorState.BUILDING_SUBTREES

        doc = self._document
        assert doc is not None
        children = [self._subtree_results[i] for i in range(self._pending_count)]

        root = AstNode(
            entity="document",
            text=doc.text,
            start=0,
            end=len(doc.text),
            children=children,
            metadata={"format": doc.format_name, "source_path": doc.path},
        )
        ast_doc = AstDocument(
            source_path=doc.path,
            format_name=doc.format_name,
            root_entity=self._config.format_config.root_entity,
            root=root,
        )
        self._collector.tell(ParseCompleted(document=ast_doc))
        return CoordinatorState.COMPLETED

    def _finalize_with_no_children(
            self, doc: SourceDocument, root_entity_name: str,
    ) -> CoordinatorState:
        root = AstNode(
            entity="document",
            text=doc.text,
            start=0,
            end=len(doc.text),
            children=[],
            metadata={"format": doc.format_name, "source_path": doc.path},
        )
        ast_doc = AstDocument(
            source_path=doc.path,
            format_name=doc.format_name,
            root_entity=root_entity_name,
            root=root,
        )
        self._collector.tell(ParseCompleted(document=ast_doc))
        return CoordinatorState.COMPLETED


ParserCoordinatorActor = ParseCoordinatorActor
