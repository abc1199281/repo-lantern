"""Lantern CLI - Main entry point."""

import typer
import shutil
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.text import Text

from pathlib import Path
from typing import Optional

from lantern_cli.config.loader import load_config
from lantern_cli.llm.factory import create_llm
from lantern_cli.static_analysis import DependencyGraph, FileFilter
from lantern_cli.core.architect import Architect
from lantern_cli.core.state_manager import StateManager
from lantern_cli.core.runner import Runner
from lantern_cli.core.synthesizer import Synthesizer
from lantern_cli.utils.cost_tracker import CostTracker

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "template" / "defaults"
DEFAULT_CONFIG_PATH = TEMPLATE_ROOT / "lantern.toml"


def _load_default_config() -> str:
    try:
        return DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Unable to read default config at {DEFAULT_CONFIG_PATH}") from exc

app = typer.Typer(
    name="lantern",
    help="Your repository mentor - AI-guided codebase analysis",
    add_completion=False,
)

console = Console()


class FlexibleTaskProgressColumn(TaskProgressColumn):
    """Progress column that shows '...' for indeterminate tasks."""
    
    def render(self, task) -> Text:
        if task.total is None:
            return Text("...", style="progress.percentage")
        return super().render(task)

@app.command()
def init(
    repo: str = typer.Option(".", help="Repository path or URL"),
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="Force re-initialization and overwrite existing config"),
) -> None:
    """Initialize Lantern for a repository."""
    repo_path = Path(repo).resolve()
    lantern_dir = repo_path / ".lantern"
    
    if lantern_dir.exists():
        if overwrite:
            console.print(f"[yellow]Overwriting existing Lantern configuration in {repo_path}...[/yellow]")
            shutil.rmtree(lantern_dir)
        else:
            console.print(f"[yellow]Lantern is already initialized in {repo_path}[/yellow]")
            console.print("[dim]Use --overwrite to re-initialize.[/dim]")
            return

    try:
        lantern_dir.mkdir(parents=True, exist_ok=True)
        config_path = lantern_dir / "lantern.toml"
        config_content = _load_default_config()
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
            
        console.print(f"[green]Initialized Lantern in {lantern_dir}[/green]")
        console.print(f"[green]Content is as follows: {config_content}[/green]")
        console.print(f"Configuration created at: {config_path}")
        
    except Exception as e:
        console.print(f"[bold red]Failed to initialize:[/bold red] {e}")
        raise typer.Exit(code=1)

@app.command()
def plan(
    repo: str = typer.Option(".", help="Repository path"),
    output: Optional[str] = typer.Option(None, help="Output directory"),
) -> None:
    """Generate analysis plan (lantern_plan.md) without running analysis."""
    repo_path = Path(repo).resolve()
    
    # 0. Load Configuration (for filters)
    config = load_config(repo_path, output=output)

    # Respect config.output_dir when CLI `--output` is not provided
    output_dir = config.output_dir

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        FlexibleTaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        # 1. Static Analysis
        task_static = progress.add_task("Building dependency graph...", total=None)
        file_filter = FileFilter(repo_path, config.filter)
        graph = DependencyGraph(repo_path, file_filter=file_filter)
        graph.build()
        progress.update(task_static, total=1, completed=1)

        # 2. Architect Plan
        task_plan = progress.add_task("Architecting analysis plan...", total=None)
        architect = Architect(repo_path, graph)
        plan = architect.generate_plan()
        
        # Save plan
        output_path = repo_path / output_dir
        output_path.mkdir(parents=True, exist_ok=True)
        plan_path = output_path / "lantern_plan.md"
        
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan.to_markdown())
            
        progress.update(task_plan, total=1, completed=1)
        
    console.print(f"[bold green]Plan generated successfully![/bold green]")
    console.print(f"Plan file: {plan_path}")
    console.print("Run 'lantern run' to execute this plan.")


