"""
Tests for MetadataSource — the base class and its shared text helpers.

MetadataSource can be instantiated directly to test the helper methods
without needing a subclass or any data files.
"""

import pytest

from shelley.search.base import MetadataSource


@pytest.fixture
def source():
    return MetadataSource()


# ---------------------------------------------------------------------------
# _normalise
# ---------------------------------------------------------------------------


def test_normalise_lowercases(source):
    assert source._normalise("RNA") == ["rna"]


def test_normalise_preserves_hyphens(source):
    assert source._normalise("RNA-seq") == ["rna-seq"]


def test_normalise_strips_punctuation(source):
    assert source._normalise("quality!") == ["quality"]


def test_normalise_splits_on_whitespace(source):
    assert source._normalise("variant calling") == ["variant", "calling"]


# ---------------------------------------------------------------------------
# _expand_tokens
# ---------------------------------------------------------------------------


def test_expand_tokens_keeps_original(source):
    assert "rna-seq" in source._expand_tokens(["rna-seq"])


def test_expand_tokens_removes_hyphen(source):
    assert "rnaseq" in source._expand_tokens(["rna-seq"])


def test_expand_tokens_splits_on_hyphen(source):
    expanded = source._expand_tokens(["rna-seq"])
    assert "rna" in expanded
    assert "seq" in expanded


def test_expand_tokens_plain_token_unchanged(source):
    assert "alignment" in source._expand_tokens(["alignment"])


def test_expand_tokens_skips_empty(source):
    assert source._expand_tokens([""]) == set()


# ---------------------------------------------------------------------------
# _flatten_edam
# ---------------------------------------------------------------------------


def test_flatten_edam_plain_list(source):
    assert source._flatten_edam(["Mapping", "Alignment"]) == ["Mapping", "Alignment"]


def test_flatten_edam_nested_dict_term(source):
    result = source._flatten_edam([{"term": "Mapping", "formats": []}])
    assert "Mapping" in result


def test_flatten_edam_nested_dict_with_formats(source):
    result = source._flatten_edam([{"term": "Mapping", "formats": ["FASTQ"]}])
    assert "Mapping" in result
    assert "FASTQ" in result


def test_flatten_edam_none(source):
    assert source._flatten_edam(None) == []


def test_flatten_edam_empty_list(source):
    assert source._flatten_edam([]) == []


# ---------------------------------------------------------------------------
# _load_stopwords
# ---------------------------------------------------------------------------


def test_load_stopwords_returns_set(source):
    assert isinstance(source._load_stopwords(), set)


def test_load_stopwords_contains_common_words(source):
    sw = source._load_stopwords()
    assert "the" in sw
    assert "and" in sw


# ---------------------------------------------------------------------------
# Interface methods raise NotImplementedError
# ---------------------------------------------------------------------------


def test_load_raises(source):
    with pytest.raises(NotImplementedError, match="MetadataSource"):
        source.load()


def test_search_raises(source):
    with pytest.raises(NotImplementedError, match="MetadataSource"):
        source.search("quality")


# ---------------------------------------------------------------------------
# __len__
# ---------------------------------------------------------------------------


def test_len_empty(source):
    assert len(source) == 0


def test_len_after_injection(source):
    source.entries = [{"id": "a"}, {"id": "b"}]
    assert len(source) == 2
