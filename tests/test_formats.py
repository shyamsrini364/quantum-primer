from ebooklib import epub
from pypdf import PdfWriter

from quantum_primer.ingest import sections


def test_pdf_location_is_physical_page(tmp_path):
    path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.write(path)
    assert list(sections(path)) == [("PDF page 1", "")]


def test_epub_uses_spine_and_section_heading(tmp_path):
    path = tmp_path / "sample.epub"
    book = epub.EpubBook()
    book.set_identifier("test")
    book.set_title("Test")
    book.set_language("en")
    chapter = epub.EpubHtml(title="Chapter", file_name="chapter.xhtml", lang="en")
    chapter.content = "<h1>Introduction</h1><p>Some source text.</p>"
    book.add_item(chapter)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [chapter]
    epub.write_epub(str(path), book)
    result = list(sections(path))
    assert result[0][0] == "EPUB section: Introduction"
    assert "Some source text." in result[0][1]
