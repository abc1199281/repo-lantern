# Spec-Aware Documentation: Implementation Plan

## Context

Lantern CLI 目前分析程式碼時，LLM 只看到原始碼本身，無法得知該程式碼是在實作哪份規格書的哪個需求。加入 spec 文件支援後，LLM 能「對照規格說明意圖」，產出品質更好的文件。

設計決策：
- 單一檔案 `.lantern/specs.toml` 作為 spec mapping 的唯一來源
- `lantern spec add` 指令自動用 LLM 配對 spec → modules
- 使用者可直接編輯 `specs.toml` 修正配對結果
- 支援 PDF（pdfplumber）和 Markdown

---

## Step 1: Add `pdfplumber` dependency

**File:** `pyproject.toml`

- Add `"pdfplumber>=0.10.0"` to `dependencies`

---

## Step 2: Create spec manager module

**New file:** `src/lantern_cli/core/spec_manager.py`

Responsibilities:
1. **PDF extraction** — `extract_pdf(path) -> str`: 用 pdfplumber 萃取文字 + 表格轉 Markdown table
2. **Markdown extraction** — `extract_markdown(path) -> str`: 直接讀取
3. **Load specs.toml** — `load_specs(lantern_dir) -> list[SpecEntry]`: 讀取 `.lantern/specs.toml`
4. **Save specs.toml** — `save_specs(lantern_dir, entries)`: 寫入 `.lantern/specs.toml`
5. **Match file to specs** — `get_spec_context(file_path, specs) -> str`: 用 `pathspec` glob matching 找出該檔案對應的 spec summaries，串接回傳
6. **LLM auto-mapping** — `auto_map_spec(backend, spec_text, file_tree) -> list[str]`: 送 spec 前段 + file tree 給 LLM，回傳 modules glob list
7. **Summarize spec** — `summarize_spec(backend, spec_text) -> str`: 超過 token threshold 時，用 LLM 產生摘要

Data model:
```python
@dataclass
class SpecEntry:
    path: str              # relative to .lantern/, e.g. "specs/auth.pdf"
    modules: list[str]     # glob patterns, e.g. ["src/auth/", "src/middleware/auth_*.py"]
    summary_path: str      # relative to .lantern/, e.g. "specs/auth.summary.md"
```

Reuse existing: `pathspec` (already a dependency) for glob matching.

---

## Step 3: Add `lantern spec` CLI subcommand group

**File:** `src/lantern_cli/cli/main.py`

Add three subcommands:

### `lantern spec add <file_path>`
1. Copy file to `.lantern/specs/` (create dir if needed)
2. Extract text (PDF → pdfplumber, MD → direct read)
3. Load backend from config, send spec text + `file_tree` to LLM → get `modules` list
4. Generate summary → save to `.lantern/specs/{stem}.summary.md`
5. Append entry to `.lantern/specs.toml`
6. Print result for user review

### `lantern spec list`
- Read `.lantern/specs.toml`, display table: path | modules | summary_path

### `lantern spec remove <spec_name>`
- Remove entry from `specs.toml`, optionally delete files

Implementation: use `spec_app = typer.Typer()` + `app.add_typer(spec_app, name="spec")` pattern.

---

## Step 4: Add prompt template for LLM auto-mapping

**New file:** `src/lantern_cli/template/spec/prompts.json`

Two prompts:
- `"auto_map"`: system + user prompt. User prompt takes `{spec_excerpt}` (first ~3000 chars) and `{file_tree}`. Returns JSON `{"modules": ["src/auth/**", ...]}`.
- `"summarize"`: system + user prompt. User prompt takes `{spec_text}`. Returns a concise summary (~2000 tokens).

---

## Step 5: Inject spec context into bottom-up analysis

**Files to modify:**

1. **`src/lantern_cli/template/bottom_up/prompts.json`** — Append to `"user"` prompt:
   ```
   \n\n{spec_context}
   ```
   When `spec_context` is empty string, nothing changes (backward compatible).

