"""Unit tests for OrganizerEngine."""

from pathlib import Path
from bookflow.organizer.engine import OrganizerEngine, OrganizerOptions
from bookflow.models import BookFile, BookMetadata
from bookflow.metadata.openlibrary import OpenLibraryClient


def test_organizer_plan_and_dry_run(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()

    # Create dummy file
    dummy_file = source_dir / "Bernard.Minier.2020.Le.Commandant.Servaz.T6.La.Vallee.FRENCH.Epub-NoGRP.epub"
    dummy_file.write_text("dummy epub content")

    cache_db = tmp_path / "cache.sqlite"
    ol_client = OpenLibraryClient(cache_path=cache_db, request_delay=0)
    engine = OrganizerEngine(openlibrary_client=ol_client)

    options = OrganizerOptions(
        source_dir=source_dir,
        target_dir=target_dir,
        dry_run=True,
        enrich=False,
        mode="move",
    )

    books = engine.scan_directory(source_dir)
    assert len(books) == 1
    assert books[0].extension == ".epub"

    planned = engine.plan_operations(books, options)
    assert planned[0].proposed_filename == "Bernard Minier - Le Commandant Servaz T06 - La Vallee.epub"
    assert planned[0].proposed_relpath == Path("Bernard Minier/Le Commandant Servaz/Bernard Minier - Le Commandant Servaz T06 - La Vallee.epub")

    result = engine.execute_operations(planned, options)
    assert result.moved_count == 1
    # File should not be physically moved in dry-run
    assert dummy_file.exists()
    assert not (target_dir / planned[0].proposed_relpath).exists()


def test_organizer_real_move(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()

    dummy_file = source_dir / "Alain.Damasio.La.Horde.du.Contrevent.epub"
    dummy_file.write_text("dummy epub content")

    cache_db = tmp_path / "cache.sqlite"
    ol_client = OpenLibraryClient(cache_path=cache_db, request_delay=0)
    engine = OrganizerEngine(openlibrary_client=ol_client)

    options = OrganizerOptions(
        source_dir=source_dir,
        target_dir=target_dir,
        dry_run=False,
        enrich=False,
        mode="move",
    )

    books = engine.scan_directory(source_dir)
    planned = engine.plan_operations(books, options)
    result = engine.execute_operations(planned, options)

    assert result.moved_count == 1
    # Target should exist
    expected_target = target_dir / planned[0].proposed_relpath
    assert expected_target.exists()


def test_organizer_with_metadata_writing(tmp_path):
    import ebooklib
    from ebooklib import epub
    from bookflow.metadata.extractor import MetadataExtractor

    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()

    # Create valid minimal EPUB
    epub_file = source_dir / "Unknown.Book.2021.epub"
    book = epub.EpubBook()
    book.set_identifier("orig-id")
    book.set_title("Raw Bad Title")
    book.set_language("fr")
    book.add_author("Raw Author")
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    c1 = epub.EpubHtml(title="C1", file_name="c1.xhtml", lang="fr")
    c1.content = "<h1>Chapitre 1</h1>"
    book.add_item(c1)
    book.spine = ["nav", c1]
    epub.write_epub(str(epub_file), book)

    engine = OrganizerEngine(openlibrary_client=OpenLibraryClient(cache_path=tmp_path / "c.sqlite", request_delay=0))

    options = OrganizerOptions(
        source_dir=source_dir,
        target_dir=target_dir,
        dry_run=False,
        enrich=False,
        mode="move",
        write_metadata=True,
    )

    books = engine.scan_directory(source_dir)
    # Inject nice metadata into final_metadata
    books[0].final_metadata = BookMetadata(
        title="La Chambre des Merveilles",
        author="Julien Sandrel",
        series="Romans",
        volume=1.0,
        description="Une histoire émouvante d'amour maternel.",
        subjects=["Roman contemporain", "Émotion"],
        isbn="9782253258247",
        year=2018,
        publisher="Calmann-Lévy",
        language="fr",
    )

    planned = engine.plan_operations(books, options)
    result = engine.execute_operations(planned, options)

    assert result.moved_count == 1
    assert result.metadata_written_count == 1

    target_file = target_dir / planned[0].proposed_relpath
    assert target_file.exists()

    # Check internal metadata written in the target file
    extracted = MetadataExtractor.extract(target_file).extracted
    assert extracted is not None
    assert extracted.title == "La Chambre des Merveilles"
    assert extracted.author == "Julien Sandrel"
    assert extracted.series == "Romans"
    assert extracted.volume == 1.0
    assert extracted.description == "Une histoire émouvante d'amour maternel."
    assert extracted.isbn == "9782253258247"
    assert extracted.year == 2018
    assert extracted.publisher == "Calmann-Lévy"
    assert "Roman contemporain" in extracted.subjects

