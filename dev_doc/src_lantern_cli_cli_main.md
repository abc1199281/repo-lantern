# CLI Main (`src/lantern_cli/cli/main.py`)

## 概述
Lantern 的入口點 (Entry Point)，使用 `Typer` 實作 CLI 介面。負責解析使用者指令 (`init`, `plan`, `run`)，並協調各個核心模組進行工作。

## 主要指令

### `init`
初始化 Lantern 專案。
-   建立 `.lantern` 目錄。
-   建立預設設定檔 `lantern.toml`。

### `plan`
僅生成分析計畫，不執行分析。
-   載入設定與過濾器。
-   執行靜態分析 (`DependencyGraph`)。
-   呼叫 `Architect` 生成計畫。
-   將計畫存為 `lantern_plan.md`。

### `run`
執行完整的分析流程。
1.  **設定載入**: 合併設定檔與 CLI 參數 (如 `--backend`, `--lang`)。
2.  **Backend 初始化**: 透過 `BackendFactory` 建立 Adapter。
3.  **靜態分析**: 建構依賴圖。
4.  **計畫生成**: 建構分析計畫。
5.  **執行分析 (Runner)**: 迭代執行計畫中的 Batches。
    -   管理 `StateManager` 以支援斷點續傳。
    -   顯示進度條 (使用 `rich` 函式庫)。
4.  **文件合成 (Synthesizer)**: 生成最終 Top-down 文件。
