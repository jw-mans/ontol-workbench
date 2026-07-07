from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from ..model.ast_document import AstDocument
from ..model.ast_node import AstNode
from ..model.source_document import SourceDocument
from ..segmentation.text_segment import TextSegment


@dataclass(slots=True)
class ParseDocumentRequest:
    path: str
    format_name: str | None = None


@dataclass(slots=True)
class ReadDocumentRequest:
    path: str
    format_name: str


@dataclass(slots=True)
class DocumentLoaded:
    document: SourceDocument


@dataclass(slots=True)
class BuildSubtreeRequest:
    segment_index: int
    entity_name: str
    segment: TextSegment


@dataclass(slots=True)
class SubtreeCompleted:
    segment_index: int
    node: AstNode


@dataclass(slots=True)
class ParseCompleted:
    document: AstDocument


CoordinatorMessage = Union[
    ParseDocumentRequest,
    DocumentLoaded,
    SubtreeCompleted,
    ParseCompleted,
]

ReaderMessage = Union[ReadDocumentRequest]

WorkerMessage = Union[BuildSubtreeRequest]

CollectorMessage = Union[ParseCompleted]
