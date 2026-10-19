import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from quantum_primer.api import create_app
from quantum_primer.config import Settings
from quantum_primer.graph import COMPARISON, ModelResponder, build_graph
from quantum_primer.ingest import load_chunks
from quantum_primer.models import Chunk, Draft, Grade, Hit, Statement
from quantum_primer.service import create_graph


def hit():
    return Hit(
        chunk=Chunk(
            id="a",
            text="A supported fact.",
            source_id="book-1",
            title="Source",
            locator="PDF page 7",
        ),
        score=0.9,
    )


def test_no_context_never_calls_model():
    retriever, responder = Mock(), Mock()
    retriever.search.return_value = []
    result = build_graph(retriever, responder).invoke({"question": "Missing answer?"})
    assert result["response"].status == "insufficient_context"
    responder.grade.assert_not_called()
    responder.generate.assert_not_called()


def test_grader_rejection_stops_generation():
    retriever, responder = Mock(), Mock()
    retriever.search.return_value = [hit()]
    responder.grade.return_value = False
    result = build_graph(retriever, responder).invoke({"question": "Unrelated?"})
    assert result["response"].status == "insufficient_context"
    assert result["response"].citations == []
    responder.generate.assert_not_called()


def test_same_page_citations_merge_without_dropping_chunks():
    retriever, responder = Mock(), Mock()
    first = hit()
    second = first.model_copy(update={
        "chunk": first.chunk.model_copy(update={"id": "b", "text": "Another fact."})
    })
    other_page = first.model_copy(update={
        "chunk": first.chunk.model_copy(update={"id": "c", "locator": "PDF page 8"})
    })
    other_book = first.model_copy(update={
        "chunk": first.chunk.model_copy(update={"id": "d", "source_id": "book-2"})
    })
    hits = [first, second, other_page, other_book]
    retriever.search.return_value = hits
    responder.grade.return_value = True
    responder.generate.return_value = Draft(statements=[
        Statement(text="Both facts.", citation_ids=["2", "1", "2"]),
        Statement(text="Other page.", citation_ids=["3", "1"]),
        Statement(text="Other book.", citation_ids=["4"]),
    ])
    result = build_graph(retriever, responder).invoke({"question": "What facts?"})
    responder.generate.assert_called_once_with("What facts?", hits)
    assert result["hits"] == hits
    answer = result["response"]
    assert answer.answer == "Both facts. [1]\n\nOther page. [2] [1]\n\nOther book. [3]"
    assert [(c.id, c.source_id, c.locator) for c in answer.citations] == [
        ("1", "book-1", "PDF page 7"),
        ("2", "book-1", "PDF page 8"),
        ("3", "book-2", "PDF page 7"),
    ]


@pytest.mark.parametrize("citation_id,expected", [("1", "answered"), ("9", "insufficient_context")])
def test_citations_are_validated(citation_id, expected):
    retriever, responder = Mock(), Mock()
    retriever.search.return_value = [hit()]
    responder.grade.return_value = True
    responder.generate.return_value = Draft(
        statements=[Statement(text="A supported fact.", citation_ids=[citation_id])]
    )
    response = build_graph(retriever, responder).invoke({"question": "What fact?"})["response"]
    assert response.status == expected
    if expected == "answered":
        assert response.citations[0].locator == "PDF page 7"
        assert "[1]" in response.answer


def test_malformed_model_output_fails_closed():
    retriever, responder = Mock(), Mock()
    retriever.search.return_value = [hit()]
    responder.grade.side_effect = ValueError("bad JSON")
    assert (
        build_graph(retriever, responder).invoke({"question": "Question?"})["response"].status
        == "insufficient_context"
    )


def test_ingest_metadata_and_stable_ids(tmp_path):
    (tmp_path / "book.md").write_text("# Chapter One\nA book about electron tunnelling.\n")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {"sources": [{"id": "book", "path": "book.md", "title": "A book", "author": "Author"}]}
        )
    )
    first = load_chunks(catalog)
    assert first == load_chunks(catalog)
    assert first[0].locator == "Section: Chapter One"
    assert first[0].author == "Author"
    (tmp_path / "book.md").write_text("# Chapter One\nUpdated content.")
    assert first[0].id != load_chunks(catalog)[0].id


def test_empty_and_duplicate_sources_rejected(tmp_path):
    (tmp_path / "empty.txt").write_text("")
    catalog = tmp_path / "catalog.json"
    source = {"id": "empty", "path": "empty.txt", "title": "Empty"}
    catalog.write_text(json.dumps({"sources": [source]}))
    with pytest.raises(ValueError, match="No extractable"):
        load_chunks(catalog)
    (tmp_path / "empty.txt").write_text("Some content")
    catalog.write_text(json.dumps({"sources": [source, source]}))
    with pytest.raises(ValueError, match="Duplicate"):
        load_chunks(catalog)


