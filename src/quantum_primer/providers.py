import hashlib
import json
import os
from pathlib import Path

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec


def embeddings(settings):
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.model_api_key.get_secret_value(),
        base_url=settings.model_base_url,
        check_embedding_ctx_length=False,
        request_timeout=45,
        max_retries=2,
    )


def chat(settings):
    return ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.model_api_key.get_secret_value(),
        base_url=settings.model_base_url,
        temperature=0,
        timeout=45,
        max_retries=2,
    )


def pinecone(settings):
    return Pinecone(api_key=settings.pinecone_api_key.get_secret_value())


def index_corpus(settings, chunks):
    """Build an immutable snapshot; switch local manifest only after successful upserts.

    Old namespaces are retained for manual cleanup/rollback. Pinecone is eventually
    consistent: wait for vectors to become searchable before serving a new snapshot.
    """
    settings.require_live()
    embedder, pc = embeddings(settings), pinecone(settings)
    probe = embedder.embed_query("dimension probe")
    dimension = len(probe)
    if settings.pinecone_index not in pc.list_indexes().names():
        pc.create_index(
            name=settings.pinecone_index,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud=settings.pinecone_cloud, region=settings.pinecone_region),
        )
    description = pc.describe_index(settings.pinecone_index)
    if description.dimension != dimension or description.metric != "cosine":
        raise ValueError("Index dimension/metric mismatch; use a new cosine index for this model")
    if not description.status["ready"]:
        raise RuntimeError("Pinecone index is provisioning. Retry ingestion when it is ready.")
    rows = [chunk.model_dump() for chunk in chunks]
    digest = hashlib.sha256(
        json.dumps(
            [rows, settings.embedding_model, settings.model_base_url], sort_keys=True
        ).encode()
    ).hexdigest()[:16]
    namespace = f"{settings.namespace_prefix}-{digest}"
    index = pc.Index(host=description.host)
    for start in range(0, len(chunks), 64):
        batch = chunks[start : start + 64]
        vectors = embedder.embed_documents([c.text for c in batch])
        if len(vectors) != len(batch) or any(len(v) != dimension for v in vectors):
            raise ValueError("Embedding provider returned inconsistent dimensions or count")
        index.upsert(
            namespace=namespace,
            vectors=[
                {"id": c.id, "values": vector, "metadata": {"source_id": c.source_id}}
                for c, vector in zip(batch, vectors, strict=True)
            ],
        )
    payload = {
        "namespace": namespace,
        "index": settings.pinecone_index,
        "embedding_model": settings.embedding_model,
        "base_url": settings.model_base_url,
        "dimension": dimension,
        "chunks": rows,
    }
    target = Path(settings.manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, target)
    return {"chunks": len(chunks), "namespace": namespace}
