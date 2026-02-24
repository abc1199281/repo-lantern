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
from lantern_cli.core.architect import Architect
from lantern_cli.core.runner import Runner
from lantern_cli.core.state_manager import StateManager
from lantern_cli.core.synthesizer import Synthesizer
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

        # 4. Architect Plan
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

            runner = Runner(
                repo_path,
                backend,
                state_manager,
                language=config.language,
                output_dir=config.output_dir,
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

                    agentic_synth = AgenticSynthesizer(
                        repo_path, backend, language=config.language, output_dir=config.output_dir
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
                    )
                    synthesizer.generate_top_down_docs()
            else:
                task_synth = progress.add_task("Synthesizing documentation...", total=None)
                synthesizer = Synthesizer(
                    repo_path,
                    language=config.language,
                    output_dir=config.output_dir,
                    backend=backend,
                )
                synthesizer.generate_top_down_docs()
            progress.update(task_synth, total=1, completed=1)

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
def version() -> None:
    """Show version information."""
    from lantern_cli import __version__

    console.print(f"Lantern CLI version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
