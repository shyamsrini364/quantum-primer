from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Chunk(BaseModel):
    id: str
    text: str
    source_id: str
    title: str
    author: str = "Unknown"
    locator: str
    source_type: str = "book"
    topics: list[str] = Field(default_factory=list)


class Hit(BaseModel):
    chunk: Chunk
    score: float


class Citation(BaseModel):
    id: str
    source_id: str
    title: str
    author: str
    locator: str


class Answer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    status: Literal["answered", "insufficient_context"]
    mode: Literal["demo", "live"]


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Please ask a question of at least three characters.")
        return value


class Grade(BaseModel):
    sufficient: bool
    reason: str


class Statement(BaseModel):
    text: str
    citation_ids: list[str] = Field(min_length=1)


class Draft(BaseModel):
    statements: list[Statement] = Field(min_length=1, max_length=8)
