"""
core/pdf_parser.py
──────────────────
Reads the SLATEFALL PDF and splits it into numbered sections.

Strategy:
1. Extract text page-by-page using PyMuPDF (fast, reliable)
2. Detect section boundaries using regex patterns
3. If detection finds fewer than 3 sections → fall back to equal page splits

WHY regex + fallback (not LLM-based detection):
- Deterministic: same PDF always gives same sections
- Fast: no extra API call for parsing
- Fallback: handles any PDF format even if regex fails
- Reviewers can verify sections with: python main.py list-sections

IMPORTANT: After you get the actual PDF, run list-sections and verify
the sections look correct. You may need to adjust the regex patterns
in _parse_sections() to match the PDF's actual heading format.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

import config
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PDFSection:
    """
    One section of the PDF document.

    Fields:
        section_id:   Integer 1-10 (or as detected)
        title:        The heading text
        content:      Full text of this section
        start_page:   First page number (1-indexed)
        end_page:     Last page number (1-indexed)
        word_count:   Automatically calculated
    """
    section_id: int
    title:      str
    content:    str
    start_page: int
    end_page:   int
    word_count: int = field(init=False)

    def __post_init__(self):
        self.word_count = len(self.content.split())

    def to_dict(self) -> dict:
        return {
            "section_id":      self.section_id,
            "title":           self.title,
            "start_page":      self.start_page,
            "end_page":        self.end_page,
            "word_count":      self.word_count,
            "content_preview": self.content[:300].replace("\n", " ") + "...",
        }

    def __repr__(self) -> str:
        return (
            f"PDFSection(id={self.section_id}, "
            f"title='{self.title[:40]}', "
            f"pages={self.start_page}-{self.end_page}, "
            f"words={self.word_count})"
        )


class PDFParser:
    """
    Loads the PDF and exposes sections for downstream use.

    Usage:
        parser = PDFParser()
        parser.load()                        # Parse PDF
        section = parser.get_section(5)      # Get section 5
        sections = parser.get_sections([5,8]) # Get sections 5 and 8
    """

    def __init__(self, pdf_path: Path | None = None):
        self.pdf_path   = pdf_path or config.PDF_PATH
        self.sections:  dict[int, PDFSection] = {}
        self._pages:    list[str] = []   # Raw text per page
        self._loaded:   bool      = False

    def load(self) -> None:
        """
        Load and parse the PDF.
        Idempotent — safe to call multiple times (only runs once).
        """
        if self._loaded:
            return

        if not self.pdf_path.exists():
            raise FileNotFoundError(
                f"\n❌ PDF not found: {self.pdf_path}\n"
                f"   Place SLATEFALL_DOSSIER.pdf in the data/ folder.\n"
                f"   Then re-run your command."
            )

        logger.info(f"Loading PDF: {self.pdf_path}")
        self._extract_pages()
        self._parse_sections()
        self._loaded = True

        logger.info(
            f"PDF loaded — {len(self._pages)} pages, "
            f"{len(self.sections)} sections detected"
        )

    def _extract_pages(self) -> None:
        """Extract plain text from every page."""
        doc = fitz.open(str(self.pdf_path))
        self._pages = []

        for page in doc:
            text = page.get_text("text")
            self._pages.append(text)

        doc.close()
        logger.info(f"Extracted text from {len(self._pages)} pages")

    def _parse_sections(self) -> None:
        """
        Detect section boundaries using regex.

        Patterns tried (in order):
        1. "Section 1 - Title" or "Section 1: Title"
        2. "1. TITLE" (numbered heading, all-caps)
        3. "1. Title" (numbered heading, mixed case)
        4. "CHAPTER 1" or "PART 1"

        If fewer than 3 sections found → fall back to equal page split.

        ADAPT THIS: If none of the patterns match the actual PDF,
        run this to see what the headings look like:
            python -c "
            import fitz
            doc = fitz.open('data/SLATEFALL_DOSSIER.pdf')
            for i, page in enumerate(doc[:5]):
                print(f'=== PAGE {i+1} ===')
                print(page.get_text())
            "
        Then adjust the patterns below.
        """
        full_text = "\n".join(self._pages)

        # Each pattern: group(1) = section number, group(2) = title
        patterns = [
            # "Section 3 - The PAMC Protocol" or "Section 3: ..."
            r"(?:Section|SECTION)\s+(\d{1,2})\s*[:\-–—]\s*([^\n]{3,80})",
            # "3. OPERATIONAL FRAMEWORK" (all caps, numbered)
            r"^\s*(\d{1,2})\.\s+([A-Z][A-Z0-9 ,\-]{4,60})\s*$",
            # "3. Operational Framework" (title case, numbered)
            r"^\s*(\d{1,2})\.\s+([A-Z][a-zA-Z0-9 ,\-]{4,60})\s*$",
            # "CHAPTER 3" or "PART 3"
            r"(?:CHAPTER|PART)\s+(\d{1,2})\s*[:\-–]?\s*([^\n]{0,60})",
        ]

        # Collect all matches across all patterns
        found: list[tuple[int, str, int]] = []  # (section_num, title, char_pos)

        for pattern in patterns:
            for match in re.finditer(pattern, full_text, re.MULTILINE):
                try:
                    num = int(match.group(1))
                    title = match.group(2).strip() if match.lastindex >= 2 else f"Section {num}"
                    if 1 <= num <= 15:  # Reasonable section range
                        found.append((num, title, match.start()))
                except (ValueError, IndexError):
                    continue

        # Sort by position in document
        found.sort(key=lambda x: x[2])

        # Deduplicate: keep first occurrence of each section number
        seen: set[int] = set()
        unique: list[tuple[int, str, int]] = []
        for num, title, pos in found:
            if num not in seen:
                seen.add(num)
                unique.append((num, title, pos))

        logger.info(f"Section boundaries detected: {[u[0] for u in unique]}")

        if len(unique) < 3:
            logger.warning(
                f"Only {len(unique)} sections detected by regex. "
                f"Using page-based fallback split."
            )
            self._fallback_split()
            return

        # Extract content between detected boundaries
        for i, (num, title, start_pos) in enumerate(unique):
            end_pos = unique[i + 1][2] if i + 1 < len(unique) else len(full_text)
            content = full_text[start_pos:end_pos].strip()

            self.sections[num] = PDFSection(
                section_id = num,
                title      = title,
                content    = content,
                start_page = self._char_to_page(full_text, start_pos),
                end_page   = self._char_to_page(full_text, end_pos),
            )

    def _fallback_split(self) -> None:
        """
        Emergency fallback: split document into 10 equal page chunks.

        Called when regex detection fails.
        Produces sections 1-10 regardless of PDF structure.
        Always works. Questions will still make sense per chunk.
        """
        total = len(self._pages)
        per_section = max(1, total // 10)

        for i in range(10):
            num        = i + 1
            start_page = i * per_section
            end_page   = min(start_page + per_section, total)
            content    = "\n".join(self._pages[start_page:end_page])

            self.sections[num] = PDFSection(
                section_id = num,
                title      = f"Section {num}",
                content    = content,
                start_page = start_page + 1,
                end_page   = end_page,
            )

        logger.info(
            f"Fallback split complete: 10 sections "
            f"({per_section} pages each)"
        )

    def _char_to_page(self, full_text: str, char_pos: int) -> int:
        """Map a character position in full_text to a page number (1-indexed)."""
        cumulative = 0
        for page_num, page_text in enumerate(self._pages):
            cumulative += len(page_text)
            if cumulative >= char_pos:
                return page_num + 1
        return len(self._pages)

    # ── Public API ────────────────────────────────────────────────

    def get_section(self, section_id: int) -> Optional[PDFSection]:
        """Get one section by ID. Returns None if not found."""
        if not self._loaded:
            self.load()
        section = self.sections.get(section_id)
        if section is None:
            available = sorted(self.sections.keys())
            logger.warning(
                f"Section {section_id} not found. "
                f"Available sections: {available}"
            )
        return section

    def get_sections(self, section_ids: list[int]) -> list[PDFSection]:
        """Get multiple sections. Skips IDs that don't exist."""
        if not self._loaded:
            self.load()
        result = []
        for sid in section_ids:
            s = self.get_section(sid)
            if s:
                result.append(s)
        return result

    def get_all_sections(self) -> list[PDFSection]:
        """Return all sections sorted by ID."""
        if not self._loaded:
            self.load()
        return sorted(self.sections.values(), key=lambda s: s.section_id)

    def available_ids(self) -> list[int]:
        """Return sorted list of available section IDs."""
        if not self._loaded:
            self.load()
        return sorted(self.sections.keys())


# ─── Global singleton ─────────────────────────────────────────────
pdf_parser = PDFParser()