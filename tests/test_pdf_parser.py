"""Tests for PDF parsing."""
import pytest
from pathlib import Path
from core.pdf_parser import PDFParser, PDFSection


class TestPDFSection:
    def test_word_count_calculated(self):
        s = PDFSection(1, "Test", "one two three four five", 1, 2)
        assert s.word_count == 5

    def test_to_dict_has_required_keys(self):
        s = PDFSection(3, "Title", "content here", 5, 10)
        d = s.to_dict()
        assert "section_id" in d
        assert "title" in d
        assert "word_count" in d
        assert "content_preview" in d


class TestPDFParser:
    def test_missing_pdf_raises_file_not_found(self):
        parser = PDFParser(pdf_path=Path("/does/not/exist.pdf"))
        with pytest.raises(FileNotFoundError):
            parser.load()

    def test_fallback_creates_10_sections(self):
        parser = PDFParser(pdf_path=Path("/fake.pdf"))
        parser._pages = [f"page {i} content text here" for i in range(50)]
        parser._fallback_split()
        assert len(parser.sections) == 10
        assert all(i in parser.sections for i in range(1, 11))

    def test_get_section_returns_none_for_missing_id(self):
        parser = PDFParser(pdf_path=Path("/fake.pdf"))
        parser._pages = ["page"]
        parser._fallback_split()
        parser._loaded = True
        assert parser.get_section(99) is None

    def test_get_sections_skips_invalid_ids(self):
        parser = PDFParser(pdf_path=Path("/fake.pdf"))
        parser._pages = ["page content text here words"] * 30
        parser._fallback_split()
        parser._loaded = True
        result = parser.get_sections([1, 99, 2])
        assert len(result) == 2
        assert all(s.section_id in [1, 2] for s in result)