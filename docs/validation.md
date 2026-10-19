# Validation — 18 October 2026

Executed on Python 3.12.14 in a fresh virtual environment:

- Installed package with development dependencies successfully.
- `pytest -q`: **14 passed**.
- `ruff check .`: **all checks passed**.
- Demo CLI question returned an answer with a source title, author and section citation.
- Three-case demo evaluation completed (two supported questions and one refusal).
- Example catalog dry-run completed: one source, one chunk.

Tests cover source-preserving chunking, stable IDs, duplicate/empty documents, PDF page locators, EPUB sections, refusal without generation, rejected coverage, malformed output, invalid citations, API validation/authentication/error handling, dense-plus-keyword retrieval, and preservation of the active manifest after a failed upload. Pinecone/provider tests use mocks.

An initial EPUB test exposed an invalid fixture missing navigation metadata and the need to prefer the chapter heading over the document title; both were corrected before the passing run.

Not verified: live Pinecone provisioning/upsert/query, Nebius model availability/JSON adherence, real book extraction quality, live latency, semantic faithfulness, frontend or deployment. No provider credentials or scientific book corpus were supplied. Offline tests are not a live RAG evaluation result.
