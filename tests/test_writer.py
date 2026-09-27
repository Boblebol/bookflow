"""Unit tests for MetadataWriter EPUB atomic modification."""

from pathlib import Path
import ebooklib
from ebooklib import epub

from bookflow.metadata.writer import MetadataWriter
from bookflow.metadata.extractor import MetadataExtractor
from bookflow.models import BookMetadata


def test_write_and_read_epub_metadata(tmp_path):
    epub_path = tmp_path / "test_book.epub"

    # Create minimal valid EPUB
    book = epub.EpubBook()
    book.set_identifier("test-12345")
    book.set_title("Original Title")
    book.set_language("fr")
    book.add_author("Original Author")
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    c1 = epub.EpubHtml(title="Chapitre 1", file_name="chap_1.xhtml", lang="fr")
    c1.content = "<h1>Chapitre 1</h1><p>Test content.</p>"
    book.add_item(c1)
    book.spine = ["nav", c1]

    epub.write_epub(str(epub_path), book)
    assert epub_path.exists()

    # Update metadata via BookFlow MetadataWriter
    new_meta = BookMetadata(
        title="Nouveau Titre Magnifique",
        author="Victor Hugo",
        series="Les Miserables",
        volume=1.0,
        subjects=["Classique", "Littérature"],
    )

    success = MetadataWriter.write_epub_metadata(epub_path, new_meta)
    assert success is True

    # Read back and verify
    book_file = MetadataExtractor.extract(epub_path)
    extracted = book_file.extracted

    assert extracted is not None
    assert extracted.title == "Nouveau Titre Magnifique"
    assert extracted.author == "Victor Hugo"
    assert extracted.series == "Les Miserables"
    assert extracted.volume == 1.0
    assert "Classique" in extracted.subjects
