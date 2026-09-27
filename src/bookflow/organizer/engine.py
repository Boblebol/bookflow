"""Orchestration engine for auditing, planning, enriching, and organizing book files."""

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from bookflow.metadata.extractor import MetadataExtractor
from bookflow.metadata.normalizer import MetadataNormalizer
from bookflow.metadata.openlibrary import OpenLibraryClient
from bookflow.metadata.writer import MetadataWriter
from bookflow.models import BookFile, BookMetadata

logger = logging.getLogger(__name__)


@dataclass
class OrganizerOptions:
    """Options governing organization workflow."""

    source_dir: Path
    target_dir: Optional[Path] = None
    dry_run: bool = True
    mode: str = "move"  # 'move' or 'copy'
    enrich: bool = True
    write_metadata: bool = False
    structure: str = "hierarchical"  # 'hierarchical' or 'flat'
    author_format: str = "last"  # 'last', 'full', 'last-first'
    preserve_accents: bool = False
    component_sep: str = "_"
    word_sep: str = "-"


@dataclass
class OrganizerResult:
    """Summary of operations performed."""

    total_scanned: int = 0
    epubs_count: int = 0
    pdfs_count: int = 0
    series_detected: int = 0
    enriched_count: int = 0
    moved_count: int = 0
    copied_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    books: list[BookFile] = field(default_factory=list)


class OrganizerEngine:
    """Core engine for BookFlow file organization."""

    def __init__(self, openlibrary_client: Optional[OpenLibraryClient] = None):
        self.ol_client = openlibrary_client or OpenLibraryClient()

    def scan_directory(self, source_dir: Path) -> list[BookFile]:
        """Scan directory recursively for EPUB and PDF files."""
        books: list[BookFile] = []
        if not source_dir.exists():
            return books

        for file_path in source_dir.rglob("*"):
            # Skip hidden files, system files, or macOS metadata
            if file_path.name.startswith("._") or file_path.name.startswith("."):
                continue
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()
            if ext not in (".epub", ".pdf"):
                continue

            # Extract basic metadata
            book = MetadataExtractor.extract(file_path)
            books.append(book)

        return books

    def plan_operations(
        self,
        books: list[BookFile],
        options: OrganizerOptions,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[BookFile]:
        """Compute enriched metadata, proposed filenames and destination paths."""
        target_root = options.target_dir or options.source_dir
        used_target_paths: set[Path] = set()

        total = len(books)
        for idx, book in enumerate(books):
            if progress_callback:
                progress_callback(idx + 1, total, book.path.name)

            meta = book.final_metadata or BookMetadata(title=book.path.stem, author="Unknown")

            # Enrich via Open Library if enabled and metadata lacks details or confidence
            if options.enrich:
                try:
                    enriched_meta = self.ol_client.enrich_metadata(meta)
                    book.enriched = enriched_meta
                    book.final_metadata = enriched_meta
                    meta = enriched_meta
                except Exception as e:
                    logger.debug("Enrichment skipped for %s: %s", book.path.name, e)

            # Generate standardized filename
            filename = MetadataNormalizer.generate_filename(
                metadata=meta,
                extension=book.extension,
                author_format=options.author_format,
                component_sep=options.component_sep,
                word_sep=options.word_sep,
                preserve_accents=options.preserve_accents,
            )
            book.proposed_filename = filename

            # Generate relative destination path
            relpath = MetadataNormalizer.generate_relpath(
                metadata=meta,
                filename=filename,
                structure=options.structure,
                author_format=options.author_format,
                word_sep=options.word_sep,
                preserve_accents=options.preserve_accents,
            )
            book.proposed_relpath = relpath

            # Handle filename collisions
            target_path = target_root / relpath
            if target_path in used_target_paths or (target_path.exists() and target_path != book.path):
                counter = 1
                base_stem = target_path.stem
                while True:
                    candidate_name = f"{base_stem}_{counter}{book.extension}"
                    candidate_path = target_path.parent / candidate_name
                    if candidate_path not in used_target_paths and (not candidate_path.exists() or candidate_path == book.path):
                        target_path = candidate_path
                        book.proposed_filename = candidate_name
                        book.proposed_relpath = relpath.parent / candidate_name
                        break
                    counter += 1

            used_target_paths.add(target_path)
            book.status = "ready"

        return books

    def execute_operations(
        self,
        books: list[BookFile],
        options: OrganizerOptions,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> OrganizerResult:
        """Execute plan: move/copy files and optionally write metadata."""
        target_root = options.target_dir or options.source_dir
        res = OrganizerResult(total_scanned=len(books), books=books)

        for b in books:
            if b.extension == ".epub":
                res.epubs_count += 1
            elif b.extension == ".pdf":
                res.pdfs_count += 1
            if b.final_metadata and b.final_metadata.series:
                res.series_detected += 1
            if b.enriched:
                res.enriched_count += 1

        total = len(books)
        for idx, book in enumerate(books):
            if progress_callback:
                progress_callback(idx + 1, total, book.proposed_filename or book.path.name)

            if not book.proposed_relpath:
                res.skipped_count += 1
                continue

            target_path = target_root / book.proposed_relpath

            # Check if source and target are identical
            if book.path.resolve() == target_path.resolve():
                book.status = "skipped_identical"
                res.skipped_count += 1
                continue

            if options.dry_run:
                # Simulation mode: nothing modified
                book.status = "dry_run_ready"
                if options.mode == "copy":
                    res.copied_count += 1
                else:
                    res.moved_count += 1
                continue

            # Real execution
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Write metadata into EPUB first if requested
                if options.write_metadata and book.extension == ".epub" and book.final_metadata:
                    MetadataWriter.write_epub_metadata(book.path, book.final_metadata)

                if options.mode == "copy":
                    shutil.copy2(str(book.path), str(target_path))
                    book.status = "copied"
                    res.copied_count += 1
                else:
                    shutil.move(str(book.path), str(target_path))
                    book.status = "moved"
                    res.moved_count += 1

            except Exception as e:
                book.status = "error"
                book.error_message = str(e)
                res.error_count += 1
                logger.error("Error organizing %s -> %s: %s", book.path, target_path, e)

        return res
