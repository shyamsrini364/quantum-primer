# Build log — 18 October 2026

## User coding prompt
“Hey can you go through this planning conversation and start to build out the python Repo for this project”

## Inputs read
- Supplied “RAG application ideas” conversation; final scope is Quantum Primer.
- Linked Week 2 project handout; no sample solution repositories were read.

## Initial implementation
- Created Python package, CLI and FastAPI interface.
- Added PDF/EPUB/Markdown/text loading and token-aware chunking with source locations.
- Added provider-configurable embeddings/generation and Pinecone 7.x adapters.
- Added immutable corpus snapshots to avoid retrieving old chunks after edits.
- Combined Pinecone dense retrieval and local BM25 through reciprocal rank fusion.
- Built LangGraph coverage gate, generation and refusal paths.
- Enforced structured statements with valid source IDs, without claiming this verifies semantic faithfulness.
- Added credential-free fixture mode, sample questions and evaluation templates.
- Added private-data Git exclusions and server-side API key support.

## Validation
See `validation.md` for executed checks. Live provider calls and real-book evaluation remain pending because no keys or book corpus were supplied.

## Next iteration
Supply the corpus and model IDs, run ingestion, inspect retrieved context, label expected sources, and evaluate before tuning thresholds or adding a reranker. Then connect a separately built frontend using `frontend-handoff.md`.
