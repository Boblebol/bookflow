"""BookFlow CLI - Beautiful terminal interface powered by Typer and Rich."""

from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from bookflow import __version__
from bookflow.metadata.extractor import MetadataExtractor
from bookflow.metadata.normalizer import MetadataNormalizer
from bookflow.metadata.openlibrary import OpenLibraryClient
from bookflow.organizer.engine import OrganizerEngine, OrganizerOptions
from bookflow.models import BookMetadata

app = typer.Typer(
    name="bookflow",
    help="📚 BookFlow Studio - Automatic ePub & PDF organizer and Open Library metadata enricher.",
    add_completion=False,
)
console = Console()


@app.command()
def scan(
    source_dir: Path = typer.Argument(
        ...,
        help="Directory to scan recursively for ebooks.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of books to display in detail."),
):
    """🔍 Audit an ebook directory and check metadata completeness."""
    console.print(Panel(f"[bold cyan]Scanning directory:[/bold cyan] {source_dir}", border_style="cyan"))

    engine = OrganizerEngine()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[green]Scanning books...", total=None)
        books = engine.scan_directory(source_dir)
        progress.update(task, completed=len(books), total=len(books))

    if not books:
        console.print("[yellow]No EPUB or PDF books found in this directory.[/yellow]")
        return

    # Count stats
    epubs = sum(1 for b in books if b.extension == ".epub")
    pdfs = sum(1 for b in books if b.extension == ".pdf")
    with_series = sum(1 for b in books if b.final_metadata and b.final_metadata.series)
    missing_author = sum(
        1 for b in books if not b.final_metadata or b.final_metadata.author in ("Unknown", "Inconnu", "")
    )

    table = Table(
        title=f"Sample Audit ({min(limit, len(books))}/{len(books)} books)",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    table.add_column("Type", width=6, style="dim")
    table.add_column("Original Filename", style="white", max_width=40, overflow="ellipsis")
    table.add_column("Detected Author", style="green")
    table.add_column("Detected Title", style="cyan")
    table.add_column("Series & Vol", style="yellow")
    table.add_column("ISBN / Year", style="dim")

    for book in books[:limit]:
        meta = book.final_metadata or BookMetadata()
        series_str = ""
        if meta.series:
            series_str = f"{meta.series} (#{meta.formatted_volume})"
        year_str = str(meta.year) if meta.year else "-"
        isbn_str = meta.isbn or "-"

        table.add_row(
            book.extension.upper().lstrip("."),
            book.path.name,
            meta.author or "[red]Missing[/red]",
            meta.title or "[red]Missing[/red]",
            series_str or "-",
            f"{year_str} / {isbn_str}",
        )

    console.print(table)

    summary_panel = Panel(
        f"[bold]Total Ebooks Scanned:[/bold] {len(books)}\n"
        f"  • EPUBs: [cyan]{epubs}[/cyan]\n"
        f"  • PDFs: [cyan]{pdfs}[/cyan]\n"
        f"  • Series Identified: [green]{with_series}[/green]\n"
        f"  • Incomplete Authors: [red]{missing_author}[/red]",
        title="[bold green]Scan Summary[/bold green]",
        border_style="green",
    )
    console.print(summary_panel)


@app.command()
def organize(
    source_dir: Path = typer.Argument(
        ...,
        help="Directory containing ebooks to organize.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    target_dir: Optional[Path] = typer.Option(
        None,
        "--target",
        "-t",
        help="Target directory. If omitted, organizes in-place inside source.",
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--execute",
        help="Simulate actions without moving/modifying files (default: --dry-run for safety).",
    ),
    mode: str = typer.Option(
        "move",
        "--mode",
        "-m",
        help="Operation mode: 'move' (rename/move) or 'copy' (keep originals).",
    ),
    enrich: bool = typer.Option(
        True,
        "--enrich/--no-enrich",
        help="Query Open Library to enrich missing tags, author, and titles.",
    ),
    write_metadata: bool = typer.Option(
        False,
        "--write-metadata",
        "-w",
        help="Write enriched metadata directly into EPUB Dublin Core/OPF tags.",
    ),
    structure: str = typer.Option(
        "hierarchical",
        "--structure",
        "-s",
        help="Folder structure: 'hierarchical' (Author/Series/Book) or 'flat'.",
    ),
    author_format: str = typer.Option(
        "full",
        "--author-format",
        "-a",
        help="Author format: 'full' (Prenom Nom), 'last' (Nom), or 'last-first'.",
    ),
    preserve_accents: bool = typer.Option(
        True,
        "--preserve-accents/--no-preserve-accents",
        help="Preserve accents in filenames (default: True for clean readable names).",
    ),
    naming_style: str = typer.Option(
        "standard",
        "--naming-style",
        "-n",
        help="Naming style: 'standard' (Auteur - Série T01 - Titre), 'bracket' (Auteur - [Série 01] - Titre), or 'posix' (Nom_Série_01_Titre).",
    ),
    limit: int = typer.Option(30, "--limit", "-l", help="Number of preview rows to show in table."),
):
    """⚡ Organize books into standardized naming convention: Prénom Nom - Série T01 - Titre.epub."""
    if dry_run:
        console.print(
            Panel(
                "[bold yellow]⚠️  DRY RUN MODE ENABLED[/bold yellow]\n"
                "No files will be moved or modified. Run with [bold green]--execute[/bold green] to apply changes.",
                border_style="yellow",
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]🚨 EXECUTION MODE ACTIVE[/bold red]\nFiles will be renamed/moved to their new destinations.",
                border_style="red",
            )
        )

    options = OrganizerOptions(
        source_dir=source_dir,
        target_dir=target_dir,
        dry_run=dry_run,
        mode=mode,
        enrich=enrich,
        write_metadata=write_metadata,
        structure=structure,
        author_format=author_format,
        preserve_accents=preserve_accents,
        naming_style=naming_style,
    )

    engine = OrganizerEngine()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        scan_task = progress.add_task("[cyan]Scanning books...", total=None)
        books = engine.scan_directory(source_dir)
        progress.update(scan_task, completed=len(books), total=len(books))

        if not books:
            console.print("[yellow]No ebook files found to organize.[/yellow]")
            return

        plan_task = progress.add_task("[magenta]Planning & Enriching (Open Library)...", total=len(books))

        def on_plan_progress(current, total, name):
            progress.update(plan_task, completed=current, description=f"[magenta]Enriching: {name[:25]}...")

        planned_books = engine.plan_operations(books, options, progress_callback=on_plan_progress)

        exec_task = progress.add_task("[green]Executing operations...", total=len(books))

        def on_exec_progress(current, total, name):
            progress.update(exec_task, completed=current, description=f"[green]Processing: {name[:25]}...")

        result = engine.execute_operations(planned_books, options, progress_callback=on_exec_progress)

    # Preview Table
    table = Table(
        title=f"Plan Preview ({min(limit, len(result.books))}/{len(result.books)} books)",
        box=box.ROUNDED,
        header_style="bold blue",
    )
    table.add_column("Original", style="dim", max_width=35, overflow="ellipsis")
    table.add_column("Standardized Name & Path", style="green", max_width=50, overflow="ellipsis")
    table.add_column("Status", width=12)

    for book in result.books[:limit]:
        status_color = "green" if "ready" in book.status or "moved" in book.status or "copied" in book.status else "yellow"
        dest_display = str(book.proposed_relpath) if book.proposed_relpath else book.proposed_filename or "-"
        table.add_row(
            book.path.name,
            dest_display,
            f"[{status_color}]{book.status}[/{status_color}]",
        )

    console.print(table)

    summary_text = (
        f"[bold]Total Processed:[/bold] {result.total_scanned}\n"
        f"  • Series Identified: [yellow]{result.series_detected}[/yellow]\n"
        f"  • Enriched via Open Library: [cyan]{result.enriched_count}[/cyan]\n"
    )
    if dry_run:
        summary_text += f"  • Planned Actions: [green]{result.moved_count + result.copied_count}[/green] files\n"
        summary_text += "\n[italic]Tip: Pass --execute to physically apply these changes.[/italic]"
    else:
        summary_text += (
            f"  • Moved: [green]{result.moved_count}[/green]\n"
            f"  • Copied: [green]{result.copied_count}[/green]\n"
            f"  • Skipped: [yellow]{result.skipped_count}[/yellow]\n"
            f"  • Errors: [red]{result.error_count}[/red]"
        )

    console.print(
        Panel(
            summary_text,
            title="[bold green]Execution Report[/bold green]",
            border_style="green",
        )
    )


