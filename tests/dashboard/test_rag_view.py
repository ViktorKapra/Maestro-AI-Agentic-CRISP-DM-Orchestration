"""Tests for dashboard RAG view."""
from __future__ import annotations

from maads.config import load_case_config
from maads.dashboard.rag_view import build_rag_view, parse_passage
from maads.paths import resolve_path
from maads.state import CrispDMState


def test_parse_passage():
    hit = "[disaster_tweets.md] Binary classification on tweet text."
    parsed = parse_passage(hit)
    assert parsed["source"] == "disaster_tweets.md"
    assert "Binary" in parsed["text"]


def test_build_rag_view_for_case():
    cfg = load_case_config(resolve_path("configs/disaster_tweets.yaml"))
    state = CrispDMState.from_config(cfg)
    view = build_rag_view(state)
    assert view["case_id"] == "disaster_tweets"
    assert view["chunk_count"] > 0
    assert view["corpus_files"]
    assert view["consumer_agent"] == "domain"
    assert view["explicit_rag_enabled"] is True
    assert view["crewai_knowledge_enabled"] is False
    assert "disaster_tweets" in view["retrieval_query_preview"]
    assert isinstance(view["retrieved_passages"], list)
