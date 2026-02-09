# 實例展示：Lantern 自我分析

以下是 Lantern 分析自身程式碼庫 (`lantern-cli`) 後生成的架構報告摘要 (由 `lantern run --lang zh-TW` 生成)：

### [生成的] 專案總覽 (Project Overview)

**Lantern CLI** 是一個基於 Python 的命令行工具，旨在協助開發者快速理解陌生的程式碼庫。

#### 核心架構
系統採用 **PipelinePattern (管線模式)** 設計，主要由以下模組組成：

1.  **CLI 層 (`src/lantern_cli/cli`)**
    -   使用 `Typer` 框架處理命令行輸入 (`main.py`)。
    -   負責協調 `init`, `plan`, `run` 三大指令的執行流程。

2.  **核心層 (`src/lantern_cli/core`)**
    -   **Architect (`architect.py`)**: 擔任「建築師」角色，負責分析依賴圖 (`DependencyGraph`) 並生成分批次的分析計畫 (`lantern_plan.md`)。
    -   **Runner (`runner.py`)**: 擔任「執行者」，負責與 LLM 後端溝通，執行批次分析，並具備斷點續傳 (`StateManager`) 功能。
    -   **Synthesizer (`synthesizer.py`)**: 擔任「合成器」，將零散的批次分析結果 (`.sense` 檔) 彙整為最終的 Top-down 文件。

3.  **後端適配層 (`src/lantern_cli/backends`)**
    -   透過 `BackendFactory` 實現策略模式 (Strategy Pattern)。
    -   支援多種 LLM 後端：`CodexAdapter`, `GeminiAdapter`, `ClaudeAdapter`。
    -   抽象化了不同 CLI 工具的調用細節。
