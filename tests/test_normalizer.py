"""Unit tests for MetadataNormalizer."""

from pathlib import Path

from bookflow.metadata.normalizer import MetadataNormalizer
from bookflow.models import BookMetadata


def test_extract_author_name_modes():
    # Full name (default)
    assert MetadataNormalizer.extract_author_name("Isaac Asimov") == "Isaac Asimov"
    assert MetadataNormalizer.extract_author_name("Bernard Minier") == "Bernard Minier"
    assert MetadataNormalizer.extract_author_name("Jean-Christophe Grangé") == "Jean-Christophe Grangé"
    assert MetadataNormalizer.extract_author_name("Grangé, Jean-Christophe") == "Jean-Christophe Grangé"

    # Last name only
    assert MetadataNormalizer.extract_author_name("Isaac Asimov", format_mode="last") == "Asimov"
    assert MetadataNormalizer.extract_author_name("Bernard Minier", format_mode="last") == "Minier"
    assert MetadataNormalizer.extract_author_name("Jean-Christophe Grangé", format_mode="last") == "Grangé"
    assert MetadataNormalizer.extract_author_name("Jean-Christophe Grangé", format_mode="last", preserve_accents=False) == "Grange"

    # Inverted
    assert MetadataNormalizer.extract_author_name("Isaac Asimov", format_mode="last-first") == "Asimov, Isaac"
    assert MetadataNormalizer.extract_author_name("Isaac Asimov", format_mode="last-first", word_sep="-") == "Asimov-Isaac"


def test_extract_multiple_authors():
    author = "Douglas Preston, Lincoln Child"
    # Default full format with space
    assert MetadataNormalizer.extract_author_name(author) == "Douglas Preston & Lincoln Child"
    # Last name format
    assert MetadataNormalizer.extract_author_name(author, format_mode="last") == "Preston & Child"
    # POSIX style
    assert MetadataNormalizer.extract_author_name(author, format_mode="last", word_sep="-", preserve_accents=False) == "Preston-Child"


def test_extract_author_with_particles_and_initials():
    # Inverted name with initials and without space after comma (e.g. Van Vogt,A. E.)
    assert MetadataNormalizer.extract_author_name("Van Vogt,A. E.") == "A E Van Vogt"
    assert MetadataNormalizer.extract_author_name("Van Vogt,A. E.", format_mode="last") == "Van Vogt"

    # Inverted name with initials and space
    assert MetadataNormalizer.extract_author_name("Van Vogt, A. E.") == "A E Van Vogt"

    # Inverted name with particle and full first name
    assert MetadataNormalizer.extract_author_name("Van Vogt, Alfred Elton") == "Alfred Elton Van Vogt"
    assert MetadataNormalizer.extract_author_name("De Balzac, Honoré") == "Honoré De Balzac"
    assert MetadataNormalizer.extract_author_name("Le Carré, John") == "John Le Carré"



def test_clean_component_strips_noise_and_preserves_accents():
    title = "Tombes oubliées (French Edition)"
    clean_default = MetadataNormalizer.clean_component(title)
    assert clean_default == "Tombes Oubliées"
    assert "Edition" not in clean_default

    clean_no_accents = MetadataNormalizer.clean_component(title, preserve_accents=False, word_sep="-")
    assert clean_no_accents == "Tombes-Oubliees"


def test_clean_component_preserves_french_apostrophes():
    assert MetadataNormalizer.clean_component("l'ultime expérience") == "L'Ultime Expérience"
    assert MetadataNormalizer.clean_component("Des ailes d'argent") == "Des Ailes d'Argent"


def test_generate_filename_with_series():
    meta = BookMetadata(
        title="La Vallée",
        author="Bernard Minier",
        series="Le Commandant Servaz",
        volume=6.0,
    )
    # 1. Standard (Default): Prénom Nom - Série T01 - Titre.epub
    filename = MetadataNormalizer.generate_filename(meta, extension=".epub")
    assert filename == "Bernard Minier - Le Commandant Servaz T06 - La Vallée.epub"

    # 2. Bracket style: Prénom Nom - [Série 01] - Titre.epub
    filename_bracket = MetadataNormalizer.generate_filename(meta, extension=".epub", naming_style="bracket")
    assert filename_bracket == "Bernard Minier - [Le Commandant Servaz 06] - La Vallée.epub"

    # 3. POSIX style: Nom_Série_01_Titre.epub
    filename_posix = MetadataNormalizer.generate_filename(meta, extension=".epub", naming_style="posix")
    assert filename_posix == "Minier_Le-Commandant-Servaz_06_La-Vallee.epub"


def test_generate_filename_without_series():
    meta = BookMetadata(
        title="La Horde du Contrevent",
        author="Alain Damasio",
    )
    # Default standard
    filename = MetadataNormalizer.generate_filename(meta, extension=".epub")
    assert filename == "Alain Damasio - La Horde du Contrevent.epub"

    # POSIX style
    filename_posix = MetadataNormalizer.generate_filename(meta, extension=".epub", naming_style="posix")
    assert filename_posix == "Damasio_La-Horde-du-Contrevent.epub"


def test_generate_filename_strips_repeated_series_in_title():
    meta = BookMetadata(
        title="Sans soleil. Disco inferno",
        author="Jean-Christophe Grangé",
        series="Sans soleil",
        volume=1.0,
    )
    filename = MetadataNormalizer.generate_filename(meta, extension=".epub")
    assert filename == "Jean-Christophe Grangé - Sans Soleil T01 - Disco Inferno.epub"


def test_generate_relpath():
    meta = BookMetadata(
        title="La Vallée",
        author="Bernard Minier",
        series="Le Commandant Servaz",
        volume=6.0,
    )
    # Hierarchical
    relpath = MetadataNormalizer.generate_relpath(
        meta,
        filename="Bernard Minier - Le Commandant Servaz T06 - La Vallée.epub",
        structure="hierarchical",
    )
    assert relpath == Path("Bernard Minier/Le Commandant Servaz/Bernard Minier - Le Commandant Servaz T06 - La Vallée.epub")

    # Flat
    relpath_flat = MetadataNormalizer.generate_relpath(
        meta,
        filename="Bernard Minier - Le Commandant Servaz T06 - La Vallée.epub",
        structure="flat",
    )
    assert relpath_flat == Path("Bernard Minier - Le Commandant Servaz T06 - La Vallée.epub")
