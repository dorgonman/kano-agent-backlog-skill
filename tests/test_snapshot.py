"""
test_snapshot.py - Tests for Snapshot and Evidence functionality.
"""
import json
from pathlib import Path
from dataclasses import asdict

import pytest

from kano_backlog_ops.snapshot import (
    EvidencePack, SnapshotMeta, StubEntry, 
    collect_stubs, generate_pack
)
from kano_backlog_ops.template_engine import TemplateEngine


@pytest.fixture
def sample_pack():
    meta = SnapshotMeta(
        timestamp="2026-01-01T00:00:00",
        git_sha="abcdef",
        scope="repo",
    )
    stubs = [
        StubEntry(type="TODO", file="foo.py", line=10, message="Implement me"),
    ]
    return EvidencePack(
        meta=meta,
        cli_tree=[],
        stub_inventory=stubs,
        capabilities=[],
        health=[]
    )


def test_template_engine_basic_vars():
    """Test standard variable substitution."""
    engine = TemplateEngine()
    tpl = "Hello {{ name }}!"
    ctx = {"name": "World"}
    assert engine.render(tpl, ctx) == "Hello World!"


def test_template_engine_nested_vars():
    """Test nested dict access."""
    engine = TemplateEngine()
    tpl = "Version: {{ meta.version }}"
    ctx = {"meta": {"version": "1.0"}}
    assert engine.render(tpl, ctx) == "Version: 1.0"


def test_template_engine_each_loop():
    """Test #each loop rendering."""
    engine = TemplateEngine()
    tpl = """
    Items:
    {{#each items}}
    - {{ name }}: {{ qty }}
    {{/each}}
    """
    ctx = {
        "items": [
            {"name": "Apple", "qty": 10},
            {"name": "Banana", "qty": 5},
        ]
    }
    rendered = engine.render(tpl, ctx)
    assert "- Apple: 10" in rendered
    assert "- Banana: 5" in rendered


def test_template_engine_if_eq_helpers():
    """Test #if (eq ...) helper."""
    engine = TemplateEngine()
    tpl = """
    {{#if (eq status "done")}}
    DONE
    {{/if}}
    {{#if (eq status "pending")}}
    PENDING
    {{/if}}
    """
    assert "DONE" in engine.render(tpl, {"status": "done"})
    assert "PENDING" not in engine.render(tpl, {"status": "done"})


def test_evidence_pack_json_roundtrip(sample_pack):
    """Verify JSON serialization and deserialization."""
    json_str = sample_pack.to_json()
    assert '"git_sha": "abcdef"' in json_str
    
    reloaded = EvidencePack.from_json(json_str)
    assert reloaded.meta.git_sha == "abcdef"
    assert len(reloaded.stub_inventory) == 1
    assert reloaded.stub_inventory[0].message == "Implement me"


def test_collect_stubs(tmp_path):
    """Verify stub collection picks up markers."""
    f = tmp_path / "test.py"
    f.write_text("# TODO: fix this\nraise NotImplementedError('oops')", encoding="utf-8")
    
    stubs = collect_stubs(tmp_path)
    assert len(stubs) == 2
    types = sorted([s.type for s in stubs])
    assert types == ["NotImplementedError", "TODO"]
