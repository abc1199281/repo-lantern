# LangGraph Subagent 架構評估與重構規劃

> **日期**: 2026-02-15
> **狀態**: 評估報告
> **範圍**: 分析現有架構是否適合改為 LangGraph Subagent，並規劃重構路徑

---

## 1. 現有架構深度分析

### 1.1 當前工作流程

```
CLI (main.py)
    │
    ▼
┌─────────────────┐
│  Static Analysis │ ← 純 Python，無 LLM
│  (DependencyGraph)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Architect     │ ← 純演算法（拓撲排序 + 分層分組）
│  (generate_plan) │    無 LLM 參與規劃
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Runner       │ ← LangChain Batch API（chain.batch()）
│  (run_batch)     │    **逐批次循序執行**
│                  │    狀態透過 StateManager 手動管理
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Synthesizer    │ ← **純規則聚合**，無 LLM
│  (generate_docs) │    從 .sense 檔案提取文字拼接
└─────────────────┘
```

### 1.2 狀態轉移的問題

目前的狀態管理存在以下結構性問題：

#### 問題 1：線性流水線，無條件分支

```python
# main.py 中的流程是完全線性的
graph.build()           # Step 1
plan = architect.generate_plan()  # Step 2
for batch in pending_batches:     # Step 3 (逐個)
    runner.run_batch(batch, prompt)
synthesizer.generate_top_down_docs()  # Step 4
```

缺乏的能力：
- 無法根據中間結果動態調整後續行為（如：發現某模組特別複雜，需要深入分析）
- 無法回溯（如：Batch 5 發現 Batch 2 的分析有誤，需要重新分析）
- 無法並行處理獨立的 Batch

#### 問題 2：Temporal RAG 上下文傳遞太弱

```python
# state_manager.py
class ExecutionState:
    global_summary: str = ""  # 整個專案的理解壓縮在一個字串中

# runner.py
MAX_CONTEXT_LENGTH = 4000  # 硬上限
```

**具體問題**：
- 100 個檔案的專案，所有洞察壓縮至 4000 字元
- 無法選擇性回憶（如：「Batch 15 分析 auth.py 時，需要 Batch 3 關於 User model 的分析」）
- 壓縮損失不可逆，早期批次的細節在後期完全消失

#### 問題 3：Synthesizer 是死的聚合器

```python
# synthesizer.py - _extract_section 方法
def _extract_section(self, records, section_type):
    grouped = self._group_by_file(records)
    for file_path, record in grouped.items():
        analysis = record.get("analysis", {})
        summary = analysis.get("summary", "")
        # ... 純粹提取欄位、拼接文字
```

**不具備的能力**：
- 無法做橫向比較（如 `sc_port` vs `sc_export` 的設計差異）
- 無法識別跨檔案的設計模式（Factory、Observer 等）
- 無法產生高層次的架構洞察（「這個專案整體採用 Hexagonal Architecture」）
- ARCHITECTURE.md 的品質取決於個別檔案分析的品質，沒有全域推理

#### 問題 4：Architect 缺乏語意理解

```python
# architect.py
def generate_plan(self):
    layers = self.dep_graph.calculate_layers()  # 純拓撲排序
    # 按 layer 分組，每 3 個一批 → 完全基於 import 關係
```

**不具備的能力**：
- 無法理解「這 3 個檔案雖然沒有 import 關係，但都實作了 Observer Pattern」
- 無法給每個 Batch 加入分析提示（如「比較這兩個 Factory 的差異」）
- 學習目標是模板化的，沒有實際的語意理解

---

## 2. LangGraph Subagent 能帶來什麼？

### 2.1 LangGraph StateGraph 的核心優勢

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from operator import add

class LanternState(TypedDict):
    # 顯式、結構化的狀態定義
    explored_files: list[str]
    discovered_patterns: list[dict]
    batch_results: Annotated[list[dict], add]  # 自動合併
    architecture_insights: list[str]
    quality_score: float
    needs_reanalysis: list[str]
