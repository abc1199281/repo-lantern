"""Lantern CLI - Main entry point."""

import shutil
from pathlib import Path

import typer
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

from lantern_cli.config.loader import load_config
from lantern_cli.core.architect import Architect, Batch, Phase, Plan
from lantern_cli.core.diff_tracker import DiffTracker
from lantern_cli.core.runner import Runner
from lantern_cli.core.state_manager import StateManager
from lantern_cli.core.synthesizer import Synthesizer
from lantern_cli.core.translator import Translator
from lantern_cli.llm.factory import create_backend
from lantern_cli.static_analysis import DependencyGraph, FileFilter
from lantern_cli.utils.cost_tracker import CostTracker
from lantern_cli.utils.observability import configure_langsmith

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
    overwrite: bool = typer.Option(
        False, "--overwrite", "-f", help="Force re-initialization and overwrite existing config"
    ),
) -> None:
    """Initialize Lantern for a repository."""
    repo_path = Path(repo).resolve()
    lantern_dir = repo_path / ".lantern"

    if lantern_dir.exists():
        if overwrite:
            console.print(
                f"[yellow]Overwriting existing Lantern configuration in {repo_path}...[/yellow]"
            )
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
    output: str | None = typer.Option(None, help="Output directory"),
    lang: str | None = typer.Option(None, help="Output language (en/zh-TW)"),
    planning_mode: str = typer.Option(
        "agentic",
        "--planning-mode",
        help="Planning mode: 'static' (topological) or 'agentic' (LLM-enhanced)",
    ),
) -> None:
    """Generate analysis plan (lantern_plan.md) without running analysis."""
    repo_path = Path(repo).resolve()

    # 0. Load Configuration (for filters)
    config = load_config(repo_path, output=output, lang=lang)

    # Respect config.output_dir when CLI `--output` is not provided
    output_dir = config.output_dir

    # Initialize backend if agentic planning is requested
    backend = None
    if planning_mode == "agentic":
        try:
            backend = create_backend(config)
        except Exception as e:
            console.print(
                f"[bold yellow]Failed to initialize LLM backend: {e}. "
                f"Falling back to static planning.[/bold yellow]"
            )
            planning_mode = "static"

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
        if planning_mode == "agentic":
            task_plan = progress.add_task("Architecting analysis plan (agentic)...", total=None)
            try:
                from lantern_cli.core.agentic_planner import AgenticPlanner

                agentic_planner = AgenticPlanner(repo_path, backend, language=config.language)
                plan = agentic_planner.generate_enhanced_plan(
                    file_list=list(graph.dependencies.keys()),
                    dependencies=graph.dependencies,
                    reverse_dependencies=graph.reverse_dependencies,
                    layers=graph.calculate_layers(),
                    mermaid_graph=Architect(repo_path, graph).generate_mermaid_graph(),
                )
            except ImportError:
                console.print(
                    "[bold yellow]langgraph not installed. "
                    "Falling back to static planning.[/bold yellow]"
                )
                architect = Architect(repo_path, graph)
                plan = architect.generate_plan()
            except Exception as e:
                console.print(
                    f"[bold yellow]Agentic planning failed: {e}. "
                    f"Falling back to static planning.[/bold yellow]"
                )
                architect = Architect(repo_path, graph)
                plan = architect.generate_plan()
        else:
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

    console.print("[bold green]Plan generated successfully![/bold green]")
    console.print(f"Plan file: {plan_path}")
    console.print(f"Planning mode: {planning_mode}")
    console.print("Run 'lantern run' to execute this plan.")


