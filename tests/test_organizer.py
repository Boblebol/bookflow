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
    # Original should be gone
    assert not dummy_file.exists()
    # Target should exist
    expected_target = target_dir / planned[0].proposed_relpath
    assert expected_target.exists()
