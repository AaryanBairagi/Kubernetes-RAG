import re
from typing import List
import logfire

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _split_oversized(text: str, chunk_size: int) -> List[str]:
    """
    Break a paragraph that is longer than chunk_size into smaller pieces:
    first by line, then by sentence, and as a last resort by hard cut.
    """
    pieces: List[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if len(line) <= chunk_size:
            pieces.append(line)
            continue
        for sentence in _SENTENCE_END.split(line):
            while len(sentence) > chunk_size:
                pieces.append(sentence[:chunk_size])
                sentence = sentence[chunk_size:]
            if sentence.strip():
                pieces.append(sentence.strip())
    return pieces


def _overlap_tail(chunk: str, overlap: int) -> str:
    """Last `overlap` characters of a chunk, trimmed to start at a word boundary."""
    if overlap <= 0 or len(chunk) <= overlap:
        return ""
    tail = chunk[-overlap:]
    space = tail.find(" ")
    return tail[space + 1 :] if space != -1 else tail


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """
    Paragraph-aware chunker.
    - Packs paragraphs together up to chunk_size characters.
    - Splits paragraphs that are too long on their own (the old version kept them as one huge chunk).
    - Carries `overlap` characters from the end of each chunk into the next,
      so context isn't lost at chunk boundaries.
    """
    with logfire.span("Text chunking", text_length=len(text or "")):
        if not text or not text.strip():
            return []

        # 1. Break the text into units that each fit within chunk_size
        units: List[str] = []
        for paragraph in text.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) <= chunk_size:
                units.append(paragraph)
            else:
                units.extend(_split_oversized(paragraph, chunk_size))

        # 2. Pack units into chunks
        chunks: List[str] = []
        current = ""
        for unit in units:
            candidate = f"{current}\n\n{unit}" if current else unit
            if len(candidate) <= chunk_size:
                current = candidate
                continue

            chunks.append(current)
            tail = _overlap_tail(current, overlap)
            if tail and len(tail) + 2 + len(unit) <= chunk_size:
                current = f"{tail}\n\n{unit}"
            else:
                current = unit

        if current:
            chunks.append(current)

        logfire.info(f"Created {len(chunks)} chunks")
        return chunks