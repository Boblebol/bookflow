# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Human-Readable Naming Styles (`--naming-style`)**:
  - `standard` (Default): `Prénom Nom - Série T01 - Titre.epub` (or `Prénom Nom - Titre.epub` for standalone books).
  - `bracket`: `Prénom Nom - [Série 01] - Titre.epub`.
  - `posix`: `Nom_Série_01_Titre.epub` (legacy slug format).
- **French Contractions & Apostrophe Preservation**: Preserves apostrophes (`L'Ultime Expérience`, `Des Ailes d'Argent`, `L'Étranger`) and compound first names (`Jean-Christophe Grangé`).
- **Co-Author Delimiter**: Clean ` & ` separator for multiple authors (e.g. `Douglas Preston & Lincoln Child`).
- **Bidirectional 3-Part Filename Parsing**: FilenameParser now recognizes standard 3-part names (`Author - Series Tome - Title`).

### Changed
- Default `author_format` changed from `"last"` to `"full"` (`Prénom Nom`).
- Default `preserve_accents` changed from `False` to `True` for clean, ungarbled literature titles.
- Default `component_sep` changed from `"_"` to `" - "`.
- Default `word_sep` changed from `"-"` to `" "`.

### Fixed
- **Author Extraction Recursion & Particle/Initial Handling**: Fixed a critical `RecursionError` caused by infinite recursive splitting on inverted author names with initials and no space after comma (e.g. `Van Vogt,A. E.`). Added `allow_multi=False` recursion guard and prevented false multi-author detection for surnames with particles (`Van Vogt`, `De Balzac`) or given names with initials.

## [0.1.0] - 2026-09-27

### Added
- **Core CLI**: Built high-performance Typer & Rich CLI (`bookflow`) with `scan`, `organize`, `inspect`, `lookup`, and `version` subcommands.
- **Internal Metadata Extractor**: Robust extraction from EPUBs (Dublin Core, Calibre OPF series, EPUB3 collections) and PDFs (`pypdf`).
- **Heuristic Scene Parser**: Regex engine parsing dirty scene releases (`Bernard.Minier.2020.Le.Commandant.Servaz.T6...`), stripping tags (`FRENCH`, `NoGRP`, `Epub-NoTag`) and detecting series/tomes (`T1`, `T01`, `Tome 6`, `#1`).
- **Open Library Enrichment**: Client supporting Search API and Works API with polite rate-limiting and persistent SQLite caching (`~/.cache/bookflow/openlibrary_cache.sqlite`).
- **Standardized Normalizer**: Strict naming engine implementing `NomAuteur_Série_Tome_Titre.epub` or `NomAuteur_Titre.epub` with intelligent French stop-word handling, author deduplication, and cross-platform filename sanitation.
- **Safe Execution & Dry Run**: Simulation by default (`--dry-run`), collision resolution, hierarchical or flat directory structures.
- **Atomic EPUB Metadata Writer**: Safe updates of internal Dublin Core tags and Calibre OPF series tags without risking file corruption.
- **Test Suite**: 17 unit tests verifying parsing, normalization, API caching, atomic writing, and organizational planning.
