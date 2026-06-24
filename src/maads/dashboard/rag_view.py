"""Build RAG status payloads for the dashboard."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from maads.rag import build_retrieval_query, rag_status, retrieve_for_state
from maads.state import CrispDMState

_DOMAIN_RAG_SUBSTEPS = ("1.1", "1.2", "1.3")


def parse_passage(hit: str) -> dict[str, str]:
    """Split ``[source] text`` into components."""
    m = re.match(r"^\[([^\]]+)\]\s*(.*)$", hit, re.DOTALL)
    if m:
        return {"source": m.group(1), "text": m.group(2).strip()}
    return {"source": "unknown", "text": hit.strip()}


def build_rag_view(state: CrispDMState | None, *, case_id: str = "") -> dict[str, Any]:
    """Snapshot of corpus, embedder, and passages for the active case."""
    cid = state.case_id if state is not None else case_id
    status = rag_status(cid) if cid else {
        "case_id": "",
        "corpus_files": [],
        "chunk_count": 0,
        "embedding_backend": "none",
        "embedding_model": None,
        "crewai_knowledge_enabled": False,
    }
    query = ""
    passages: list[dict[str, str]] = []
    if state is not None:
        query = build_retrieval_query(state)
        passages = [parse_passage(p) for p in retrieve_for_state(state, k=8)]

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "case_id": status["case_id"],
        "embedding_backend": status["embedding_backend"],
        "embedding_model": status["embedding_model"],
        "chunk_count": status["chunk_count"],
        "crewai_knowledge_enabled": status["crewai_knowledge_enabled"],
        "corpus_files": status["corpus_files"],
        "retrieval_query_preview": _preview(query, 500),
        "retrieved_passages": passages,
        "domain_substeps_using_rag": list(_DOMAIN_RAG_SUBSTEPS),
        "consumer_agent": "domain",
    }


def _preview(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
