# Synthesizer (`src/lantern_cli/core/synthesizer.py`)

## 概述
`Synthesizer` 負責分析的最後階段：將所有 Bottom-up 的分析碎片 (`.sense` files) 整合，生成 Top-down 的高層次文件 (Overview, Architecture 等)。

## 主要類別

### `Synthesizer`
-   **初始化**: 設定輸入 (`.lantern/sense`) 與輸出 (`.lantern/output/{lang}/top_down`) 目錄。
-   **`load_sense_files()`**: 讀取所有儲存的分析片段。
-   **`generate_top_down_docs()`**:
    -   匯總所有內容 (MVP 採用簡單串接或 Context Window 內的聚合)。
    -   生成四份核心文件：
        1.  `OVERVIEW.md`: 專案願景與範疇。
        2.  `ARCHITECTURE.md`: 系統架構與設計。
        3.  `GETTING_STARTED.md`: 上手指南。
        4.  `CONCEPTS.md`: 核心概念與抽象。
