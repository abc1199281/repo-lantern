# Test Backend Factory (`tests/unit/test_backend_factory.py`)

## 目的
測試 `BackendFactory` 與 `detect_cli` 工具，驗證是否能依據設定 (Config) 或環境自動選擇並建立正確的 Backend Adapter。

## 測試類別: `TestCLIBackendDetection`
測試 `detect_cli` 函式的 CLI 工具偵測邏輯。

-   **`test_detect_cli_order`**: 驗證偵測優先權 (Priority: Antigravity > Codex > Gemini ...)。
-   **`test_no_cli_found`**: 驗證無可用 CLI 工具時拋出 `RuntimeError`。

## 測試類別: `TestBackendFactory`
測試 `BackendFactory.create` 方法。

### 測試案例 (Test Cases)

1.  **`test_create_cli_backend_explicit`**
    -   **目的**: 驗證明確指定 CLI Command 的建立流程。
    -   **設定**: `type="cli"`, `cli_command="custom"`。
    -   **驗證點**: 建立 `CodexAdapter`，Command 為 "custom"，未呼叫 `detect_cli`。

2.  **`test_create_cli_backend_auto`**
    -   **目的**: 驗證自動偵測 CLI 的建立流程。
    -   **設定**: `type="cli"`, `cli_command=None`。
    -   **驗證點**: 建立 `CodexAdapter`，Command 為 `detect_cli` 的回傳值。

3.  **`test_create_api_backend_gemini`**
    -   **目的**: 驗證 Gemini API Backend 的建立。
    -   **設定**: `type="api"`, `api_provider="gemini"`。
    -   **驗證點**: 建立 `GeminiAdapter`，Model 設定正確。

4.  **`test_create_api_backend_claude`**
    -   **目的**: 驗證 Claude API Backend 的建立。
    -   **設定**: `type="api"`, `api_provider="anthropic"`。
    -   **驗證點**: 建立 `ClaudeAdapter`，API Key Env 設定正確。

5.  **`test_create_unknown_api_backend`**
    -   **目的**: 驗證未知 Provider 的錯誤處理。
    -   **設定**: `api_provider="unknown"`。
    -   **驗證點**: 拋出 `NotImplementedError`。
