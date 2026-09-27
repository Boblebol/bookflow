"""String normalization, author extraction, and standard book filename generation."""

import re
import unicodedata
from pathlib import Path
from typing import Optional

from slugify import slugify

from bookflow.models import BookMetadata

# Common author suffixes/prefixes to strip or handle
PARTICLES = {"de", "des", "du", "le", "la", "von", "van", "da", "di"}


TITLE_NOISE_PATTERN = re.compile(
    r"(?i)\s*[\(\[]\s*(?:(?:french|english|german|spanish|italian)\s+edition|edition\s+(?:francaise|anglaise)|epub|pdf|ebook|notag|nogrp|scan)\s*[\)\]]",
)


STOP_WORDS = {
    "de", "des", "du", "d", "l", "le", "la", "les", "un", "une", "et", "en",
    "au", "aux", "par", "pour", "sur", "dans", "of", "and", "in", "to", "the", "a", "an",
}


class MetadataNormalizer:
    """Normalizes titles, series, author names and builds standardized filenames."""

    @classmethod
    def strip_accents(cls, text: str) -> str:
        """Strip accents from a string for safe filesystem usage."""
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    @classmethod
    def clean_component(
        cls,
        text: str,
        preserve_accents: bool = False,
        word_sep: str = "-",
    ) -> str:
        """Clean a filename component (title, series, etc.) into safe characters."""
        if not text:
            return ""

        # Strip title noise like (French Edition)
        text = TITLE_NOISE_PATTERN.sub("", text)

        # Normalize special ligatures like œ, æ
        text = text.replace("œ", "oe").replace("Œ", "Oe")
        text = text.replace("æ", "ae").replace("Æ", "Ae")

        # Replace apostrophes and quotation marks with hyphen or space
        text = re.sub(r"['’`]", "-", text)

        # Remove illegal filename chars and parentheses
        text = re.sub(r'[\\/*?:"<>|;~#%&{}()[\]]', " ", text)

        if not preserve_accents:
            text = cls.strip_accents(text)

        # Normalize whitespace into word_sep
        words = [w for w in re.split(r"[\s._-]+", text) if w]
        if not words:
            return "Unknown"

        # Capitalize each word nicely (Title Case with lowercase minor words)
        formatted_words = []
        for i, w in enumerate(words):
            if len(w) == 1 and w.isalpha():
                formatted_words.append(w.upper() if i == 0 else (w.lower() if w.lower() in STOP_WORDS else w.upper()))
            elif i > 0 and w.lower() in STOP_WORDS:
                formatted_words.append(w.lower())
            else:
                formatted_words.append(w.capitalize())

        return word_sep.join(formatted_words)

    @classmethod
    def extract_author_name(
        cls,
        author_raw: str,
        format_mode: str = "last",
        preserve_accents: bool = False,
        word_sep: str = "-",
    ) -> str:
        """Extract and format author name according to chosen format mode.

        Modes:
        - 'last': Last name only (e.g. Asimov, Minier, Grange, Preston-Child)
        - 'full': Full name (e.g. Isaac-Asimov, Bernard-Minier)
        - 'last-first': Inverted name (e.g. Asimov-Isaac)
        """
        if not author_raw or author_raw.strip().lower() in ("unknown", "inconnu", "inconnue", ""):
            return "Inconnu"

        raw = author_raw.strip()

        # Handle conjunction-based multiple authors (e.g. "Douglas Preston & Lincoln Child")
        multi_sep = None
        for sep in [" & ", " et ", " and ", "; "]:
            if sep in raw:
                multi_sep = sep
                break

        # Check if single comma is between two full names (e.g. "Douglas Preston, Lincoln Child")
        if not multi_sep and raw.count(",") == 1:
            p0, p1 = [p.strip() for p in raw.split(",")]
            if len(p0.split()) > 1 and len(p1.split()) > 1:
                multi_sep = ", "

        if multi_sep:
            sub_authors = [cls.extract_author_name(p, format_mode, preserve_accents, word_sep) for p in raw.split(multi_sep)]
            sub_authors = [a for a in sub_authors if a and a != "Inconnu"]
            if len(sub_authors) > 1:
                return f"{sub_authors[0]}-{sub_authors[1]}"

        # Check for inverted "Last, First" format (e.g. "Grangé, Jean-Christophe" or "Minier, Bernard")
        if "," in raw:
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            last_name = parts[0]
            first_name = parts[1] if len(parts) > 1 else ""
        else:
            tokens = [t for t in re.split(r"\s+", raw) if t]
            if len(tokens) == 1:
                last_name = tokens[0]
                first_name = ""
            else:
                # Handle particles like "de", "le", "van"
                if len(tokens) > 2 and tokens[-2].lower() in PARTICLES:
                    last_name = f"{tokens[-2]} {tokens[-1]}"
                    first_name = " ".join(tokens[:-2])
                else:
                    last_name = tokens[-1]
                    first_name = " ".join(tokens[:-1])

        clean_last = cls.clean_component(last_name, preserve_accents, word_sep)
        clean_first = cls.clean_component(first_name, preserve_accents, word_sep) if first_name else ""

        if format_mode == "full" and clean_first:
            return f"{clean_first}{word_sep}{clean_last}"
        elif format_mode == "last-first" and clean_first:
            return f"{clean_last}{word_sep}{clean_first}"
        return clean_last

    @classmethod
    def format_series_and_volume(
        cls,
        series_raw: Optional[str],
        volume: Optional[float] = None,
        volume_raw: Optional[str] = None,
        preserve_accents: bool = False,
        word_sep: str = "-",
    ) -> tuple[Optional[str], Optional[str]]:
        """Clean series name and format volume to two digits."""
        if not series_raw:
            return None, None

        # Clean series name: remove trailing volume numbers if present (e.g. "Sans soleil 2T" -> "Sans soleil")
        clean_series = re.sub(r"(?i)\s*(?:Tome|Vol|T)?\s*\d+\s*(?:T|t)?$", "", series_raw).strip()
        series_clean = cls.clean_component(clean_series, preserve_accents, word_sep)

        # Format volume
        formatted_vol = "01"
        if volume is not None:
            if volume.is_integer():
                formatted_vol = f"{int(volume):02d}"
            else:
                formatted_vol = f"{volume:04.1f}"
        elif volume_raw:
            digits = "".join(c for c in volume_raw if c.isdigit())
            if digits:
                formatted_vol = f"{int(digits):02d}"
            else:
                formatted_vol = volume_raw.strip()

        return series_clean, formatted_vol

    @classmethod
    def generate_filename(
        cls,
        metadata: BookMetadata,
        extension: str = ".epub",
        author_format: str = "last",
        component_sep: str = "_",
        word_sep: str = "-",
        preserve_accents: bool = False,
    ) -> str:
        """Generate standardized filename based on specification.

        Format:
        - With series: NomAuteur_Série_Tome_Titre.epub
        - Without series: NomAuteur_Titre.epub
        """
        # 1. Author
        author = cls.extract_author_name(
            metadata.author,
            format_mode=author_format,
            preserve_accents=preserve_accents,
            word_sep=word_sep,
        )

        # 2. Title
        raw_title = metadata.title or "Livre"
        clean_title = cls.clean_component(raw_title, preserve_accents, word_sep)

        # 3. Series and volume
        series_name, vol_str = cls.format_series_and_volume(
            metadata.series,
            volume=metadata.volume,
            volume_raw=metadata.volume_raw,
            preserve_accents=preserve_accents,
            word_sep=word_sep,
        )

        # Avoid repeating series name in title if title starts with series name
        if series_name and clean_title.lower().startswith(series_name.lower()):
            stripped = clean_title[len(series_name):].lstrip(word_sep)
            if stripped:
                clean_title = stripped

        ext = extension if extension.startswith(".") else f".{extension}"

        if series_name and vol_str:
            filename = f"{author}{component_sep}{series_name}{component_sep}{vol_str}{component_sep}{clean_title}{ext}"
        else:
            filename = f"{author}{component_sep}{clean_title}{ext}"

        # Limit total filename length to 240 chars to respect filesystem limits
        if len(filename) > 240:
            max_title_len = 240 - len(author) - len(ext) - len(component_sep) * 3 - (len(series_name or "") + len(vol_str or ""))
            if max_title_len > 10:
                clean_title = clean_title[:max_title_len].rstrip(word_sep)
                if series_name and vol_str:
                    filename = f"{author}{component_sep}{series_name}{component_sep}{vol_str}{component_sep}{clean_title}{ext}"
                else:
                    filename = f"{author}{component_sep}{clean_title}{ext}"

        return filename

    @classmethod
    def generate_relpath(
        cls,
        metadata: BookMetadata,
        filename: str,
        structure: str = "hierarchical",
        author_format: str = "last",
        word_sep: str = "-",
        preserve_accents: bool = False,
    ) -> Path:
        """Generate relative folder path for organizing.

        Structures:
        - 'hierarchical': Author/Series/filename or Author/filename
        - 'flat': filename directly in destination root
        """
        if structure == "flat":
            return Path(filename)

        author_folder = cls.extract_author_name(
            metadata.author,
            format_mode=author_format,
            preserve_accents=preserve_accents,
            word_sep=word_sep,
        )

        series_name, _ = cls.format_series_and_volume(
            metadata.series,
            volume=metadata.volume,
            volume_raw=metadata.volume_raw,
            preserve_accents=preserve_accents,
            word_sep=word_sep,
        )

        if series_name:
            return Path(author_folder) / series_name / filename
        return Path(author_folder) / filename
