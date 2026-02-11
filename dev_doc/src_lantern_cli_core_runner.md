# Runner (`src/lantern_cli/core/runner.py`)

## 概述
`Runner` 是分析執行的協調者。它負責讀取計畫中的 Batch，調用 Backend 進行分析，管理上下文 (Context) 的傳遞 (Temporal RAG)，並觸發文件的生成與狀態更新。

## 主要類別

### `Runner`
-   **初始化**: 接收 Root Path, Backend Adapter, State Manager。
-   **`run_batch(batch, prompt)`**: 執行單一 Batch 的標準流程。
    1.  **Context Preparation**: 從 `StateManager` 獲取當前的全域摘要 (Global Summary)。
    2.  **API Call**: 傳遞檔案列表、Context 與 Prompt 給 Backend。
    3.  **Persistence**: 將原始分析結果存為 `.sense` 檔案。
    4.  **Bottom-up Doc**: 為每個原始檔案生成對應的 Markdown 文件 (如 `src/utils.py.md`)。
    5.  **Summary Update**: 更新全域摘要 (Rolling Summary)，將本批次的發現累加進 Context。
    6.  **State Update**: 標記 Batch 為完成。
-   **`_generate_bottom_up_doc`**: 將分析結果寫入 `.lantern/output/{lang}/bottom_up/`。
