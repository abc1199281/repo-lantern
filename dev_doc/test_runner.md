# Test Runner (`tests/unit/test_runner.py`)

## 目的
測試 `Runner` 模組，驗證其執行分析批次 (Batch)、整合 Backend 呼叫、管理狀態更新以及上下文注入 (Context Injection) 的流程。

## 測試類別: `TestRunner`

### Fixtures
- **`mock_backend`**: 模擬 Backend Adapter，回傳預定義的 `AnalysisResult`。
- **`mock_state_manager`**: 模擬 State Manager，預設包含舊的全域摘要 (Global Summary)。
- **`runner`**: 建立 `Runner` 實例，注入模擬的組件。

### 測試案例 (Test Cases)

1.  **`test_run_batch_success`**
    -   **目的**: 驗證成功的 Batch 執行流程。
    -   **流程**: 執行包含 "file1.py" 的 Batch。
    -   **驗證點**:
        -   Backend 的 `analyze_batch` 被呼叫，且上下文包含先前摘要。
        -   State Manager 的 `update_batch_status` 被呼叫 (success=True)。
        -   State Manager 的 `update_global_summary` 被呼叫。
        -   檔案寫入操作被觸發 (生成 `.sense` 與 `.md` 文件)。

2.  **`test_run_batch_failure`**
    -   **目的**: 驗證 Batch 執行失敗的處理。
    -   **Mock**: Backend 拋出異常。
    -   **驗證點**:
        -   回傳值為 False。
        -   State Manager 的 `update_batch_status` 被呼叫 (success=False)。

3.  **`test_context_injection`**
    -   **目的**: 驗證上下文注入機制與長度限制。
    -   **驗證點**:
        -   生成的 Context 包含 Global Summary。
        -   若 Summary 過長，應進行截斷 (Truncation) 以符合 Token 限制。
