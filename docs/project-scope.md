# Scope and decisions

Source: the supplied “RAG application ideas” planning conversation, final Quantum Biology decision, and the Week 2 handout read on 18 October 2026.

## One-liner

Quantum Primer helps curious beginners ask introductory questions about quantum biology and Jack Kruse's ideas from a personal collection of books, through a web-chat API with cited answers, targeting 90% manually assessed faithfulness. This is a target, not a result.

## Framework

| Field | Initial implementation |
|---|---|
| Use case | Beginner explanations and source-grounded questions; API for a future web app. |
| Corpus | User-supplied English books/articles; actual titles and count still to be supplied. PDF, EPUB, Markdown and plain text. |
| Cleaning | Whitespace and line-break hyphenation; section/page locators. OCR and automatic repeated boilerplate removal deferred. |
| Freshness | Manual full-catalog ingestion; immutable snapshot namespace; restart API after rebuilding. |
| Chunking and embeddings | Section/page-bounded 650-token chunks, 80-token overlap; configurable OpenAI-compatible embedding provider. Model ID selected by user. |
| Retrieval | Pinecone dense + local BM25, reciprocal rank fusion, 8 candidates per channel, 4 final contexts. |
| Generation | LangGraph retrieve → grade → generate/refuse; structured statements and validated citation IDs. |
| Quality | 15-question live evaluation template; human faithfulness review needed. |
| Latency | Proposed p95 <15 seconds; live measurement pending. |

## Decisions preserved

- Focus on Quantum Primer, not the earlier athlete/relationship ideas.
- Use Pinecone, LangChain and LangGraph.
- Cite sources, with no imposed evidence-tier taxonomy.
- Support a beginner app with sample questions.
- Start with a working backend and explicit insufficient-context path.

## Deliberate implementation choices

- Hybrid uses local BM25 plus Pinecone dense retrieval, avoiding a separate sparse service for this small personal corpus.
- A neural reranker is deferred until evaluation shows whether it helps.
- Demo mode is deterministic, not a substitute corpus or a simulated live-quality result.
- The model prompt attributes claims and avoids personalized medical prescriptions while still explaining source content.
- No GitHub remote or deployment was selected. A local Git repository and portable ZIP are supplied.

## API references checked

- https://reference.langchain.com/python/langgraph/graph/state/StateGraph
- https://sdk.pinecone.io/python/how-to/vectors/upsert-and-query.html
- https://api.tokenfactory.nebius.com/docs
- https://github.com/nebius/nebius-physical-ai/blob/main/docs/workbench/token-factory.md

Pinecone is intentionally pinned to the tested 7.x vector API. Newer SDKs introduce different APIs; do not upgrade the major version without adapting and testing the provider layer.
