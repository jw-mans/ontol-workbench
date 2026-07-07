from __future__ import annotations

from actor import Actor, ActorHandle

from ...parsing.lexer import DslLexer
from ...parsing.messages import DslParseFailed, DslTokenized, LexerMessage, TokenizeDslRequest
from ...parsing.states import DslWorkerState


class DslLexerActor(Actor[DslWorkerState, LexerMessage, LexerMessage]):
    def __init__(self, reply_to: ActorHandle[object] | None = None) -> None:
        super().__init__(DslWorkerState, DslWorkerState.READY)
        self._lexer = DslLexer()
        self._reply_to = reply_to

    def set_reply_to(self, handle: ActorHandle[object]) -> None:
        self._reply_to = handle

    def on_ready_tokenize_dsl_request(self, message: TokenizeDslRequest) -> DslWorkerState:
        if self._reply_to is None:
            raise RuntimeError("reply_to handle is not configured")
        try:
            tokens = self._lexer.tokenize(message.source)
        except Exception as error:
            self._reply_to.tell(DslParseFailed(error))
            return DslWorkerState.READY
        self._reply_to.tell(DslTokenized(tokens=tokens))
        return DslWorkerState.READY
