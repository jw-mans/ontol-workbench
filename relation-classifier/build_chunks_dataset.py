"""build_chunks_dataset.py — DSL DiGr -> чистый эталонный кусок текста -> (опц.) Qdrant.

Прокладка для ВКР: по ЗАДАННОМУ списку пар понятий находит фрагмент учебного текста,
где оба понятия встречаются вместе, и формирует ЧИСТЫЙ кусок из ЦЕЛЫХ предложений
(без LaTeX, формул, переносов строк и обрывков), по которому можно определить тип связи.

Понятия ищутся ТЕКСТОВЫМ поиском через DSL `CONTEXT` (по словоформам имени), а не по
разметке \\odmkey — так совместная встречаемость находится во много раз чаще (\\odmkey
ставится ~1 раз на понятие). Алгоритм на пару (A, B):
  1) `CONTEXT semantic_block[<=N] FOR /regexA/i, /regexB/i` — минимальные окна, где есть оба;
  2) внутри окна re.search'ем находим позиции A и B;
  3) чистим LaTeX (формулы $...$, таблицы, команды — вон), схлопываем пробелы;
  4) оставляем ТОЛЬКО целые предложения от предложения с A до предложения с B (без обрывков);
  5) при необходимости ужимаем под окно эмбеддинга, НЕ разрывая предложения.

Запуск (из корня; имена понятий ищутся в тексте, поэтому resolve не нужен):
    PYTHONPATH=src python build_chunks_dataset.py --pairs pairs_w_relation.json \
        --tex tex/all_lectures.tex --jsonl-out chunks_ontology_text.jsonl
    PYTHONPATH=src python build_chunks_dataset.py --pair "Множество" "Алгебра"

По умолчанию — dry-run: пишет JSONL, БЕЗ эмбеддингов и Qdrant (их зависимости
подгружаются лениво, только когда заданы --embed / --qdrant-*).

Формат строки JSONL (плоско):
    concept_a / concept_b      — понятия простыми словами (для эмбеддинга/поиска)
    relation_type              — ИСТИННЫЙ тип связи из файла пар (онтологии) либо null
    predicted_relation_type    — тип, предсказанный моделью (заполняет predict_relations.py)
    reference_chunk            — чистый текст-эталон: целые предложения с обоими понятиями
    index_a / index_b          — имена понятий как в онтологии (ключ/дедуп)
    source                     — имя исходного файла
(с флагом --debug добавляется поле _debug с метриками отбора куска.)
"""
from __future__ import annotations

import argparse
import bisect
import csv
import dataclasses
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

# --- чтобы скрипт работал и без PYTHONPATH=src, и с ним ----------------------
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from document_ast import ActorAstParser  # noqa: E402
from dsl import ActorDslEngine  # noqa: E402

# Фиксированный namespace для детерминированных id точек Qdrant (idempotent upsert).
ID_NAMESPACE = uuid.UUID("8f1d2c5a-2b7e-4c3a-9d6f-0a1b2c3d4e5f")

# Сколько символов сырого текста захватываем по краям от пары понятий, чтобы
# гарантированно поймать ЦЕЛЫЕ предложения с понятиями (лишнее потом отрезаем).
WINDOW_PAD = 1000

# Маркеры «явной» связи между понятиями (стемы, lower) — для ранжирования кусков.
DEFAULT_CUE_WORDS = (
    "являет", "называ", "то есть", "если", "тогда", "входит", "содерж",
    "част", "вид ", "подмножеств", "эквивалент", "обознач", "определя",
    "состоит", "представля", "задаёт", "задает", "следовательн", "поэтому",
    "множеств", "относит", "есть ", "или ", "это ",
)

# Приватные символы-маркеры: метим позиции целевых понятий и точки сокращений,
# чтобы корректно найти предложения и не рвать текст по «т.е.» и т.п.
_MARK_A = ""
_MARK_B = ""
_ABBR_DOT = ""


# ============================================================================
# Доменные типы
# ============================================================================
@dataclasses.dataclass(slots=True)
class ConceptOccurrence:
    index: str          # metadata.index — каноничная идентичность понятия
    name: str           # metadata.name — видимый термин (может быть пустым)
    start: int          # смещение в document.root.text (начало \odmkey)
    end: int


