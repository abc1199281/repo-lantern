"""Lantern CLI - Main entry point."""

import typer
from rich.console import Console

app = typer.Typer(
    name="lantern",
    help="Your repository mentor - AI-guided codebase analysis",
    add_completion=False,
)

console = Console()


@app.command()
def init(
    repo: str = typer.Option(".", help="Repository path or URL"),
) -> None:
    """Initialize Lantern for a repository."""
    console.print(f"[green]Initializing Lantern for:[/green] {repo}")
    console.print("[yellow]⚠️  Not implemented yet[/yellow]")


@app.command()
def plan() -> None:
    """Generate analysis plan (lantern_plan.md)."""
    console.print("[green]Generating analysis plan...[/green]")
    console.print("[yellow]⚠️  Not implemented yet[/yellow]")


@app.command()
def run(
    repo: str = typer.Option(".", help="Repository path"),
    output: str = typer.Option(".lantern", help="Output directory"),
    backend: str = typer.Option(None, help="LLM backend (codex/gemini/claude)"),
    lang: str = typer.Option("en", help="Output language (en/zh-TW)"),
) -> None:
    """Run analysis on repository."""
    console.print(f"[green]Analyzing repository:[/green] {repo}")
    console.print(f"[green]Output directory:[/green] {output}")
    console.print(f"[green]Language:[/green] {lang}")
    if backend:
        console.print(f"[green]Backend:[/green] {backend}")
    console.print("[yellow]⚠️  Not implemented yet[/yellow]")


@app.command()
def version() -> None:
    """Show version information."""
    from lantern_cli import __version__

    console.print(f"Lantern CLI version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
