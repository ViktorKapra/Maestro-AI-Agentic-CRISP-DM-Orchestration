"""Tests for agent–LLM communication observability."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maads.observability.communication_exporter import write_communication_artifacts
from maads.observability.llm_communications import (
    LLMCommunicationRegistry,
    build_communications_summary,
    llm_io_mode,
    reset_communication_registry,
    serialize_messages,
    serialize_response,
)
from maads.observability.render.communications import render_communications


@pytest.fixture(autouse=True)
def fresh_registry():
    reset_communication_registry()
    yield
    reset_communication_registry()


def test_open_enrich_close_merges_maads_and_provider():
    reg = reset_communication_registry()
    comm_id = reg.open_record(
        run_id="run-1",
        case_id="titanic",
        substep="1.1",
        agent_name="domain",
        role="Domain Expert",
        model="gpt-4o-mini",
        maads={
            "task_description": "Do domain work",
            "instruction": "Analyze",
            "schema_hint": "{}",
            "state_view": '{"phase": 1}',
        },
        trace_event_id="evt_crew_start",
    )
    reg.enrich_start(
        call_id="call-abc",
        agent_role="Domain Expert",
        messages=[{"role": "user", "content": "hello"}],
        trace_event_id="evt_llm_start",
    )
    reg.enrich_end(
        call_id="call-abc",
        response='{"ok": true}',
        usage={"total_tokens": 99, "prompt_tokens": 50, "completion_tokens": 49},
        finish_reason="stop",
        trace_event_id="evt_llm_end",
    )
    rec = reg.close_record(
        comm_id,
        raw_response='{"ok": true}',
        parsed_json={"ok": True},
        parse_ok=True,
        tokens={"total": 99},
        trace_event_id="evt_crew_end",
        duration_ms=1200.0,
    )
    assert rec is not None
    assert rec.call_id == "call-abc"
    assert rec.maads["task_description"] == "Do domain work"
    assert rec.provider["messages"] == [{"role": "user", "content": "hello"}]
    assert rec.outcome["parsed_json"] == {"ok": True}
    assert rec.tokens["total"] == 99
    assert rec.trace_event_ids["llm.start"] == "evt_llm_start"


def test_call_id_links_listener_before_close():
    reg = reset_communication_registry()
    comm_id = reg.open_record(
        run_id="r",
        case_id=None,
        substep="2.1",
        agent_name="data_engineer",
        maads={"task_description": "prep"},
    )
    linked = reg.enrich_start(call_id="cid-1", messages=[{"role": "system", "content": "x"}])
    assert linked == comm_id
    reg.enrich_end(call_id="cid-1", response="done")
    rec = reg.get_record(comm_id)
    assert rec is not None
    assert rec.provider["raw_response"] == "done"


def test_truncation_preview_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE_LLM_IO", "preview")
    assert llm_io_mode() == "preview"
    long_text = "x" * 3000
    result = serialize_response(long_text)
    assert isinstance(result, dict)
    assert result["_truncated"] is True
    assert result["len"] == 3000


def test_truncation_off_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE_LLM_IO", "off")
    reg = reset_communication_registry()
    comm_id = reg.open_record(
        run_id="r",
        case_id=None,
        substep="1.1",
        agent_name="pm",
        maads={"task_description": "secret prompt text"},
    )
    rec = reg.close_record(comm_id, raw_response="secret response", parse_ok=True)
    assert rec is not None
    assert "task_description" not in rec.maads
    assert rec.maads["task_description_len"] == len("secret prompt text")
    assert "raw_response" not in rec.outcome
    assert rec.outcome["raw_response_len"] == len("secret response")


def test_render_communications_markdown():
    reg = reset_communication_registry()
    comm_id = reg.open_record(
        run_id="r",
        case_id="titanic",
        substep="1.1",
        agent_name="domain",
        model="test-model",
        maads={"task_description": "TASK BODY"},
    )
    reg.enrich_start(messages=[{"role": "user", "content": "hi"}])
    reg.close_record(
        comm_id,
        raw_response='{"a": 1}',
        parsed_json={"a": 1},
        parse_ok=True,
        duration_ms=500.0,
        tokens={"total": 10},
    )
    md = render_communications(reg.all_records())
    assert "# Agent–LLM Communications" in md
    assert "domain @ 1.1" in md
    assert "TASK BODY" in md
    assert "Provider messages" in md
    assert '"a": 1' in md


def test_write_communication_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MAADS_WRITE_RENDERS", "1")
    reg = reset_communication_registry()
    comm_id = reg.open_record(
        run_id="r",
        case_id="titanic",
        substep="1.1",
        agent_name="pm",
        maads={"task_description": "plan"},
    )
    reg.close_record(comm_id, raw_response="{}", parsed_json={}, parse_ok=True)
    out = tmp_path / "trace"
    write_communication_artifacts(reg, out)
    collected = tmp_path / "collected" / "communications.jsonl"
    assert collected.is_file()
    assert (out / "communications.jsonl").is_file()
    assert (out / "communications.md").is_file()
    summary = tmp_path / "derived" / "communications_summary.json"
    assert summary.is_file()
    lines = collected.read_text().strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["agent_name"] == "pm"
    summary_data = json.loads(summary.read_text())
    assert summary_data["turn_count"] == 1
    assert summary_data["by_agent"]["pm"]["turns"] == 1


def test_build_communications_summary():
    reg = reset_communication_registry()
    c1 = reg.open_record(
        run_id="r", case_id=None, substep="1.1", agent_name="pm",
        maads={"task_description": "abc"},
    )
    reg.close_record(c1, raw_response="x", parse_ok=False, tokens={"total": 5}, duration_ms=100.0)
    summary = build_communications_summary(reg.all_records())
    assert summary["turn_count"] == 1
    assert summary["parse_failures"] == 1
    assert summary["by_agent"]["pm"]["prompt_chars"] == 3


def test_resolve_comm_id_prefers_agent_role_with_multiple_open():
    reg = reset_communication_registry()
    de_id = reg.open_record(
        run_id="r",
        case_id="titanic",
        substep="2.4",
        agent_name="data_engineer",
        role="Senior Data Engineer",
        maads={"task_description": "de task"},
    )
    dev_id = reg.open_record(
        run_id="r",
        case_id="titanic",
        substep="2.4",
        agent_name="developer",
        role="Senior Developer & On-Call Debugger",
        maads={"task_description": "debug task"},
        parent_comm_id=de_id,
    )
    linked = reg.enrich_start(
        call_id="developer-call-1",
        agent_role="Senior Developer & On-Call Debugger",
        messages=[{"role": "user", "content": "debug"}],
    )
    assert linked == dev_id
    de_linked = reg.enrich_start(
        call_id="de-call-1",
        agent_role="Senior Data Engineer",
        messages=[{"role": "user", "content": "de"}],
    )
    assert de_linked == de_id
    assert de_id != dev_id


def test_close_record_schema_fields():
    reg = reset_communication_registry()
    comm_id = reg.open_record(
        run_id="r",
        case_id=None,
        substep="2.4",
        agent_name="data_engineer",
        maads={"task_description": "x"},
    )
    rec = reg.close_record(
        comm_id,
        raw_response="{}",
        parsed_json={},
        parse_ok=False,
        json_valid=True,
        schema_ok=False,
        schema_errors=["assignment_id: expected '2.4'"],
        repair={"kind": "developer_llm", "requesting_agent": "data_engineer", "succeeded": False},
    )
    assert rec is not None
    assert rec.outcome["json_valid"] is True
    assert rec.outcome["schema_ok"] is False
    assert rec.outcome["parse_ok"] is False


def test_apply_patches_replaces_agents_run_json_task(monkeypatch: pytest.MonkeyPatch):
    """agents imports run_json_task before auto_enable; patch must update agents too."""
    monkeypatch.setenv("MAADS_TRACE", "1")
    import maads.agents as agents_mod
    import maads.crew as crew_mod
    from maads.observability.patches import apply_patches

    assert agents_mod.run_json_task is crew_mod.run_json_task
    apply_patches()
    assert getattr(crew_mod.run_json_task, "_maads_traced", False)
    assert agents_mod.run_json_task is crew_mod.run_json_task
    assert getattr(agents_mod.run_json_task, "_maads_traced", False)


@patch("maads.crew.Crew")
def test_traced_run_json_task_captures_communication(MockCrew, monkeypatch: pytest.MonkeyPatch):
    """Patch + registry path with mocked CrewAI kickoff."""
    monkeypatch.setenv("MAADS_TRACE", "1")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")

    from maads.config import load_case_config
    from maads.observability.collector import get_collector, reset_collector
    from maads.observability.patches import apply_patches
    from maads.state import CrispDMState

    from maads.paths import repo_root

    repo = repo_root()
    cfg = load_case_config(repo / "configs" / "titanic.yaml")

    reset_collector()
    reset_communication_registry()
    register_listener = __import__(
        "maads.observability.crewai_listener", fromlist=["register_crewai_listener"]
    ).register_crewai_listener
    register_listener()
    apply_patches()

    mock_output = MagicMock()
    mock_output.token_usage.total_tokens = 42
    mock_output.__str__ = lambda self: '{"action": "advance"}'
    MockCrew.return_value.kickoff.return_value = mock_output

    state = CrispDMState.from_config(cfg)
    state.substep = "1.1"
    get_collector().start_run("titanic")

    import maads.agents as agents_mod

    result = agents_mod.run_json_task("pm", "decide next step", state, "")
    assert result == {"action": "advance"}

    from maads.observability.llm_communications import get_communication_registry

    records = get_communication_registry().all_records()
    assert len(records) == 1
    assert records[0].agent_name == "pm"
    assert records[0].outcome["parse_ok"] is True
    assert "task_description" in records[0].maads


def _unwrap_traced(fn):
    while getattr(fn, "_maads_traced", False):
        fn = fn.__wrapped__
    return fn


def _restore_crew_task_impls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Undo conftest codegen stub and any prior traced wrappers for a fresh patch."""
    import maads.crew as crew_mod

    monkeypatch.setattr(crew_mod, "run_json_task", _unwrap_traced(crew_mod.run_json_task))
    monkeypatch.setattr(
        crew_mod,
        "run_text_task",
        lambda agent_name, instruction, state, expected_output="The requested output.": crew_mod._kickoff(
            agent_name, instruction, state, "", expected_output, json_enforced=False,
        ),
    )


