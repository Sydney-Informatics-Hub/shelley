"""
Base class for metadata sources.

MetadataSource defines the shared interface (load, search, __len__) and the
text-processing helpers that both RsecSource and ToolfinderSource use.
Subclasses only need to implement load() and search().

Why not an ABC (Abstract Base Class)?
ABCs enforce interface compliance at instantiation time via Python's metaclass
machinery, which adds a layer of indirection that's hard to follow without
knowing how ABCs work. A plain class with NotImplementedError gives the same
"you forgot to implement this" signal at call time, which is when it matters,
and is immediately understandable to anyone who can read a traceback.
"""

import re

from shelley.utils.constants import STOP_WORDS


class MetadataSource:
    """
    Base class for metadata sources. Subclass and implement load() and search().

    Usage:
        source = RsecSource()        # or ToolfinderSource()
        source.load()                # reads from disk into self.entries
        results = source.search("variant calling")
    """

    name: str = "base"  # override in subclass; used for logging

    def __init__(self):
        self.entries: list[dict] = []  # populated by load(); tests may inject directly

    # ------------------------------------------------------------------
    # Interface — implement in subclasses
    # ------------------------------------------------------------------

    def load(self) -> "MetadataSource":
        """Load entries from disk into self.entries. Returns self for chaining."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement load()")

    def search(self, query: str, limit: int | None = None) -> list[str]:
        """Return tool names matching query, sorted alphabetically."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement search()")

    def __len__(self) -> int:
        return len(self.entries)

    # ------------------------------------------------------------------
    # Text helpers — shared by all subclasses, called as self._normalise() etc.
    # ------------------------------------------------------------------

    def _normalise(self, text: str) -> list[str]:
        """
        Lowercase, strip non-alphanumeric characters (keeping hyphens), and split.

        "RNA-seq Quality!" → ["rna-seq", "quality"]
        """
        text = text.lower()
        text = re.sub(r"[^\w\s\-]", " ", text)
        return text.split()

    def _expand_tokens(self, tokens) -> set[str]:
        """
        Expand a collection of tokens to include hyphen variants.

        For each token:
        - keep the original   ("rna-seq" → "rna-seq")
        - remove hyphens      ("rna-seq" → "rnaseq")
        - split on hyphens    ("rna-seq" → "rna", "seq")
        """
        expanded: set[str] = set()
        for token in tokens:
            if not token:
                continue
            expanded.add(token)
            expanded.add(token.replace("-", ""))
            if "-" in token:
                expanded.update(part for part in token.split("-") if part)
        return expanded

    def _flatten_edam(self, value) -> list[str]:
        """
        Flatten an EDAM field to a plain list of strings.

        Handles two formats:
        - RSEC (already flat):      ["Read mapping", "Sequence alignment"]
        - Toolfinder (nested dict): [{"term": "Read mapping", "formats": ["SAM"]}]

        Always returns a list of strings; never raises on unexpected input.
        """
        if not value:
            return []

        results: list[str] = []

        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    term = item.get("term") or item.get("uri", "")
                    if term:
                        results.append(str(term))
                    for fmt in item.get("formats", []) or []:
                        if isinstance(fmt, dict):
                            t = fmt.get("term") or fmt.get("uri", "")
                            if t:
                                results.append(str(t))
                        elif fmt:
                            results.append(str(fmt))
                elif item:
                    results.append(str(item))
        elif value:
            results.append(str(value))

        return results

    def _load_stopwords(self) -> set[str]:
        """
        Return the union of all STOP_WORDS categories as a flat set.

        STOP_WORDS is a dict-of-sets in constants.py. This collapses it into
        one set for O(1) membership tests during query processing.
        """
        return set().union(*STOP_WORDS.values())