@app.command()
def run(
    repo: str = typer.Option(".", help="Repository path"),
    output: str | None = typer.Option(None, help="Output directory"),
    lang: str | None = typer.Option(None, help="Output language (en/zh-TW)"),
    assume_yes: bool = typer.Option(False, "--yes", "-y", help="Skip cost confirmation prompt"),
    synthesis_mode: str = typer.Option(
        "agentic",
        "--synthesis-mode",
        help="Synthesis mode: 'batch' (rule-based) or 'agentic' (LLM-powered)",
    ),
    planning_mode: str = typer.Option(
        "agentic",
        "--planning-mode",
        help="Planning mode: 'static' (topological) or 'agentic' (LLM-enhanced)",
    ),
    use_workflow: bool = typer.Option(
        True,
        "--workflow",
        help="Use new LangGraph workflow orchestration (Phase 3) instead of manual orchestration",
    ),
    resume_thread: str | None = typer.Option(
        None,
        "--resume",
        help="Resume execution from checkpoint with given thread ID",
    ),
) -> None:
    """Run analysis on repository."""
    repo_path = Path(repo).resolve()

    # 1. Load Configuration
    config = load_config(
        repo_path,
        output=output,
        lang=lang,
    )

    # Save user's target language; all analysis runs in English first
    target_language = config.language

    # 1.5. Configure LangSmith observability
    tracing_enabled = configure_langsmith(config.langsmith)

    console.print("[bold green]Lantern Analysis[/bold green]")
    console.print(f"Repository: {repo_path}")
    console.print(f"Backend: {config.backend.type} ({config.backend.api_provider})")
    if tracing_enabled:
        console.print(f"[cyan]LangSmith tracing: ON (project={config.langsmith.project})[/cyan]")
    if use_workflow:
        console.print("[cyan]Using LangGraph Workflow Orchestration (Phase 3)[/cyan]")

    # 2. Initialize Backend
    try:
        backend = create_backend(config)
    except Exception as e:
        console.print(f"[bold red]Error initializing LLM backend:[/bold red] {e}")
        raise typer.Exit(code=1)

    # 2.5. Execute with new LangGraph workflow if --workflow flag is set
    if use_workflow:
        try:
            from lantern_cli.core.workflow import LanternWorkflowExecutor

            executor = LanternWorkflowExecutor(
                repo_path=repo_path,
                backend=backend,
                config=config,
                language="en",
                target_language=target_language,
                synthesis_mode=synthesis_mode,
                planning_mode=planning_mode,
                assume_yes=assume_yes,
                output_dir=config.output_dir,
            )

            console.print("[cyan]Executing workflow...[/cyan]")

            # Execute workflow synchronously
            final_state = executor.execute_sync(thread_id=resume_thread)

            # Report results
            console.print("[bold green]Analysis Complete![/bold green]")
            console.print(f"Documentation available in: {repo_path / config.output_dir}")

            if final_state.get("documents"):
                console.print(f"\nGenerated {len(final_state['documents'])} documents:")
                for doc_name in final_state["documents"].keys():
                    console.print(f"  - {doc_name}")

            if final_state.get("total_cost", 0) > 0:
                console.print(f"\nTotal cost: ${final_state['total_cost']:.4f}")

            raise typer.Exit(code=0)

        except ImportError as e:
            if "langgraph" in str(e).lower():
                console.print(
                    "[bold yellow]langgraph not installed. "
                    "Falling back to manual orchestration.[/bold yellow]"
                )
                console.print("[dim]Install with: pip install langgraph[/dim]")
            else:
                console.print(
                    f"[bold yellow]Workflow import error: {e}. "
                    "Falling back to manual orchestration.[/bold yellow]"
                )
            use_workflow = False
        except Exception as e:
            console.print(
                f"[bold yellow]Workflow execution failed: {e}. "
                "Falling back to manual orchestration.[/bold yellow]"
            )
            use_workflow = False

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
        if planning_mode == "agentic":
            task_plan = progress.add_task("Architecting analysis plan (agentic)...", total=None)
            try:
                from lantern_cli.core.agentic_planner import AgenticPlanner

                agentic_planner = AgenticPlanner(repo_path, backend, language="en")
                plan = agentic_planner.generate_enhanced_plan(
                    file_list=list(graph.dependencies.keys()),
                    dependencies=graph.dependencies,
                    reverse_dependencies=graph.reverse_dependencies,
                    layers=graph.calculate_layers(),
                    mermaid_graph=Architect(repo_path, graph).generate_mermaid_graph(),
                )
            except ImportError:
                console.print(
                    "[bold yellow]langgraph not installed. "
                    "Falling back to static planning.[/bold yellow]"
                )
                architect = Architect(repo_path, graph)
                plan = architect.generate_plan()
            except Exception as e:
                console.print(
                    f"[bold yellow]Agentic planning failed: {e}. "
                    f"Falling back to static planning.[/bold yellow]"
                )
                architect = Architect(repo_path, graph)
                plan = architect.generate_plan()
        else:
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
    model_name = backend.model_name
    is_local = config.backend.type == "ollama"

    # Initialize state manager (needed for pending batches)
    state_manager = StateManager(repo_path, backend=backend)

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
            prompt="Analyze these files and provide insights.",
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
    console.print(f"   Planning Mode: {planning_mode}")
    console.print(f"   Synthesis Mode: {synthesis_mode}")

    if pricing_available:
        if is_local:
            console.print("   Pricing Source: [green]Local (Free)[/green]")
            console.print(f"   Estimated Tokens: ~{total_estimated_tokens:,} (Input + Est. Output)")
            console.print("   Estimated Cost: [bold green]$0.0000 (Free)[/bold green]")
        else:
            console.print("   Pricing Source: [green]Online (Live)[/green]")
            console.print(f"   Estimated Tokens: ~{total_estimated_tokens:,} (Input + Est. Output)")
            console.print(
                f"   Estimated Cost: [bold yellow]${total_estimated_cost:.4f}[/bold yellow]"
            )
    else:
        if config.backend.type == "cli":
            console.print("   Pricing Source: [yellow]CLI Tool[/yellow]")
            console.print(
                "   Estimated Cost: [bold yellow]CLI estimate not available[/bold yellow]"
            )
        else:
            console.print("   Pricing Source: [red]Offline[/red]")
            console.print(
                "   Estimated Cost: [bold red]Unable to estimate (Network unavailable)[/bold red]"
            )

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
            task_runner = progress.add_task(
                "Running analysis batches...", total=len(plan.phases)
            )  # Rough progress
            task_batch = progress.add_task(
                f"Processing {len(pending_batches)} batches...", total=len(pending_batches)
            )

            runner = Runner(
                repo_path,
                backend,
                state_manager,
                language="en",
                model_name=model_name,
                is_local=is_local,
                output_dir=config.output_dir,
            )

            for batch in pending_batches:
                progress.update(
                    task_batch,
                    description=f"Analyzing Batch {batch.id} ({len(batch.files)} files)...",
                )

                task_files = progress.add_task(
                    f"  Batch {batch.id}: preparing...",
                    total=len(batch.files),
                    visible=True,
                )

                def file_callback(
                    file_path: str,
                    status: str,
                    _task_id: int = task_files,
                ) -> None:
                    if status == "start":
                        short = Path(file_path).name
                        progress.update(_task_id, description=f"  Analyzing {short}...")
                    elif status == "done":
                        progress.advance(_task_id)

                # Construct prompt with optional batch hint
                hint_instruction = f"\n\nAnalysis guidance: {batch.hint}" if batch.hint else ""
                prompt = (
                    f"Analyze these files: {batch.files}. "
                    f"Provide a summary and key insights."
                    f"{hint_instruction}"
                )

                success = runner.run_batch(batch, prompt, on_file_progress=file_callback)
                if not success:
                    console.print(f"[bold red]Batch {batch.id} failed.[/bold red]")
                    # For MVP, continue on failure; retry logic is in Runner

                progress.remove_task(task_files)
                progress.advance(task_batch)
                progress.advance(task_runner)  # Advance phase/runner progress roughly

            # 6. Synthesize Docs
            if synthesis_mode == "agentic":
                task_synth = progress.add_task(
                    "Synthesizing documentation (agentic)...", total=None
                )
                try:
                    from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

                    agentic_synth = AgenticSynthesizer(
                        repo_path, backend, language="en", output_dir=config.output_dir
                    )
                    agentic_synth.generate_top_down_docs()
                except ImportError:
                    console.print(
                        "[bold yellow]langgraph not installed. "
                        "Falling back to batch synthesis.[/bold yellow]"
                    )
                    console.print("[dim]Install with: pip install langgraph[/dim]")
                    synthesizer = Synthesizer(
                        repo_path,
                        language="en",
                        output_dir=config.output_dir,
                        backend=backend,
                    )
                    synthesizer.generate_top_down_docs()
                except Exception as e:
                    console.print(
                        f"[bold yellow]Agentic synthesis failed: {e}. "
                        f"Falling back to batch synthesis.[/bold yellow]"
                    )
                    synthesizer = Synthesizer(
                        repo_path,
                        language="en",
                        output_dir=config.output_dir,
                        backend=backend,
                    )
                    synthesizer.generate_top_down_docs()
            else:
                task_synth = progress.add_task("Synthesizing documentation...", total=None)
                synthesizer = Synthesizer(
                    repo_path,
                    language="en",
                    output_dir=config.output_dir,
                    backend=backend,
                )
                synthesizer.generate_top_down_docs()
            progress.update(task_synth, total=1, completed=1)

            # 7. Translation (if target language is not English)
            if target_language != "en":
                task_translate = progress.add_task(
                    f"Translating to {target_language}...", total=None
                )
                translator = Translator(backend, target_language, repo_path / config.output_dir)
                translator.translate_all()
                progress.update(task_translate, total=1, completed=1)

    console.print("[bold green]Analysis Complete![/bold green]")
    console.print(f"Documentation available in: {repo_path / config.output_dir}")

    # Record git commit SHA for incremental tracking
    diff_tracker = DiffTracker(repo_path)
    if diff_tracker.is_git_repo():
        try:
            sha = diff_tracker.get_current_commit()
            state_manager.update_git_commit(sha)
            console.print(f"[dim]Recorded git commit: {sha[:8]}[/dim]")
        except RuntimeError:
            pass

    # Show final cost report if batches were processed
    if pending_batches:
        console.print("")
        console.print(runner.get_cost_report())


