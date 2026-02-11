# Codex Adapter (`src/lantern_cli/backends/codex.py`)

## 概述
實作 CLI 工具 (如 `codex`, `antigravity` 等) 的 Adapter。此 Adapter 透過 `subprocess` 呼叫外部命令列工具來進行分析。

## 主要類別

### `CodexAdapter`
繼承自 `BackendAdapter`。

-   **初始化**: 接收 `command` (CLI指令), `timeout` (逾時秒數), `use_exec` (是否使用 `exec` 子命令)。
-   **`analyze_batch`**:
    -   建構 CLI 指令。
    -   呼叫 `subprocess.run` 執行分析。
    -   處理 `TimeoutExpired` 與 `CalledProcessError`。
    -   呼叫 `_parse_output` 解析 stdout。
-   **`_parse_output`**:
    -   解析 CLI 的純文字輸出。
    -   支援辨識 `SUMMARY:`, `INSIGHTS:`, `QUESTIONS:` 等區塊標記。
-   **`health_check`**: 使用 `shutil.which` 檢查 CLI 工具是否存在於 PATH 中。
