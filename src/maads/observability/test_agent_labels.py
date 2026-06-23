"""Tests for agent label resolution in traces."""
from __future__ import annotations

from maads.observability.agent_labels import format_agent_label, resolve_maads_agent_id
from maads.observability.render.narrative import render_narrative
from maads.observability.schema import TraceEvent, TraceRun


def test_resolve_maads_agent_from_maads_agent_key():
    assert resolve_maads_agent_id({"maads_agent": "domain"}) == "domain"


def test_format_agent_label_includes_role_and_id():
    label = format_agent_label({"maads_agent": "pm"})
    assert "Project Manager" in label
    assert "`pm`" in label


def test_narrative_crew_end_uses_maads_agent():
    run = TraceRun(
        run_id="r1",
        case_id="titanic",
        events=[
            TraceEvent(
                id="e1",
                type="crew.end",
                name="CrewKickoffCompleted",
                attributes={"maads_agent": "domain", "substep": "1.1"},
            ),
        ],
    )
    text = render_narrative(run)
    assert "Domain Knowledge Expert" in text
    assert "`domain`" in text
    assert "`?`" not in text