@app.command()
def inspect(
    file_path: Path = typer.Argument(
        ...,
        help="Path to an EPUB or PDF file to inspect.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    enrich: bool = typer.Option(True, "--enrich/--no-enrich", help="Simulate Open Library enrichment."),
    author_format: str = typer.Option("full", "--author-format", "-a", help="Author format: 'full', 'last', or 'last-first'."),
    preserve_accents: bool = typer.Option(True, "--preserve-accents/--no-preserve-accents", help="Preserve accents."),
    naming_style: str = typer.Option("standard", "--naming-style", "-n", help="Naming style: 'standard', 'bracket', or 'posix'."),
):
    """📖 Deep inspection of a single ebook file."""
    console.print(Panel(f"[bold cyan]Inspecting File:[/bold cyan] {file_path}", border_style="cyan"))

    book = MetadataExtractor.extract(file_path)
    meta = book.final_metadata or BookMetadata()

    if enrich:
        with console.status("[magenta]Looking up Open Library..."):
            ol_client = OpenLibraryClient()
            enriched = ol_client.enrich_metadata(meta)
            book.enriched = enriched
            meta = enriched

    # Computed filename and relative path
    filename = MetadataNormalizer.generate_filename(
        meta,
        extension=book.extension,
        author_format=author_format,
        preserve_accents=preserve_accents,
        naming_style=naming_style,
    )
    relpath = MetadataNormalizer.generate_relpath(
        meta,
        filename=filename,
        author_format=author_format,
        preserve_accents=preserve_accents,
    )

    table = Table(box=box.ROUNDED, show_header=False)
    table.add_column("Property", style="bold yellow", width=22)
    table.add_column("Value", style="white")

    table.add_row("Format", book.extension.upper().lstrip("."))
    table.add_row("File Size", f"{book.file_size_bytes / (1024 * 1024):.2f} MB")
    table.add_row("Extracted Title", meta.title or "[red]None[/red]")
    table.add_row("Extracted Author", meta.author or "[red]None[/red]")
    table.add_row("Normalized Author", MetadataNormalizer.extract_author_name(meta.author, format_mode=author_format, preserve_accents=preserve_accents))
    table.add_row("Series", meta.series or "[dim]None[/dim]")
    table.add_row("Volume", meta.formatted_volume if meta.series else "[dim]None[/dim]")
    table.add_row("ISBN", meta.isbn or "[dim]None[/dim]")
    table.add_row("Publication Year", str(meta.year) if meta.year else "[dim]None[/dim]")
    table.add_row("Subjects / Tags", ", ".join(meta.subjects[:6]) if meta.subjects else "[dim]None[/dim]")
    table.add_row("Open Library Key", meta.openlibrary_key or "[dim]None[/dim]")
    table.add_row("---", "---")
    table.add_row("Standard Filename", f"[bold green]{filename}[/bold green]")
    table.add_row("Standard Destination", f"[bold cyan]{relpath}[/bold cyan]")

    console.print(table)


@app.command()
def lookup(
    title: str = typer.Argument(..., help="Book title to search for."),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Author name."),
    isbn: Optional[str] = typer.Option(None, "--isbn", "-i", help="ISBN number."),
):
    """🌐 Query Open Library search API directly."""
    console.print(Panel(f"Searching Open Library for: [bold cyan]{title}[/bold cyan]", border_style="cyan"))

    client = OpenLibraryClient()
    with console.status("[green]Querying Open Library..."):
        res = client.search(title=title, author=author, isbn=isbn)

    if not res or not res.get("docs"):
        console.print("[yellow]No matching records found on Open Library.[/yellow]")
        return

    table = Table(title=f"Open Library Results ({len(res['docs'])} found)", box=box.ROUNDED)
    table.add_column("Title", style="cyan")
    table.add_column("Author(s)", style="green")
    table.add_column("Year", width=6)
    table.add_column("Subjects", style="dim", max_width=40, overflow="ellipsis")
    table.add_column("Work Key", style="yellow")

    for doc in res["docs"][:10]:
        subjects = ", ".join(doc.get("subject", [])[:3])
        authors = ", ".join(doc.get("author_name", [])[:2])
        table.add_row(
            doc.get("title", ""),
            authors or "-",
            str(doc.get("first_publish_year", "-")),
            subjects or "-",
            doc.get("key", "-"),
        )

    console.print(table)


@app.command()
def version():
    """Display BookFlow version."""
    console.print(f"[bold green]BookFlow Studio[/bold green] v{__version__}")


if __name__ == "__main__":
    app()
