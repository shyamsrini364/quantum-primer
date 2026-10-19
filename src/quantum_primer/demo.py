"""Deterministic software fixture, NOT a scientific corpus or live model."""

from .models import Chunk, Draft, Hit, Statement
from .retrieval import tokens

TEXT = "Quantum Primer is a beginner learning assistant. Its answers cite the source title, author and location. It can explain only material present in its indexed library."


class DemoRetriever:
    def search(self, question):
        if not set(tokens(question)) & {"primer", "citations", "sources", "library"}:
            return []
        return [
            Hit(
                chunk=Chunk(
                    id="demo",
                    text=TEXT,
                    source_id="demo-guide",
                    title="Quantum Primer demo guide",
                    author="Project fixture",
                    locator="Section: About this demo",
                    source_type="demo",
                ),
                score=1,
            )
        ]


class DemoResponder:
    def grade(self, question, hits):
        return question.lower().strip(" ?.") in {
            "what is quantum primer",
            "how do citations work",
            "what is in the demo library",
        }

    def generate(self, question, hits):
        return Draft(statements=[Statement(text=TEXT, citation_ids=["1"])])
