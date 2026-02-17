"""Agent-based analyzer for CLI backends with file writing capabilities.

This analyzer is designed for CLI tools (like Codex) that have agent capabilities
and can use file tools to write output directly. Instead of forcing structured JSON
output, it lets the agent write Markdown files directly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lantern_cli.llm.backends.cli_backend import CLIBackend

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "template" / "agent"


def _load_json(name: str) -> dict[str, Any]:
    """Load JSON file from agent template directory."""
    with open(TEMPLATE_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class AgentAnalyzer:
    """Agent-based analyzer for CLI backends that support file tools.

    Unlike StructuredAnalyzer which expects JSON output, this analyzer
    lets the agent write Markdown documentation files directly using its
    file writing capabilities.
    """

    def __init__(self, backend: CLIBackend) -> None:
        """Initialize with a CLI backend.

        Args:
            backend: CLIBackend instance with file tool capabilities.
        """
        self.backend = backend
        self.prompts = _load_json("prompts.json")

    def analyze_and_write_batch(
        self,
        items: list[dict[str, str]],
        output_paths: list[Path],
        source_files: list[str],
        batch_id: int,
        language: str = "en",
    ) -> list[dict[str, Any]]:
        """Analyze files and let agent write Markdown documentation.

        Args:
            items: List of dicts with 'file_content' and 'language' keys.
            output_paths: List of Path objects where Markdown should be written.
            source_files: List of source file paths (for metadata).
            batch_id: Batch ID for sense tracking.
            language: Target language code.

        Returns:
            List of metadata dicts for sense tracking, one per file.
        """
        results: list[dict[str, Any]] = []
        total_files = len(items)

        for idx, (item, out_path, src_file) in enumerate(zip(items, output_paths, source_files), 1):
            file_content = item.get("file_content", "")

            # Format the prompt
            prompt = self.prompts["bottom_up"].format(
                source_file=src_file,
                output_path=str(out_path),
                language=language,
                file_content=file_content,
                batch_id=batch_id,
                file_index=idx,
                total_files=total_files,
            )

            try:
                # Invoke the agent
                logger.info(f"Agent analyzing {src_file} → {out_path}")
                response = self.backend.invoke(prompt)

                # Verify file was written
                if out_path.exists():
                    status = "success"
                    error_msg = None
                    logger.info(f"✓ Agent wrote {out_path}")
                else:
                    status = "file_not_written"
                    error_msg = "Agent did not write the output file"
                    logger.warning(f"✗ Agent failed to write {out_path}")

                    # Write fallback Markdown
                    self._write_fallback_markdown(
                        out_path,
                        src_file,
                        batch_id,
                        idx,
                        total_files,
                        error_msg=f"Agent analysis incomplete: {error_msg}",
                    )

                results.append(
                    {
                        "batch": batch_id,
                        "file_index": idx - 1,  # 0-indexed for consistency
                        "file_path": src_file,
                        "output_path": str(out_path),
                        "prompt": {"file_content": file_content, "language": language},
                        "raw_response": response.content[:1000],  # Truncate for sense file
                        "status": status,
                        "error": error_msg,
                    }
                )

            except Exception as exc:
                logger.error(f"Agent analysis failed for {src_file}: {exc}")

                # Write fallback Markdown
                self._write_fallback_markdown(
                    out_path, src_file, batch_id, idx, total_files, error_msg=f"Agent error: {exc}"
                )

                results.append(
                    {
                        "batch": batch_id,
                        "file_index": idx - 1,
                        "file_path": src_file,
                        "output_path": str(out_path),
                        "prompt": {"file_content": file_content, "language": language},
                        "raw_response": f"error: {exc}",
                        "status": "error",
                        "error": str(exc),
                    }
                )

        return results

    def synthesize_top_down(
        self,
        sense_dir: Path,
        bottom_up_dir: Path,
        output_dir: Path,
        plan_path: Path,
        language: str = "en",
    ) -> dict[str, Any]:
        """Let agent generate top-down synthesis documents.

        Args:
            sense_dir: Directory with .sense files (for reference).
            bottom_up_dir: Directory with bottom-up .md files to read.
            output_dir: Output directory for top-down docs.
            plan_path: Path to lantern_plan.md (for dependency graph).
            language: Target language code.

        Returns:
            Metadata dict with synthesis results.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        docs_to_generate = [
            ("top_down_overview", "OVERVIEW.md"),
            ("top_down_architecture", "ARCHITECTURE.md"),
            ("top_down_concepts", "CONCEPTS.md"),
            ("top_down_getting_started", "GETTING_STARTED.md"),
        ]

        results = {}

        for prompt_key, filename in docs_to_generate:
            output_path = output_dir / filename

            prompt = self.prompts[prompt_key].format(
                bottom_up_dir=str(bottom_up_dir),
                output_path=str(output_path),
                plan_path=str(plan_path),
                language=language,
            )

            try:
                logger.info(f"Agent generating {filename}")
                self.backend.invoke(prompt)

                if output_path.exists():
                    results[filename] = {
                        "status": "success",
                        "path": str(output_path),
                    }
                    logger.info(f"✓ Agent wrote {output_path}")
                else:
                    results[filename] = {
                        "status": "file_not_written",
                        "path": str(output_path),
                        "error": "Agent did not write the file",
                    }
                    logger.warning(f"✗ Agent failed to write {output_path}")

                    # Write minimal fallback
                    output_path.write_text(
                        f"# {filename.replace('.md', '').replace('_', ' ').title()}\n\n"
                        f"> Generated by Lantern (Agent Mode)\n\n"
                        f"Agent synthesis incomplete. Please try again.\n",
                        encoding="utf-8",
                    )

            except Exception as exc:
                logger.error(f"Agent synthesis failed for {filename}: {exc}")
                results[filename] = {
                    "status": "error",
                    "path": str(output_path),
                    "error": str(exc),
                }

                # Write error fallback
                output_path.write_text(
                    f"# {filename.replace('.md', '').replace('_', ' ').title()}\n\n"
                    f"> Generated by Lantern (Agent Mode)\n\n"
                    f"## Error\n\nAgent synthesis failed: {exc}\n",
                    encoding="utf-8",
                )

        return {"top_down_synthesis": results}

    @staticmethod
    def _write_fallback_markdown(
        out_path: Path,
        source_file: str,
        batch_id: int,
        file_index: int,
        total_files: int,
        error_msg: str = "Analysis failed or not available",
    ) -> None:
        """Write a fallback Markdown file when agent analysis fails."""
        out_path.parent.mkdir(parents=True, exist_ok=True)

        filename = Path(source_file).name
        content = (
            f"# {filename}\n\n"
            f"> **Original File**: `{source_file}`\n"
            f"> **Batch**: {batch_id} ({file_index}/{total_files})\n\n"
            f"## Summary\n\n{error_msg}\n"
        )

        out_path.write_text(content, encoding="utf-8")
        logger.info(f"Wrote fallback Markdown to {out_path}")
