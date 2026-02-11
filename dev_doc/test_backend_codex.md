# Test Codex Adapter (`tests/unit/test_backend_codex.py`)

## 目的
測試 `CodexAdapter` (CLI Backend) 的功能，驗證其是否能正確呼叫外部 CLI 工具、處理輸出解析以及錯誤處理。

## 測試類別: `TestCodexAdapter`

### Fixtures
- **`adapter`**: 建立 `CodexAdapter` 實例。

### 測試案例 (Test Cases)

1.  **`test_health_check_success`**
    -   **目的**: 驗證當 CLI 工具存在時，健康檢查回傳 True。
    -   **Mock**: `shutil.which` 回傳有效路徑。

2.  **`test_health_check_failure`**
    -   **目的**: 驗證當 CLI 工具缺失時，健康檢查回傳 False。
    -   **Mock**: `shutil.which` 回傳 None。

3.  **`test_analyze_batch_success`**
    -   **目的**: 驗證成功的 Batch 分析流程。
    -   **Mock**: 模擬 CLI 輸出 (包含 SUMMARY, INSIGHTS, QUESTIONS 區塊)。
    -   **驗證點**:
        -   回傳結果為 `AnalysisResult` 實例。
        -   摘要 (Summary)、洞察 (Insights) 與問題 (Questions) 是否正確解析。
        -   原始輸出 (Raw Output) 是否保留。

4.  **`test_analyze_batch_timeout`**
    -   **目的**: 驗證執行逾時 (Timeout) 的處理。
    -   **Mock**: `subprocess.run` 拋出 `TimeoutExpired` 異常。
    -   **驗證點**: 是否拋出 `RuntimeError` 並包含 "timed out" 訊息。

5.  **`test_analyze_batch_failure`**
    -   **目的**: 驗證 CLI 執行失敗 (非 0 回傳碼) 的處理。
    -   **Mock**: `subprocess.run` 拋出 `CalledProcessError`。
    -   **驗證點**: 是否拋出 `RuntimeError` 並包含 "failed" 訊息。
