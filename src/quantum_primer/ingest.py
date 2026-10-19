"""Manifest-driven ingestion; book bytes never enter the public repository."""

import hashlib
import json
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .models import Chunk


def clean(text: str) -> str:
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def sections(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        for number, page in enumerate(PdfReader(path).pages, 1):
            yield f"PDF page {number}", page.extract_text() or ""
    elif suffix == ".epub":
        from bs4 import BeautifulSoup
        from ebooklib import ITEM_DOCUMENT, epub

        book = epub.read_epub(str(path))
        for item_id, _ in book.spine:
            item = book.get_item_with_id(item_id)
            if item and item.get_type() == ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                heading = soup.find(["h1", "h2"]) or soup.find("title")
                label = heading.get_text(" ", strip=True) if heading else item.get_name()
                yield f"EPUB section: {label}", soup.get_text("\n", strip=True)
    elif suffix in {".md", ".txt"}:
        text = path.read_text(encoding="utf-8")
        for part in re.split(r"(?m)(?=^#{1,6} )", text):
            if part.strip():
                heading = part.splitlines()[0].lstrip("# ")[:150]
                yield f"Section: {heading}", part
    else:
        raise ValueError(f"Unsupported format: {suffix}")


def load_chunks(catalog_path: Path, chunk_size=650, overlap=80) -> list[Chunk]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require 0 <= overlap < chunk_size")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base", chunk_size=chunk_size, chunk_overlap=overlap
    )
    output, seen = [], set()
    for source in catalog["sources"]:
        source_id = source["id"]
        if source_id in seen:
            raise ValueError(f"Duplicate source id: {source_id}")
        seen.add(source_id)
        path = catalog_path.parent / source["path"]
        count = 0
        for locator, raw in sections(path):
            for text in splitter.split_text(clean(raw)):
                identity = f"{source_id}|{locator}|{count}|{text}"
                output.append(
                    Chunk(
                        id=hashlib.sha256(identity.encode()).hexdigest()[:32],
                        text=text,
                        source_id=source_id,
                        title=source["title"],
                        author=source.get("author", "Unknown"),
                        locator=locator,
                        source_type=source.get("source_type", "book"),
                        topics=source.get("topics", []),
                    )
                )
                count += 1
        if not count:
            raise ValueError(f"No extractable text in {path.name}; OCR scanned PDFs first")
    if not output:
        raise ValueError("The catalog has no text to index")
    return output