@app.command()
def update(
    repo: str = typer.Option(".", help="Repository path"),
    output: str | None = typer.Option(None, help="Output directory"),
    lang: str | None = typer.Option(None, help="Output language (en/zh-TW)"),
    assume_yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    synthesis_mode: str = typer.Option(
        "agentic",
        "--synthesis-mode",
        help="Synthesis mode: 'batch' (rule-based) or 'agentic' (LLM-powered)",
    ),
    planning_mode: str = typer.Option(
        "agentic",
        "--planning-mode",
        help="Planning mode: 'static' (topological) or 'agentic' (LLM-enhanced)",
    ),
) -> None:
    """Incrementally update analysis for a previously analyzed repository.

    Uses ``git diff`` to detect changes since the last analysis and only
    re-analyzes affected files plus their direct dependents.
    """
    repo_path = Path(repo).resolve()

    # 1. Load configuration
    config = load_config(repo_path, output=output, lang=lang)
    target_language = config.language

    # 2. Validate git state
    diff_tracker = DiffTracker(repo_path)
    if not diff_tracker.is_git_repo():
        console.print("[bold red]Error:[/bold red] Not a git repository.")
        console.print("Incremental update requires git. Use `lantern run` instead.")
        raise typer.Exit(code=1)

    state_manager = StateManager(repo_path, output_dir=config.output_dir)
    base_sha = state_manager.state.git_commit_sha

    if not base_sha:
        console.print(
            "[bold yellow]No previous analysis found.[/bold yellow] "
            "Run `lantern run` first to perform initial analysis."
        )
        raise typer.Exit(code=1)

    if not diff_tracker.commit_exists(base_sha):
        console.print(
            f"[bold yellow]Previous commit {base_sha[:8]} no longer exists "
            f"(force push / rebase?).[/bold yellow]"
        )
        console.print("Please run `lantern run --overwrite` for a full re-analysis.")
        raise typer.Exit(code=1)

    # 3. Detect changes
    current_sha = diff_tracker.get_current_commit()
    if current_sha == base_sha:
        console.print("[green]No changes detected since last analysis.[/green]")
        raise typer.Exit(code=0)

    diff_result = diff_tracker.get_diff(base_sha)

    total_changes = (
        len(diff_result.added)
        + len(diff_result.modified)
        + len(diff_result.deleted)
        + len(diff_result.renamed)
    )
    if total_changes == 0:
        console.print("[green]No relevant file changes detected.[/green]")
        state_manager.update_git_commit(current_sha)
        raise typer.Exit(code=0)

    console.print("[bold cyan]Incremental Update[/bold cyan]")
    console.print(f"Repository: {repo_path}")
    console.print(f"Base commit: {base_sha[:8]} -> HEAD: {current_sha[:8]}")
    console.print(
        f"Changes: +{len(diff_result.added)} modified:{len(diff_result.modified)} "
        f"-{len(diff_result.deleted)} renamed:{len(diff_result.renamed)}"
    )

    # 4. Rebuild dependency graph & calculate impact
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        FlexibleTaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_graph = progress.add_task("Rebuilding dependency graph...", total=None)
        file_filter = FileFilter(repo_path, config.filter)
        graph = DependencyGraph(repo_path, file_filter=file_filter)
        graph.build()
        progress.update(task_graph, total=1, completed=1)

    impact = diff_tracker.calculate_impact(diff_result, graph, state_manager.state.file_manifest)

    total_files = len(graph.dependencies)
    if diff_tracker.should_full_reanalyze(impact, total_files):
        console.print(
            f"[bold yellow]{len(impact.reanalyze)}/{total_files} files affected "
            f"(>{int(DiffTracker.FULL_REANALYSIS_THRESHOLD * 100)}%).[/bold yellow] "
            f"Consider running `lantern run` for full re-analysis."
        )

    # Filter impact set to only files in the current dependency graph scope
    scope_files = set(graph.dependencies.keys())
    impact.reanalyze = {f for f in impact.reanalyze if f in scope_files}

    if not impact.reanalyze and not impact.remove:
        console.print("[green]No analysable files affected.[/green]")
        state_manager.update_git_commit(current_sha)
        raise typer.Exit(code=0)

    console.print(f"\nFiles to re-analyse: {len(impact.reanalyze)}")
    for f in sorted(impact.reanalyze):
        console.print(f"  [cyan]+[/cyan] {f}  ({impact.reason.get(f, '')})")
    if impact.remove:
        console.print(f"Files to clean up: {len(impact.remove)}")
        for f in sorted(impact.remove):
            console.print(f"  [red]-[/red] {f}")

    # 5. Clean stale artefacts
    if impact.remove:
        state_manager.clean_stale_artefacts(impact.remove, output_dir=config.output_dir)
        console.print(f"[dim]Cleaned artefacts for {len(impact.remove)} removed file(s).[/dim]")

    # 6. Initialize backend
    try:
        backend = create_backend(config)
    except Exception as e:
        console.print(f"[bold red]Error initializing LLM backend:[/bold red] {e}")
        raise typer.Exit(code=1)

    # 7. Create incremental plan (only for impact set files)
    files_to_analyze = sorted(impact.reanalyze)
    layers = graph.calculate_layers()

    # Group by layer, same as Architect, but only for affected files
    layer_groups: dict[int, list[str]] = {}
    for f in files_to_analyze:
        layer_idx = layers.get(f, 0)
        if layer_idx not in layer_groups:
            layer_groups[layer_idx] = []
        layer_groups[layer_idx].append(f)

    batch_size = Architect.BATCH_SIZE
    next_batch_id = state_manager.state.last_batch_id + 1
    phases: list[Phase] = []

    for layer_idx in sorted(layer_groups.keys()):
        files = sorted(layer_groups[layer_idx])
        batches: list[Batch] = []
        for i in range(0, len(files), batch_size):
            batch_files = files[i : i + batch_size]
            batches.append(Batch(id=next_batch_id, files=batch_files))
            next_batch_id += 1
        phases.append(Phase(id=layer_idx + 1 if layer_idx >= 0 else 0, batches=batches))

    incremental_plan = Plan(phases=phases)
    pending_batches = [b for p in incremental_plan.phases for b in p.batches]

    console.print(f"\nIncremental plan: {len(pending_batches)} batch(es)")

    # Cost estimation
    model_name = backend.model_name
    is_local = config.backend.type == "ollama"
    cost_tracker = CostTracker(model_name, is_local=is_local)

    total_est_cost = 0.0
    for batch in pending_batches:
        est = cost_tracker.estimate_batch_cost(
            files=batch.files, context="", prompt="Analyze these files."
        )
        if est:
            total_est_cost += est[1]

    if not is_local and total_est_cost > 0:
        console.print(f"   Estimated cost: [bold yellow]${total_est_cost:.4f}[/bold yellow]")

    if not assume_yes:
        proceed = typer.confirm("Continue with incremental analysis?")
        if not proceed:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # 8. Execute incremental batches
    state_manager_run = StateManager(repo_path, backend=backend, output_dir=config.output_dir)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        FlexibleTaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_batch = progress.add_task(
            f"Analysing {len(pending_batches)} batch(es)...", total=len(pending_batches)
        )

        runner = Runner(
            repo_path,
            backend,
            state_manager_run,
            language="en",
            model_name=model_name,
            is_local=is_local,
            output_dir=config.output_dir,
        )

        for batch in pending_batches:
            progress.update(
                task_batch,
                description=f"Batch {batch.id} ({len(batch.files)} files)...",
            )
            hint = ""
            prompt = (
                f"Analyze these files: {batch.files}. "
                f"Provide a summary and key insights."
                f"{hint}"
            )
            success = runner.run_batch(batch, prompt)
            if not success:
                console.print(f"[bold red]Batch {batch.id} failed.[/bold red]")
            progress.advance(task_batch)

        # 9. Re-synthesize top-down docs
        task_synth = progress.add_task("Re-synthesizing documentation...", total=None)
        if synthesis_mode == "agentic":
            try:
                from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

                agentic_synth = AgenticSynthesizer(
                    repo_path, backend, language="en", output_dir=config.output_dir
                )
                agentic_synth.generate_top_down_docs()
            except (ImportError, Exception):
                synthesizer = Synthesizer(
                    repo_path, language="en", output_dir=config.output_dir, backend=backend
                )
                synthesizer.generate_top_down_docs()
        else:
            synthesizer = Synthesizer(
                repo_path, language="en", output_dir=config.output_dir, backend=backend
            )
            synthesizer.generate_top_down_docs()
        progress.update(task_synth, total=1, completed=1)

        # 10. Translation
        if target_language != "en":
            task_translate = progress.add_task(f"Translating to {target_language}...", total=None)
            translator = Translator(backend, target_language, repo_path / config.output_dir)
            translator.translate_all()
            progress.update(task_translate, total=1, completed=1)

    # 11. Record new git commit
    state_manager_run.update_git_commit(current_sha)

    console.print("[bold green]Incremental update complete![/bold green]")
    console.print(f"Documentation available in: {repo_path / config.output_dir}")
    console.print(f"[dim]Git commit: {base_sha[:8]} -> {current_sha[:8]}[/dim]")


