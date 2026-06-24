"""Retrieval-augmented generation over the ``knowledge/`` markdown corpus.

Used by the Domain Expert task prompts (explicit passages in ``domain_corpus``)
and complemented by CrewAI ``TextFileKnowledgeSource`` on the domain agent.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from maads.knowledge_setup import knowledge_corpus_paths, resolve_embedder_config
from maads.state import CrispDMState

_log = logging.getLogger(__name__)

_DEFAULT_OPENAI_EMBED_MODEL = "text-embedding-3-small"
_CHUNK_MAX_CHARS = 1200


@dataclass(frozen=True)
class _Chunk:
    source: str
    text: str


@dataclass
class _Index:
    chunks: list[_Chunk]
    vectors: list[list[float]] | None
    backend: str


def clear_rag_cache() -> None:
    """Drop cached retrievers (e.g. after Loop D appends experience)."""
    _retriever_for.cache_clear()


@lru_cache(maxsize=16)
def _retriever_for(case_id: str) -> "RAGRetriever":
    return RAGRetriever(knowledge_corpus_paths(case_id))


def retrieve_for_state(state: CrispDMState, *, k: int = 6) -> list[str]:
    """Return top-k RAG passages for a CRISP-DM state."""
    query = build_retrieval_query(state)
    return _retriever_for(state.case_id).retrieve(query, k=k)


def rag_status(case_id: str) -> dict[str, Any]:
    """Index metadata for dashboards and observability."""
    paths = knowledge_corpus_paths(case_id)
    if not paths:
        return {
            "case_id": case_id,
            "corpus_files": [],
            "chunk_count": 0,
            "embedding_backend": "none",
            "embedding_model": None,
            "crewai_knowledge_enabled": False,
        }
    retriever = RAGRetriever(paths)
    embed_cfg = resolve_embedder_config() or {}
    model = None
    if retriever.backend == "ollama":
        model = (embed_cfg.get("config") or {}).get("model_name")
    elif retriever.backend == "openai":
        model = (os.getenv("OPENAI_EMBED_MODEL") or _DEFAULT_OPENAI_EMBED_MODEL).strip()
    return {
        "case_id": case_id,
        "corpus_files": [_corpus_file_entry(p, case_id) for p in paths],
        "chunk_count": retriever.chunk_count,
        "embedding_backend": retriever.backend,
        "embedding_model": model,
        "crewai_knowledge_enabled": True,
    }


def _corpus_file_entry(path: Path, case_id: str) -> dict[str, Any]:
    name = path.name
    if name.endswith("_experience.md"):
        role = "experience"
    elif name == f"{case_id}.md":
        role = "case"
    else:
        role = "shared"
    stat = path.stat()
    return {
        "name": name,
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "role": role,
    }


def build_retrieval_query(state: CrispDMState) -> str:
    """Build a retrieval query from case config and any DU reports in state."""
    cfg = state.config
    parts = [
        cfg.case_id,
        cfg.problem_type,
        cfg.target_column,
        cfg.evaluation_metric,
        cfg.problem_statement or "",
        cfg.kaggle_competition or "",
    ]
    for report in (
        state.du.data_description_report,
        state.du.data_quality_report,
        state.du.data_exploration_report,
    ):
        if report:
            parts.append(json.dumps(report, default=str)[:2000])
    return " ".join(p for p in parts if p)


class RAGRetriever:
    """Embed or keyword-search paragraph chunks from markdown knowledge files."""

    def __init__(self, corpus_paths: list[Path] | Path | None = None) -> None:
        if corpus_paths is None:
            paths = knowledge_corpus_paths("")
        elif isinstance(corpus_paths, Path):
            if corpus_paths.is_dir():
                paths = sorted(corpus_paths.glob("*.md"))
            else:
                paths = [corpus_paths]
        else:
            paths = list(corpus_paths)
        self._paths = [Path(p) for p in paths if Path(p).exists()]
        self._index = self._build_index()

    @property
    def backend(self) -> str:
        return self._index.backend

    @property
    def chunk_count(self) -> int:
        return len(self._index.chunks)

    @property
    def corpus_paths(self) -> list[Path]:
        return list(self._paths)

    def retrieve(self, query: str, k: int = 4) -> list[str]:
        """Return top-k passages formatted as ``[source] text``."""
        if not query.strip() or not self._index.chunks:
            return []
        k = max(1, k)
        if self._index.vectors:
            ranked = self._rank_by_embedding(query, k)
        else:
            ranked = self._rank_by_keywords(query, k)
        return [f"[{c.source}] {c.text}" for c in ranked]

    def _build_index(self) -> _Index:
        chunks: list[_Chunk] = []
        for path in self._paths:
            text = path.read_text(encoding="utf-8")
            for para in _split_paragraphs(text):
                chunks.append(_Chunk(source=path.name, text=para))
        backend, vectors = _embed_chunks([c.text for c in chunks])
        return _Index(chunks=chunks, vectors=vectors, backend=backend)

    def _rank_by_embedding(self, query: str, k: int) -> list[_Chunk]:
        assert self._index.vectors is not None
        q_vecs = _embed_texts([query], self._index.backend)
        if not q_vecs:
            return self._rank_by_keywords(query, k)
        q_vec = q_vecs[0]
        scored: list[tuple[float, int]] = []
        for i, vec in enumerate(self._index.vectors):
            scored.append((_cosine(q_vec, vec), i))
        scored.sort(key=lambda x: -x[0])
        return [self._index.chunks[i] for _, i in scored[:k]]

    def _rank_by_keywords(self, query: str, k: int) -> list[_Chunk]:
        terms = {t.lower() for t in re.findall(r"[a-zA-Z0-9_]{3,}", query)}
        if not terms:
            return self._index.chunks[:k]
        scored: list[tuple[int, int]] = []
        for i, chunk in enumerate(self._index.chunks):
            lower = chunk.text.lower()
            score = sum(1 for t in terms if t in lower)
            if score:
                scored.append((score, i))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return self._index.chunks[:k]
        return [self._index.chunks[i] for _, i in scored[:k]]


def _split_paragraphs(text: str) -> list[str]:
    out: list[str] = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if len(para) <= _CHUNK_MAX_CHARS:
            out.append(para)
            continue
        for i in range(0, len(para), _CHUNK_MAX_CHARS):
            piece = para[i : i + _CHUNK_MAX_CHARS].strip()
            if piece:
                out.append(piece)
    return out


def _embed_chunks(texts: list[str]) -> tuple[str, list[list[float]] | None]:
    if not texts:
        return "none", None
    ollama_cfg = resolve_embedder_config()
    if ollama_cfg is not None:
        vecs = _embed_texts(texts, "ollama")
        if vecs:
            return "ollama", vecs
        _log.warning("Ollama embeddings failed; falling back to keyword RAG")
    if (os.getenv("OPENAI_API_KEY") or "").strip():
        vecs = _embed_texts(texts, "openai")
        if vecs:
            return "openai", vecs
        _log.warning("OpenAI embeddings failed; falling back to keyword RAG")
    return "keyword", None


def _embed_texts(texts: list[str], backend: str) -> list[list[float]] | None:
    if not texts:
        return []
    try:
        if backend == "ollama":
            return _embed_ollama(texts)
        if backend == "openai":
            return _embed_openai(texts)
    except Exception as exc:  # noqa: BLE001 — degrade to keyword search
        _log.debug("embedding backend %s failed: %s", backend, exc)
    return None


def _embed_ollama(texts: list[str]) -> list[list[float]]:
    cfg = resolve_embedder_config() or {}
    model = (cfg.get("config") or {}).get("model_name") or "nomic-embed-text"
    try:
        import ollama

        host = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        client = ollama.Client(host=host)
        resp = client.embed(model=model, input=texts)
        embeddings = resp.embeddings
        if embeddings and len(embeddings) == len(texts):
            return [list(map(float, e)) for e in embeddings]
    except Exception:
        pass
    return _embed_ollama_http(texts, model)


def _embed_ollama_http(texts: list[str], model: str) -> list[list[float]]:
    cfg = resolve_embedder_config() or {}
    url = (cfg.get("config") or {}).get("url") or "http://localhost:11434/api/embeddings"
    out: list[list[float]] = []
    for text in texts:
        body = json.dumps({"model": model, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        embedding = payload.get("embedding")
        if not embedding:
            raise ValueError(f"no embedding in Ollama response from {url}")
        out.append([float(x) for x in embedding])
    return out


def _embed_openai(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    model = (os.getenv("OPENAI_EMBED_MODEL") or _DEFAULT_OPENAI_EMBED_MODEL).strip()
    client = OpenAI()
    # OpenAI accepts batches; chunk to stay within limits
    batch_size = 64
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embeddings.create(model=model, input=batch)
        vectors.extend([list(d.embedding) for d in resp.data])
    return vectors


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def ensure_embedding_model_available() -> str | None:
    """Pull the default Ollama embedding model when using local embeddings.

    Returns a warning message when the model could not be verified, else None.
    """
    cfg = resolve_embedder_config()
    if cfg is None:
        return None
    model = (cfg.get("config") or {}).get("model_name") or "nomic-embed-text"
    try:
        import ollama

        host = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        client = ollama.Client(host=host)
        client.show(model)
        return None
    except Exception:
        try:
            import ollama

            host = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
            client = ollama.Client(host=host)
            _log.info("Pulling Ollama embedding model %s …", model)
            client.pull(model)
            return None
        except Exception as exc:
            return (
                f"Could not verify or pull Ollama embedding model '{model}': {exc}. "
                f"Run: ollama pull {model}"
            )
