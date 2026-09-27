"""Unit tests for OpenLibraryClient and SQLite caching."""

from bookflow.metadata.openlibrary import OpenLibraryClient
from bookflow.models import BookMetadata


def test_sqlite_cache_roundtrip(tmp_path):
    cache_db = tmp_path / "test_cache.sqlite"
    client = OpenLibraryClient(cache_path=cache_db, request_delay=0)

    test_data = {"numFound": 1, "docs": [{"title": "Foundation", "author_name": ["Isaac Asimov"]}]}
    client._save_to_cache("test_key", test_data)

    retrieved = client._get_from_cache("test_key")
    assert retrieved == test_data
    assert retrieved["docs"][0]["title"] == "Foundation"


def test_enrich_metadata_from_cached_response(tmp_path):
    cache_db = tmp_path / "test_cache.sqlite"
    client = OpenLibraryClient(cache_path=cache_db, request_delay=0)

    # Pre-populate cache so no network calls are made
    query_key = "ta:fondation:isaac asimov"
    mock_response = {
        "numFound": 1,
        "docs": [
            {
                "title": "Foundation",
                "author_name": ["Isaac Asimov"],
                "first_publish_year": 1951,
                "subject": ["Psychohistory", "Galactic Empire"],
                "key": "/works/OL46125W",
            }
        ],
    }
    client._save_to_cache(query_key, mock_response)

    meta = BookMetadata(title="fondation", author="isaac asimov", source="filename")
    enriched = client.enrich_metadata(meta)

    assert enriched.title == "Foundation"
    assert enriched.author == "Isaac Asimov"
    assert enriched.year == 1951
    assert "Psychohistory" in enriched.subjects
    assert enriched.openlibrary_key == "/works/OL46125W"
