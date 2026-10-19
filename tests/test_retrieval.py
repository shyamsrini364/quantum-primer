import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from rank_bm25 import BM25Okapi

from quantum_primer.config import Settings
from quantum_primer.models import Chunk
from quantum_primer.retrieval import HybridRetriever, tokens


def test_hybrid_finds_exact_term_and_dense_candidate(tmp_path):
    chunks = [
        Chunk(id=str(i), text=text, source_id=str(i), title="Book", locator="Section")
        for i, text in enumerate(
            ["cryptochrome radical pair", "semantic concept", "other topic", "fourth subject"]
        )
    ]
    manifest = tmp_path / "index.json"
    manifest.write_text(
        json.dumps(
            {
                "index": "quantum-primer",
                "embedding_model": "test",
                "base_url": "http://test",
                "dimension": 2,
                "namespace": "snapshot",
                "chunks": [c.model_dump() for c in chunks],
            }
        )
    )
    settings = Settings(
        _env_file=None, manifest_path=manifest, embedding_model="test", model_base_url="http://test"
    )
    embedder, pc, index = Mock(), Mock(), Mock()
    embedder.embed_query.return_value = [0.1, 0.2]
    pc.Index.return_value = index
    index.query.return_value = SimpleNamespace(
        matches=[
            SimpleNamespace(id="1", score=0.8),
            SimpleNamespace(id="2", score=0.1),
            SimpleNamespace(id="unknown", score=0.9),
        ]
    )
    with (
        patch("quantum_primer.retrieval.embeddings", return_value=embedder),
        patch("quantum_primer.retrieval.pinecone", return_value=pc),
    ):
        result = HybridRetriever(settings).search("cryptochrome")
    assert {h.chunk.id for h in result} == {"0", "1"}
    assert index.query.call_args.kwargs["namespace"] == "snapshot"


@pytest.mark.parametrize("question,expected_sources", [
    ("In Optimize, how does Catherine Clinton describe exclusion zone water?", {"clinton"}),
    ("Compare Optimize and Health and Light on water.", {"clinton", "ott"}),
    ('Compare “Optimize” and “Health and Light” on water.', {"clinton", "ott"}),
    ('Compare Health and Light and Optimize on water.', {"clinton", "ott"}),
    ("Compare Health and Light with Life on the Edge on water.", {"ott", "edge"}),
    ("How can I optimize water intake?", None),
])
def test_named_books_scope_both_rankings(question, expected_sources):
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.settings = Settings(_env_file=None)
    retriever.manifest = {"dimension": 2, "namespace": "snapshot"}
    retriever.chunks = [
        Chunk(id=sid, source_id=sid, title=title, text=text, locator="Page 1",
              author="Catherine Clinton" if sid == "clinton" else "Unknown")
        for sid, title, text in [
            ("clinton", "Optimize: A Plan", "exclusion zone water"),
            ("ott", "Health and Light", "exclusion zone water"),
            ("edge", "Life on the Edge", "exclusion zone water"),
            ("other", "Other Book", "unrelated"),
        ]
    ]
    retriever.by_id = {c.id: c for c in retriever.chunks}
    retriever.bm25 = BM25Okapi([tokens(c.text) for c in retriever.chunks])
    retriever.embedder = Mock()
    retriever.embedder.embed_query.return_value = [0.1, 0.2]
    retriever.index = Mock()
    retriever.index.query.return_value = SimpleNamespace(matches=[
        SimpleNamespace(id=c.id, score=0.9) for c in retriever.chunks
    ])
    hits = retriever.search(question)
    query = retriever.index.query.call_args.kwargs
    if expected_sources:
        assert {call.kwargs["filter"]["source_id"]["$in"][0]
                for call in retriever.index.query.call_args_list} == expected_sources
        assert {h.chunk.source_id for h in hits} == expected_sources
        if expected_sources == {"clinton"}:
            search_text = retriever.embedder.embed_query.call_args.args[0]
            assert "catherine" not in search_text
            assert "clinton" not in search_text
            assert "exclusion zone water" in search_text
    else:
        assert "filter" not in query
        assert {h.chunk.source_id for h in hits} == set(retriever.by_id)


def test_comparison_preserves_two_passages_per_book_despite_rank_imbalance():
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.settings = Settings(_env_file=None, context_k=4)
    retriever.manifest = {"dimension": 2, "namespace": "snapshot"}
    retriever.chunks = [
        Chunk(id=f"{sid}-{i}", source_id=sid, title=title,
              text="water charge", locator=f"Page {i}")
        for sid, title in [("a", "Optimize"), ("b", "The Mitochondriac Manifesto")]
        for i in range(8)
    ]
    retriever.by_id = {c.id: c for c in retriever.chunks}
    retriever.bm25 = Mock()
    retriever.bm25.get_scores.return_value = [100] * 8 + [1] * 8
    retriever.embedder = Mock()
    retriever.embedder.embed_query.return_value = [0.1, 0.2]
    retriever.index = Mock()

    def query(**kwargs):
        sid = kwargs["filter"]["source_id"]["$in"][0]
        return SimpleNamespace(matches=[
            SimpleNamespace(id=f"{sid}-{i}", score=0.99 if sid == "a" else 0.4)
            for i in range(8)
        ])

    retriever.index.query.side_effect = query
    hits = retriever.search('Compare “Optimize” and “The Mitochondriac Manifesto” on water.')
    assert [h.chunk.source_id for h in hits] == ["a", "b", "a", "b"]
    assert len({h.chunk.id for h in hits}) == 4


def test_teaching_instructions_do_not_crowd_out_subject_passage():
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.settings = Settings(_env_file=None, context_k=1)
    retriever.manifest = {"dimension": 2, "namespace": "snapshot"}
    texts = [
        "DHA interacts with light in biology.",
        "Explain the term and his proposed role in plain language with one example " * 8,
        "Copyright author book all rights reserved.",
        "Agriculture crops soil harvest.",
        "Mitochondria metabolism energy cells.",
        "Circadian rhythms darkness sleep.",
    ]
    retriever.chunks = [
        Chunk(id=str(i), source_id="kruse", title="Epi-paleo Rx", author="Jack Kruse",
              text=text, locator=f"Page {i}") for i, text in enumerate(texts)
    ]
    retriever.by_id = {c.id: c for c in retriever.chunks}
    retriever.bm25 = BM25Okapi([tokens(c.text) for c in retriever.chunks])
    retriever.embedder = Mock()
    retriever.embedder.embed_query.return_value = [0.1, 0.2]
    retriever.index = Mock()
    retriever.index.query.return_value = SimpleNamespace(matches=[])
    question = (
        "In Epi-paleo Rx, what is DHA, and why does Jack Kruse connect it to light and "
        "biology? Explain the term and his proposed role for it in plain language, "
        "with one example supported by the book."
    )
    assert retriever.search(question)[0].chunk.id == "0"
