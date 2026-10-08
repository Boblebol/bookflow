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
        description="Une fresque sociale grandiose au XIXe siècle.",
        isbn="9782253006275",
        year=1862,
        publisher="Pagnerre",
        language="fr",
    )

    success = MetadataWriter.write_metadata(epub_path, new_meta)
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
    assert extracted.description == "Une fresque sociale grandiose au XIXe siècle."
    assert extracted.isbn == "9782253006275"
    assert extracted.year == 1862
    assert extracted.publisher == "Pagnerre"
    assert extracted.language == "fr"


def test_write_and_read_pdf_metadata(tmp_path):
    import pypdf

    pdf_path = tmp_path / "test_doc.pdf"

    # Create minimal valid PDF
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    meta = BookMetadata(
        title="Le Grand Meaulnes",
        author="Alain-Fournier",
        series="Romans Français",
        volume=1.0,
        description="Un roman initiatique mystérieux et poétique.",
        subjects=["Roman", "Classique"],
        publisher="Éditions Émile-Paul Frères",
    )

    success = MetadataWriter.write_metadata(pdf_path, meta)
    assert success is True

    # Verify with pypdf
    reader = pypdf.PdfReader(str(pdf_path))
    pdf_info = reader.metadata
    assert pdf_info is not None
    assert pdf_info.get("/Title") == "Le Grand Meaulnes"
    assert pdf_info.get("/Author") == "Alain-Fournier"
    assert pdf_info.get("/Subject") == "Un roman initiatique mystérieux et poétique."
    assert "Roman" in pdf_info.get("/Keywords", "")
    assert pdf_info.get("/Producer") == "Éditions Émile-Paul Frères"

    # Verify with MetadataExtractor
    extracted_file = MetadataExtractor.extract(pdf_path)
    assert extracted_file.extracted is not None
    assert extracted_file.extracted.title == "Le Grand Meaulnes"
    assert extracted_file.extracted.author == "Alain-Fournier"

