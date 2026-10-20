"""Lightweight, local primary-text retrieval for the Lyceum.

The SQLite FTS5 index contains only cleaned public-domain text passages. Retrieved
passages are reference material for a philosopher prompt; they are never treated
as instructions and are never sent to the independent evaluator.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"
SOURCES_PATH = DATA_ROOT / "sources.json"
INDEX_PATH = DATA_ROOT / "lyceum_fts.sqlite3"
RETRIEVAL_LOG = PROJECT_ROOT / "output" / "retrieval_log.jsonl"

RETRIEVAL_SIGNALS = {
    "justice", "soul", "forms", "knowledge", "virtue", "happiness", "flourishing", "cause", "causation",
    "effect", "substance", "metaphysics", "politics", "republic", "socrates", "third man", "beauty",
    "love", "fortune", "virtù", "power", "prince", "ruler", "state", "necessity", "fear", "arms",
    "custom", "impression", "sentiment", "reason", "skeptic", "religion", "miracle", "duty", "moral",
    "obligation", "autonomy", "categorical", "universal", "maxim", "experience", "a priori", "book vii",
    "chapter", "passage", "quotation", "quote", "argue", "argument", "counterexample", "believe",
}


@dataclass(frozen=True)
class Passage:
    philosopher: str
    work: str
    passage: str
    source_url: str
    chunk_id: str


def should_retrieve(query: str) -> bool:
    """Return true only when primary-text grounding could materially help."""
    lowered = query.lower()
    if len(lowered.strip()) < 12:
        return False
    return any(signal in lowered for signal in RETRIEVAL_SIGNALS)


def _clean_gutenberg(text: str) -> str:
    """Remove license/header/footer boilerplate while keeping the work text."""
    start_markers = (
        "*** START OF THE PROJECT GUTENBERG EBOOK",
        "*** START OF THIS PROJECT GUTENBERG EBOOK",
    )
    end_markers = (
        "*** END OF THE PROJECT GUTENBERG EBOOK",
        "*** END OF THIS PROJECT GUTENBERG EBOOK",
    )
    for marker in start_markers:
        position = text.upper().find(marker)
        if position >= 0:
            newline = text.find("\n", position)
            text = text[newline + 1 :] if newline >= 0 else text[position:]
            break
    for marker in end_markers:
        position = text.upper().find(marker)
        if position >= 0:
            text = text[:position]
            break
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    # Prefer the first substantive book/section/chapter marker over translator
    # introductions and tables of contents when the edition exposes one.
    marker = re.search(r"\n(?:BOOK\s+(?:I|FIRST)|CHAPTER\s+(?:I|1)|SECTION\s+(?:I|1)|FIRST SECTION|PART\s+I)\b", text, flags=re.I)
    if marker and marker.start() > 500:
        text = text[marker.start() + 1 :]
    return text.strip()


def _chunks(text: str, target_chars: int = 1400) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in paragraphs:
        upper = paragraph.upper()
        if len(paragraph) < 100 or "PROJECT GUTENBERG" in upper or "TABLE OF CONTENTS" in upper or "EBOOK #" in upper:
            continue
        if "TRANSLATOR'S INTRODUCTION" in upper or "TRANSCRIBER'S NOTE" in upper or "EDITOR'S NOTE" in upper:
            continue
        if current and size + len(paragraph) + 2 > target_chars:
            chunks.append("\n\n".join(current))
            current, size = [], 0
        current.append(paragraph)
        size += len(paragraph) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _sources() -> list[dict]:
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))


def build_index() -> int:
    """Rebuild the FTS5 index from the included cleaned-at-build source files."""
    if INDEX_PATH.exists():
        INDEX_PATH.unlink()
    connection = sqlite3.connect(INDEX_PATH)
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE passages USING fts5(philosopher, work, passage, source_url UNINDEXED, chunk_id UNINDEXED, tokenize='porter unicode61')"
        )
        inserted = 0
        for source in _sources():
            local_path = source.get("local_path")
            if source.get("availability") != "available" or not local_path:
                continue
            path = DATA_ROOT / local_path
            if not path.exists():
                raise FileNotFoundError(f"Included corpus text is missing: {path}")
            cleaned = _clean_gutenberg(path.read_text(encoding="utf-8", errors="replace"))
            for index, passage in enumerate(_chunks(cleaned)):
                chunk_id = f"{source['philosopher']}:{source['slug']}:{index:05d}"
                connection.execute(
                    "INSERT INTO passages(philosopher, work, passage, source_url, chunk_id) VALUES (?, ?, ?, ?, ?)",
                    (source["philosopher"], source["title"], passage, source["source_url"], chunk_id),
                )
                inserted += 1
        connection.commit()
        return inserted
    finally:
        connection.close()


def _query_terms(query: str) -> list[str]:
    stopwords = {"what", "which", "how", "does", "about", "think", "your", "that", "this", "with", "from", "into", "the", "and", "for"}
    return [term for term in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", query.lower()) if term not in stopwords][:16]


def search(philosopher: str, query: str, limit: int = 4) -> list[Passage]:
    if not INDEX_PATH.exists():
        build_index()
    terms = _query_terms(query)
    if not terms:
        return []
    expressions = [" AND ".join(terms)] if len(terms) > 1 else []
    expressions.append(" OR ".join(terms))
    connection = sqlite3.connect(INDEX_PATH)
    try:
        rows = []
        for expression in expressions:
            rows = connection.execute(
                "SELECT philosopher, work, passage, source_url, chunk_id FROM passages WHERE passages MATCH ? AND philosopher = ? ORDER BY bm25(passages) LIMIT ?",
                (expression, philosopher, limit * 4),
            ).fetchall()
            if rows:
                break
    except sqlite3.OperationalError:
        rows = []
    finally:
        connection.close()
    selected: list[Passage] = []
    seen_works: set[str] = set()
    remaining: list[Passage] = []
    for row in rows:
        passage = Passage(*row)
        if passage.work not in seen_works:
            selected.append(passage)
            seen_works.add(passage.work)
        else:
            remaining.append(passage)
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        selected.extend(remaining[: limit - len(selected)])
    return selected


def retrieve_context(philosopher: str, query: str, limit: int = 4) -> str:
    """Retrieve passages and log which sources were supplied as reference material."""
    passages = search(philosopher, query, limit=limit)
    RETRIEVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "philosopher": philosopher,
        "query": query[:240],
        "passages": [{"chunk_id": p.chunk_id, "work": p.work, "source_url": p.source_url} for p in passages],
        "use": "reference_only_context_for_philosopher; never_an_instruction_or_evaluator_input",
    }
    with RETRIEVAL_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    if not passages:
        return "No relevant primary-text passage was retrieved. Answer from the philosopher's commitments and conversational context."
    return "\n\n".join(
        f"[Primary-text reference: {p.work}; passage {p.chunk_id}]\n{p.passage[:1200]}" for p in passages
    )


def log_answer_use(philosopher: str, query: str, mode: str) -> None:
    """Record how the retrieved passages were made available to the answer."""
    RETRIEVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RETRIEVAL_LOG.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": "answer_grounding",
                    "philosopher": philosopher,
                    "query": query[:240],
                    "how_informed_answer": mode,
                },
                ensure_ascii=True,
            )
            + "\n"
        )
