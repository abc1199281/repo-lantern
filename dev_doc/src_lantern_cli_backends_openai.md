# OpenAI Adapter (`src/lantern_cli/backends/openai.py`)

## 概述
實作 OpenAI API (GPT) 的 Adapter。使用 `openai` SDK 與 GPT-4o 等模型互動。

## 主要類別

### `OpenAIAdapter`
繼承自 `BackendAdapter`。

-   **初始化**: 接收 `model` (預設 `gpt-4o`) 與 `api_key_env`。
-   **`analyze_batch`**: 與其他 API Adapter 類似流程。
-   **`_call_api`**:
    -   使用 `openai` SDK (`client.chat.completions.create`)。
    -   建構 User Message。
-   **`_parse_output`**:
    -   共用強健的 Markdown 解析邏輯。
