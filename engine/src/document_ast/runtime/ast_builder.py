from __future__ import annotations

from ..config.parser_config import ParserConfig
from ..model.ast_document import AstDocument
from ..model.ast_node import AstNode
from ..model.source_document import SourceDocument
from ..segmentation.text_segment import TextSegment
from ..segmentation.text_segmenter import TextSegmenter


class AstBuilder:
    def __init__(self, config: ParserConfig, segmenter: TextSegmenter | None = None) -> None:
        self._config = config
        self._segmenter = segmenter or TextSegmenter()
        self._excluded_symbols = set(config.format_config.symbols.get("exclude", []))

    def build(self, document: SourceDocument) -> AstDocument:
        if self._config.format_name != document.format_name:
            raise ValueError(
                f"Runtime config is for format '{self._config.format_name}', "
                f"got document with format '{document.format_name}'"
            )
        root_entity = self._config.format_config.root_entity
        root_node = AstNode(
            entity="document",
            text=document.text,
            start=0,
            end=len(document.text),
            children=[
                self.build_entity_node(root_entity, segment)
                for segment in self._segment_entity(root_entity, document.text, 0)
            ],
            metadata={"format": document.format_name, "source_path": document.path},
        )
        return AstDocument(
            source_path=document.path,
            format_name=document.format_name,
            root_entity=root_entity,
            root=root_node,
        )

    def build_entity_node(self, entity_name: str, segment: TextSegment) -> AstNode:
        entity_config = self._config.get_entity(entity_name)
        children: list[AstNode] = []
        if entity_config.contains:
            for child_entity in entity_config.contains:
                children.extend(
                    self.build_entity_node(child_entity, child_segment)
                    for child_segment in self._segment_entity(
                        child_entity,
                        segment.text,
                        segment.start,
                    )
                )

        if self._should_build_symbols(entity_config):
            children.extend(self._build_symbol_nodes(segment))

        return AstNode(
            entity=entity_name,
            text=segment.text,
            start=segment.start,
            end=segment.end,
            children=children,
            metadata=dict(segment.metadata),
        )

    def _segment_entity(self, entity_name: str, text: str, base_start: int) -> list[TextSegment]:
        entity_config = self._config.get_entity(entity_name)
        return self._segmenter.segment(text, base_start, entity_config.segmenter)

    def _build_symbol_nodes(self, segment: TextSegment) -> list[AstNode]:
        return [
            AstNode(
                entity="symbol",
                text=char,
                start=segment.start + index,
                end=segment.start + index + 1,
            )
            for index, char in enumerate(segment.text)
            if char not in self._excluded_symbols
        ]

    @staticmethod
    def _should_build_symbols(entity_config) -> bool:
        if entity_config.symbols is not None:
            return entity_config.symbols
        return not entity_config.contains
