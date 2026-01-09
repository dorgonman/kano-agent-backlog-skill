from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

from ..util import ensure_core_on_path, resolve_product_root

app = typer.Typer()


@app.command()
def refresh(
    agent: str = typer.Option(..., "--agent", help="Agent name (for audit trail)"),
    backlog_root: str = typer.Option("_kano/backlog", "--backlog-root", help="Backlog root directory"),
    product: str | None = typer.Option(None, "--product", help="Product name (optional)"),
    config: str | None = typer.Option(None, "--config", help="Config file path"),
):
    """Refresh all dashboards (views) in the backlog."""
    ensure_core_on_path()
    
    backlog_path = Path(backlog_root)
    if not backlog_path.exists():
        typer.echo(f"❌ Backlog root not found: {backlog_path}", err=True)
        raise typer.Exit(1)
    
    # Find and invoke the view_refresh_dashboards.py script
    skill_root = Path(__file__).resolve().parents[3]  # src/kano_cli/commands/view.py -> skills/kano-agent-backlog-skill
    script_path = skill_root / "scripts" / "backlog" / "view_refresh_dashboards.py"
    
    if not script_path.exists():
        typer.echo(f"❌ Script not found: {script_path}", err=True)
        raise typer.Exit(1)
    
    # Build command
    cmd = [sys.executable, str(script_path), "--backlog-root", backlog_root, "--agent", agent]
    
    if product:
        cmd.extend(["--product", product])
    if config:
        cmd.extend(["--config", config])
    
    # Run the script
    typer.echo(f"🔄 Refreshing views in {backlog_root}...")
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    if result.returncode == 0:
        typer.echo("✓ Views refreshed successfully")
    else:
        typer.echo("❌ Failed to refresh views", err=True)
        raise typer.Exit(result.returncode)
