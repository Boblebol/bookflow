"""Unit tests for FilenameParser."""

from bookflow.metadata.filename_parser import FilenameParser


def test_parse_scene_release_with_series_and_tome():
    name = "Bernard.Minier.2020.Le.Commandant.Servaz.T6.La.Vallee.FRENCH.Epub-NoGRP.epub"
    meta = FilenameParser.parse(name)

    assert meta.author == "Bernard Minier"
    assert meta.series == "Le Commandant Servaz"
    assert meta.volume == 6.0
    assert meta.volume_raw == "6"
    assert meta.title == "La Vallee"
    assert meta.year == 2020


def test_parse_scene_release_two_digit_tome():
    name = "Douglas.Preston.Lincoln.Child.2020.Nora.Kelly.T01.Tombes.Oubliees.FRENCH.EPUB-NoTag.epub"
    meta = FilenameParser.parse(name)

    assert "Preston" in meta.author
    assert meta.series == "Nora Kelly"
    assert meta.volume == 1.0
    assert meta.volume_raw == "01"
    assert meta.title == "Tombes Oubliees"
    assert meta.year == 2020


def test_parse_title_author_hyphen():
    name = "La Horde du Contrevent - Alain Damasio.epub"
    meta = FilenameParser.parse(name)

    assert meta.title == "La Horde du Contrevent"
    assert meta.author == "Alain Damasio"


def test_parse_author_series_hyphen():
    name = "Blacke Pierce - Un mystere Adele Sharp T2 Condamne a fuir.epub"
    meta = FilenameParser.parse(name)

    assert meta.author == "Blacke Pierce"
    assert meta.series == "Un mystere Adele Sharp"
    assert meta.volume == 2.0
    assert meta.title == "Condamne a fuir"


def test_parse_standalone_tome_with_parent():
    name = "T1 Disco inferno.epub"
    meta = FilenameParser.parse(name, parent_dir="Sans soleil 2T")

    assert meta.title == "Disco inferno"
    assert meta.series == "Sans soleil"
    assert meta.volume == 1.0
    assert meta.formatted_volume == "01"


def test_parse_three_part_standard_naming():
    name = "Bernard Minier - Le Commandant Servaz T06 - La Vallée.epub"
    meta = FilenameParser.parse(name)

    assert meta.author == "Bernard Minier"
    assert meta.series == "Le Commandant Servaz"
    assert meta.volume == 6.0
    assert meta.volume_raw == "06"
    assert meta.title == "La Vallée"


def test_parse_three_part_bracket_naming():
    name = "Bernard Minier - [Le Commandant Servaz 06] - La Vallée.epub"
    meta = FilenameParser.parse(name)

    assert meta.author == "Bernard Minier"
    assert meta.series == "Le Commandant Servaz"
    assert meta.volume == 6.0
    assert meta.volume_raw == "06"
    assert meta.title == "La Vallée"

