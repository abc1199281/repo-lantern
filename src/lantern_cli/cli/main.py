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
    TimeElapsedColumn,
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
from lantern_cli.utils.observability import configure_langsmith

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "template" / "defaults"
DEFAULT_CONFIG_PATH = TEMPLATE_ROOT / "lantern.toml"
SKILLS_TEMPLATE_PATH = TEMPLATE_ROOT / "lantern_skills.md"

LANTERN_SECTION_START = "<!-- lantern-skills -->"
LANTERN_SECTION_END = "<!-- /lantern-skills -->"

TOOL_DESTINATIONS: dict[str, str] = {
    "codex": "AGENTS.md",
    "copilot": ".github/copilot-instructions.md",
    "claude": "CLAUDE.md",
}


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
    output: str | None = typer.Option(None, help="Output directory (default: .lantern)"),
    overwrite: bool = typer.Option(
        False, "--overwrite", "-f", help="Force re-initialization and overwrite existing config"
    ),
) -> None:
    """Initialize Lantern for a repository."""
    repo_path = Path(repo).resolve()
    lantern_dir = repo_path / ".lantern"

    # Resolve --output relative to CWD so it doesn't get joined with repo_path
    if output is not None:
        output = str(Path(output).resolve())

    # Determine the output directory (where analysis results go)
    output_dir = output if output is not None else ".lantern"

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

        # If a custom output directory is specified, update it in the config
        if output is not None:
            config_content = config_content.replace(
                'output_dir = ".lantern"',
                f'output_dir = "{output_dir}"',
            )
            # Create the custom output directory
            custom_output = repo_path / output_dir
            custom_output.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]Output directory created: {custom_output}[/green]")

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

    # Resolve --output relative to CWD so it doesn't get joined with repo_path
    if output is not None:
        output = str(Path(output).resolve())

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

        # 2. Load spec context for planning
        from lantern_cli.core.spec_manager import get_all_spec_summaries, load_specs

        plan_spec_entries = load_specs(repo_path / output_dir)
        plan_spec_ctx = get_all_spec_summaries(plan_spec_entries, repo_path / output_dir)

        # 3. Architect Plan
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
                    spec_context=plan_spec_ctx,
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
    use_workflow: bool = typer.Option(
        True,
        "--workflow",
        help="Use LangGraph workflow orchestration instead of manual orchestration",
    ),
    resume_thread: str | None = typer.Option(
        None,
        "--resume",
        help="Resume execution from checkpoint with given thread ID",
    ),
) -> None:
    """Run analysis on repository."""
    repo_path = Path(repo).resolve()

    # Resolve --output relative to CWD so it doesn't get joined with repo_path
    if output is not None:
        output = str(Path(output).resolve())

    # 1. Load Configuration
    config = load_config(
        repo_path,
        output=output,
        lang=lang,
    )

    # 1.5. Configure LangSmith observability
    tracing_enabled = configure_langsmith(config.langsmith)

    console.print("[bold green]Lantern Analysis[/bold green]")
    console.print(f"Repository: {repo_path}")
    console.print(f"Backend: {config.backend.type} ({config.backend.api_provider})")
    if tracing_enabled:
        console.print(f"[cyan]LangSmith tracing: ON (project={config.langsmith.project})[/cyan]")
    if use_workflow:
        console.print("[cyan]Using LangGraph Workflow Orchestration[/cyan]")

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
                language=config.language,
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

        # 4. Load spec context for planning
        from lantern_cli.core.spec_manager import (
            get_all_spec_summaries as get_all_run_specs,
        )
        from lantern_cli.core.spec_manager import (
            load_specs as load_run_specs,
        )

        run_spec_entries = load_run_specs(repo_path / config.output_dir)
        run_spec_ctx = get_all_run_specs(run_spec_entries, repo_path / config.output_dir)

        # 5. Architect Plan
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
                    spec_context=run_spec_ctx,
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

    # 5. Plan Summary
    model_name = backend.model_name

    # Initialize state manager (needed for pending batches)
    state_manager = StateManager(repo_path, backend=backend, output_dir=config.output_dir)
    pending_batches = state_manager.get_pending_batches(plan)

    console.print("\n[bold cyan]Analysis Plan Summary[/bold cyan]")
    console.print(f"   Total Phases: {len(plan.phases)}")
    console.print(f"   Total Batches: {len([b for p in plan.phases for b in p.batches])}")
    console.print(f"   Pending Batches: {len(pending_batches)}")
    console.print(f"   Model: {model_name}")
    console.print(f"   Planning Mode: {planning_mode}")
    console.print(f"   Synthesis Mode: {synthesis_mode}")

    # Confirmation prompt (skip if --yes flag or no pending batches)
    if pending_batches and not assume_yes:
        console.print("")
        proceed = typer.confirm("Continue with analysis?")
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
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            total_batches = len(pending_batches)
            task_batch = progress.add_task(
                f"Batch 0/{total_batches} — Starting...",
                total=total_batches,
            )

            # Load spec entries for context injection
            from lantern_cli.core.spec_manager import load_specs

            spec_entries = load_specs(repo_path / config.output_dir)

            runner = Runner(
                repo_path,
                backend,
                state_manager,
                language=config.language,
                output_dir=config.output_dir,
                spec_entries=spec_entries,
                plan=plan,
            )

            for batch_idx, batch in enumerate(pending_batches, 1):
                batch_label = f"Batch {batch_idx}/{total_batches}"
                file_names = ", ".join(Path(f).name for f in batch.files[:3])
                if len(batch.files) > 3:
                    file_names += f" +{len(batch.files) - 3} more"

                progress.update(
                    task_batch,
                    description=f"{batch_label} — Preparing [{file_names}]",
                )

                task_files = progress.add_task(
                    "  Waiting for LLM...",
                    total=None,
                    visible=True,
                )

                def phase_callback(
                    phase: str,
                    batch_id: int,
                    _task_id: int = task_files,
                    _batch_label: str = batch_label,
                    _num_files: int = len(batch.files),
                ) -> None:
                    if phase == "analyzing":
                        progress.update(
                            _task_id,
                            description=f"  {_batch_label}: Waiting for LLM...",
                            total=None,
                        )
                    elif phase == "writing":
                        progress.update(
                            _task_id,
                            description=f"  {_batch_label}: Writing results...",
                            total=_num_files,
                            completed=0,
                        )

                def file_callback(
                    file_path: str,
                    status: str,
                    _task_id: int = task_files,
                ) -> None:
                    if status == "start":
                        short = Path(file_path).name
                        progress.update(_task_id, description=f"  Writing {short}...")
                    elif status == "done":
                        progress.advance(_task_id)

                # Construct prompt with optional batch hint
                language_instruction = (
                    f" Please respond in {config.language}." if config.language != "en" else ""
                )
                hint_instruction = f"\n\nAnalysis guidance: {batch.hint}" if batch.hint else ""
                prompt = (
                    f"Analyze these files: {batch.files}. "
                    f"Provide a summary and key insights."
                    f"{language_instruction}{hint_instruction}"
                )

                success = runner.run_batch(
                    batch,
                    prompt,
                    on_file_progress=file_callback,
                    on_batch_phase=phase_callback,
                )
                if not success:
                    console.print(f"[bold red]Batch {batch.id} failed.[/bold red]")

                progress.remove_task(task_files)
                progress.advance(task_batch)
                progress.update(
                    task_batch,
                    description=f"Batch {batch_idx}/{total_batches} — Done",
                )

            # 6. Synthesize Docs
            if synthesis_mode == "agentic":
                task_synth = progress.add_task(
                    "Synthesizing documentation (agentic)...", total=None
                )
                try:
                    from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer
                    from lantern_cli.core.spec_manager import (
                        get_all_spec_summaries,
                    )

                    spec_ctx = get_all_spec_summaries(spec_entries, repo_path / config.output_dir)
                    agentic_synth = AgenticSynthesizer(
                        repo_path,
                        backend,
                        language=config.language,
                        output_dir=config.output_dir,
                        spec_context=spec_ctx,
                        plan=plan,
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
                        language=config.language,
                        output_dir=config.output_dir,
                        backend=backend,
                        plan=plan,
                    )
                    synthesizer.generate_top_down_docs()
                except Exception as e:
                    console.print(
                        f"[bold yellow]Agentic synthesis failed: {e}. "
                        f"Falling back to batch synthesis.[/bold yellow]"
                    )
                    synthesizer = Synthesizer(
                        repo_path,
                        language=config.language,
                        output_dir=config.output_dir,
                        backend=backend,
                        plan=plan,
                    )
                    synthesizer.generate_top_down_docs()
            else:
                task_synth = progress.add_task("Synthesizing documentation...", total=None)
                synthesizer = Synthesizer(
                    repo_path,
                    language=config.language,
                    output_dir=config.output_dir,
                    backend=backend,
                    plan=plan,
                )
                synthesizer.generate_top_down_docs()
            progress.update(task_synth, total=1, completed=1)

    # Save git commit SHA for incremental tracking
    diff_tracker = DiffTracker(repo_path)
    if diff_tracker.is_git_repo():
        try:
            current_sha = diff_tracker.get_current_commit()
            state_manager.update_git_commit(current_sha)
        except RuntimeError:
            pass

    console.print("[bold green]Analysis Complete![/bold green]")
    console.print(f"Documentation available in: {repo_path / config.output_dir}")


