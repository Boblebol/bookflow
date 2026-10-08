"""Safe internal metadata writer for EPUB and PDF files using atomic writes."""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from bookflow.models import BookMetadata

logger = logging.getLogger(__name__)


class MetadataWriter:
    """Writes updated and enriched metadata into EPUB and PDF files safely."""

    @classmethod
    def write_metadata(cls, file_path: Path, metadata: BookMetadata) -> bool:
        """Dispatch metadata writing based on file format (EPUB or PDF)."""
        ext = file_path.suffix.lower()
        if ext == ".epub":
            return cls.write_epub_metadata(file_path, metadata)
        elif ext == ".pdf":
            return cls.write_pdf_metadata(file_path, metadata)
        return False

    @classmethod
    def write_epub_metadata(cls, epub_path: Path, metadata: BookMetadata) -> bool:
        """Update Dublin Core and OPF metadata inside an EPUB file."""
        if not epub_path.exists() or epub_path.suffix.lower() != ".epub":
            return False

        try:
            import ebooklib
            from ebooklib import epub

            # Read book
            book = epub.read_epub(str(epub_path))

            # 1. Update DC:title
            if metadata.title:
                book.metadata["http://purl.org/dc/elements/1.1/"]["title"] = [(metadata.title, {})]

            # 2. Update DC:creator (Author)
            if metadata.author:
                file_as = metadata.author
                if " " in metadata.author:
                    parts = metadata.author.split()
                    file_as = f"{parts[-1]}, {' '.join(parts[:-1])}"
                book.metadata["http://purl.org/dc/elements/1.1/"]["creator"] = [
                    (
                        metadata.author,
                        {
                            "{http://www.idpf.org/2007/opf}file-as": file_as,
                            "{http://www.idpf.org/2007/opf}role": "aut",
                        },
                    )
                ]

            # 3. Update DC:description
            if metadata.description:
                book.metadata["http://purl.org/dc/elements/1.1/"]["description"] = [(metadata.description, {})]

            # 4. Update DC:identifier (ISBN)
            if metadata.isbn:
                clean_isbn = metadata.isbn.replace("-", "").strip()
                existing_ids = book.metadata.get("http://purl.org/dc/elements/1.1/", {}).get("identifier", [])
                clean_ids = [
                    (val, attrs)
                    for val, attrs in existing_ids
                    if attrs.get("{http://www.idpf.org/2007/opf}scheme", "").upper() != "ISBN"
                    and attrs.get("id") != "isbn"
                ]
                clean_ids.append(
                    (
                        clean_isbn,
                        {
                            "{http://www.idpf.org/2007/opf}scheme": "ISBN",
                            "id": "isbn",
                        },
                    )
                )
                book.metadata["http://purl.org/dc/elements/1.1/"]["identifier"] = clean_ids

            # 5. Update DC:publisher
            if metadata.publisher:
                book.metadata["http://purl.org/dc/elements/1.1/"]["publisher"] = [(metadata.publisher, {})]

            # 6. Update DC:date (Year)
            if metadata.year:
                book.metadata["http://purl.org/dc/elements/1.1/"]["date"] = [(str(metadata.year), {})]

            # 7. Update DC:language
            if metadata.language:
                book.metadata["http://purl.org/dc/elements/1.1/"]["language"] = [(metadata.language, {})]

            # 8. Update DC:subject (tags)
            if metadata.subjects:
                existing_subjects = [
                    s[0]
                    for s in book.metadata.get("http://purl.org/dc/elements/1.1/", {}).get("subject", [])
                ]
                all_subjects = list(existing_subjects)
                for s in metadata.subjects:
                    if s not in all_subjects:
                        all_subjects.append(s)
                book.metadata["http://purl.org/dc/elements/1.1/"]["subject"] = [
                    (s, {}) for s in all_subjects
                ]

            # 9. Update Calibre series in OPF
            if metadata.series:
                opf_ns = "http://www.idpf.org/2007/opf"
                if opf_ns not in book.metadata:
                    book.metadata[opf_ns] = {}
                meta_list = book.metadata[opf_ns].get("meta", [])

                # Filter out existing calibre series entries
                clean_meta = [
                    item
                    for item in meta_list
                    if item[1].get("name") not in ("calibre:series", "calibre:series_index")
                ]

                # Add series
                clean_meta.append((None, {"name": "calibre:series", "content": metadata.series}))
                if metadata.volume is not None:
                    clean_meta.append(
                        (None, {"name": "calibre:series_index", "content": str(int(metadata.volume))})
                    )
                elif metadata.volume_raw:
                    clean_meta.append(
                        (None, {"name": "calibre:series_index", "content": metadata.volume_raw})
                    )

                book.metadata[opf_ns]["meta"] = clean_meta

            # Atomic write to temporary file in same directory
            temp_dir = epub_path.parent
            with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False, suffix=".epub") as tmp:
                temp_path = Path(tmp.name)

            epub.write_epub(str(temp_path), book)

            # Check size to ensure write was successful
            if temp_path.exists() and temp_path.stat().st_size > 1024:
                # Replace original file atomically
                temp_path.replace(epub_path)
                return True
            else:
                if temp_path.exists():
                    temp_path.unlink()
                return False

        except Exception as e:
            logger.error("Failed to write metadata to %s: %s", epub_path, e)
            return False

    @classmethod
    def write_pdf_metadata(cls, pdf_path: Path, metadata: BookMetadata) -> bool:
        """Update standard Document Information dictionary in a PDF file."""
        if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
            return False

        try:
            import pypdf

            reader = pypdf.PdfReader(str(pdf_path))
            writer = pypdf.PdfWriter()
            writer.append(reader)

            pdf_meta: dict[str, str] = {}
            if metadata.title:
                pdf_meta["/Title"] = metadata.title
            if metadata.author:
                pdf_meta["/Author"] = metadata.author
            if metadata.description:
                pdf_meta["/Subject"] = metadata.description
            elif metadata.series:
                series_info = metadata.series
                if metadata.volume is not None:
                    series_info += f" T{int(metadata.volume):02d}"
                pdf_meta["/Subject"] = series_info

            if metadata.subjects:
                pdf_meta["/Keywords"] = ", ".join(metadata.subjects)
            if metadata.publisher:
                pdf_meta["/Producer"] = metadata.publisher
            else:
                pdf_meta["/Producer"] = "BookFlow Studio"

            writer.add_metadata(pdf_meta)

            temp_dir = pdf_path.parent
            with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False, suffix=".pdf") as tmp:
                temp_path = Path(tmp.name)

            with open(temp_path, "wb") as f:
                writer.write(f)

            if temp_path.exists() and temp_path.stat().st_size > 512:
                temp_path.replace(pdf_path)
                return True
            else:
                if temp_path.exists():
                    temp_path.unlink()
                return False

        except Exception as e:
            logger.error("Failed to write PDF metadata to %s: %s", pdf_path, e)
            return False

