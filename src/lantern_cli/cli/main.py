"""Lantern CLI - Main entry point."""

import typer
import shutil
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path

from lantern_cli.config.loader import load_config
from lantern_cli.backends.factory import BackendFactory
from lantern_cli.static_analysis.dependency_graph import DependencyGraph
from lantern_cli.core.architect import Architect
from lantern_cli.core.state_manager import StateManager
from lantern_cli.core.runner import Runner
from lantern_cli.core.synthesizer import Synthesizer

app = typer.Typer(
    name="lantern",
    help="Your repository mentor - AI-guided codebase analysis",
    add_completion=False,
)

console = Console()


@app.command()
@app.command()
def init(
    repo: str = typer.Option(".", help="Repository path or URL"),
) -> None:
    """Initialize Lantern for a repository."""
    repo_path = Path(repo).resolve()
    lantern_dir = repo_path / ".lantern"
    
    if lantern_dir.exists():
        console.print(f"[yellow]Lantern is already initialized in {repo_path}[/yellow]")
        return

    try:
        lantern_dir.mkdir(parents=True, exist_ok=True)
        # Create default config
        config_path = lantern_dir / "lantern.toml"
        # Minimal default config
        config_content = """# Lantern Configuration

[lantern]
language = "en"
output_dir = ".lantern"

[filter]
exclude = [
    "**/__pycache__/*", 
    "**/.git/*", 
    "**/node_modules/*", 
    "**/.venv/*", 
    "**/.idea/*", 
    "**/.vscode/*"
]

[backend]
type = "cli"
cli_timeout = 300
"""
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
            
        console.print(f"[green]Initialized Lantern in {lantern_dir}[/green]")
        console.print(f"Configuration created at: {config_path}")
        
    except Exception as e:
        console.print(f"[bold red]Failed to initialize:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
@app.command()
def plan(
    repo: str = typer.Option(".", help="Repository path"),
    output: str = typer.Option(".lantern", help="Output directory"),
) -> None:
    """Generate analysis plan (lantern_plan.md) without running analysis."""
    repo_path = Path(repo).resolve()
    
    # 0. Load Configuration (for filters)
    config = load_config(repo_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # 1. Static Analysis
        task_static = progress.add_task("Building dependency graph...", total=None)
        graph = DependencyGraph(repo_path, excludes=config.filter.exclude)
        graph.build()
        progress.update(task_static, completed=True)

        # 2. Architect Plan
        task_plan = progress.add_task("Architecting analysis plan...", total=None)
        architect = Architect(repo_path, graph)
        plan = architect.generate_plan()
        
        # Save plan
        output_path = repo_path / output
        output_path.mkdir(parents=True, exist_ok=True)
        plan_path = output_path / "lantern_plan.md"
        
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan.to_markdown())
            
        progress.update(task_plan, completed=True)
        
    console.print(f"[bold green]Plan generated successfully![/bold green]")
    console.print(f"Plan file: {plan_path}")
    console.print("Run 'lantern run' to execute this plan.")


@app.command()
def run(
    repo: str = typer.Option(".", help="Repository path"),
    output: str = typer.Option(".lantern", help="Output directory"),
    backend: str = typer.Option(None, help="LLM backend (codex/gemini/claude/openai)"),
    api: bool = typer.Option(False, help="Force API mode (api_provider)"),
    lang: str = typer.Option("en", help="Output language (en/zh-TW)"),
    model: str = typer.Option(None, help="Model name (e.g., 'llama3' for ollama, 'gpt-4o' for openai)"),
) -> None:
    """Run analysis on repository."""
    repo_path = Path(repo).resolve()
    
    # 1. Load Configuration
    config = load_config(repo_path)
    
    # Override config with CLI args
    if output:
        config.output_dir = output
    if lang:
        config.language = lang
    
    if api:
        config.backend.type = "api"

    if backend == "ollama":
        config.backend.type = "ollama"
        
    if backend:
        # If --api matching flag is set, treat backend as api_provider
        if config.backend.type == "api" or api:
             config.backend.type = "api"
             config.backend.api_provider = backend
        elif config.backend.type == "ollama":
             pass
        else:
             # Heuristic: if backend matches known API providers AND is not meant to be CLI
             if backend in ("claude", "anthropic", "openai", "gpt"):
                 config.backend.type = "api"
                 config.backend.api_provider = backend
             elif backend == "gemini":
                 # Special handling for Gemini which has both
                 if shutil.which("gemini") and not api:
                     config.backend.type = "cli"
                     config.backend.cli_command = "gemini"
                 else:
                     config.backend.type = "api"
                     config.backend.api_provider = "gemini"
             else:
                 config.backend.type = "cli"
                 config.backend.cli_command = backend

    # Handle model overrides
    if model:
        if config.backend.type == "ollama":
            config.backend.ollama_model = model
        elif config.backend.type == "api":
            config.backend.api_model = model

    console.print(f"[bold green]Lantern Analysis[/bold green]")
    console.print(f"Repository: {repo_path}")
    console.print(f"Backend: {config.backend.type} ({config.backend.api_provider or config.backend.cli_command})")

    # 2. Initialize Backend
    try:
        backend_adapter = BackendFactory.create(config)
    except Exception as e:
        console.print(f"[bold red]Error initializing backend:[/bold red] {e}")
        raise typer.Exit(code=1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        # 3. Static Analysis
        task_static = progress.add_task("Building dependency graph...", total=None)
        graph = DependencyGraph(repo_path, excludes=config.filter.exclude)
        graph.build()
        progress.update(task_static, completed=True)

        # 4. Architect Plan
        task_plan = progress.add_task("Architecting analysis plan...", total=None)
        architect = Architect(repo_path, graph)
        plan = architect.generate_plan()
        
        # Save plan
        plan_path = repo_path / config.output_dir / "lantern_plan.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan.to_markdown())
            
        progress.update(task_plan, completed=True)
        console.print(f"Plan generated: {plan_path}")

        # 5. Runner Execution
        task_runner = progress.add_task("Running analysis batches...", total=len(plan.phases)) # Rough progress
        
        state_manager = StateManager(repo_path)
        runner = Runner(repo_path, backend_adapter, state_manager, language=config.language)
        
        pending_batches = state_manager.get_pending_batches(plan)
        
        if not pending_batches:
             console.print("[yellow]All batches completed. Skipping execution.[/yellow]")
        else:
            task_batch = progress.add_task(f"Processing {len(pending_batches)} batches...", total=len(pending_batches))
            
            for batch in pending_batches:
                progress.update(task_batch, description=f"Analyzing Batch {batch.id} ({len(batch.files)} files)...")
                
                # Construct prompt (MVP: simple prompt)
                language_instruction = f" Please respond in {config.language}." if config.language != "en" else ""
                prompt = f"Analyze these files: {batch.files}. Provide a summary and key insights.{language_instruction}"
                
                success = runner.run_batch(batch, prompt)
                if not success:
                    console.print(f"[bold red]Batch {batch.id} failed.[/bold red]")
                    # Continue or break based on policy? For MVP, continue/retry logic is in Runner state
                
                progress.advance(task_batch)
        
        progress.update(task_runner, completed=True)

        # 6. Synthesize Docs
        task_synth = progress.add_task("Synthesizing documentation...", total=None)
        synthesizer = Synthesizer(repo_path, language=config.language)
        synthesizer.generate_top_down_docs()
        progress.update(task_synth, completed=True)

    console.print(f"[bold green]Analysis Complete![/bold green]")
    console.print(f"Documentation available in: {repo_path / config.output_dir}")


@app.command()
def version() -> None:
    """Show version information."""
    from lantern_cli import __version__

    console.print(f"Lantern CLI version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
