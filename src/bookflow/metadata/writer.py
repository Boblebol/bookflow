"""Safe internal metadata writer for EPUB files using atomic writes."""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from bookflow.models import BookMetadata

logger = logging.getLogger(__name__)


class MetadataWriter:
    """Writes updated and enriched metadata into EPUB files safely."""

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

            # Update DC:title
            if metadata.title:
                book.metadata["http://purl.org/dc/elements/1.1/"]["title"] = [(metadata.title, {})]

            # Update DC:creator
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

            # Update DC:subject (tags)
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

            # Update Calibre series in OPF
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