def _load_skills_template() -> str:
    try:
        return SKILLS_TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Unable to read skills template at {SKILLS_TEMPLATE_PATH}") from exc


def _write_skills(dest: Path, skills_content: str, overwrite: bool) -> str:
    """Write lantern skills section to a destination file.

    Returns a status string: 'created', 'appended', 'replaced', or 'skipped'.
    """
    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        if LANTERN_SECTION_START in existing:
            if not overwrite:
                return "skipped"
            if LANTERN_SECTION_END not in existing:
                # Corrupted section: start marker without end marker.
                # Remove the orphaned start marker and append fresh content.
                existing = existing.replace(LANTERN_SECTION_START, "")
                separator = "\n\n" if existing.rstrip() else ""
                dest.write_text(
                    existing.rstrip() + separator + skills_content + "\n",
                    encoding="utf-8",
                )
                return "replaced"
            # Replace existing section
            start = existing.index(LANTERN_SECTION_START)
            end = existing.index(LANTERN_SECTION_END) + len(LANTERN_SECTION_END)
            new_content = existing[:start] + skills_content + existing[end:]
            dest.write_text(new_content, encoding="utf-8")
            return "replaced"
        else:
            # Append to existing file
            separator = "\n\n" if existing.rstrip() else ""
            dest.write_text(existing.rstrip() + separator + skills_content + "\n", encoding="utf-8")
            return "appended"
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(skills_content + "\n", encoding="utf-8")
        return "created"