```

**vs 現有方案**：
| 面向 | 現有方案 | LangGraph StateGraph |
|------|---------|---------------------|
| 狀態定義 | `ExecutionState` dataclass + JSON | TypedDict + Annotated reducers |
| 狀態轉移 | 手動 if/else 在 main.py | 圖的邊（edges）+ 條件路由 |
| 並行處理 | 不支援 | `Send()` API 原生支援 |
| 條件分支 | 不支援 | `add_conditional_edges()` |
| 可視化 | 無 | `graph.get_graph().draw_mermaid()` |
| 中斷/恢復 | 手動 state.json | 內建 checkpointer |
| 人機互動 | typer.confirm() 一次性 | `interrupt()` 可在任意節點暫停 |

### 2.2 具體場景分析

#### 場景 A：智慧合成（Agentic Synthesis）— **價值最高**

現狀的 Synthesizer 只是文字拼接，改為 Subagent 後：

```python
# 概念示意
synthesis_graph = StateGraph(SynthesisState)

synthesis_graph.add_node("load_context", load_all_sense_files)
synthesis_graph.add_node("identify_patterns", agent_identify_patterns)
synthesis_graph.add_node("cross_compare", agent_cross_compare_components)
synthesis_graph.add_node("generate_overview", agent_generate_overview)
synthesis_graph.add_node("generate_architecture", agent_generate_architecture)
synthesis_graph.add_node("quality_check", agent_quality_check)
synthesis_graph.add_node("refine", agent_refine_docs)

synthesis_graph.add_edge("load_context", "identify_patterns")
synthesis_graph.add_edge("identify_patterns", "cross_compare")
synthesis_graph.add_edge("cross_compare", "generate_overview")
synthesis_graph.add_edge("generate_overview", "generate_architecture")
synthesis_graph.add_edge("generate_architecture", "quality_check")
synthesis_graph.add_conditional_edges(
    "quality_check",
    lambda state: "refine" if state["quality_score"] < 0.8 else END
)
synthesis_graph.add_edge("refine", "quality_check")
```

**品質提升預期**：
- ARCHITECTURE.md：從「檔案列表 + 類別列表」→「設計模式分析 + 架構風格識別 + 模組關係推理」
- CONCEPTS.md：從「類別名稱列表」→「核心抽象解釋 + 設計決策分析 + 概念間關聯圖」
- GETTING_STARTED.md：從「函數列表」→「智慧學習路徑 + 建議閱讀順序 + 關鍵進入點分析」

#### 場景 B：智慧規劃（Agentic Planning）— **價值高**

```python
planning_graph = StateGraph(PlanningState)

planning_graph.add_node("scan_structure", scan_directory_structure)
planning_graph.add_node("sample_files", agent_sample_key_files)
planning_graph.add_node("identify_patterns", agent_identify_design_patterns)
planning_graph.add_node("group_batches", agent_group_semantic_batches)
planning_graph.add_node("add_hints", agent_add_analysis_hints)
planning_graph.add_node("generate_plan", generate_enhanced_plan)
```

**具體改善**：
- Batch 分組從「拓撲排序 + 每 3 個切一刀」→「語意相關的檔案放一起 + 加入比較提示」
- 學習目標從模板化→基於實際程式碼內容生成
- 自動識別高價值的檔案比較（如 port vs export）

#### 場景 C：並行批次執行 — **價值中等**

```python
from langgraph.constants import Send

def route_batches(state):
    """將獨立的 batch 並行發送給 subagent"""
    independent_batches = find_independent_batches(state["pending_batches"])
    return [Send("analyze_batch", {"batch": b}) for b in independent_batches]

runner_graph = StateGraph(RunnerState)
runner_graph.add_node("analyze_batch", batch_analysis_subagent)
runner_graph.add_conditional_edges("route", route_batches)
```

**但注意**：LLM API 本身已支援並行請求，用 `asyncio` + `chain.abatch()` 也能達到類似效果，不一定需要 LangGraph。

#### 場景 D：全流程統一狀態圖 — **架構價值高**

```python
# 將整個 Lantern 流程建模為一個 StateGraph
lantern_graph = StateGraph(LanternState)

lantern_graph.add_node("static_analysis", static_analysis_node)
lantern_graph.add_node("planning", planning_subgraph)        # 子圖
lantern_graph.add_node("human_review", human_review_node)     # interrupt()
lantern_graph.add_node("batch_execution", batch_execution_subgraph)  # 子圖
lantern_graph.add_node("synthesis", synthesis_subgraph)       # 子圖
lantern_graph.add_node("quality_gate", quality_gate_node)

