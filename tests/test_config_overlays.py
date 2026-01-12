"""Tests for config resolution using defaults + topic/workset overlays.

This exercises kano_backlog_core.config.ConfigLoader without requiring CLI wiring.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

# Ensure src/ is importable when running tests directly.
import sys

test_dir = Path(__file__).parent
src_dir = test_dir.parent / "src"
sys.path.insert(0, str(src_dir))

from kano_backlog_core.config import ConfigLoader


def _mk_backlog(tmp: Path, *, products: list[str]) -> Path:
    backlog_root = tmp / "_kano" / "backlog"
    (backlog_root / "_shared").mkdir(parents=True, exist_ok=True)
    products_root = backlog_root / "products"
    products_root.mkdir(parents=True, exist_ok=True)

    for product in products:
        product_root = products_root / product
        (product_root / "_config").mkdir(parents=True, exist_ok=True)
        (product_root / "_config" / "config.json").write_text(
            json.dumps({"project": {"name": product, "prefix": product[:3].upper()}}),
            encoding="utf-8",
        )

    return backlog_root


def _tmp_workspace() -> Path:
    return Path(tempfile.mkdtemp())


def _cleanup(tmp: Path) -> None:
    shutil.rmtree(tmp, ignore_errors=True)


def test_from_path_uses_defaults_default_product_when_not_inferable():
    tmp = _tmp_workspace()
    try:
        backlog_root = _mk_backlog(tmp, products=["prod-a", "prod-b"])
        (backlog_root / "_shared" / "defaults.json").write_text(
            json.dumps({"default_product": "prod-b"}), encoding="utf-8"
        )

        ctx = ConfigLoader.from_path(tmp)
        assert ctx.product_name == "prod-b"
        assert ctx.product_root == backlog_root / "products" / "prod-b"
    finally:
        _cleanup(tmp)


def test_from_path_topic_override_beats_defaults_when_agent_has_active_topic():
    tmp = _tmp_workspace()
    try:
        backlog_root = _mk_backlog(tmp, products=["prod-a", "prod-b"])
        (backlog_root / "_shared" / "defaults.json").write_text(
            json.dumps({"default_product": "prod-b"}), encoding="utf-8"
        )

        # Create topic config override and active topic marker for agent
        topic_name = "mytopic"
        topic_dir = backlog_root / "topics" / topic_name
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "config.json").write_text(
            json.dumps({"default_product": "prod-a"}), encoding="utf-8"
        )
        active_marker = backlog_root / ".cache" / "worksets" / "active_topic.copilot.txt"
        active_marker.parent.mkdir(parents=True, exist_ok=True)
        active_marker.write_text(topic_name, encoding="utf-8")

        ctx = ConfigLoader.from_path(tmp, agent="copilot")
        assert ctx.product_name == "prod-a"
    finally:
        _cleanup(tmp)


def test_load_effective_config_layers_merge_in_order():
    tmp = _tmp_workspace()
    try:
        backlog_root = _mk_backlog(tmp, products=["prod-a"])
        (backlog_root / "_shared" / "defaults.json").write_text(
            json.dumps({"views": {"auto_refresh": False}, "x": 1}),
            encoding="utf-8",
        )

        # product config adds nested key
        product_cfg_path = backlog_root / "products" / "prod-a" / "_config" / "config.json"
        product_cfg_path.write_text(
            json.dumps({"views": {"auto_refresh": False, "mode": "product"}, "x": 2}),
            encoding="utf-8",
        )

        # topic override flips auto_refresh
        topic_name = "mytopic"
        topic_dir = backlog_root / "topics" / topic_name
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "config.json").write_text(
            json.dumps({"views": {"auto_refresh": True}}), encoding="utf-8"
        )
        active_marker = backlog_root / ".cache" / "worksets" / "active_topic.copilot.txt"
        active_marker.parent.mkdir(parents=True, exist_ok=True)
        active_marker.write_text(topic_name, encoding="utf-8")

        # workset override adds another leaf
        item_id = "PRO-TSK-0001"
        workset_dir = backlog_root / ".cache" / "worksets" / "items" / item_id
        workset_dir.mkdir(parents=True, exist_ok=True)
        (workset_dir / "config.json").write_text(
            json.dumps({"views": {"mode": "workset"}, "x": 3}), encoding="utf-8"
        )

        ctx, cfg = ConfigLoader.load_effective_config(
            tmp,
            agent="copilot",
            workset_item_id=item_id,
        )
        assert ctx.product_name == "prod-a"
        assert cfg["x"] == 3
        assert cfg["views"]["auto_refresh"] is True
        assert cfg["views"]["mode"] == "workset"
    finally:
        _cleanup(tmp)