@app.command(name="diff")
def show_diff(
    repo: str = typer.Option(".", help="Repository path"),
    output: str | None = typer.Option(None, help="Output directory"),
) -> None:
    """Show changes since the last analysis without running analysis.

    Previews what ``lantern update`` would re-analyse.
    """
    repo_path = Path(repo).resolve()
    config = load_config(repo_path, output=output)

    diff_tracker = DiffTracker(repo_path)
    if not diff_tracker.is_git_repo():
        console.print("[bold red]Error:[/bold red] Not a git repository.")
        raise typer.Exit(code=1)

    state_manager = StateManager(repo_path, output_dir=config.output_dir)
    base_sha = state_manager.state.git_commit_sha

    if not base_sha:
        console.print("[yellow]No previous analysis found. Run `lantern run` first.[/yellow]")
        raise typer.Exit(code=1)

    if not diff_tracker.commit_exists(base_sha):
        console.print(
            f"[bold yellow]Previous commit {base_sha[:8]} no longer exists.[/bold yellow]"
        )
        raise typer.Exit(code=1)

    current_sha = diff_tracker.get_current_commit()
    if current_sha == base_sha:
        console.print("[green]No changes since last analysis.[/green]")
        raise typer.Exit(code=0)

    diff_result = diff_tracker.get_diff(base_sha)

    # Build graph for impact analysis
    file_filter = FileFilter(repo_path, config.filter)
    graph = DependencyGraph(repo_path, file_filter=file_filter)
    graph.build()

    impact = diff_tracker.calculate_impact(diff_result, graph, state_manager.state.file_manifest)
    scope_files = set(graph.dependencies.keys())
    impact.reanalyze = {f for f in impact.reanalyze if f in scope_files}

    console.print(f"[bold]Changes: {base_sha[:8]} -> {current_sha[:8]}[/bold]\n")

    if diff_result.added:
        console.print(f"[green]Added ({len(diff_result.added)}):[/green]")
        for f in sorted(diff_result.added):
            console.print(f"  + {f}")
    if diff_result.modified:
        console.print(f"[yellow]Modified ({len(diff_result.modified)}):[/yellow]")
        for f in sorted(diff_result.modified):
            console.print(f"  ~ {f}")
    if diff_result.deleted:
        console.print(f"[red]Deleted ({len(diff_result.deleted)}):[/red]")
        for f in sorted(diff_result.deleted):
            console.print(f"  - {f}")
    if diff_result.renamed:
        console.print(f"[cyan]Renamed ({len(diff_result.renamed)}):[/cyan]")
        for old, new in sorted(diff_result.renamed):
            console.print(f"  {old} -> {new}")

    console.print("\n[bold]Impact analysis:[/bold]")
    console.print(f"  Files to re-analyse: {len(impact.reanalyze)}")
    for f in sorted(impact.reanalyze):
        console.print(f"    {f}  ({impact.reason.get(f, '')})")
    if impact.remove:
        console.print(f"  Files to clean up: {len(impact.remove)}")

    total_files = len(graph.dependencies)
    if diff_tracker.should_full_reanalyze(impact, total_files):
        console.print(
            f"\n[bold yellow]>{int(DiffTracker.FULL_REANALYSIS_THRESHOLD * 100)}% of files "
            f"affected. Consider full re-analysis.[/bold yellow]"
        )


@app.command()
def version() -> None:
    """Show version information."""
    from lantern_cli import __version__

    console.print(f"Lantern CLI version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
