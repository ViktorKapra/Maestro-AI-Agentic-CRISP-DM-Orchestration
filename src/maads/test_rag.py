"""Tests for maads.rag retrieval."""
from __future__ import annotations

from pathlib import Path

from maads.knowledge_setup import knowledge_corpus_paths
from maads.rag import RAGRetriever, build_retrieval_query, clear_rag_cache, retrieve_for_state
from maads.state import CrispDMState
from maads.config import load_case_config
from maads.paths import resolve_path


def test_knowledge_corpus_includes_case_and_experience(tmp_path: Path, monkeypatch):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "crisp-dm-excerpt.md").write_text("crisp", encoding="utf-8")
    (knowledge / "ml-problem-approach-notes.md").write_text("ml", encoding="utf-8")
    (knowledge / "titanic.md").write_text("ship", encoding="utf-8")
    (knowledge / "titanic_experience.md").write_text("prior run notes", encoding="utf-8")
    monkeypatch.setattr("maads.knowledge_setup._REPO_ROOT", tmp_path)

    paths = knowledge_corpus_paths("titanic")
    names = {p.name for p in paths}
    assert "titanic.md" in names
    assert "titanic_experience.md" in names


def test_rag_keyword_fallback(tmp_path: Path):
    corpus = tmp_path / "knowledge"
    corpus.mkdir()
    (corpus / "a.md").write_text(
        "Titanic survival prediction uses passenger features.\n\n"
        "Unrelated housing price regression notes.",
        encoding="utf-8",
    )
    rag = RAGRetriever(corpus)
    hits = rag.retrieve("Titanic survival passenger", k=2)
    assert hits
    assert "Titanic" in hits[0]


def test_retrieve_for_state_uses_case_config(monkeypatch, tmp_path: Path):
    cfg = load_case_config(resolve_path("configs/disaster_tweets.yaml"))
    state = CrispDMState.from_config(cfg)
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    for name in ("crisp-dm-excerpt.md", "ml-problem-approach-notes.md", "disaster_tweets.md"):
        src = resolve_path("knowledge") / name
        if src.exists():
            (knowledge / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr("maads.knowledge_setup._REPO_ROOT", tmp_path)
    clear_rag_cache()

    query = build_retrieval_query(state)
    assert "disaster_tweets" in query
    assert "target" in query

    passages = retrieve_for_state(state, k=3)
    assert isinstance(passages, list)


def test_rag_uses_ollama_embeddings_when_available(monkeypatch, tmp_path: Path):
    corpus = tmp_path / "knowledge"
    corpus.mkdir()
    (corpus / "a.md").write_text(
        "Alpha bravo charlie delta.\n\nEcho foxtrot golf hotel.",
        encoding="utf-8",
    )
    monkeypatch.setenv("MODEL", "ollama/gemma2:9b")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("EMBEDDINGS_OLLAMA_MODEL_NAME", "nomic-embed-text")

    def fake_embed(texts, backend):
        assert backend == "ollama"
        return [[1.0, 0.0] if "Alpha" in t else [0.0, 1.0] for t in texts]

    monkeypatch.setattr("maads.rag._embed_texts", fake_embed)
    rag = RAGRetriever(corpus)
    hits = rag.retrieve("Alpha bravo", k=1)
    assert hits and "Alpha" in hits[0]