lantern_graph.add_edge("static_analysis", "planning")
lantern_graph.add_edge("planning", "human_review")
lantern_graph.add_conditional_edges(
    "human_review",
    lambda s: "planning" if s["plan_rejected"] else "batch_execution"
)
lantern_graph.add_edge("batch_execution", "synthesis")
lantern_graph.add_edge("synthesis", "quality_gate")
lantern_graph.add_conditional_edges(
    "quality_gate",
    lambda s: END if s["quality_ok"] else "synthesis"
)
```

**架構優勢**：
- 整個流程可視化為一張圖
- 天然支援人機互動（Human-in-the-loop）
- 狀態轉移邏輯從 main.py 的 procedural code 變成宣告式的圖定義
- 可以在任意節點暫停/恢復

---

## 3. 哪些地方不適合改用 LangGraph？

### 3.1 批次分析的核心 LLM 呼叫

```python
# structured.py - analyze_batch
# 這裡用 chain.batch() 已經是最高效的做法
responses = self.chain.batch(items)
```

把每個檔案的分析改成一個獨立的 Agent 會：
- 成本增加 3-5x（Agent 需要多輪推理）
- 延遲顯著增加
- 結果不確定性增加

**結論**：保留 `StructuredAnalyzer` 的 Batch API，它已經是效率與品質的良好平衡。

### 3.2 靜態分析

```python
# dependency_graph.py - 純 Python 演算法
# 不需要 LLM，更不需要 Agent
```

### 3.3 配置載入與 CLI 命令

這些是純邏輯，不涉及 LLM。

---

## 4. 結論：應該重構嗎？

### 4.1 明確的答案：是的，但採用**漸進式混合架構**

| 元件 | 是否改用 LangGraph | 理由 |
|------|-------------------|------|
| **Synthesizer** | **是，最優先** | 現有純聚合方式是品質瓶頸，Agent 可做橫向推理 |
| **Architect/Planning** | **是，第二優先** | 語意分組比拓撲排序更智慧 |
| **全流程編排** | **是，第三優先** | StateGraph 比手動 if/else 更清晰，支援條件分支 |
| **Runner/Batch 分析** | **否** | Batch API 已足夠高效，改 Agent 成本過高 |
| **Static Analysis** | **否** | 純演算法，不需要 LLM |

### 4.2 品質提升預期

根據 spec.md 中提到的觀察（Agentic CLI 生成 vs Batch API 生成的品質差距）：

- **Top-down 文檔品質**：預期提升 30-50%（主要來自 Agentic Synthesis）
- **分析計畫品質**：預期提升 20-30%（語意分組 + 分析提示）
- **Bottom-up 文檔品質**：間接提升 10-15%（因為 Planning Agent 提供更好的上下文提示）

### 4.3 成本影響

| 架構方案 | Planning | Bottom-up | Synthesis | 總成本 |
|---------|----------|-----------|-----------|--------|
| 現有（純 Batch） | ~$0.10 | $1-5 | ~$0.50 | $1.60-$5.60 |
| 混合 LangGraph | $0.50-$2.00 | $1-5 | $0.30-$1.00 | $1.80-$8.00 |
| 完全 Agentic | $2-5 | $10-30 | $2-5 | $14-$40 |

**混合方案的成本增幅約 10-40%，但品質提升顯著，性價比最高。**

---

## 5. 重構規劃

### Phase 1：Agentic Synthesis（最高價值，最低風險）

**目標**：用 LangGraph Subagent 取代 `synthesizer.py` 的規則聚合

**範圍**：
- 新增 `src/lantern_cli/core/agentic_synthesizer.py`
- 定義 `SynthesisState` TypedDict
- 實作 StateGraph，包含以下節點：
  1. `load_context`：讀取所有 .sense 檔案 + lantern_plan.md
  2. `identify_patterns`：LLM 分析設計模式與架構風格
  3. `cross_compare`：LLM 做跨檔案橫向比較
  4. `generate_docs`：逐一生成 OVERVIEW / ARCHITECTURE / CONCEPTS / GETTING_STARTED
  5. `quality_check`：自我評估生成品質（可選的品質回饋循環）
- 保留原有 `synthesizer.py` 作為 fallback（`--synthesis-mode=batch`）

**需要的工具（Agent Tools）**：
```python
tools = [
    read_sense_file,          # 讀取特定 .sense 檔案
    list_sense_files,         # 列出所有 .sense 檔案
    read_plan,                # 讀取 lantern_plan.md
    compare_components,       # 比較兩個元件的差異
    search_pattern,           # 在分析結果中搜尋特定模式
    write_document,           # 寫入最終文檔
]
```

**State 定義**：
```python
class SynthesisState(TypedDict):
    sense_records: list[dict]           # 所有 .sense 檔案內容
    plan_content: str                    # lantern_plan.md 內容
    dependency_graph: str                # Mermaid 依賴圖
    discovered_patterns: list[str]       # 發現的設計模式
    cross_comparisons: list[dict]        # 橫向比較結果
    overview_draft: str                  # OVERVIEW.md 草稿
    architecture_draft: str              # ARCHITECTURE.md 草稿
    concepts_draft: str                  # CONCEPTS.md 草稿
    getting_started_draft: str           # GETTING_STARTED.md 草稿
    quality_score: float                 # 品質評分
    iteration_count: int                 # 迭代次數（防無限循環）
