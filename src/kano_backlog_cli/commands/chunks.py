"""CLI commands for canonical chunks DB (FTS5) operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from kano_backlog_cli.util import ensure_core_on_path


app = typer.Typer(help="Canonical chunks SQLite DB (FTS5) operations")


@app.command("build")
def build_chunks(
    product: str = typer.Option("kano-agent-backlog-skill", "--product", help="Product name"),
    backlog_root: Optional[Path] = typer.Option(None, "--backlog-root", help="Backlog root (_kano/backlog)"),
    force: bool = typer.Option(False, "--force", help="Force rebuild if DB exists"),
    output_format: str = typer.Option("markdown", "--format", help="Output format: markdown|json"),
):
    """Build per-product canonical chunks DB (items/chunks/chunks_fts)."""
    ensure_core_on_path()

    from kano_backlog_ops.chunks_db import build_chunks_db

    result = build_chunks_db(product=product, backlog_root=backlog_root, force=force)

    if output_format == "json":
        payload = {
            "product": product,
            "db_path": str(result.db_path),
            "items_indexed": result.items_indexed,
            "chunks_indexed": result.chunks_indexed,
            "build_time_ms": result.build_time_ms,
        }
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))
        return

    typer.echo(f"# Build Chunks DB: {product}")
    typer.echo(f"- db_path: {result.db_path}")
    typer.echo(f"- items_indexed: {result.items_indexed}")
    typer.echo(f"- chunks_indexed: {result.chunks_indexed}")
    typer.echo(f"- build_time_ms: {result.build_time_ms:.2f}")


@app.command("query")
def query_chunks(
    query: str = typer.Argument(..., help="FTS query (SQLite MATCH syntax)"),
    product: str = typer.Option("kano-agent-backlog-skill", "--product", help="Product name"),
    backlog_root: Optional[Path] = typer.Option(None, "--backlog-root", help="Backlog root (_kano/backlog)"),
    k: int = typer.Option(10, "--k", help="Number of results to return"),
    output_format: str = typer.Option("markdown", "--format", help="Output format: markdown|json"),
):
    """Keyword search over canonical chunks_fts."""
    ensure_core_on_path()

    from kano_backlog_ops.chunks_db import query_chunks_fts

    results = query_chunks_fts(product=product, backlog_root=backlog_root, query=query, k=k)

    if output_format == "json":
        payload = {
            "product": product,
            "query": query,
            "k": k,
            "results": [
                {
                    "item_id": r.item_id,
                    "item_title": r.item_title,
                    "item_path": r.item_path,
                    "chunk_id": r.chunk_id,
                    "parent_uid": r.parent_uid,
                    "section": r.section,
                    "content": r.content,
                    "score": r.score,
                }
                for r in results
            ],
        }
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))
        return

    typer.echo(f"# Chunks Search: {product}")
    typer.echo(f"- query: {query}")
    typer.echo(f"- k: {k}")
    typer.echo(f"- results_count: {len(results)}")
    typer.echo()

    for i, r in enumerate(results, 1):
        preview = r.content[:200] + ("..." if len(r.content) > 200 else "")
        typer.echo(f"## Result {i} (score: {r.score:.4f})")
        typer.echo(f"- item: {r.item_id} ({r.item_title})")
        typer.echo(f"- path: {r.item_path}")
        typer.echo(f"- section: {r.section or 'unknown'}")
        typer.echo(f"- chunk_id: {r.chunk_id}")
        typer.echo(f"- text: {preview}")
        typer.echo()
