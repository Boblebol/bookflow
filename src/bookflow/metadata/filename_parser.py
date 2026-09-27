"""Heuristic and regex parser for book filenames, especially scene and dirty release names."""

import re
from pathlib import Path
from typing import Optional

from bookflow.models import BookMetadata

# Regex to detect release tags at the end of filenames
TAGS_PATTERN = re.compile(
    r"""(?i)
    [\s._-]*(?:
        FRENCH|FR|TRUEFRENCH|VOSTFR|MULTI|ENGLISH|ENG|
        EPUB(?:-NoGRP|-NoTag|-NoTaG|-TFA|-KFT)?|
        PDF|EBOOK|MOBI|AZW3|
        NoGRP|NoTag|NoTaG
    )\b.*$
    """,
    re.VERBOSE,
)

# Regex to detect volume / tome markers
VOLUME_PATTERN = re.compile(
    r"(?i)\b(?:Tome|Vol(?:ume)?|T)[\s._-]*(\d+(?:\.\d+)?)|#(\d+(?:\.\d+)?)",
)

# Year pattern
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")


class FilenameParser:
    """Parses raw, messy, or scene-style filenames to extract metadata."""

    @classmethod
    def clean_raw_string(cls, raw: str) -> str:
        """Clean string by removing tags and replacing dot-separators."""
        stem = Path(raw).stem

        # Strip scene release tags
        cleaned = TAGS_PATTERN.sub("", stem)

        # Replace dots with spaces if it's dot-delimited (e.g. Bernard.Minier.2020)
        # Avoid breaking initials like A.E. Van Vogt or J.K. Rowling
        # If dot is surrounded by non-space words of length > 1, replace with space
        cleaned = re.sub(r"(?<=\w{2})\.(?=\w)", " ", cleaned)
        cleaned = re.sub(r"(?<=\w)\.(?=\w{2})", " ", cleaned)

        # Remove stray punctuation artifacts
        cleaned = re.sub(r"[_\s]+", " ", cleaned).strip()
        return cleaned

    @classmethod
    def parse(cls, filepath_or_name: str | Path, parent_dir: Optional[str] = None) -> BookMetadata:
        """Parse filename and return candidate BookMetadata."""
        path = Path(filepath_or_name)
        stem = path.stem
        raw_clean = cls.clean_raw_string(stem)

        # Extract year if present
        year = None
        year_match = YEAR_PATTERN.search(raw_clean)
        if year_match:
            year = int(year_match.group(1))

        # Check for volume / tome marker
        volume = None
        volume_raw = None
        vol_match = VOLUME_PATTERN.search(raw_clean)
        if vol_match:
            valid_groups = [g for g in vol_match.groups() if g is not None]
            vol_str = valid_groups[0] if valid_groups else None
            volume_raw = vol_str
            if vol_str:
                try:
                    volume = float(vol_str)
                except ValueError:
                    pass

        # Try structured separator splits: " - "
        if " - " in stem:
            parts = [p.strip() for p in stem.split(" - ") if p.strip()]
            if len(parts) == 2:
                # E.g. "La Horde du Contrevent - Alain Damasio"
                # Or "Blacke Pierce - Un mystere Adele Sharp T2 Condamne a fuir"
                first, second = parts[0], parts[1]
                # If second is an author-like name or first is author-like
                # Let's inspect volume in second part
                vol_in_second = VOLUME_PATTERN.search(second)
                if vol_in_second:
                    author = cls.clean_raw_string(first)
                    rest = cls.clean_raw_string(second)
                    # Split rest into series, tome, title
                    series, title = cls._split_series_and_title(rest, vol_in_second)
                    return BookMetadata(
                        title=title,
                        author=author,
                        series=series,
                        volume=volume,
                        volume_raw=volume_raw,
                        year=year,
                        source="filename",
                    )
                # Standard Title - Author or Author - Title
                # Usually: Title - Author
                # If first has words like "T1", "Tome 1"
                if VOLUME_PATTERN.search(first):
                    series_name = parent_dir or ""
                    return BookMetadata(
                        title=cls.clean_raw_string(second),
                        author=series_name,
                        volume=volume,
                        volume_raw=volume_raw,
                        source="filename",
                    )
                return BookMetadata(
                    title=cls.clean_raw_string(first),
                    author=cls.clean_raw_string(second),
                    year=year,
                    source="filename",
                )

        # Standalone "T1 Title" e.g. "T1 Disco inferno"
        standalone_tome = re.match(r"(?i)^(?:tome|t)[\s._-]*(\d+)\s+(.+)$", raw_clean)
        if standalone_tome:
            vol_num = int(standalone_tome.group(1))
            title = standalone_tome.group(2).strip()
            # If parent dir has series info (e.g. "Sans soleil 2T")
            series = None
            if parent_dir:
                clean_parent = re.sub(r"(?i)\s*\d+T.*$", "", parent_dir).strip()
                if clean_parent and clean_parent != "books":
                    series = clean_parent
            return BookMetadata(
                title=title,
                series=series,
                volume=float(vol_num),
                volume_raw=str(vol_num),
                source="filename",
            )

        # Scene pattern with dots / spaces and embedded year & tome
        # E.g. "Bernard Minier 2020 Le Commandant Servaz T6 La Vallee"
        if vol_match and year_match:
            # Everything before year: author
            year_start = year_match.start()
            author_candidate = raw_clean[:year_start].strip(" ._-")

            # Everything between year and volume: series
            vol_start = vol_match.start()
            vol_end = vol_match.end()
            series_candidate = raw_clean[year_match.end():vol_start].strip(" ._-")

            # Everything after volume: title
            title_candidate = raw_clean[vol_end:].strip(" ._-")
            # Strip trailing tags if any
            title_candidate = TAGS_PATTERN.sub("", title_candidate).strip(" ._-")

            if author_candidate and title_candidate:
                return BookMetadata(
                    title=title_candidate,
                    author=author_candidate,
                    series=series_candidate if series_candidate else None,
                    volume=volume,
                    volume_raw=volume_raw,
                    year=year,
                    source="filename",
                )

        # Fallback: simple cleanup of the stem
        clean_title = cls.clean_raw_string(stem)
        return BookMetadata(
            title=clean_title,
            volume=volume,
            volume_raw=volume_raw,
            year=year,
            source="filename",
        )

    @classmethod
    def _split_series_and_title(cls, text: str, vol_match: re.Match) -> tuple[Optional[str], str]:
        """Split a string like 'Un mystere Adele Sharp T2 Condamne a fuir'."""
        series_part = text[: vol_match.start()].strip(" ._-")
        title_part = text[vol_match.end():].strip(" ._-")
        title_part = TAGS_PATTERN.sub("", title_part).strip(" ._-")
        return (series_part if series_part else None, title_part if title_part else text)
