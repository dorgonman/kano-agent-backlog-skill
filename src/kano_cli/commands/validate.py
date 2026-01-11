from __future__ import annotations

from pathlib import Path
import typer

from ..util import ensure_core_on_path

app = typer.Typer(help="Validation helpers")


@app.command("uids")
def validate_uids(
    product: str | None = typer.Option(None, "--product", help="Product name (validate all if omitted)"),
    backlog_root: Path | None = typer.Option(None, "--backlog-root", help="Backlog root (_kano/backlog)"),
):
    """Validate that all backlog items use UUIDv7 UIDs."""
    ensure_core_on_path()
    from kano_backlog_ops.validate import validate_uids as validate_uids_op

    results = validate_uids_op(product=product, backlog_root=backlog_root)

    total_checked = 0
    total_violations = 0
    for res in results:
        total_checked += res.checked
        total_violations += len(res.violations)
        if res.violations:
            typer.echo(f"❌ {res.product}: {len(res.violations)} UID violations")
            for v in res.violations:
                typer.echo(f"  - {v.path}: {v.uid} ({v.reason})")
        else:
            typer.echo(f"✓ {res.product}: all {res.checked} items have UUIDv7 UIDs")

    if total_violations:
        raise typer.Exit(1)
    typer.echo(f"All products clean. Items checked: {total_checked}")
