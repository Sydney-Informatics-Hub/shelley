"""
RsecSource — loads and searches the RSEC bio.tools corpus.

The RSEC artifact (rsec_meta.json.gz) stores EDAM fields as plain string lists,
already flattened during ingestion by build_rsec_meta.py. This means
_flatten_edam() passes them through unchanged, unlike toolfinder entries which
use nested dicts.
"""

import gzip
import json
from pathlib import Path

from shelley.search.base import MetadataSource
from shelley.utils.globals import DATA_DIR

RSEC_DATA_PATH = DATA_DIR / "rsec_meta.json.gz"


class RsecSource(MetadataSource):
    """
    Metadata source backed by the RSEC bio.tools corpus (rsec_meta.json.gz).

    Usage:
        source = RsecSource().load()
        results = source.search("variant calling")

    For testing, inject entries directly instead of loading from disk:
        source = RsecSource()
        source.entries = [{"id": "bwa", "name": "BWA", ...}]
    """

    name = "rsec"

    def __init__(self, data_path: Path = RSEC_DATA_PATH):
        super().__init__()
        self.data_path = Path(data_path)

    def load(self) -> "RsecSource":
        """
        Load rsec_meta.json.gz into self.entries.

        The artifact is a gzipped JSON file produced by shelley-build-rsec.
        Top-level keys: generated_at, source, source_commit, entry_count,
        field_coverage, entries. Only entries is loaded here.
        """
        with gzip.open(self.data_path, "rt", encoding="utf-8") as f:
            doc = json.load(f)
        self.entries = doc["entries"]
        return self

    def search(self, query: str, limit: int | None = None) -> list[str]:
        """
        Keyword OR-match across name, description, edam-operations, edam-topics.
        Returns tool names sorted alphabetically, truncated to limit.

        RSEC entries store EDAM fields as plain string lists (already flattened
        during build_rsec_meta.py ingestion), so _flatten_edam() passes them
        through unchanged.

        Algorithm:
        # 1. self._normalise(query) → raw token list
        # 2. drop stopwords via self._load_stopwords(); fall back to raw tokens
        #    if all tokens are stopwords (to avoid returning an empty set)
        # 3. self._expand_tokens(tokens) → query token set (adds hyphen variants)
        # 4. for each entry in self.entries:
        #      a. collect searchable text from: name, description,
        #         edam-operations, edam-topics
        #         (edam-inputs/outputs excluded — see explanation/search-design.md)
        #      b. self._flatten_edam() each EDAM field → plain strings
        #      c. self._expand_tokens(self._normalise(joined_text)) → entry token set
        #      d. if query_tokens ∩ entry_tokens is non-empty → entry matches
        # 5. collect matched tool names (deduplicated, preserving first occurrence)
        # 6. sort alphabetically, then return names[:limit]
        """
        raw_tokens = self._normalise(query)

        stopwords = self._load_stopwords()
        filtered = [t for t in raw_tokens if t not in stopwords]
        tokens = filtered if filtered else raw_tokens

        query_tokens = self._expand_tokens(tokens)
        if not query_tokens:
            return []

        names: list[str] = []
        seen: set[str] = set()
        for entry in self.entries:
            text_parts = [
                str(entry.get("name") or ""),
                str(entry.get("description") or ""),
            ]
            for field in ("edam-operations", "edam-topics"):
                text_parts.extend(self._flatten_edam(entry.get(field)))

            entry_tokens = self._expand_tokens(self._normalise(" ".join(text_parts)))

            if query_tokens & entry_tokens:
                name = str(entry.get("name") or entry.get("id") or "")
                if name and name not in seen:
                    names.append(name)
                    seen.add(name)

        names.sort()
        return names[:limit] if limit is not None else names