def test_api_demo_validation_auth_and_sources():
    settings = Settings(_env_file=None, mode="demo", api_key=SecretStr("test-key"))
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["mode"] == "demo"
        assert client.post("/chat", json={"question": "What is Quantum Primer?"}).status_code == 401
        headers = {"X-API-Key": "test-key"}
        assert client.post("/chat", json={"question": "   "}, headers=headers).status_code == 422
        response = client.post(
            "/chat", json={"question": "What is Quantum Primer?"}, headers=headers
        ).json()
        assert response["status"] == "answered"
        assert response["citations"][0]["source_id"] == "demo-guide"
        response = client.post(
            "/chat", json={"question": "What is quantum coherence?"}, headers=headers
        ).json()
        assert response["status"] == "insufficient_context"


def test_api_hides_provider_exceptions():
    graph = Mock()
    graph.invoke.side_effect = RuntimeError("secret-private-content")
    with TestClient(create_app(Settings(_env_file=None), graph)) as client:
        response = client.post("/chat", json={"question": "What happened?"})
        assert response.status_code == 503
        assert "secret-private-content" not in response.text


def test_live_settings_fail_early():
    with pytest.raises(ValueError, match="Missing live settings"):
        create_graph(Settings(_env_file=None, mode="live"))


@pytest.mark.parametrize("missing_retrieval,missing_citation", [(True, False), (False, True),
                                                              (False, False)])
def test_comparison_requires_each_book_in_context_and_answer(missing_retrieval, missing_citation):
    retriever, responder = Mock(), Mock()
    first = hit()
    second = Hit(chunk=first.chunk.model_copy(update={"id": "b", "source_id": "book-2"}),
                 score=0.8)
    retriever.search.return_value = [first] if missing_retrieval else [first, second]
    responder.grade.return_value = True
    responder.verify_comparison.return_value = Grade(sufficient=True, reason="Supported")
    responder.generate.return_value = Draft(statements=[
        Statement(text="Both authors describe a shared idea.",
                  citation_ids=["1"] if missing_citation else ["1", "2"])
    ])
    graph = build_graph(retriever, responder,
                        source_resolver=lambda q: {"book-1": "First", "book-2": "Second"})
    result = graph.invoke({"question": "Compare First and Second."})["response"]
    if missing_retrieval or missing_citation:
        assert result.status == "insufficient_context"
        assert "every requested book" in result.answer
        assert not result.citations
    else:
        assert result.status == "answered"
        assert {c.source_id for c in result.citations} == {"book-1", "book-2"}
    if missing_retrieval:
        responder.grade.assert_not_called()
        responder.generate.assert_not_called()


@pytest.mark.parametrize("repair_passes", [True, False])
def test_comparison_review_repairs_once_then_fails_closed(repair_passes):
    retriever, responder = Mock(), Mock()
    first = hit()
    second = Hit(chunk=first.chunk.model_copy(update={"id": "b", "source_id": "book-2"}),
                 score=0.8)
    retriever.search.return_value = [first, second]
    responder.grade.return_value = True
    responder.generate.return_value = Draft(statements=[
        Statement(text="A shared claim.", citation_ids=["1", "2"])
    ])
    responder.verify_comparison.side_effect = [
        Grade(sufficient=False, reason="Unsupported absence claim"),
        Grade(sufficient=repair_passes, reason="Second review"),
    ]
    graph = build_graph(retriever, responder,
                        source_resolver=lambda q: {"book-1": "First", "book-2": "Second"})
    answer = graph.invoke({"question": "Compare these books."})["response"]
    assert answer.status == ("answered" if repair_passes else "insufficient_context")
    assert responder.generate.call_count == 2
    assert responder.verify_comparison.call_count == 2
    assert responder.generate.call_args.kwargs == {"feedback": "Unsupported absence claim"}


@pytest.mark.parametrize("question,compare", [
    ("Explain water with a practical example.", False),
    ("Compare both books on water.", True),
])
def test_tutoring_prompt_only_adds_comparison_rules_when_requested(question, compare):
    model = Mock()
    model.invoke.return_value.content = json.dumps({"statements": [
        {"text": "A simple explanation.", "citation_ids": ["1"]}
    ]})
    first = hit()
    second = Hit(chunk=first.chunk.model_copy(update={"source_id": "book-2"}), score=0.8)
    draft = ModelResponder(model).generate(question, [first, second])
    messages = model.invoke.call_args.args[0]
    assert (COMPARISON in messages[0][1]) == compare
    assert json.loads(messages[1][1])["question"] == question
    assert len(json.loads(messages[1][1])["passages"]) == 2
    assert draft.statements[0].citation_ids == ["1"]