@dataclasses.dataclass(slots=True)
class SemanticBlock:
    start: int
    end: int
    kind: Optional[str]


@dataclasses.dataclass(slots=True)
class ChunkRecord:
    concept_a: str                 # простое слово (для Qdrant)
    concept_b: str
    relation_type: Optional[str]   # ИСТИННЫЙ тип связи (из файла пар) либо None
    reference_chunk: str
    index_a: str                   # каноничный id (ключ/дедуп) = имя понятия
    index_b: str
    source: str
    predicted_relation_type: Optional[str] = None  # заполняется моделью (predict_relations.py)
    debug: Optional[dict] = None   # метрики отбора, только при --debug


# ============================================================================
# Шаг 1. Загрузка документа и semantic_block-ов (DSL)
# ============================================================================
def load_document(tex_path: str, config_dir: str = "config/formats"):
    parser = ActorAstParser.from_config_dir(config_dir)
    return parser.parse(tex_path)


def load_semantic_blocks(engine: ActorDslEngine, document) -> list[SemanticBlock]:
    result = engine.execute(document, "FIND semantic_block RETURN nodes")
    blocks = [
        SemanticBlock(
            start=item["nodes"]["start"],
            end=item["nodes"]["end"],
            kind=item["nodes"].get("metadata", {}).get("kind"),
        )
        for item in result.to_dict()["items"]
    ]
    blocks.sort(key=lambda b: b.start)
    return blocks


class BlockIndex:
    """Быстрый поиск semantic_block по смещению (блоки не вложены и не пересекаются)."""

    def __init__(self, blocks: Sequence[SemanticBlock]):
        self.blocks = list(blocks)
        self._starts = [b.start for b in self.blocks]

    def index_of(self, offset: int) -> Optional[int]:
        if not self.blocks:
            return None
        i = bisect.bisect_right(self._starts, offset) - 1
        if i >= 0 and self.blocks[i].start <= offset < self.blocks[i].end:
            return i
        return None


# ============================================================================
# Шаг 2. Поиск совместной встречаемости (пары вхождений A и B)
# ============================================================================
@dataclasses.dataclass(slots=True)
class Candidate:
    occ_a: ConceptOccurrence
    occ_b: ConceptOccurrence
    same_block: bool
    symbol_distance: int


def _symbol_distance(a: ConceptOccurrence, b: ConceptOccurrence) -> int:
    earlier, later = (a, b) if a.start <= b.start else (b, a)
    return max(0, later.start - earlier.end)


def concept_regex(name: str) -> str:
    """Регэксп русских словоформ понятия из имени онтологии (для DSL `~=` и re.search).

    Берём самый длинный значимый токен (наиболее различающий) и его стем + `\\w*`,
    напр. «Натуральное число» -> `натуральн\\w*`, «Множество» -> `множеств\\w*`.
    Короткие/символьные имена («Бит», «1», «OR») экранируем как есть."""
    words = [w for w in re.findall(r"[A-Za-zА-Яа-яЁё]+", name) if len(w) > 3]
    if not words:
        toks = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", name)
        return re.escape(toks[0]) if toks else re.escape(name.strip())
    core = max(words, key=len)
    stem = core[: max(4, len(core) - 2)]
    return rf"{re.escape(stem)}\w*"


