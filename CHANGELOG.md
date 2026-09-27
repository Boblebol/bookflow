# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
