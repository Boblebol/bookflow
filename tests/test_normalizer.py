"""Unit tests for MetadataNormalizer."""

from pathlib import Path

from bookflow.metadata.normalizer import MetadataNormalizer
from bookflow.models import BookMetadata


def test_extract_author_name_modes():
    # Last name only (default)
    assert MetadataNormalizer.extract_author_name("Isaac Asimov") == "Asimov"
    assert MetadataNormalizer.extract_author_name("Bernard Minier") == "Minier"
    assert MetadataNormalizer.extract_author_name("Jean-Christophe Grangé") == "Grange"
    assert MetadataNormalizer.extract_author_name("Grangé, Jean-Christophe") == "Grange"

    # Full name
    assert MetadataNormalizer.extract_author_name("Isaac Asimov", format_mode="full") == "Isaac-Asimov"

    # Inverted
    assert MetadataNormalizer.extract_author_name("Isaac Asimov", format_mode="last-first") == "Asimov-Isaac"


def test_extract_multiple_authors():
    author = "Douglas Preston, Lincoln Child"
    assert MetadataNormalizer.extract_author_name(author) == "Preston-Child"


def test_clean_component_strips_noise():
    title = "Tombes oubliées (French Edition)"
    clean = MetadataNormalizer.clean_component(title)
    assert clean == "Tombes-Oubliees"
    assert "Edition" not in clean


def test_generate_filename_with_series():
    meta = BookMetadata(
        title="La Vallée",
        author="Bernard Minier",
        series="Le Commandant Servaz",
        volume=6.0,
    )
    filename = MetadataNormalizer.generate_filename(meta, extension=".epub")
    assert filename == "Minier_Le-Commandant-Servaz_06_La-Vallee.epub"


def test_generate_filename_without_series():
    meta = BookMetadata(
        title="La Horde du Contrevent",
        author="Alain Damasio",
    )
    filename = MetadataNormalizer.generate_filename(meta, extension=".epub")
    assert filename == "Damasio_La-Horde-du-Contrevent.epub"


def test_generate_filename_strips_repeated_series_in_title():
    meta = BookMetadata(
        title="Sans soleil. Disco inferno",
        author="Jean-Christophe Grangé",
        series="Sans soleil",
        volume=1.0,
    )
    filename = MetadataNormalizer.generate_filename(meta, extension=".epub")
    assert filename == "Grange_Sans-Soleil_01_Disco-Inferno.epub"


def test_generate_relpath():
    meta = BookMetadata(
        title="La Vallée",
        author="Bernard Minier",
        series="Le Commandant Servaz",
        volume=6.0,
    )
    relpath = MetadataNormalizer.generate_relpath(
        meta,
        filename="Minier_Le-Commandant-Servaz_06_La-Vallee.epub",
        structure="hierarchical",
    )
    assert relpath == Path("Minier/Le-Commandant-Servaz/Minier_Le-Commandant-Servaz_06_La-Vallee.epub")