@patch("maads.crew.Crew")
def test_traced_run_text_task_records_codegen_shape(MockCrew, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE", "1")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")

    from maads.config import load_case_config
    from maads.observability.collector import get_collector, reset_collector
    from maads.observability.patches import apply_patches
    from maads.state import CrispDMState

    from maads.paths import repo_root

    repo = repo_root()
    cfg = load_case_config(repo / "configs" / "titanic.yaml")

    reset_collector()
    reset_communication_registry()
    _restore_crew_task_impls(monkeypatch)
    register_listener = __import__(
        "maads.observability.crewai_listener", fromlist=["register_crewai_listener"]
    ).register_crewai_listener
    register_listener()
    apply_patches()

    code_json = '{"code": "import json\\nprint(json.dumps({\\"n\\": 1}))"}'
    mock_output = MagicMock()
    mock_output.token_usage.total_tokens = 17
    mock_output.__str__ = lambda self: code_json
    MockCrew.return_value.kickoff.return_value = mock_output

    state = CrispDMState.from_config(cfg)
    state.substep = "4.3"
    get_collector().start_run("titanic")

    import maads.crew as crew_mod

    result = crew_mod.run_text_task("data_scientist", "write code", state)
    assert result == code_json

    from maads.observability.llm_communications import get_communication_registry

    records = get_communication_registry().all_records()
    assert len(records) == 1
    outcome = records[0].outcome
    assert outcome["response_shape"] == "json_code_wrapper"
    assert outcome["json_valid"] is True
    assert outcome["parse_ok"] is True
    assert outcome["parsed_json"] is not None