```

**驗收標準**：
- 在 2-3 個不同規模的開源專案上，人工比較 Agentic vs Batch 生成的 ARCHITECTURE.md 品質
- Agentic 版本應包含：設計模式識別、跨元件比較、高層次架構洞察
- 成本控制在 $1.00/repository 以內

**預估影響的檔案**：
```
新增：
  src/lantern_cli/core/agentic_synthesizer.py    # 主邏輯
  src/lantern_cli/core/synthesis_tools.py        # Agent 工具定義
  tests/unit/test_agentic_synthesizer.py

修改：
  src/lantern_cli/cli/main.py                    # 加入 --synthesis-mode 選項
  pyproject.toml                                  # 加入 langgraph 依賴
```

---

### Phase 2：Agentic Planning

**目標**：用 LangGraph Agent 增強 `architect.py` 的規劃能力

**範圍**：
- 新增 `src/lantern_cli/core/agentic_planner.py`
- 定義 `PlanningState` TypedDict
- 實作 StateGraph：
  1. `scan_structure`：分析目錄結構（使用現有 FileFilter）
  2. `sample_key_files`：Agent 選擇性讀取關鍵檔案（入口、介面定義等）
  3. `identify_patterns`：識別設計模式與架構風格
  4. `semantic_grouping`：基於語意將檔案分組
  5. `generate_hints`：為每個 Batch 生成分析提示
  6. `generate_plan`：輸出增強版 Plan
- 保留原有 `architect.py` 的拓撲排序作為 fallback

**需要的工具（Agent Tools）**：
```python
tools = [
    read_file,                # 讀取檔案內容
    list_directory,           # 列出目錄結構
    analyze_imports,          # 分析 import 關係
    identify_pattern,         # 識別設計模式
    compare_file_signatures,  # 比較檔案的函數/類別簽名
]
```

**State 定義**：
```python
class PlanningState(TypedDict):
    repo_path: str
    file_list: list[str]
    dependency_graph: dict[str, list[str]]
    sampled_files: dict[str, str]         # path → 內容摘要
    discovered_patterns: list[dict]
    semantic_groups: list[list[str]]       # 語意相關的檔案分組
    batch_hints: dict[int, str]           # batch_id → 分析提示
    enhanced_plan: dict                    # 最終計畫
```

**預估影響的檔案**：
```
新增：
  src/lantern_cli/core/agentic_planner.py      # 主邏輯
  src/lantern_cli/core/planning_tools.py       # Agent 工具定義
  tests/unit/test_agentic_planner.py

修改：
  src/lantern_cli/core/architect.py            # 提供靜態分析結果供 Agent 使用
  src/lantern_cli/core/runner.py               # 接收 batch_hints 並注入 prompt
  src/lantern_cli/cli/main.py                  # 加入 --planning-mode 選項
```

---

### Phase 3：全流程 StateGraph 編排

**目標**：用 LangGraph StateGraph 重構 `main.py` 中的流程編排

**範圍**：
- 新增 `src/lantern_cli/core/workflow.py`
- 將整個 `lantern run` 流程建模為一個 StateGraph
- 利用 LangGraph 的 checkpointer 取代手動 state.json
- 支援在 `human_review` 節點暫停/恢復

**State 定義**：
```python
class LanternWorkflowState(TypedDict):
    # 輸入
    repo_path: str
    config: dict
    language: str

    # 靜態分析結果
    dependency_graph: dict
    file_list: list[str]

    # 規劃結果
    plan: dict
    plan_approved: bool

    # 執行狀態
    completed_batches: list[int]
    failed_batches: list[int]
    sense_records: Annotated[list[dict], add]
    global_summary: str

    # 合成結果
    documents: dict[str, str]

    # 品質與成本
    quality_score: float
    total_cost: float