@app.command()
def onboard(
    repo: str = typer.Option(".", help="Repository path"),
    tools: list[str] = typer.Option(
        ["codex", "copilot", "claude"], help="Target tools (codex, copilot, claude)"
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", "-f", help="Replace existing lantern section"
    ),
) -> None:
    """Set up AI coding tool instructions for Lantern."""
    repo_path = Path(repo).resolve()
    skills_content = _load_skills_template()

    for tool in tools:
        tool_key = tool.lower()
        if tool_key not in TOOL_DESTINATIONS:
            console.print(
                f"[bold red]Unknown tool: {tool}[/bold red] "
                f"(valid: {', '.join(TOOL_DESTINATIONS)})"
            )
            continue

        dest = repo_path / TOOL_DESTINATIONS[tool_key]
        status = _write_skills(dest, skills_content, overwrite)

        status_colors = {
            "created": "green",
            "appended": "green",
            "replaced": "yellow",
            "skipped": "dim",
        }
        color = status_colors[status]
        console.print(f"[{color}]{tool_key}: {status} → {dest}[/{color}]")

    console.print("[bold green]Onboarding complete![/bold green]")


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
) -> None:
    """Incrementally update analysis for a previously analyzed repository.

    Uses ``git diff`` to detect changes since the last analysis and only
    re-analyzes affected files plus their direct dependents.
    """
    repo_path = Path(repo).resolve()

    # 1. Load configuration
    config = load_config(repo_path, output=output, lang=lang)

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
        console.print("Please run `lantern run` for a full re-analysis.")
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
        TimeElapsedColumn(),
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
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        total_batches = len(pending_batches)
        task_batch = progress.add_task(
            f"Batch 0/{total_batches} — Starting...",
            total=total_batches,
        )

        # Load spec entries for context injection
        from lantern_cli.core.spec_manager import load_specs as load_specs_update

        spec_entries_update = load_specs_update(repo_path / config.output_dir)

        runner = Runner(
            repo_path,
            backend,
            state_manager_run,
            language=config.language,
            output_dir=config.output_dir,
            spec_entries=spec_entries_update,
            plan=incremental_plan,
        )

        for batch_idx, batch in enumerate(pending_batches, 1):
            batch_label = f"Batch {batch_idx}/{total_batches}"
            file_names = ", ".join(Path(f).name for f in batch.files[:3])
            if len(batch.files) > 3:
                file_names += f" +{len(batch.files) - 3} more"

            progress.update(
                task_batch,
                description=f"{batch_label} — Preparing [{file_names}]",
            )

            task_files = progress.add_task(
                "  Waiting for LLM...",
                total=None,
                visible=True,
            )

            def phase_callback(
                phase: str,
                batch_id: int,
                _task_id: int = task_files,
                _batch_label: str = batch_label,
                _num_files: int = len(batch.files),
            ) -> None:
                if phase == "analyzing":
                    progress.update(
                        _task_id,
                        description=f"  {_batch_label}: Waiting for LLM...",
                        total=None,
                    )
                elif phase == "writing":
                    progress.update(
                        _task_id,
                        description=f"  {_batch_label}: Writing results...",
                        total=_num_files,
                        completed=0,
                    )

            def file_callback(
                file_path: str,
                status: str,
                _task_id: int = task_files,
            ) -> None:
                if status == "start":
                    short = Path(file_path).name
                    progress.update(_task_id, description=f"  Writing {short}...")
                elif status == "done":
                    progress.advance(_task_id)

            language_instruction = (
                f" Please respond in {config.language}." if config.language != "en" else ""
            )
            prompt = (
                f"Analyze these files: {batch.files}. "
                f"Provide a summary and key insights."
                f"{language_instruction}"
            )

            success = runner.run_batch(
                batch,
                prompt,
                on_file_progress=file_callback,
                on_batch_phase=phase_callback,
            )
            if not success:
                console.print(f"[bold red]Batch {batch.id} failed.[/bold red]")

            progress.remove_task(task_files)
            progress.advance(task_batch)
            progress.update(
                task_batch,
                description=f"Batch {batch_idx}/{total_batches} — Done",
            )

        # 9. Re-synthesize top-down docs
        if synthesis_mode == "agentic":
            task_synth = progress.add_task("Re-synthesizing documentation (agentic)...", total=None)
            try:
                from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer
                from lantern_cli.core.spec_manager import (
                    get_all_spec_summaries as get_all_spec_summaries_update,
                )

                spec_ctx_update = get_all_spec_summaries_update(
                    spec_entries_update, repo_path / config.output_dir
                )
                agentic_synth = AgenticSynthesizer(
                    repo_path,
                    backend,
                    language=config.language,
                    output_dir=config.output_dir,
                    spec_context=spec_ctx_update,
                    plan=incremental_plan,
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
                    language=config.language,
                    output_dir=config.output_dir,
                    backend=backend,
                    plan=incremental_plan,
                )
                synthesizer.generate_top_down_docs()
        else:
            task_synth = progress.add_task("Re-synthesizing documentation...", total=None)
            synthesizer = Synthesizer(
                repo_path,
                language=config.language,
                output_dir=config.output_dir,
                backend=backend,
                plan=incremental_plan,
            )
            synthesizer.generate_top_down_docs()
        progress.update(task_synth, total=1, completed=1)

        # 10. Translation
        if config.language != "en":
            task_translate = progress.add_task(f"Translating to {config.language}...", total=None)
            translator = Translator(backend, config.language, repo_path / config.output_dir)
            translator.translate_all()
            progress.update(task_translate, total=1, completed=1)

    # 11. Record new git commit
    state_manager_run.update_git_commit(current_sha)

    console.print("[bold green]Incremental update complete![/bold green]")
    console.print(f"Documentation available in: {repo_path / config.output_dir}")
    console.print(f"[dim]Git commit: {base_sha[:8]} -> {current_sha[:8]}[/dim]")