def find_candidates_text(
    engine: ActorDslEngine,
    document,
    full_text: str,
    block_index: BlockIndex,
    a_name: str,
    b_name: str,
    *,
    window_blocks: int,
) -> list[Candidate]:
    """Текстовая совместная встречаемость через DSL `CONTEXT` (без \\odmkey).

    `CONTEXT semantic_block[<=N] FOR a:/regexA/i, b:/regexB/i` находит минимальные окна
    из <=N соседних блоков, где встречаются ОБА понятия (по регэкспу словоформ). Точные
    позиции понятий внутри окна до-находим re.search'ем (у regex-паттернов CONTEXT нет
    AST-узла, поэтому позиций он не отдаёт — только span окна)."""
    ra, rb = concept_regex(a_name), concept_regex(b_name)
    query = (f"CONTEXT semantic_block[<={window_blocks}] "
             f"FOR a: /{ra}/i, b: /{rb}/i RETURN text, span")
    try:
        result = engine.execute(document, query).to_dict()
    except Exception:
        return []
    pa, pb = re.compile(ra, re.IGNORECASE), re.compile(rb, re.IGNORECASE)
    out: list[Candidate] = []
    seen: set[tuple[int, int]] = set()
    for item in result.get("items", []):
        span = item.get("span") or {}
        ws, we = span.get("start"), span.get("end")
        if ws is None or we is None:
            continue
        window = full_text[ws:we]
        ma, mb = pa.search(window), pb.search(window)
        if not ma or not mb:
            continue
        occ_a = ConceptOccurrence(a_name, a_name, ws + ma.start(), ws + ma.end())
        occ_b = ConceptOccurrence(b_name, b_name, ws + mb.start(), ws + mb.end())
        key = (min(occ_a.start, occ_b.start), max(occ_a.start, occ_b.start))
        if key in seen:
            continue
        seen.add(key)
        ba, bb = block_index.index_of(occ_a.start), block_index.index_of(occ_b.start)
        same_block = ba is not None and ba == bb
        out.append(Candidate(occ_a, occ_b, same_block, _symbol_distance(occ_a, occ_b)))
    return out


# ============================================================================
# Шаг 3. Очистка LaTeX и разбивка на предложения
# ============================================================================
_ODMKEY = re.compile(r"\\odmkey\s*\{(?P<name>.*?)\}\s*\{(?P<index>.*?)\}", re.DOTALL)
_MATH_DD = re.compile(r"\$\$.*?\$\$", re.DOTALL)
_MATH_D = re.compile(r"\$.*?\$", re.DOTALL)
_MATH_BR = re.compile(r"\\\[.*?\\\]", re.DOTALL)
_MATH_PAREN = re.compile(r"\\\(.*?\\\)", re.DOTALL)
_COMMENT = re.compile(r"(?<!\\)%[^\n]*")     # комментарий LaTeX до конца строки
# Окружения, чьё СОДЕРЖИМОЕ выбрасываем целиком (формулы, таблицы, рисунки, код) —
# это не связный текст и для определения типа связи бесполезно.
_DROP_ENV = re.compile(
    r"\\begin\{(equation|align|eqnarray|gather|multline|displaymath|"
    r"tabular|tabularx|array|longtable|tabu|"
    r"figure|wrapfigure|table|tikzpicture|lstlisting|verbatim|picture)\*?\}.*?"
    r"\\end\{\1\*?\}",
    re.DOTALL,
)
_GRAPHICS = re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{[^}]*\}")
_SLIDE_NUM = re.compile(r"\(\s*\d+\s*/\s*\d+\s*\)")   # счётчик слайдов «(2/8)»
_AXIOM_REF = re.compile(r"\([A-ZА-Я]\d{1,2}\)")       # ссылки на аксиомы «(A1)», «(A8)»
# Англоязычные глоссы в скобках «(set)», «(subalgebra)», «(finitely generated)» — остатки
# двуязычных индексов \odmkey; в русском тексте такие скобки = шум, срезаем.
_ENG_GLOSS = re.compile(r"\(\s*[A-Za-z][\w\s/.\-]*\)")
# Команды, чьё содержимое в фигурных скобках тоже выбрасываем (шум для смысла:
# заголовки разделов и слайдов, метки, ссылки, отступы).
_ARG_CMDS = re.compile(
    r"\\(?:part|chapter|section|subsection|subsubsection|paragraph|subparagraph|"
    r"frametitle|framesubtitle|title|author|date|label|index|cite[a-zA-Z]*|"
    r"ref|eqref|pageref|input|include|usepackage|hypertarget|hyperlink|caption|"
    r"footnote|vspace|hspace|color|textcolor|colorbox|fcolorbox)\*?\s*\{.*?\}",
    re.DOTALL,
)
_SPACING_CMD = re.compile(r"\\[ ,;:!]")     # \, \; \: \! \(пробел) — мат. отступы
# begin/end окружений вместе с их необязательными/обязательными аргументами,
# напр. \begin{column}{0.6\textwidth} или \begin{frame}[t]{Заголовок}.
_ENV = re.compile(
    r"\\begin\{[a-zA-Z*]+\}\s*(?:\[[^\]]*\])?\s*(?:\{[^}]*\})?|\\end\{[a-zA-Z*]+\}"
)
_CMD = re.compile(r"\\[a-zA-Z@]+\*?")        # прочие команды (контент в {} сохраняем)
_PUNCT_RUN = re.compile(r"[,;:]+\s*(?=[.,;:])")  # осиротевшая пунктуация подряд
_SENT_SPLIT = re.compile(
    r"(?<=[.!?…])\s+(?=[«»\"(\[A-ZА-ЯЁ0-9" + _MARK_A + _MARK_B + r"])"
)
_ABBRS = (
    "и т. д.", "и т. п.", "т. е.", "т. д.", "т. к.", "т. п.",
    "т.е.", "т.д.", "т.к.", "т.п.", "см.", "напр.", "рис.", "табл.",
    "гл.", "стр.", "др.", "пр.", "вв.",
)


