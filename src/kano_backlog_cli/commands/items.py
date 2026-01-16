from __future__ import annotations

from pathlib import Path
import json
import typer

from kano_backlog_cli.util import ensure_core_on_path

app = typer.Typer(help="Item maintenance helpers")


@app.command("trash")
def trash(
    item_ref: str = typer.Argument(..., help="Item ID, UID, or path to trash"),
    product: str | None = typer.Option(None, "--product", help="Product name"),
    backlog_root: Path | None = typer.Option(None, "--backlog-root", help="Backlog root (_kano/backlog)"),
    agent: str = typer.Option(..., "--agent", help="Agent name for audit/worklog"),
    model: str | None = typer.Option(None, "--model", help="Model used by agent"),
    reason: str | None = typer.Option(None, "--reason", help="Reason for trashing"),
    apply: bool = typer.Option(False, "--apply", help="Write changes to disk"),
    output_format: str = typer.Option("markdown", "--format", help="Output format: markdown|json"),
):
    """Move an item file to a per-product _trash folder."""
    ensure_core_on_path()
    from kano_backlog_ops.workitem import trash_item

    result = trash_item(
        item_ref,
        agent=agent,
        reason=reason,
        model=model,
        product=product,
        backlog_root=backlog_root,
        apply=apply,
    )

    if output_format == "json":
        payload = {
            "item_ref": result.item_ref,
            "status": result.status,
            "source_path": str(result.source_path),
            "trashed_path": str(result.trashed_path),
            "reason": result.reason,
        }
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))
        return

    typer.echo(f"# Trash item: {result.item_ref}")
    typer.echo(f"- status: {result.status}")
    typer.echo(f"- source_path: {result.source_path}")
    typer.echo(f"- trashed_path: {result.trashed_path}")
    if result.reason:
        typer.echo(f"- reason: {result.reason}")
