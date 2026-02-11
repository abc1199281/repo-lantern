# Claude Adapter (`src/lantern_cli/backends/claude.py`)

## 概述
實作 Anthropic Claude API 的 Adapter。使用 `anthropic` SDK 與 Claude 模型互動。

## 主要類別

### `ClaudeAdapter`
繼承自 `BackendAdapter`。

-   **初始化**: 接收 `model` (預設 `claude-3-opus-20240229`) 與 `api_key_env`。
-   **`analyze_batch`**: 與 Gemini Adapter 類似流程。
-   **`_call_api`**:
    -   使用 `anthropic` SDK (`client.messages.create`)。
    -   建構 User Message，包含 Prompt, Context 與檔案內容。
-   **`_parse_output`**:
    -   共用與 `GeminiAdapter` 相同的強健解析邏輯，處理 Markdown 格式輸出。
