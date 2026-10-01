"""
ToolfinderSource — loads and searches the toolfinder corpus.

The toolfinder artifact (toolfinder_meta.yaml) stores EDAM fields as nested
dicts: [{"term": "Read mapping", "formats": ["SAM"]}]. The inherited
_flatten_edam() method handles this format alongside RSEC's plain string lists,
so the search algorithm is the same — _flatten_edam() does the format bridging.
"""

from pathlib import Path

import yaml

from shelley.search.base import MetadataSource
from shelley.utils.globals import DATA_DIR

TOOLFINDER_DATA_PATH = DATA_DIR / "toolfinder_meta.yaml"


class ToolfinderSource(MetadataSource):
    """
    Metadata source backed by the toolfinder corpus (toolfinder_meta.yaml).

    Usage:
        source = ToolfinderSource().load()
        results = source.search("variant calling")

    For testing, inject entries directly instead of loading from disk:
        source = ToolfinderSource()
        source.entries = [{"id": "fastqc", "name": "FastQC", ...}]
    """

    name = "toolfinder"

    def __init__(self, data_path: Path = TOOLFINDER_DATA_PATH):
        super().__init__()
        self.data_path = Path(data_path)

    def load(self) -> "ToolfinderSource":
        """Load toolfinder_meta.yaml into self.entries."""
        with open(self.data_path, encoding="utf-8") as f:
            self.entries = yaml.safe_load(f)
        return self

    def search(self, query: str, limit: int | None = None) -> list[str]:
        """
        Same algorithm as RsecSource.search() — see that docstring for the steps.

        Why not inherit the implementation from MetadataSource (polymorphism)?
        The algorithm is identical, but toolfinder entries use a nested EDAM dict
        format that must go through _flatten_edam() before tokenisation.
        Keeping the full algorithm description here — rather than delegating to a
        shared parent method — means a maintainer can read this file without
        following the inheritance chain to understand what search() does.

        # 1–6 same as RsecSource.search()
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