# ---------------------------------------------------------------------------
# Spec subcommand group
# ---------------------------------------------------------------------------

spec_app = typer.Typer(help="Manage specification documents for enhanced analysis")
app.add_typer(spec_app, name="spec")


@spec_app.command("add")
def spec_add(
    file_path: str = typer.Argument(help="Path to the spec file (PDF or Markdown)"),
    repo: str = typer.Option(".", help="Repository path"),
    output: str | None = typer.Option(None, help="Output directory"),
    lang: str | None = typer.Option(None, help="Output language"),
) -> None:
    """Add a specification document and auto-map it to source modules."""
    from lantern_cli.core.spec_manager import add_spec, build_file_tree

    repo_path = Path(repo).resolve()
    spec_file = Path(file_path).resolve()

    if not spec_file.exists():
        console.print(f"[bold red]File not found:[/bold red] {spec_file}")
        raise typer.Exit(code=1)

    suffix = spec_file.suffix.lower()
    if suffix not in (".pdf", ".md", ".markdown"):
        console.print(f"[bold red]Unsupported format:[/bold red] {suffix}. Use .pdf or .md files.")
        raise typer.Exit(code=1)

    config = load_config(repo_path, output=output, lang=lang)
    lantern_dir = repo_path / config.output_dir

    if not lantern_dir.exists():
        console.print(
            "[bold yellow]Lantern not initialized.[/bold yellow] " "Run `lantern init` first."
        )
        raise typer.Exit(code=1)

    # Initialize backend for LLM calls
    try:
        backend = create_backend(config)
    except Exception as e:
        console.print(f"[bold red]Error initializing LLM backend:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Build file tree for auto-mapping
    file_filter = FileFilter(repo_path, config.filter)
    file_list = [str(p.relative_to(repo_path)) for p in file_filter.walk()]
    file_tree = build_file_tree(repo_path, file_list)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Adding spec...", total=None)
        entry = add_spec(lantern_dir, spec_file, backend, file_tree)
        progress.update(task, total=1, completed=1)

    console.print(f"\n[bold green]Spec added:[/bold green] {entry.path}")
    console.print(f"  Label: {entry.label}")
    console.print(f"  Modules: {', '.join(entry.modules) or '(none detected)'}")
    console.print(f"  Summary: {entry.summary_path}")
    console.print("\n[dim]Edit .lantern/specs.toml to adjust module mappings if needed.[/dim]")


@spec_app.command("list")
def spec_list(
    repo: str = typer.Option(".", help="Repository path"),
    output: str | None = typer.Option(None, help="Output directory"),
) -> None:
    """List all registered specification documents."""
    from rich.table import Table

    from lantern_cli.core.spec_manager import load_specs

    repo_path = Path(repo).resolve()
    config = load_config(repo_path, output=output)
    lantern_dir = repo_path / config.output_dir

    entries = load_specs(lantern_dir)
    if not entries:
        console.print("[yellow]No specs registered.[/yellow]")
        console.print("[dim]Use `lantern spec add <file>` to add a spec.[/dim]")
        return

    table = Table(title="Registered Specifications")
    table.add_column("Label", style="cyan")
    table.add_column("Path", style="white")
    table.add_column("Modules", style="green")
    table.add_column("Summary", style="dim")

    for entry in entries:
        table.add_row(
            entry.label or Path(entry.path).stem,
            entry.path,
            ", ".join(entry.modules) or "(none)",
            entry.summary_path or "(none)",
        )

    console.print(table)


@spec_app.command("remove")
def spec_remove(
    spec_name: str = typer.Argument(help="Spec label or filename to remove"),
    repo: str = typer.Option(".", help="Repository path"),
    output: str | None = typer.Option(None, help="Output directory"),
    delete_files: bool = typer.Option(
        False, "--delete-files", help="Also delete the spec and summary files"
    ),
) -> None:
    """Remove a specification document from specs.toml."""
    from lantern_cli.core.spec_manager import load_specs, save_specs

    repo_path = Path(repo).resolve()
    config = load_config(repo_path, output=output)
    lantern_dir = repo_path / config.output_dir

    entries = load_specs(lantern_dir)
    remaining = []
    removed = None

    for entry in entries:
        label = entry.label or Path(entry.path).stem
        filename = Path(entry.path).name
        if label == spec_name or filename == spec_name or entry.path == spec_name:
            removed = entry
        else:
            remaining.append(entry)

    if removed is None:
        console.print(f"[bold red]Spec not found:[/bold red] {spec_name}")
        console.print("[dim]Use `lantern spec list` to see registered specs.[/dim]")
        raise typer.Exit(code=1)

    save_specs(lantern_dir, remaining)

    if delete_files:
        for rel_path in [removed.path, removed.summary_path]:
            if rel_path:
                full_path = lantern_dir / rel_path
                if full_path.exists():
                    full_path.unlink()
                    console.print(f"  [dim]Deleted {full_path}[/dim]")

    console.print(f"[green]Removed spec:[/green] {removed.path}")


@app.command()
def version() -> None:
    """Show version information."""
    from lantern_cli import __version__

    console.print(f"Lantern CLI version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
