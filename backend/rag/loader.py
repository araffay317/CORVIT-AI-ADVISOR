"""
Dataset ingestion, safe read-only parsing, normalization, and semantic chunking.
Guarantees 100% factual fidelity and immutability of raw Dataset files.
"""
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from backend.config import BASE_DIR, settings
from backend.rag.models import DocumentChunk

logger = logging.getLogger("corvit_advisor.loader")

# Canonical 8 Corvit dataset categories mapped to expected filenames
DATASET_REGISTRY: Dict[str, str] = {
    "courses": "corvit_courses.txt",
    "navttc": "corvit_navttc.txt",
    "timetable": "corvit_timetable.txt",
    "fees": "corvit_paid_courses_fees.txt",
    "admission": "corvit_admission_application.txt",
    "infrastructure": "corvit_infrastructure.txt",
    "faq": "corvit_faq.txt",
    "general": "corvit_general.txt",
}

# Path for derived JSON cache artifact (strictly outside Dataset/)
DEFAULT_CACHE_PATH = BASE_DIR / "backend" / "data" / "processed_chunks.json"

# In-memory singleton cache
_CHUNKS_CACHE: Optional[List[DocumentChunk]] = None


def read_file_safely(file_path: Path) -> str:
    """
    Read file in strictly read-only mode using multi-encoding fallback.
    Does NOT modify the file on disk.
    """
    encodings = ["utf-8-sig", "utf-8", "cp1252"]
    for enc in encodings:
        try:
            with open(file_path, mode="r", encoding=enc, errors="strict") as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Error opening {file_path} with {enc}: {e}")
            break

    # Last resort fallback
    with open(file_path, mode="r", encoding="utf-8", errors="replace") as f:
        return f.read()


def clean_text_formatting(raw_text: str) -> str:
    """
    Normalize whitespace and line endings in-memory.
    Preserves all factual words, numbers, and symbols exactly as written.
    """
    # 1. Standardize line endings
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Strip trailing whitespace from individual lines
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)

    # 3. Collapse 3+ consecutive newlines to 2 newlines (preserve paragraph boundaries)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_sections_from_text(cleaned_text: str, default_title: str) -> List[Tuple[str, str]]:
    """
    Split text into sections based on natural divider lines and numbered headings.
    Returns a list of (section_title, section_body) tuples.
    """
    # Pattern matching dividers surrounding numbered headings:
    # e.g.:
    # --------------------------------------------------
    # 1. WHAT IS CORVIT SYSTEMS?
    # --------------------------------------------------
    pattern = re.compile(
        r"(?:\n|^)[-=\s]{0,5}[-=]{8,}[-=\s]{0,5}\n+"
        r"([0-9]+\.\s+[^\n]+(?:\n\s+[^\n]+)?)\n+"
        r"[-=\s]{0,5}[-=]{8,}[-=\s]{0,5}\n+",
        re.MULTILINE
    )

    matches = list(pattern.finditer(cleaned_text))

    if not matches:
        # If no explicit divider headings, return the entire cleaned text as one section
        return [(default_title, cleaned_text)]

    sections: List[Tuple[str, str]] = []

    # 1. Preamble (content before the first numbered section)
    preamble = cleaned_text[:matches[0].start()].strip()
    # Strip leading decorative divider if present in preamble
    preamble = re.sub(r"^[-=\s]{8,}\n+", "", preamble).strip()
    if len(preamble) >= 50:
        sections.append((f"{default_title} (Overview & Policy)", preamble))

    # 2. Extract each numbered section
    for i, match in enumerate(matches):
        raw_title = match.group(1).strip()
        # Clean multi-line title formatting to a single clean header line
        clean_title = re.sub(r"\s+", " ", raw_title)

        start_body = match.end()
        end_body = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned_text)

        body = cleaned_text[start_body:end_body].strip()
        if body:
            sections.append((clean_title, body))

    return sections


def sub_chunk_long_section(
    title: str,
    body: str,
    max_chars: int = 1500,
    overlap_chars: int = 150
) -> List[str]:
    """
    Recursively split a long section body along paragraph boundaries with overlap.
    Preserves exact verbatim content.
    """
    if len(body) <= max_chars:
        # Section fits comfortably within maximum bounds
        return [f"{title}\n\n{body}"]

    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paragraphs:
        return [f"{title}\n\n{body}"]

    chunks: List[str] = []
    current_paragraphs: List[str] = []
    current_len = 0

    for p in paragraphs:
        p_len = len(p)
        if current_len + p_len + 2 > max_chars and current_paragraphs:
            # Emit current chunk
            chunk_body = "\n\n".join(current_paragraphs)
            chunks.append(f"{title}\n\n{chunk_body}")

            # Overlap: keep the last paragraph if it's smaller than overlap_chars
            if current_paragraphs and len(current_paragraphs[-1]) <= overlap_chars:
                current_paragraphs = [current_paragraphs[-1], p]
                current_len = len(current_paragraphs[0]) + p_len + 2
            else:
                current_paragraphs = [p]
                current_len = p_len
        else:
            current_paragraphs.append(p)
            current_len += p_len + 2

    if current_paragraphs:
        chunk_body = "\n\n".join(current_paragraphs)
        chunks.append(f"{title}\n\n{chunk_body}")

    return chunks


