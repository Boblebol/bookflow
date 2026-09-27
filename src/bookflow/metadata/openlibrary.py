"""Open Library API client with SQLite caching and polite rate-limiting."""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

import requests

from bookflow.models import BookMetadata

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "bookflow"
DEFAULT_CACHE_FILE = DEFAULT_CACHE_DIR / "openlibrary_cache.sqlite"
USER_AGENT = "BookFlow/0.1.0 (https://github.com/Boblebol/bookflow; mailto:alexandre.enouf@gmail.com)"
BASE_URL = "https://openlibrary.org"


class OpenLibraryClient:
    """Client for Open Library Search and Works APIs."""

    def __init__(self, cache_path: Optional[Path] = None, request_delay: float = 0.25):
        self.cache_path = cache_path or DEFAULT_CACHE_FILE
        self.request_delay = request_delay
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._init_cache()

    def _init_cache(self) -> None:
        """Initialize SQLite cache database."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_cache (
                    cache_key TEXT PRIMARY KEY,
                    data_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def _get_from_cache(self, key: str) -> Optional[dict[str, Any]]:
        """Fetch cached response by key."""
        try:
            with sqlite3.connect(self.cache_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT data_json FROM api_cache WHERE cache_key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception as e:
            logger.warning("Cache read error: %s", e)
        return None

    def _save_to_cache(self, key: str, data: dict[str, Any]) -> None:
        """Save API response into cache."""
        try:
            with sqlite3.connect(self.cache_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO api_cache (cache_key, data_json) VALUES (?, ?)",
                    (key, json.dumps(data)),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Cache write error: %s", e)

    def search(
        self,
        title: Optional[str] = None,
        author: Optional[str] = None,
        isbn: Optional[str] = None,
        q: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Perform search on Open Library with fallback strategies."""
        # 1. Try ISBN if available
        if isbn:
            clean_isbn = isbn.replace("-", "").strip()
            isbn_key = f"isbn:{clean_isbn}"
            cached = self._get_from_cache(isbn_key)
            if cached:
                return cached

            res = self._fetch_json(f"{BASE_URL}/search.json", params={"isbn": clean_isbn})
            if res and res.get("docs"):
                self._save_to_cache(isbn_key, res)
                return res

        # 2. Try title + author
        clean_title = (title or "").strip()
        clean_author = (author or "").strip()

        if clean_title:
            params = {}
            if clean_author:
                params["title"] = clean_title
                params["author"] = clean_author
                query_key = f"ta:{clean_title}:{clean_author}".lower()
            else:
                params["title"] = clean_title
                query_key = f"t:{clean_title}".lower()

            cached = self._get_from_cache(query_key)
            if cached:
                return cached

            res = self._fetch_json(f"{BASE_URL}/search.json", params=params)
            if res and res.get("numFound", 0) > 0:
                self._save_to_cache(query_key, res)
                return res

            # 3. Fallback: general query q="author title"
            general_q = f"{clean_author} {clean_title}".strip()
            q_key = f"q:{general_q}".lower()
            cached_q = self._get_from_cache(q_key)
            if cached_q:
                return cached_q

            res_q = self._fetch_json(f"{BASE_URL}/search.json", params={"q": general_q})
            if res_q and res_q.get("numFound", 0) > 0:
                self._save_to_cache(q_key, res_q)
                return res_q

        elif q:
            q_key = f"q:{q.strip()}".lower()
            cached = self._get_from_cache(q_key)
            if cached:
                return cached

            res = self._fetch_json(f"{BASE_URL}/search.json", params={"q": q.strip()})
            if res:
                self._save_to_cache(q_key, res)
                return res

        return None

    def get_work_details(self, work_key: str) -> Optional[dict[str, Any]]:
        """Fetch subjects and description from /works/{ID}.json."""
        if not work_key.startswith("/works/"):
            work_key = f"/works/{work_key}"

        cache_key = f"work:{work_key}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        res = self._fetch_json(f"{BASE_URL}{work_key}.json")
        if res:
            self._save_to_cache(cache_key, res)
            return res
        return None

    def _fetch_json(self, url: str, params: Optional[dict[str, str]] = None) -> Optional[dict[str, Any]]:
        """Make HTTP GET request with rate limiting and error handling."""
        try:
            time.sleep(self.request_delay)
            resp = self.session.get(url, params=params, timeout=8.0)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                logger.warning("Open Library rate limit encountered. Waiting 2s...")
                time.sleep(2.0)
        except Exception as e:
            logger.warning("Open Library request error for %s: %s", url, e)
        return None

    def enrich_metadata(self, metadata: BookMetadata) -> BookMetadata:
        """Enrich existing metadata with Open Library records."""
        # Check if already rich
        search_res = self.search(
            title=metadata.title,
            author=metadata.author,
            isbn=metadata.isbn,
        )

        if not search_res or not search_res.get("docs"):
            return metadata

        docs = search_res["docs"]
        best_doc = docs[0]

        # Extract cleaner title and author if original was empty/fallback
        title = metadata.title
        if not title or metadata.source in ("fallback", "filename"):
            title = best_doc.get("title", title)

        author = metadata.author
        if not author or metadata.source in ("fallback", "filename"):
            authors = best_doc.get("author_name", [])
            if authors:
                author = authors[0]

        # Year
        year = metadata.year
        if not year and best_doc.get("first_publish_year"):
            year = best_doc.get("first_publish_year")

        # Subjects / Tags
        subjects = list(metadata.subjects)
        doc_subjects = best_doc.get("subject", [])
        if doc_subjects:
            for s in doc_subjects[:5]:
                if s not in subjects:
                    subjects.append(s)

        # Work key & details
        work_key = best_doc.get("key")
        description = metadata.description
        if work_key:
            work_data = self.get_work_details(work_key)
            if work_data:
                work_subjects = work_data.get("subjects", [])
                for s in work_subjects[:5]:
                    if s not in subjects:
                        subjects.append(s)
                if not description and work_data.get("description"):
                    raw_desc = work_data["description"]
                    if isinstance(raw_desc, dict):
                        description = raw_desc.get("value", "")
                    elif isinstance(raw_desc, str):
                        description = raw_desc

        return BookMetadata(
            title=title,
            author=author,
            author_last_name=metadata.author_last_name,
            series=metadata.series,
            volume=metadata.volume,
            volume_raw=metadata.volume_raw,
            isbn=metadata.isbn or (best_doc.get("isbn", [None])[0] if best_doc.get("isbn") else None),
            year=year,
            publisher=metadata.publisher or (best_doc.get("publisher", [None])[0] if best_doc.get("publisher") else None),
            subjects=subjects,
            description=description,
            language=metadata.language,
            openlibrary_key=work_key,
            source="openlibrary",
        )
