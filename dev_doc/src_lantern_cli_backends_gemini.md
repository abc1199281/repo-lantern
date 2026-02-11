# Gemini Adapter (`src/lantern_cli/backends/gemini.py`)

## 概述
實作 Google Gemini API 的 Adapter。使用 `google-generativeai` SDK 直接與 Gemini 模型互動。

## 主要類別

### `GeminiAdapter`
繼承自 `BackendAdapter`。

-   **初始化**: 接收 `model` (預設 `gemini-1.5-pro`) 與 `api_key_env`。
-   **`analyze_batch`**:
    -   檢查 API Key 是否存在。
    -   呼叫 `_call_api` 獲取回應。
    -   呼叫 `_parse_output` 解析 Markdown 回應。
-   **`_call_api`**:
    -   使用 `google.generativeai` SDK。
    -   建構包含 Context, Prompt, 以及檔案內容 (`File: ... ```...``` `) 的多部分請求。
-   **`_parse_output`**:
    -   強健的解析邏輯，支援 Markdown 標題 (`# Summary`, `Summary:`) 與列表格式。
    -   相容於測試用的 `Key: Value` 格式。
