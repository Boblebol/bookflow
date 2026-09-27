"""Metadata extractor for EPUB and PDF files with filename fallback and merging."""

import logging
import warnings
from pathlib import Path
from typing import Optional

from bookflow.metadata.filename_parser import FilenameParser
from bookflow.models import BookFile, BookMetadata

# Suppress ebooklib XML warnings
warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib")
logging.getLogger("ebooklib").setLevel(logging.ERROR)


class MetadataExtractor:
    """Extracts internal metadata from EPUB and PDF files."""

    @classmethod
    def extract(cls, file_path: str | Path) -> BookFile:
        """Extract metadata from an ebook file and combine with filename heuristics."""
        path = Path(file_path).resolve()
        ext = path.suffix.lower()
        size = path.stat().st_size if path.exists() else 0

        book_file = BookFile(
            path=path,
            extension=ext,
            file_size_bytes=size,
        )

        parent_dir = path.parent.name
        from_filename = FilenameParser.parse(path.name, parent_dir=parent_dir)
        book_file.from_filename = from_filename

        extracted: Optional[BookMetadata] = None
        if ext == ".epub":
            extracted = cls._extract_epub(path)
        elif ext == ".pdf":
            extracted = cls._extract_pdf(path)

        book_file.extracted = extracted
        book_file.final_metadata = cls.merge(extracted, from_filename)
        return book_file

    @classmethod
    def _extract_epub(cls, path: Path) -> Optional[BookMetadata]:
        """Read Dublin Core and OPF metadata from an EPUB file."""
        try:
            import ebooklib
            from ebooklib import epub

            book = epub.read_epub(str(path), options={"ignore_ncx": True})

            # 1. Title
            titles = book.get_metadata("DC", "title")
            title = titles[0][0].strip() if titles and titles[0][0] else ""

            # 2. Author / Creator
            creators = book.get_metadata("DC", "creator")
            author = ""
            author_last_name = ""
            if creators and creators[0][0]:
                author = creators[0][0].strip()
                # Check for file-as attribute
                attrs = creators[0][1] if len(creators[0]) > 1 else {}
                file_as = attrs.get("{http://www.idpf.org/2007/opf}file-as", "")
                if file_as and "," in file_as:
                    author_last_name = file_as.split(",")[0].strip()

            # 3. Identifiers (ISBN, etc.)
            identifiers = book.get_metadata("DC", "identifier")
            isbn = None
            if identifiers:
                for ident, attrs in identifiers:
                    if not ident:
                        continue
                    scheme = attrs.get("{http://www.idpf.org/2007/opf}scheme", "").upper()
                    clean_id = ident.strip().replace("-", "")
                    if scheme == "ISBN" or (clean_id.isdigit() and len(clean_id) in (10, 13)):
                        isbn = clean_id
                        break

            # 4. Subjects (Genres / Tags)
            subjects_raw = book.get_metadata("DC", "subject")
            subjects = [s[0].strip() for s in subjects_raw if s and s[0] and s[0].strip()]

            # 5. Date / Year
            dates = book.get_metadata("DC", "date")
            year = None
            if dates and dates[0][0]:
                date_str = str(dates[0][0])[:4]
                if date_str.isdigit():
                    year = int(date_str)

            # 6. Publisher
            publishers = book.get_metadata("DC", "publisher")
            publisher = publishers[0][0].strip() if publishers and publishers[0][0] else None

            # 7. Language
            languages = book.get_metadata("DC", "language")
            language = languages[0][0].strip() if languages and languages[0][0] else None

            # 8. Description
            descriptions = book.get_metadata("DC", "description")
            description = descriptions[0][0].strip() if descriptions and descriptions[0][0] else None

            # 9. Series from Calibre OPF or EPUB3 collection
            series = None
            volume = None
            volume_raw = None

            opf_meta = book.metadata.get("http://www.idpf.org/2007/opf", {}).get("meta", [])
            for item in opf_meta:
                val, attrs = item
                name = attrs.get("name", "")
                content = attrs.get("content", "")
                prop = attrs.get("property", "")

                if name == "calibre:series" and content:
                    series = content.strip()
                elif name == "calibre:series_index" and content:
                    try:
                        volume = float(content.strip())
                        volume_raw = content.strip()
                    except ValueError:
                        volume_raw = content.strip()
                elif prop == "belongs-to-collection" and val:
                    series = str(val).strip()
                elif prop == "group-position" and val:
                    try:
                        volume = float(str(val).strip())
                        volume_raw = str(val).strip()
                    except ValueError:
                        volume_raw = str(val).strip()

            return BookMetadata(
                title=title,
                author=author,
                author_last_name=author_last_name,
                series=series,
                volume=volume,
                volume_raw=volume_raw,
                isbn=isbn,
                year=year,
                publisher=publisher,
                subjects=subjects,
                description=description,
                language=language,
                source="internal",
            )
        except Exception:
            return None

    @classmethod
    def _extract_pdf(cls, path: Path) -> Optional[BookMetadata]:
        """Read basic metadata from a PDF file using pypdf."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            meta = reader.metadata
            if not meta:
                return None

            title = meta.title or ""
            author = meta.author or ""
            subject = meta.subject or ""
            subjects = [subject.strip()] if subject else []

            year = None
            if meta.creation_date:
                try:
                    year = meta.creation_date.year
                except Exception:
                    pass

            return BookMetadata(
                title=title.strip(),
                author=author.strip(),
                subjects=subjects,
                year=year,
                source="internal",
            )
        except Exception:
            return None

    @classmethod
    def merge(cls, internal: Optional[BookMetadata], filename: Optional[BookMetadata]) -> BookMetadata:
        """Merge internal metadata with filename parsed metadata, choosing highest quality fields."""
        if not internal and not filename:
            return BookMetadata(title="Unknown", author="Unknown", source="fallback")
        if not internal:
            res = filename
            res.source = "filename"
            return res
        if not filename:
            res = internal
            res.source = "internal"
            return res

        # Prefer internal title unless empty or looks like raw filename
        title = internal.title.strip()
        if not title or title.lower().endswith(".epub") or len(title) < 2:
            title = filename.title or title

        # Author
        author = internal.author.strip()
        if not author or author.lower() in ("unknown", "inconnu", "inconnue"):
            author = filename.author or author

        author_last_name = internal.author_last_name
        if not author_last_name and author:
            # Will be computed by Normalizer
            pass

        # Series & volume: if missing internally, fallback to filename
        series = internal.series or filename.series
        volume = internal.volume if internal.volume is not None else filename.volume
        volume_raw = internal.volume_raw or filename.volume_raw

        # Year
        year = internal.year or filename.year

        # Combined subjects
        subjects = list(internal.subjects)

        return BookMetadata(
            title=title,
            author=author,
            author_last_name=author_last_name,
            series=series,
            volume=volume,
            volume_raw=volume_raw,
            isbn=internal.isbn,
            year=year,
            publisher=internal.publisher,
            subjects=subjects,
            description=internal.description,
            language=internal.language,
            openlibrary_key=internal.openlibrary_key,
            source="merged",
        )
