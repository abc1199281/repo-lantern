"""Translator - Post-processing translation of English analysis outputs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lantern_cli.llm.backend import Backend

logger = logging.getLogger(__name__)

PROMPTS_PATH = Path(__file__).resolve().parents[1] / "template" / "translation" / "prompts.json"


def _load_prompts() -> dict:
    """Load translation prompt templates."""
    with open(PROMPTS_PATH, encoding="utf-8") as f:
        return json.load(f)


class Translator:
    """Translates English analysis outputs to a target language via LLM.

    Reads from ``<base_output_dir>/output/en/`` and writes translated files
    to ``<base_output_dir>/output/{target_language}/``, preserving directory
    structure.
    """

    def __init__(self, backend: Backend, target_language: str, base_output_dir: Path) -> None:
        self.backend = backend
        self.target_language = target_language
        self.base_output_dir = base_output_dir
        self.prompts = _load_prompts()["translate_document"]

    def translate_all(self) -> None:
        """Translate both bottom-up and top-down English outputs.

        No-op when ``target_language`` is ``"en"``.
        """
        if self.target_language == "en":
            return

        en_dir = self.base_output_dir / "output" / "en"
        dst_root = self.base_output_dir / "output" / self.target_language

        # Translate bottom-up files
        en_bottom_up = en_dir / "bottom_up"
        if en_bottom_up.is_dir():
            self._translate_directory(en_bottom_up, dst_root / "bottom_up")

        # Translate top-down files
        en_top_down = en_dir / "top_down"
        if en_top_down.is_dir():
            self._translate_directory(en_top_down, dst_root / "top_down")

    def _translate_directory(self, src_dir: Path, dst_dir: Path) -> None:
        """Walk *src_dir*, translate each ``.md`` file, and write to *dst_dir*."""
        for src_file in src_dir.rglob("*.md"):
            rel = src_file.relative_to(src_dir)
            dst_file = dst_dir / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)

            content = src_file.read_text(encoding="utf-8")
            translated = self._translate_file(content)
            dst_file.write_text(translated, encoding="utf-8")
            logger.info("Translated %s -> %s", src_file, dst_file)

    def _translate_file(self, content: str) -> str:
        """Translate a single document via one LLM call."""
        system_prompt = self.prompts["system"].format(target_language=self.target_language)
        user_prompt = self.prompts["user"].format(
            target_language=self.target_language, content=content
        )
        prompt = f"{system_prompt}\n\n{user_prompt}"
        response = self.backend.invoke(prompt)
        return response.content
