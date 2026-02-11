# Backend Factory (`src/lantern_cli/backends/factory.py`)

## 概述
負責根據設定 (Configuration) 或環境自動偵測，建立適當的 `BackendAdapter` 實例。實現了工廠模式 (Factory Pattern) 與簡單的 CLI 工具偵測邏輯。

## 主要功能

### `detect_cli() -> str`
自動偵測系統中可用的 CLI 工具。
-   **優先順序**: `antigravity` > `codex` > `gemini` > `claude`。
-   若找不到任何支援的工具，拋出 `RuntimeError`。

### `BackendFactory` (Class)
-   `create(config: LanternConfig) -> BackendAdapter`: 靜態方法，根據設定建立 Adapter。
    -   **CLI 模式 (`type="cli"`)**: 若未指定 `cli_command`，則自動偵測。建立 `CodexAdapter`。
    -   **API 模式 (`type="api"`)**:
        -   `gemini`: 建立 `GeminiAdapter`。
        -   `anthropic` / `claude`: 建立 `ClaudeAdapter`。
        -   `openai` / `gpt`: 建立 `OpenAIAdapter`。
    -   若 Provider 未知，拋出 `NotImplementedError`。