2. **`src/lantern_cli/core/runner.py`** — In `Runner.__init__`, add `spec_entries: list[SpecEntry] = []` parameter. In `_generate_bottom_up_doc_structured`, when building `batch_data`:
   ```python
   spec_ctx = get_spec_context(file_path, self.spec_entries, self.base_output_dir)
   batch_data.append({
       "file_content": file_content,
       "language": self.language,
       "spec_context": spec_ctx,
   })
   ```

3. **`src/lantern_cli/cli/main.py`** — In `run` command, after `load_config`, load specs:
   ```python
   from lantern_cli.core.spec_manager import load_specs
   spec_entries = load_specs(repo_path / ".lantern")
   ```
   Pass `spec_entries` to `Runner(...)`.

---

## Step 6: Inject spec context into agentic planner

**Files to modify:**

1. **`src/lantern_cli/core/agentic_planner.py`** — Add `spec_context: str` to `PlanningState`. In `generate_enhanced_plan`, load all spec summaries and concatenate into `spec_context`. Pass into initial state.

2. **`src/lantern_cli/template/planning/prompts.json`** — Add `{spec_context}` to `analyze_structure` and `identify_patterns` user prompts.

---

## Step 7: Inject spec context into synthesis

**Files to modify:**

1. **`src/lantern_cli/core/agentic_synthesizer.py`** — Add `spec_context: str` to `SynthesisState`. Load all spec summaries in `generate_top_down_docs`.

2. **`src/lantern_cli/template/synthesis/prompts.json`** — Add `{spec_context}` to `generate_overview` and `generate_architecture` user prompts.

3. **`src/lantern_cli/core/synthesizer.py`** — In structured synthesizer path, pass spec summaries as additional context.

---

## Step 8: Tests

**New files:**
- `tests/unit/test_spec_manager.py` — Test PDF/MD extraction, glob matching, specs.toml load/save, auto-mapping prompt construction
- Update `tests/unit/test_runner.py` — Test that spec_context flows into batch_data
- Update `tests/unit/test_architect.py` or add `test_agentic_planner.py` — Test spec_context in planning state

---

## File Summary

| Action | File |
|--------|------|
| Modify | `pyproject.toml` — add pdfplumber |
| **Create** | `src/lantern_cli/core/spec_manager.py` — core spec logic |
| **Create** | `src/lantern_cli/template/spec/prompts.json` — auto-map & summarize prompts |
| Modify | `src/lantern_cli/cli/main.py` — add `spec` subcommand group |
| Modify | `src/lantern_cli/template/bottom_up/prompts.json` — add `{spec_context}` |
| Modify | `src/lantern_cli/core/runner.py` — thread spec_entries, build spec_context per file |
| Modify | `src/lantern_cli/core/agentic_planner.py` — add spec_context to state & prompts |
| Modify | `src/lantern_cli/template/planning/prompts.json` — add `{spec_context}` |
| Modify | `src/lantern_cli/core/agentic_synthesizer.py` — add spec_context to state |
| Modify | `src/lantern_cli/template/synthesis/prompts.json` — add `{spec_context}` |
| Modify | `src/lantern_cli/core/synthesizer.py` — pass spec context in structured path |
| **Create** | `tests/unit/test_spec_manager.py` |

---

## Verification

1. `pip install -e ".[dev]"` — 確認 pdfplumber 安裝成功
2. `lantern spec add tests/fixtures/sample.pdf` — 測試 PDF 萃取 + LLM auto-mapping
3. `cat .lantern/specs.toml` — 確認 mapping 正確寫入
4. `lantern spec list` — 確認顯示正確
5. `lantern run --repo . --lang en` — 確認 bottom-up 分析 prompt 中包含 spec_context
6. `pytest tests/ -v --cov=lantern_cli` — 全部測試通過
7. `ruff check src/ tests/ && black --check src/ tests/` — lint 通過
