"""
snapshot.py - Snapshot command for generating evidence packs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional, List, Dict, Any

import typer
from rich.console import Console
from rich.syntax import Syntax

from kano_backlog_ops import snapshot as snapshot_ops
from kano_backlog_ops.template_engine import TemplateEngine
from kano_backlog_cli.util import resolve_product_root, ensure_core_on_path

app = typer.Typer()
console = Console()


def _collect_cli_remotely() -> List[snapshot_ops.CliCommand]:
    """
    Collect CLI tree by running 'kano --help' and parsing output.
    This simulates an external audit of the surface.
    """
    # Find the kano script wrapper or module
    # We try to run the same command that invoked us, or default to standard locations
    cmd = [sys.executable, "skills/kano-agent-backlog-skill/scripts/kano-backlog"]
    if not Path("skills/kano-agent-backlog-skill/scripts/kano-backlog").exists():
        # Fallback to module execution if script not found
        cmd = [sys.executable, "-m", "kano_backlog_cli"]

    try:
        # Run help
        result = subprocess.run(
            cmd + ["--help"], 
            capture_output=True, 
            text=True, 
            check=False,
            encoding='utf-8' # Force utf-8
        )
        if result.returncode != 0:
            console.print(f"[yellow]Warning: Failed to run help for CLI tree: {result.stderr}[/yellow]")
            return []
            
        # Parse logic (simplified for MVP: just top level and known groups)
        # For a full tree we would need recursive parsing. 
        # Here we just capture the raw help text as a single node description for now,
        # or do a shallow parse.
        
        # PROVISIONAL: Just return top-level help as one node to prove connectivity
        return [snapshot_ops.CliCommand(
            name="kano",
            help="Full CLI Help Output (Recursive parsing TODO)",
            subcommands=[]
        )]
        
    except Exception as e:
        console.print(f"[yellow]Warning: CLI collection failed: {e}[/yellow]")
        return []


def _resolve_output_path(
    scope: str, 
    view: str, 
    format: str, 
    out: Optional[Path], 
    cwd: Path,
    timestamp: str
) -> Path:
    """Determine final output path."""
    if out:
        return out
        
    # Default structure: _kano/backlog/[products/<name>/]views/snapshots/
    stem = f"snapshot.{view}.{timestamp}"
    filename = f"{stem}.{format}"
    
    if scope.startswith("product:"):
        product_name = scope.split(":", 1)[1]
        backlog_root = Path("_kano/backlog") # Assumption, should resolve properly
        # Try to resolve product root
        try:
             # This might fail if product doesn't exist, handle gracefully
             product_root = backlog_root / "products" / product_name
             target_dir = product_root / "views" / "snapshots"
        except:
             target_dir = cwd / "snapshots"
    else:
        # Repo scope
        target_dir = Path("_kano/backlog/views/snapshots")
        
    return target_dir / filename


@app.command(name="create", help="Generate a deterministic snapshot evidence pack.")
def create(
    view: str = typer.Argument(..., help="View to capture: all|stubs|cli|health|capabilities"),
    scope: str = typer.Option("repo", "--scope", help="Scope: repo|product:<name>"),
    format: str = typer.Option("md", "--format", "-f", help="Output format: json|md"),
    write: bool = typer.Option(False, "--write", "-w", help="Write output to file"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Custom output path"),
):
    """
    Generate a deterministic snapshot evidence pack.
    """
    cwd = Path.cwd()
    ensure_core_on_path()
    
    # Parse scope
    product_name = None
    if scope.startswith("product:"):
        product_name = scope.split(":", 1)[1]
        
    # Generate pack
    console.print(f"[bold blue]Snapshotting {scope} (view={view})...[/bold blue]")
    
    pack = snapshot_ops.generate_pack(
        scope=scope,
        root_path=cwd,
        product=product_name
    )
    
    # Fill in CLI tree if requested (expensive/external)
    if view in ["all", "cli"]:
        pack.cli_tree = _collect_cli_remotely()
        
    # Format output
    output_content = ""
    if format == "json":
        output_content = pack.to_json()
    else:
        # Markdown rendering
        output_content = f"# Snapshot Report: {scope}\n\n"
        output_content += f"**Timestamp:** {pack.meta.timestamp}\n"
        output_content += f"**Git SHA:** {pack.meta.git_sha}\n\n"
        
        if view in ["all", "capabilities"]:
            output_content += "## Capabilities\n\n"
            for cap in pack.capabilities:
                output_content += f"- **{cap.area}.{cap.feature}**: {cap.status}\n"
        
        if view in ["all", "stubs"]:
            output_content += "\n## Stubs & TODOs\n\n"
            output_content += f"Found {len(pack.stub_inventory)} items.\n"
            # Limit listing for brevity in console, full in file
            for stub in pack.stub_inventory[:20]:
                output_content += f"- [{stub.type}] {stub.file}:{stub.line} - {stub.message}\n"
            if len(pack.stub_inventory) > 20:
                output_content += f"... and {len(pack.stub_inventory)-20} more.\n"

        if view in ["all", "health"]:
             output_content += "\n## Health Checks\n\n"
             for h in pack.health:
                 icon = "✅" if h.passed else "❌"
                 output_content += f"- {icon} {h.name}: {h.message}\n"
                 
        if view in ["all", "cli"]:
            output_content += "\n## CLI Surface\n\n"
            if pack.cli_tree:
                output_content += f"Command: {pack.cli_tree[0].name}\n"
                # TODO recursive print
            else:
                output_content += "No CLI tree collected.\n"

    # Display or Write
    if write:
        # Determine path
        timestamp_clean = pack.meta.timestamp.replace(":", "").replace("-", "").split(".")[0]
        target_path = _resolve_output_path(scope, view, format, out, cwd, timestamp_clean)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(output_content, encoding="utf-8")
        console.print(f"[green]Snapshot written to: {target_path}[/green]")
    else:
        console.print(output_content)


@app.command()
def report(
    persona: str = typer.Argument(..., help="Target persona: developer|pm|qa"),
    scope: str = typer.Option("repo", "--scope", help="Scope: repo|product:<name>"),
    write: bool = typer.Option(False, "--write", "-w", help="Write report to file"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Custom output path"),
):
    """
    Generate a personified report from a fresh snapshot using a template.
    """
    cwd = Path.cwd()
    ensure_core_on_path()
    
    console.print(f"[bold blue]Generating {persona} report for {scope}...[/bold blue]")
    
    # 1. Generate snapshot (evidence)
    product_name = None
    if scope.startswith("product:"):
        product_name = scope.split(":", 1)[1]
    
    pack = snapshot_ops.generate_pack(scope=scope, root_path=cwd, product=product_name)
    
    # If using 'all' info in report
    pack.cli_tree = _collect_cli_remotely()
    
    # 2. Load template
    # Assumption: templates located in skills directory
    template_name = f"snapshot_report_{persona}.md"
    skill_root = Path("skills/kano-agent-backlog-skill")
    template_path = skill_root / "templates" / template_name
    
    if not template_path.exists():
        console.print(f"[red]Error: Template {template_name} not found in {skill_root}/templates[/red]")
        raise typer.Exit(1)
        
    template_content = template_path.read_text(encoding="utf-8")
    
    # 3. Render
    engine = TemplateEngine()
    context = asdict(pack) # Flatten evidence pack to dict
    rendered = engine.render(template_content, context)
    
    # 4. Write or Print
    if write:
        timestamp_clean = pack.meta.timestamp.replace(":", "").replace("-", "").split(".")[0]
        target_path = _resolve_output_path(scope, f"report_{persona}", "md", out, cwd, timestamp_clean)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(rendered, encoding="utf-8")
        console.print(f"[green]Report written to: {target_path}[/green]")
    else:
        console.print(rendered)
