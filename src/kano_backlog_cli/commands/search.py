"""Search commands.

- query: pure vector similarity search
- hybrid: FTS5 candidates (canonical chunks DB) -> vector rerank
"""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from ..util import ensure_core_on_path

app = typer.Typer(help="Vector similarity search")
console = Console()

@app.command()
def query(
    text: str = typer.Argument(..., help="Query text to search for"),
    product: str = typer.Option(None, "--product", help="Product name"),
    k: int = typer.Option(10, "--top-k", "-k", help="Number of results to return"),
    backlog_root: Optional[Path] = typer.Option(None, "--backlog-root", help="Backlog root (_kano/backlog)"),
):
    """Search for similar content using vector embeddings."""
    ensure_core_on_path()
    from kano_backlog_ops.vector_query import search_similar
    
    try:
        results = search_similar(
            query_text=text,
            product=product or "kano-agent-backlog-skill",
            k=k,
            backlog_root=backlog_root,
        )
    except Exception as e:
        console.print(f"[red]❌ Search failed:[/red] {e}")
        raise typer.Exit(1)
    
    if not results:
        console.print("[yellow]No results found[/yellow]")
        return
    
    # Display results in a table
    table = Table(title=f"Search Results (query: '{text[:50]}...')")
    table.add_column("Rank", style="cyan", width=6)
    table.add_column("Score", style="green", width=8)
    table.add_column("Source", style="magenta", width=15)
    table.add_column("Text", style="white", width=60)
    
    for i, result in enumerate(results, 1):
        score_str = f"{result.score:.4f}"
        text_preview = result.text[:100] + "..." if len(result.text) > 100 else result.text
        table.add_row(
            str(i),
            score_str,
            result.source_id,
            text_preview
        )
    
    console.print(table)
    console.print(f"\n[dim]Search completed in {results[0].duration_ms:.1f}ms[/dim]")


@app.command()
def hybrid(
    text: str = typer.Argument(..., help="Query text to search for (also used as FTS MATCH string)"),
    product: str = typer.Option(None, "--product", help="Product name"),
    k: int = typer.Option(10, "--top-k", "-k", help="Number of results to return"),
    fts_k: int = typer.Option(200, "--fts-k", help="Number of FTS candidates to rerank"),
    snippet_tokens: int = typer.Option(20, "--snippet-tokens", help="FTS snippet token length"),
    backlog_root: Optional[Path] = typer.Option(None, "--backlog-root", help="Backlog root (_kano/backlog)"),
):
    """Hybrid search: FTS candidates -> vector rerank (with snippet)."""
    ensure_core_on_path()
    from kano_backlog_ops.vector_query import search_hybrid

    try:
        results = search_hybrid(
            query_text=text,
            product=product or "kano-agent-backlog-skill",
            k=k,
            fts_k=fts_k,
            snippet_tokens=snippet_tokens,
            backlog_root=backlog_root,
        )
    except Exception as e:
        console.print(f"[red]❌ Hybrid search failed:[/red] {e}")
        raise typer.Exit(1)

    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    table = Table(title=f"Hybrid Search Results (query: '{text[:50]}...')")
    table.add_column("Rank", style="cyan", width=6)
    table.add_column("VScore", style="green", width=8)
    table.add_column("BM25", style="green", width=8)
    table.add_column("Item", style="magenta", width=18)
    table.add_column("Section", style="cyan", width=12)
    table.add_column("Snippet", style="white", width=60)

    for i, result in enumerate(results, 1):
        snippet_preview = (
            result.snippet[:100] + "..." if len(result.snippet) > 100 else result.snippet
        )
        item_label = f"{result.item_id}"
        table.add_row(
            str(i),
            f"{result.vector_score:.4f}",
            f"{result.bm25_score:.4f}",
            item_label,
            result.section or "-",
            snippet_preview,
        )

    console.print(table)
    console.print(f"\n[dim]Hybrid search completed in {results[0].duration_ms:.1f}ms[/dim]")
