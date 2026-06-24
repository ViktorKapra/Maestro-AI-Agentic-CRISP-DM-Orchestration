"""Tests for YAML/md prompt loader."""
from __future__ import annotations

import yaml

from maads.prompts.loader import load_agent_prompts, load_task_scaffolds, task_scaffold


def test_load_agent_prompts_all_five_agents():
    prompts = load_agent_prompts()
    assert set(prompts) == {
        "pm",
        "domain",
        "data_engineer",
        "data_scientist",
        "developer",
    }
    for name, persona in prompts.items():
        assert persona["role"]
        assert persona["goal"]
        assert len(persona["backstory"]) > 100, f"{name} backstory too short"


def test_domain_role_has_dataset_placeholder():
    domain = load_agent_prompts()["domain"]
    assert "{dataset_name}" in domain["role"]
    assert "{dataset_name}" in domain["goal"]


def test_task_scaffolds_have_placeholders():
    state_only = task_scaffold("state_only")
    assert "{state_view}" in state_only["description"]
    assert "{instruction}" in state_only["description"]

    substep = task_scaffold("substep_json")
    assert "{substep}" in substep["description"]
    assert "{schema_hint}" in substep["description"]

    all_kinds = load_task_scaffolds()
    assert set(all_kinds) >= {"state_only", "substep_json", "authored_code"}


def test_agents_yaml_tier_field_present():
    """tier is documented in agents.yaml for CrewAI config readability."""
    from importlib.resources import files

    spec = yaml.safe_load(
        files("maads").joinpath("config/agents.yaml").read_text(encoding="utf-8")
    )
    for name, fields in spec.items():
        assert fields.get("tier") in ("top", "mid"), f"{name} missing tier"