def to_plain_word(index: str) -> str:
    """'Язык!регулярный' -> 'язык регулярный'. Читаемая форма, сохраняет квалификатор."""
    return index.replace("!", " ").strip().lower()


def clean_latex(raw: str, mark_at: Optional[dict[int, str]] = None) -> str:
    """Очистить фрагмент LaTeX до читаемого текста в одну строку.

    mark_at: {смещение_начала_\\odmkey_в raw: маркер} — целевые понятия помечаются
    маркером (невидимый приватный символ), чтобы потом найти их предложения.
    """
    mark_at = mark_at or {}

    def _odm(m: re.Match) -> str:
        name = " ".join(m.group("name").split()) or to_plain_word(m.group("index"))
        mk = mark_at.get(m.start())  # m.start() — позиция в raw (re.sub идёт по исходной строке)
        return (mk + name) if mk else name

    text = _ODMKEY.sub(_odm, raw)
    # комментарии LaTeX (авторские заметки) — вон; пока ещё есть переносы строк
    text = _COMMENT.sub(" ", text)
    # формулы/таблицы/рисунки/код выкидываем целиком (не связный текст)
    text = _DROP_ENV.sub(" ", text)
    text = _MATH_DD.sub(" ", text)
    text = _MATH_D.sub(" ", text)
    text = _MATH_BR.sub(" ", text)
    text = _MATH_PAREN.sub(" ", text)
    text = _GRAPHICS.sub(" ", text)
    # команды с аргументом-обёрткой (заголовки разделов/слайдов, метки, ссылки и пр.)
    text = _ARG_CMDS.sub(" ", text)
    text = _SPACING_CMD.sub(" ", text)
    text = _ENV.sub(" ", text)
    text = _SLIDE_NUM.sub(" ", text)
    text = _AXIOM_REF.sub(" ", text)
    text = _ENG_GLOSS.sub(" ", text)
    # типографика
    text = text.replace("~---", " — ").replace("---", " — ").replace("~--", " — ").replace("--", " — ")
    text = text.replace("<<", "«").replace(">>", "»").replace("~", " ")
    # прочие команды (\textbf{x} -> ' x '), затем убираем служебные символы
    text = _CMD.sub(" ", text)
    text = text.replace("\\", " ").replace("{", " ").replace("}", " ")
    text = text.replace("$", " ").replace("&", " ")
    # схлопнуть все пробелы и переносы строк в один пробел
    text = re.sub(r"\s+", " ", text)
    # склеить осиротевшую пунктуацию от удалённых формул (« форму:, где » -> « форму, где »)
    text = _PUNCT_RUN.sub("", text)
    # убрать пробелы вокруг пунктуации и пустые скобки после удаления формул
    text = re.sub(r"\s+([,.;:!?»)\]])", r"\1", text)
    text = re.sub(r"([«(\[])\s+", r"\1", text)
    text = re.sub(r"\(\s*\)", " ", text)
    text = re.sub(r"«\s*»", " ", text)
    text = re.sub(r"\s+([,.;:!?»)\]])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    """Разбить на предложения, не разрывая распространённые сокращения (т.е., см., и т.д.)."""
    protected = text
    for ab in _ABBRS:
        protected = protected.replace(ab, ab.replace(".", _ABBR_DOT))
    out: list[str] = []
    for part in _SENT_SPLIT.split(protected):
        s = part.replace(_ABBR_DOT, ".").strip()
        if s:
            out.append(s)
    return out


def _fit_span(sents: list[str], lo: int, hi: int, limit: int) -> str:
    """Целые предложения [lo..hi]. Если длиннее limit — оставляем предложения с
    понятиями (lo, hi) и добиваем серединой, пока влезает, не разрывая предложения."""
    full = " ".join(sents[lo:hi + 1])
    if len(full) <= limit or lo == hi:
        return full
    chosen = {lo, hi}
    size = len(sents[lo]) + 1 + len(sents[hi])
    for i in range(lo + 1, hi):
        add = 1 + len(sents[i])
        if size + add > limit:
            break
        chosen.add(i)
        size += add
    parts: list[str] = []
    prev: Optional[int] = None
    for i in sorted(chosen):
        if prev is not None and i != prev + 1:
            parts.append("…")
        parts.append(sents[i])
        prev = i
    return " ".join(parts)


def _tidy_edges(chunk: str) -> str:
    """Срезать висячую пунктуацию по краям (двоеточие/запятая/тире от удалённых формул)."""
    chunk = re.sub(r"^[\s:;,.…—–-]+", "", chunk)
    chunk = re.sub(r"[\s:;,—–-]+$", "", chunk)
    return chunk.strip()


def extract_chunk(
    full_text: str,
    occ_a: ConceptOccurrence,
    occ_b: ConceptOccurrence,
    re_a: "re.Pattern",
    re_b: "re.Pattern",
    block_index: BlockIndex,
    max_chunk_chars: int,
    no_clean: bool,
) -> tuple[str, Optional[int]]:
    """Вернуть (чистый кусок из целых предложений, число предложений или None).

    Окно берём вокруг найденной CONTEXT-ом пары (occ_a, occ_b), ограничивая границами
    semantic_block-ов (иначе цепляем чужие слайды). Внутри окна помечаем ВСЕ вхождения
    обоих понятий (по re_a/re_b) — это устойчиво к потере маркера в вырезаемой формуле и
    позволяет выбрать НАИБОЛЕЕ ТЕСНУЮ пару предложений с A и B."""
    lo_off = min(occ_a.start, occ_b.start)
    hi_off = max(occ_a.end, occ_b.end)
    ws = max(0, lo_off - WINDOW_PAD)
    we = min(len(full_text), hi_off + WINDOW_PAD)
    ba = block_index.index_of(occ_a.start)
    bb = block_index.index_of(occ_b.start)
    if ba is not None and bb is not None:
        ws = max(ws, block_index.blocks[min(ba, bb)].start)
        we = min(we, block_index.blocks[max(ba, bb)].end)
    window = full_text[ws:we]
    if no_clean:
        return window.strip(), None

    # СНАЧАЛА очищаем (\odmkey -> имя, формулы/команды вон), ПОТОМ помечаем понятия в уже
    # чистом тексте — иначе маркер внутри \odmkey ломает его разбор и оставляет индекс.
    cleaned = clean_latex(window)
    marks = [(m.start(), _MARK_A) for m in re_a.finditer(cleaned)]
    marks += [(m.start(), _MARK_B) for m in re_b.finditer(cleaned)]
    marked = cleaned
    for pos, mk in sorted(marks, reverse=True):  # вставка справа налево
        marked = marked[:pos] + mk + marked[pos:]
    sents = split_sentences(marked)
    a_idx = [i for i, s in enumerate(sents) if _MARK_A in s]
    b_idx = [i for i, s in enumerate(sents) if _MARK_B in s]
    if not a_idx or not b_idx:
        # одно из понятий не встретилось в ЧИСТОМ тексте окна — куска нет (пропускаем)
        return "", None

    # ближайшая пара предложений (A, B) — самый тесный кусок, где есть оба понятия
    lo, hi = min(((min(i, j), max(i, j)) for i in a_idx for j in b_idx),
                 key=lambda p: p[1] - p[0])
    chunk = _fit_span(sents, lo, hi, max_chunk_chars)
    chunk = chunk.replace(_MARK_A, "").replace(_MARK_B, "")
    chunk = _tidy_edges(re.sub(r"\s{2,}", " ", chunk))
    return chunk, hi - lo + 1


def count_cues(text: str, cues: Sequence[str]) -> int:
    low = text.lower()
    return sum(1 for c in cues if c in low)


def score_candidate(cand: Candidate, cue_count: int) -> float:
    """Чем «явнее» связь (один блок, близко, много слов-маркеров) — тем выше."""
    proximity = 1.0 / (1.0 + cand.symbol_distance)
    return (2.0 if cand.same_block else 0.0) + 0.5 * cue_count + proximity


# ============================================================================
# Сборка записи по паре
# ============================================================================
def build_records_for_pair(
    a_name: str,
    b_name: str,
    engine: ActorDslEngine,
    document,
    full_text: str,
    block_index: BlockIndex,
    source: str,
    opts: argparse.Namespace,
    relation_type: Optional[str] = None,
) -> list[ChunkRecord]:
    cands = find_candidates_text(
        engine, document, full_text, block_index, a_name, b_name,
        window_blocks=opts.window_blocks,
    )
    if not cands:
        return []

    re_a = re.compile(concept_regex(a_name), re.IGNORECASE)
    re_b = re.compile(concept_regex(b_name), re.IGNORECASE)
    scored: list[tuple[float, ChunkRecord]] = []
    for cand in cands:
        chunk, n_sent = extract_chunk(
            full_text, cand.occ_a, cand.occ_b, re_a, re_b, block_index,
            opts.max_chunk_chars, opts.no_clean,
        )
        if not chunk:
            continue
        cue_count = count_cues(chunk, opts.cue_words)
        score = score_candidate(cand, cue_count)
        debug = None
        if opts.debug:
            debug = {
                "score": round(score, 4),
                "same_block": cand.same_block,
                "symbol_distance": cand.symbol_distance,
                "cue_count": cue_count,
                "sentences": n_sent,
                "chunk_chars": len(chunk),
            }
        record = ChunkRecord(
            concept_a=to_plain_word(a_name),
            concept_b=to_plain_word(b_name),
            relation_type=relation_type,
            reference_chunk=chunk,
            index_a=a_name,
            index_b=b_name,
            source=source,
            predicted_relation_type=None,
            debug=debug,
        )
        scored.append((score, record))

    scored.sort(key=lambda t: t[0], reverse=True)
    out: list[ChunkRecord] = []
    seen_text: set[str] = set()
    for _, rec in scored:
        if rec.reference_chunk in seen_text:
            continue
        seen_text.add(rec.reference_chunk)
        out.append(rec)
        if len(out) >= opts.top_k:
            break
    return out


def record_to_json(rec: ChunkRecord) -> dict[str, Any]:
    d: dict[str, Any] = {
        "concept_a": rec.concept_a,
        "concept_b": rec.concept_b,
        "relation_type": rec.relation_type,                  # истинный тип (из онтологии)
        "predicted_relation_type": rec.predicted_relation_type,  # заполнит модель
        "reference_chunk": rec.reference_chunk,
        "index_a": rec.index_a,
        "index_b": rec.index_b,
        "source": rec.source,
    }
    if rec.debug:
        d["_debug"] = rec.debug
    return d


# ============================================================================
# Seam для типа связи (отдельный проход — здесь no-op)
# ============================================================================
RelationClassifier = Callable[[ChunkRecord], Optional[str]]


def classify_relations(records: list[ChunkRecord], classifier: Optional[RelationClassifier] = None) -> None:
    if classifier is None:
        return  # relation_type остаётся None; заполнит отдельный LLM-файл
    for r in records:
        r.relation_type = classifier(r)


# ============================================================================
# Шаг 4. Эмбеддинги (ленивый импорт) + Qdrant (ленивый импорт)
# ============================================================================
def embed_texts(texts: list[str], model_name: str, passage_prefix: str = "") -> list[list[float]]:
    from sentence_transformers import SentenceTransformer  # ленивый, тяжёлый импорт

    model = SentenceTransformer(model_name)
    payload = [f"{passage_prefix}{t}" for t in texts] if passage_prefix else texts
    vectors = model.encode(payload, normalize_embeddings=True, show_progress_bar=False)
    return [list(map(float, v)) for v in vectors]


def point_id(record: ChunkRecord) -> str:
    a, b = sorted((record.index_a, record.index_b))
    return str(uuid.uuid5(ID_NAMESPACE, f"{record.source}|{a}|{b}"))


def upsert_qdrant(
    records: list[ChunkRecord],
    vectors: list[list[float]],
    *,
    collection: str,
    path: Optional[str],
    url: Optional[str],
) -> None:
    from qdrant_client import QdrantClient  # ленивый импорт
    from qdrant_client.models import Distance, PointStruct, VectorParams

    client = QdrantClient(url=url) if url else QdrantClient(path=path or "./qdrant_storage")

    dim = len(vectors[0]) if vectors else 1024
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    points = [
        PointStruct(
            id=point_id(rec),
            vector=vec,
            payload={
                "concept_a": rec.concept_a,
                "concept_b": rec.concept_b,
                "relation_type": rec.relation_type,
                "predicted_relation_type": rec.predicted_relation_type,
                "reference_chunk": rec.reference_chunk,
                "index_a": rec.index_a,
                "index_b": rec.index_b,
                "source": rec.source,
            },
        )
        for rec, vec in zip(records, vectors)
    ]
    client.upsert(collection_name=collection, points=points)


# ============================================================================
# Вход: список пар понятий
# ============================================================================
def read_pairs(args: argparse.Namespace) -> list[tuple[str, str, Optional[str]]]:
    """Вернуть тройки (имя_a, имя_b, relation_type). relation_type — истинный тип или None.

    Поддерживаются JSON-объекты:
      * онтология `{"name1","name2","type"[, ...]}` (pairs_w_relation.json) — лишние поля
        (pole/predicate) игнорируются;
      * `{"a","b"[,"relation_type"|"type"]}`; список `[a, b[, type]]`; .csv/.tsv (2–3 колонки).
    Понятия ищутся в тексте по словоформам (concept_regex), поэтому имена берутся как есть."""
    pairs: list[tuple[str, str, Optional[str]]] = []
    for a, b in (args.pair or []):
        pairs.append((a, b, None))
    if args.pairs:
        path = Path(args.pairs)
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("relations", [])
            for item in data:
                if isinstance(item, dict):
                    if item.get("name1") and item.get("name2"):       # формат онтологии
                        pairs.append((item["name1"], item["name2"], item.get("type")))
                    else:
                        pairs.append((item["a"], item["b"], item.get("relation_type") or item.get("type")))
                else:
                    pairs.append((item[0], item[1], item[2] if len(item) > 2 else None))
        else:  # csv/tsv
            delim = "\t" if path.suffix.lower() == ".tsv" else ","
            with path.open(encoding="utf-8", newline="") as f:
                for row in csv.reader(f, delimiter=delim):
                    if len(row) >= 2 and row[0].strip() and row[0].strip().lower() not in ("a", "concept_a"):
                        rel = row[2].strip() if len(row) > 2 and row[2].strip() else None
                        pairs.append((row[0].strip(), row[1].strip(), rel))
    return pairs


# ============================================================================
# CLI / оркестрация
# ============================================================================
def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DSL DiGr -> чистые эталонные куски пар понятий -> (опц.) Qdrant")
    p.add_argument("--tex", default="data/all_lectures.tex", help="исходный LaTeX-файл (учебник)")
    p.add_argument("--config-dir", default="config/formats")
    p.add_argument("--pair", nargs=2, action="append", metavar=("A", "B"),
                   help="одна пара понятий по именам (можно повторять)")
    p.add_argument("--pairs", help="файл пар: .json онтологии {name1,name2,type} / {a,b} / [a,b]; .csv/.tsv")
    p.add_argument("--window-blocks", type=int, default=2,
                   help="макс. число соседних semantic_block в окне CONTEXT (текстовая встречаемость)")
    p.add_argument("--max-chunk-chars", type=int, default=1000,
                   help="потолок длины куска (~512 токенов e5); предложения не разрываются")
    p.add_argument("--top-k", type=int, default=1, help="сколько лучших кусков на пару сохранять")
    p.add_argument("--no-clean", action="store_true", help="не очищать LaTeX (для отладки)")
    p.add_argument("--debug", action="store_true", help="добавить _debug (метрики отбора) в JSONL")
    p.add_argument("--jsonl-out", default="chunks.jsonl", help="куда писать датасет (dry-run)")
    p.add_argument("--limit", type=int, default=0, help="обработать не более N пар (0 = все)")
    # эмбеддинги / Qdrant — выключены по умолчанию (ленивые зависимости)
    p.add_argument("--embed", action="store_true", help="считать эмбеддинги (нужен sentence-transformers)")
    p.add_argument("--embed-model", default="intfloat/multilingual-e5-large-instruct")
    p.add_argument("--passage-prefix", default="", help="префикс для пассажей (e5-instruct: пусто)")
    p.add_argument("--qdrant-path", help="каталог встроенного Qdrant (без сервера)")
    p.add_argument("--qdrant-url", help="URL сервера Qdrant, напр. http://localhost:6333")
    p.add_argument("--collection", default="concept_pairs")
    p.add_argument("--dry-run", action="store_true", help="не грузить в Qdrant даже если задан target")
    args = p.parse_args(argv)
    args.cue_words = DEFAULT_CUE_WORDS
    return args


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    raw_pairs = read_pairs(args)
    if not raw_pairs:
        print("Не задано ни одной пары. Используйте --pair A B или --pairs file.json")
        return 2

    print(f"Парсинг {args.tex} ...")
    document = load_document(args.tex, args.config_dir)
    full_text = document.root.text
    engine = ActorDslEngine()

    print("Загрузка semantic_block-ов через DSL ...")
    blocks = load_semantic_blocks(engine, document)
    block_index = BlockIndex(blocks)
    print(f"  semantic_block: {len(blocks)}; пар на обработку: {len(raw_pairs)}")

    source = os.path.basename(args.tex)
    records: list[ChunkRecord] = []
    not_found: list[tuple[str, str]] = []

    pairs = raw_pairs[: args.limit] if args.limit else raw_pairs
    for a_name, b_name, rel in pairs:
        recs = build_records_for_pair(a_name, b_name, engine, document, full_text, block_index,
                                      source, args, relation_type=rel)
        if not recs:
            not_found.append((a_name, b_name))
            continue
        records.extend(recs)
        best = recs[0]
        snippet = best.reference_chunk[:70] + ("…" if len(best.reference_chunk) > 70 else "")
        print(f"  [ok] {best.concept_a} <-> {best.concept_b} "
              f"({len(best.reference_chunk)} симв.): {snippet}")

    classify_relations(records, classifier=None)  # predicted_relation_type заполнит модель

    # Датасет на диск (dry-run всегда доступен, Qdrant не нужен)
    if args.jsonl_out and records:
        with open(args.jsonl_out, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(record_to_json(rec), ensure_ascii=False) + "\n")
        print(f"Записано {len(records)} записей -> {args.jsonl_out}")

    # Эмбеддинги + Qdrant (только если явно заданы)
    want_qdrant = bool(args.qdrant_path or args.qdrant_url) and not args.dry_run
    if (args.embed or want_qdrant) and records:
        print(f"Считаю эмбеддинги моделью {args.embed_model} ...")
        vectors = embed_texts([r.reference_chunk for r in records], args.embed_model, args.passage_prefix)
        if want_qdrant:
            print(f"Загрузка в Qdrant (collection={args.collection}) ...")
            upsert_qdrant(records, vectors, collection=args.collection,
                          path=args.qdrant_path, url=args.qdrant_url)
            print("Готово.")
        else:
            print("Эмбеддинги посчитаны (Qdrant target не задан или --dry-run).")

    print(f"\nИтог: пар обработано {len(pairs)}, записей {len(records)}, "
          f"без куска {len(not_found)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
