import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from quantum_primer.config import Settings
from quantum_primer.models import Chunk
from quantum_primer.providers import index_corpus


def test_ingestion_snapshot_and_atomic_failure(tmp_path):
    settings = Settings(
        _env_file=None,
        model_api_key=SecretStr("test"),
        pinecone_api_key=SecretStr("test"),
        chat_model="chat",
        embedding_model="embed",
        manifest_path=tmp_path / "index.json",
    )
    chunk = Chunk(id="one", text="source text", source_id="book", title="Book", locator="Page 1")
    embedder, pc, index = Mock(), Mock(), Mock()
    embedder.embed_query.return_value = [0.1, 0.2]
    embedder.embed_documents.return_value = [[0.1, 0.2]]
    pc.list_indexes.return_value.names.return_value = [settings.pinecone_index]
    pc.describe_index.return_value = SimpleNamespace(
        dimension=2, metric="cosine", status={"ready": True}, host="test"
    )
    pc.Index.return_value = index
    with (
        patch("quantum_primer.providers.embeddings", return_value=embedder),
        patch("quantum_primer.providers.pinecone", return_value=pc),
    ):
        result = index_corpus(settings, [chunk])
        original = settings.manifest_path.read_text()
        assert json.loads(original)["namespace"] == result["namespace"]
        assert index_corpus(settings, [chunk])["namespace"] == result["namespace"]
        index.upsert.side_effect = RuntimeError("upload failed")
        with pytest.raises(RuntimeError):
            index_corpus(settings, [chunk.model_copy(update={"text": "updated"})])
        assert settings.manifest_path.read_text() == original
        pc.describe_index.return_value.dimension = 3
        with pytest.raises(ValueError, match="mismatch"):
            index_corpus(settings, [chunk])
