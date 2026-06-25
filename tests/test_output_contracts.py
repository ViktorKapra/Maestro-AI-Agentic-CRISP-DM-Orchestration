"""Tests for agent output contract validation."""
from __future__ import annotations

from maads.output_contracts import validate_agent_output, _minimal_de_response


def test_validate_data_engineer_accepts_minimal_2_4():
    payload = _minimal_de_response()
    assert validate_agent_output("data_engineer", payload, substep="2.4") == []


def test_validate_rejects_debug_wrapper_comm_0010():
    wrapper = {
        "assignment_id": "debug-2.4",
        "agent": "data_engineer",
        "status": "FIXED",
        "summary": "The malformed JSON was corrected.",
        "state_updates": "",
        "evidence": [{"evidence_id": "x", "claim": "y", "source": "z", "method": "m"}],
        "decisions": [],
        "operations": [],
        "quality_findings": "",
        "validations": [],
        "artifacts": [],
        "assumptions": "",
        "risks": "",
        "blockers": "",
        "handoffs": [],
        "loop_signal": {
            "recommended": False,
            "contour": "NONE",
            "reason": None,
            "evidence_ids": [],
        },
        "completion_evidence": {
            "input_contract_valid": True,
            "required_outputs_present": True,
            "execution_succeeded": True,
            "artifacts_verified": True,
            "leakage_checks_passed": True,
            "reproducibility_checks_passed": True,
            "safe_for_downstream_use": True,
        },
    }
    errors = validate_agent_output("data_engineer", wrapper, substep="2.4")
    assert any("debug wrapper" in e for e in errors)
    assert any("FIXED" in e for e in errors)
    assert any("state_updates" in e for e in errors)
    assert any("quality_findings" in e for e in errors)


def test_validate_rejects_wrong_assignment_id():
    payload = _minimal_de_response(substep="2.4")
    payload["assignment_id"] = "2.2"
    errors = validate_agent_output("data_engineer", payload, substep="2.4")
    assert any("assignment_id" in e for e in errors)