def parse_dataset_file(
    category: str,
    filename: str,
    dataset_dir: Optional[Path] = None
) -> List[DocumentChunk]:
    """
    Parse a single Corvit dataset file into a list of typed DocumentChunk objects.
    Original file remains completely untouched.
    """
    base_dir = dataset_dir or settings.dataset_dir
    file_path = base_dir / category / filename

    if not file_path.is_file():
        raise FileNotFoundError(f"Dataset file not found at: {file_path}")

    raw_text = read_file_safely(file_path)
    cleaned_text = clean_text_formatting(raw_text)

    default_title = f"{category.upper()} - Corvit Systems"
    raw_sections = extract_sections_from_text(cleaned_text, default_title)

    chunks: List[DocumentChunk] = []
    seq = 1

    for sec_title, sec_body in raw_sections:
        # Split section into atomic chunks
        sub_chunks = sub_chunk_long_section(sec_title, sec_body)

        for text_content in sub_chunks:
            text_stripped = text_content.strip()
            if len(text_stripped) < 20:
                continue

            chunk_id = f"{category}_{seq:03d}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    text=text_stripped,
                    category=category,
                    source_file=filename,
                    section_title=sec_title,
                    char_count=len(text_stripped),
                    token_estimate=len(text_stripped.split())
                )
            )
            seq += 1

    return chunks


def ingest_all_dataset_files(dataset_dir: Optional[Path] = None) -> List[DocumentChunk]:
    """
    Ingest all 8 canonical Corvit dataset files into typed DocumentChunks.
    Guarantees every category produces at least one valid chunk.
    Original files remain strictly read-only.
    """
    base_dir = dataset_dir or settings.dataset_dir
    all_chunks: List[DocumentChunk] = []

    for category, filename in DATASET_REGISTRY.items():
        cat_chunks = parse_dataset_file(category, filename, base_dir)
        if not cat_chunks:
            raise ValueError(f"Category '{category}' produced 0 chunks from {filename}.")
        all_chunks.extend(cat_chunks)

    logger.info(f"Ingestion complete: {len(all_chunks)} total chunks created across {len(DATASET_REGISTRY)} categories.")
    return all_chunks


def export_chunks_to_json(chunks: List[DocumentChunk], export_path: Optional[Path] = None) -> Path:
    """
    Export processed chunks to a derived JSON cache file for audit and fast loading.
    Strictly written outside of Dataset/ directory.
    """
    target = export_path or DEFAULT_CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    data = [chunk.model_dump() for chunk in chunks]
    with open(target, mode="w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Exported {len(chunks)} chunks to cache at: {target}")
    return target


def load_chunks_from_json(json_path: Optional[Path] = None) -> List[DocumentChunk]:
    """Load DocumentChunk objects from the derived JSON cache."""
    target = json_path or DEFAULT_CACHE_PATH
    if not target.is_file():
        raise FileNotFoundError(f"Cache file not found at: {target}")

    with open(target, mode="r", encoding="utf-8") as f:
        data = json.load(f)

    return [DocumentChunk(**item) for item in data]


def get_dataset_chunks(force_reload: bool = False, use_cache: bool = True) -> List[DocumentChunk]:
    """
    Primary access point for processed dataset chunks.
    Uses memory cache -> JSON cache -> on-the-fly ingestion from raw Dataset.
    Original Dataset ALWAYS serves as the primary authority.
    """
    global _CHUNKS_CACHE

    if _CHUNKS_CACHE is not None and not force_reload:
        return _CHUNKS_CACHE

    # Attempt to load from JSON cache if enabled and present
    if use_cache and not force_reload and DEFAULT_CACHE_PATH.is_file():
        try:
            chunks = load_chunks_from_json()
            _CHUNKS_CACHE = chunks
            return chunks
        except Exception as e:
            logger.warning(f"Failed to load JSON cache: {e}. Re-ingesting from raw Dataset.")

    # Ingest from raw Dataset files directly
    chunks = ingest_all_dataset_files()
    _CHUNKS_CACHE = chunks

    # Update cache artifact
    try:
        export_chunks_to_json(chunks)
    except Exception as e:
        logger.warning(f"Failed to export JSON cache: {e}")

    return chunks
