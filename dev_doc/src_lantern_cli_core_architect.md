# Architect (`src/lantern_cli/core/architect.py`)

## 概述
`Architect` 是分析計畫的規劃者。它負責解析專案的依賴結構，並將分析工作拆解為合理的分層 (Phases) 與批次 (Batches)，確保分析過程遵循「由底層向上 (Bottom-Up)」的邏輯順序。

## 主要類別

### `Batch`, `Phase`, `Plan` (Dataclasses)
定義計畫的資料結構。
-   `Batch`: 一組並行分析的檔案。
-   `Phase`: 對應依賴圖的一個層級，包含多個 Batches。附帶學習目標與關鍵問題。
-   `Plan`: 完整的分析計畫，包含多個 Phases 與信心分數。提供 `to_markdown()` 生成可視化文件。

### `Architect` (Class)
-   **初始化**: 接收專案根目錄與 `DependencyGraph`。
-   **`generate_plan()`**:
    1.  呼叫依賴圖計算分層 (Topological Sort)。
    2.  將每層的檔案分組 (Layer Grouping)。
    3.  將每層檔案切分為多個 Batches (預設 `BATCH_SIZE=3`)。
    4.  生成學習目標與關鍵問題。
    5.  計算信心分數 (依據循環依賴程度)。
    6.  生成 Mermaid 依賴圖。
    7.  回傳 `Plan` 物件。
