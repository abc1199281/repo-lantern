# Backend Base (`src/lantern_cli/backends/base.py`)

## 概述
定義所有 LLM Backend Adapter 的基礎介面與資料結構。建立統一的合約，確保不同的 LLM (Gemini, Claude, OpenAI, Local CLI) 都能被系統一致地調用。

## 主要類別

### `AnalysisResult` (Dataclass)
標準化的分析結果容器。
-   `summary`: 分析摘要。
-   `key_insights`: 關鍵洞察列表。
-   `questions`: 待釐清問題列表。
-   `raw_output`: 原始 LLM 輸出 (用於除錯)。

### `BackendAdapter` (Abstract Base Class)
抽象基底類別，定義 Adapter 介面。
-   `analyze_batch(...)`: 分析一批檔案。接收上文 (Context) 與提示 (Prompt)，回傳 `AnalysisResult`。
-   `synthesize(...)`: 綜合生成最終文件。
-   `health_check()`: 檢查 Backend 可用性 (如 API Key 是否存在、CLI 是否安裝)。