@app.command()
def run(
    repo: str = typer.Option(".", help="Repository path"),
    output: Optional[str] = typer.Option(None, help="Output directory"),
    lang: Optional[str] = typer.Option(None, help="Output language (en/zh-TW)"),
    assume_yes: bool = typer.Option(False, "--yes", "-y", help="Skip cost confirmation prompt"),
) -> None:
    """Run analysis on repository."""
    repo_path = Path(repo).resolve()
    
    # 1. Load Configuration
    config = load_config(
        repo_path,
        output=output,
        lang=lang,
    )

    console.print(f"[bold green]Lantern Analysis[/bold green]")
    console.print(f"Repository: {repo_path}")
    console.print(f"Backend: {config.backend.type} ({config.backend.api_provider})")

    # 2. Initialize LLM
    try:
        llm = create_llm(config)
    except Exception as e:
        console.print(f"[bold red]Error initializing LLM:[/bold red] {e}")
        raise typer.Exit(code=1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        FlexibleTaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        
        # 3. Static Analysis
        task_static = progress.add_task("Building dependency graph...", total=None)
        file_filter = FileFilter(repo_path, config.filter)
        graph = DependencyGraph(repo_path, file_filter=file_filter)
        graph.build()
        progress.update(task_static, total=1, completed=1)

        # 4. Architect Plan
        task_plan = progress.add_task("Architecting analysis plan...", total=None)
        architect = Architect(repo_path, graph)
        plan = architect.generate_plan()
        
        # Save plan
        plan_path = repo_path / config.output_dir / "lantern_plan.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan.to_markdown())
            
        progress.update(task_plan, total=1, completed=1)
        console.print(f"Plan generated: {plan_path}")

    # 5. Cost Estimation
    # Determine model name for cost tracking based on configured backend
    is_local = False
    if config.backend.type == "openai":
        model_name = config.backend.openai_model or "gpt-4o-mini"
    elif config.backend.type == "openrouter":
        model_name = config.backend.openrouter_model or "openai/gpt-4o-mini"
    elif config.backend.type == "ollama":
        model_name = config.backend.ollama_model or "llama3"
        is_local = True
    else:
        # Fallback for unknown backend type
        model_name = "unknown-model"
    
    # Initialize state manager (needed for pending batches)
    # Pass LLM for MemoryManager compression
    state_manager = StateManager(repo_path, llm=llm)
    
    cost_tracker = CostTracker(model_name, is_local=is_local)
    pending_batches = state_manager.get_pending_batches(plan)
    
    # Estimate total cost
    total_estimated_tokens = 0
    total_estimated_cost = 0.0
    pricing_available = True
    
    for batch in pending_batches:
        est_result = cost_tracker.estimate_batch_cost(
            files=batch.files,
            context="",  # Simplified for estimation
            prompt="Analyze these files and provide insights."
        )
        if est_result:
            est_tokens, est_cost = est_result
            total_estimated_tokens += est_tokens
            total_estimated_cost += est_cost
        else:
            pricing_available = False
            break
    
    # Display cost estimate
    console.print("\n[bold cyan]📊 Analysis Plan Summary[/bold cyan]")
    console.print(f"   Total Phases: {len(plan.phases)}")
    console.print(f"   Total Batches: {len([b for p in plan.phases for b in p.batches])}")
    console.print(f"   Pending Batches: {len(pending_batches)}")
    console.print(f"   Model: {model_name}")
    
    if pricing_available:
        if is_local:
            console.print(f"   Pricing Source: [green]Local (Free)[/green]")
            console.print(f"   Estimated Tokens: ~{total_estimated_tokens:,} (Input + Est. Output)")
            console.print(f"   Estimated Cost: [bold green]$0.0000 (Free)[/bold green]")
        else:
            console.print(f"   Pricing Source: [green]Online (Live)[/green]")
            console.print(f"   Estimated Tokens: ~{total_estimated_tokens:,} (Input + Est. Output)")
            console.print(f"   Estimated Cost: [bold yellow]${total_estimated_cost:.4f}[/bold yellow]")
    else:
        if config.backend.type == "cli":
            console.print(f"   Pricing Source: [yellow]CLI Tool[/yellow]")
            console.print("   Estimated Cost: [bold yellow]CLI estimate not available[/bold yellow]")
        else:
            console.print(f"   Pricing Source: [red]Offline[/red]")
            console.print("   Estimated Cost: [bold red]Unable to estimate (Network unavailable)[/bold red]")
    
    # Confirmation prompt (skip if --yes flag or no pending batches)
    if pending_batches and not assume_yes:
        console.print("")
        proceed = typer.confirm("⚠️  Continue with analysis?")
        if not proceed:
            console.print("[yellow]Analysis cancelled by user.[/yellow]")
            raise typer.Exit(0)

    # 6. Runner Execution
    if not pending_batches:
            console.print("[yellow]All batches completed. Skipping execution.[/yellow]")
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            FlexibleTaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task_runner = progress.add_task("Running analysis batches...", total=len(plan.phases)) # Rough progress
            task_batch = progress.add_task(f"Processing {len(pending_batches)} batches...", total=len(pending_batches))
            
            runner = Runner(
                repo_path, 
                llm, 
                state_manager, 
                language=config.language,
                model_name=model_name,
                is_local=is_local, 
                output_dir=config.output_dir
            )
            
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
                progress.advance(task_runner) # Advance phase/runner progress roughly
        
            # 6. Synthesize Docs
            task_synth = progress.add_task("Synthesizing documentation...", total=None)
            synthesizer = Synthesizer(repo_path, language=config.language, output_dir=config.output_dir)
            synthesizer.generate_top_down_docs()
            progress.update(task_synth, total=1, completed=1)

    console.print(f"[bold green]Analysis Complete![/bold green]")
    console.print(f"Documentation available in: {repo_path / config.output_dir}")
    
    # Show final cost report if batches were processed
    if pending_batches:
        console.print("")
        console.print(runner.get_cost_report())


@app.command()
def version() -> None:
    """Show version information."""
    from lantern_cli import __version__

    console.print(f"Lantern CLI version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
