"""Data models for BookFlow."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BookMetadata:
    """Represents book metadata extracted internally or enriched externally."""

    title: str = ""
    author: str = ""
    author_last_name: str = ""
    series: Optional[str] = None
    volume: Optional[float] = None
    volume_raw: Optional[str] = None
    isbn: Optional[str] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    subjects: list[str] = field(default_factory=list)
    description: Optional[str] = None
    language: Optional[str] = None
    openlibrary_key: Optional[str] = None
    source: str = "internal"

    @property
    def has_series(self) -> bool:
        """Check if series and volume information is present."""
        return bool(self.series and (self.volume is not None or self.volume_raw))

    @property
    def formatted_volume(self) -> str:
        """Format volume as a two-digit string (e.g. 01, 02) or float if decimal."""
        if self.volume is None:
            if self.volume_raw:
                # Try parsing integer from volume_raw
                digits = "".join(c for c in self.volume_raw if c.isdigit())
                if digits:
                    return f"{int(digits):02d}"
                return self.volume_raw
            return "01"
        if self.volume.is_integer():
            return f"{int(self.volume):02d}"
        return f"{self.volume:04.1f}"

    def is_complete(self) -> bool:
        """Check if minimum required metadata is present."""
        return bool(self.title.strip() and self.author.strip())


@dataclass
class BookFile:
    """Represents an ebook file on disk."""

    path: Path
    extension: str
    file_size_bytes: int
    extracted: Optional[BookMetadata] = None
    from_filename: Optional[BookMetadata] = None
    enriched: Optional[BookMetadata] = None
    final_metadata: Optional[BookMetadata] = None
    proposed_filename: Optional[str] = None
    proposed_relpath: Optional[Path] = None
    status: str = "pending"
    error_message: Optional[str] = None
