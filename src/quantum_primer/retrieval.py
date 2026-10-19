import json
import re

from rank_bm25 import BM25Okapi

from .models import Chunk, Hit
from .providers import embeddings, pinecone


def tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower())


SEARCH_STOP_WORDS = set("""a an the and or but if in on at to of for from with by as
is are was were be been being it its this that these those i me my we our you your
he she his her they their them what which who how why when where do does did can
could would should will may might have has had not no than then also so such
explain describe tell give use using please simple simply plain language beginner
example examples term terms book books author authors passage passages supported
proposed role one""".split())


def search_terms(text):
    """Keep subject words from being swamped by repeated presentation instructions."""
    return list(dict.fromkeys(t for t in tokens(text) if t not in SEARCH_STOP_WORDS))


class HybridRetriever:
    """Pinecone dense + local BM25, combined with reciprocal rank fusion."""

    def __init__(self, settings):
        manifest = json.loads(settings.manifest_path.read_text(encoding="utf-8"))
        for field, expected in [
            ("index", settings.pinecone_index),
            ("embedding_model", settings.embedding_model),
            ("base_url", settings.model_base_url),
        ]:
            if manifest[field] != expected:
                raise ValueError(
                    f"Manifest {field} differs from settings; re-ingest into a new snapshot"
                )
        self.settings, self.manifest = settings, manifest
        self.chunks = [Chunk.model_validate(row) for row in manifest["chunks"]]
        self.by_id = {c.id: c for c in self.chunks}
        self.bm25 = BM25Okapi([tokens(c.text) for c in self.chunks])
        self.embedder = embeddings(settings)
        pc = pinecone(settings)
        self.index = pc.Index(host=pc.describe_index(settings.pinecone_index).host)

    def query_scope(self, question):
        question = question.translate(str.maketrans({"“": '"', "”": '"'}))
        normalized = " " + " ".join(tokens(question)) + " "
        source_ids, titles, author_terms = set(), set(), set()
        for chunk in self.chunks:
            title = " ".join(tokens(chunk.title.split(":", 1)[0]))
            # Single-word titles need an explicit reference, not a verb such as
            # "How can I optimize sleep?".
            explicit = f" {title} " in normalized and (
                len(title.split()) > 1 or f" in {title} " in normalized
                or f'"{title}"' in question.lower()
                or bool(re.search(r"\b(compare|comparison|versus|vs)\b", normalized))
            )
            if explicit:
                source_ids.add(chunk.source_id)
                titles.add(title)
                author_terms.update(
                    t for t in tokens(chunk.author)
                    if len(t) > 1 and t not in {"and", "with", "dr", "md", "unknown"}
                )
        search_text = normalized
        for title in sorted(titles, key=len, reverse=True):
            search_text = search_text.replace(f" {title} ", " ")
        search_text = search_text.strip() if source_ids else question
        if source_ids:
            search_text = " ".join(t for t in tokens(search_text) if t not in author_terms)
        sources = {c.source_id: c.title for c in self.chunks if c.source_id in source_ids}
        return sources, search_text or question

    def named_sources(self, question):
        return self.query_scope(question)[0]

    def search(self, question):
        sources, search_text = self.query_scope(question)
        vector = self.embedder.embed_query(search_text or question)
        if len(vector) != self.manifest["dimension"]:
            raise ValueError("Query embedding dimension changed; rebuild the index")
        scores = self.bm25.get_scores(search_terms(search_text))
        # Rank each requested book independently so one cannot crowd out another.
        groups = [self._rank(vector, scores, {sid}) for sid in sorted(sources)] if sources else [
            self._rank(vector, scores, set())
        ]
        limit = max(self.settings.context_k, len(groups))
        selected = []
        for rank in range(limit):
            for group in groups:
                if rank < len(group):
                    selected.append(group[rank])
                    if len(selected) == limit:
                        return selected
        return selected

    def _rank(self, vector, scores, source_ids):
        query_args = dict(
            vector=vector, namespace=self.manifest["namespace"], top_k=self.settings.top_k
        )
        if source_ids:
            query_args["filter"] = {"source_id": {"$in": sorted(source_ids)}}
        result = self.index.query(**query_args)
        dense = [
            m.id
            for m in result.matches
            if m.score >= self.settings.min_dense_score and m.id in self.by_id
            and (not source_ids or self.by_id[m.id].source_id in source_ids)
        ]
        lexical = [
            self.chunks[i].id
            for i in sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            if scores[i] > 0
            and (not source_ids or self.chunks[i].source_id in source_ids)
        ][: self.settings.top_k]
        fused = {}
        for ranking in [dense, lexical]:
            for rank, chunk_id in enumerate(ranking, 1):
                fused[chunk_id] = fused.get(chunk_id, 0) + 1 / (60 + rank)
        return [
            Hit(chunk=self.by_id[cid], score=score)
            for cid, score in sorted(fused.items(), key=lambda item: item[1], reverse=True)[
                : self.settings.context_k
            ]
        ]