```

**預估影響的檔案**：
```
新增：
  src/lantern_cli/core/workflow.py           # 主 StateGraph 定義
  tests/unit/test_workflow.py

修改：
  src/lantern_cli/cli/main.py               # run 命令改為呼叫 workflow
  src/lantern_cli/core/state_manager.py     # 可能被 LangGraph checkpointer 取代
```

---

### Phase 4：增強型 Context 管理（取代 Temporal RAG）

**目標**：改善跨 Batch 的上下文傳遞

**方案**：
- 使用 LangGraph state 作為結構化記憶體（而非壓縮成單一字串）
- 每個 Batch 的結果以結構化方式存入 state
- 後續 Batch 可以選擇性查詢先前結果（而非讀取壓縮摘要）

```python
class BatchExecutionState(TypedDict):
    # 不再是一個壓縮字串，而是結構化的分析結果
    file_analyses: dict[str, dict]        # file_path → analysis
    module_summaries: dict[str, str]      # module → summary
    discovered_relationships: list[dict]
    current_batch_context: str            # 動態生成的上下文（基於當前 batch 的依賴）
```

**上下文選擇邏輯**：
```python
def prepare_batch_context(state, batch):
    """根據 batch 中檔案的依賴關係，選擇性載入先前分析結果"""
    relevant_files = get_dependencies(batch.files, state["dependency_graph"])
    context_parts = []
    for dep_file in relevant_files:
        if dep_file in state["file_analyses"]:
            analysis = state["file_analyses"][dep_file]
            context_parts.append(f"{dep_file}: {analysis['summary']}")
    return "\n".join(context_parts)[:MAX_CONTEXT]
```

---

## 6. 依賴與技術棧變更

### 新增依賴

```toml
# pyproject.toml
[tool.poetry.dependencies]
langgraph = "^0.3"           # StateGraph, checkpointer
langgraph-checkpoint = "^2"  # 持久化 checkpointer（可選）
```

### 相容性

- LangGraph 建立在 LangChain 之上，與現有 LangChain 整合完全相容
- 現有的 `ChatOpenAI`、`ChatOllama` 可直接在 LangGraph Agent 中使用
- 不需要更換 LLM provider

---

## 7. 風險評估與緩解

| 風險 | 嚴重度 | 緩解策略 |
|------|--------|---------|
| Agent 非確定性（每次執行結果不同） | 中 | 儲存 Agent trace、設定 temperature=0、quality gate |
| 成本失控（Agent 無限循環） | 高 | 設定 max_iterations、預算上限、iteration_count in state |
| 除錯困難 | 中 | LangSmith 整合、trace logging、可視化 graph |
| 延遲增加 | 低 | Planning/Synthesis 只佔總時間 10-20%，增加可接受 |
| 學習曲線 | 低 | LangGraph API 相對簡潔，團隊已熟悉 LangChain |

---

## 8. 建議的實施順序

```
Phase 1: Agentic Synthesis        ← 先做，價值最高，風險最低
    │                                可獨立驗證品質提升
    │                                不影響現有 Runner/Architect
    ▼
Phase 2: Agentic Planning         ← 第二步，增強分析計畫品質
    │                                需要修改 Runner 以接收 hints
    ▼
Phase 3: 全流程 StateGraph         ← 第三步，統一架構
    │                                此時再重構 main.py 的編排邏輯
    ▼
Phase 4: 增強型 Context 管理       ← 最後，最複雜的改動
                                     取代 Temporal RAG
```

每個 Phase 都保留 fallback 到原有實作的選項，透過 CLI flag 切換：
- `--synthesis-mode=batch|agentic`
- `--planning-mode=static|agentic`
- `--mode=fast|quality`（整合版）

---

## 9. 總結

**核心判斷**：

現有架構的最大瓶頸不在 Batch 分析（Runner），而在**規劃**和**合成**兩端。改為 LangGraph Subagent 架構能在這兩端帶來顯著的品質提升，而中間的 Batch 分析保留現有高效的 Batch API。

**一句話結論**：

> 採用 LangGraph Subagent 的「三明治架構」：Agent 規劃 → Batch 分析 → Agent 合成，是成本效益最高的重構方案。預期 Top-down 文檔品質提升 30-50%，成本增幅控制在 10-40% 以內。
