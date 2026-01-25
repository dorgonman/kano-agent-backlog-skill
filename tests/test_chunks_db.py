"""Tests for canonical chunks DB (FTS5) operations."""

from pathlib import Path

import pytest

from kano_backlog_ops.chunks_db import build_chunks_db, query_chunks_fts


def test_build_chunks_db_and_query(tmp_path: Path) -> None:
    backlog_root = tmp_path / "_kano" / "backlog"
    product_root = backlog_root / "products" / "test-product"
    items_root = product_root / "items" / "task" / "0000"
    items_root.mkdir(parents=True)

    item_path = items_root / "TEST-TSK-001_test-task.md"
    item_content = """---
id: TEST-TSK-001
uid: 01234567-89ab-cdef-0123-456789abcdef
type: Task
state: Proposed
title: Test Task
priority: P3
parent: null
owner: test-agent
area: general
iteration: backlog
tags: []
created: '2026-01-23'
updated: '2026-01-23'
---

# Context
This is a test task.

# Goal
Test the chunks DB build and query.
"""
    item_path.write_text(item_content, encoding="utf-8")

    result = build_chunks_db(product="test-product", backlog_root=backlog_root, force=True)
    assert result.items_indexed == 1
    assert result.chunks_indexed > 0
    assert result.db_path.exists()

    hits = query_chunks_fts(product="test-product", backlog_root=backlog_root, query="chunks", k=10)
    assert hits
    assert hits[0].item_id == "TEST-TSK-001"
    assert "products/test-product/items" in hits[0].item_path
