# Test State Manager (`tests/unit/test_state_manager.py`)

## 目的
測試 `StateManager` 模組，驗證分析狀態的持久化 (Persistence)、載入與更新機制，確保斷點續傳功能的正確性。

## 測試類別: `TestStateManager`

### Fixtures
- **`state_manager`**: 建立 `StateManager` 實例，使用暫存目錄。

### 測試案例 (Test Cases)

1.  **`test_initial_state`**
    -   **目的**: 驗證初始狀態。
    -   **驗證點**: `last_batch_id` 為 0，`completed_batches` 為空，`global_summary` 為空。

2.  **`test_save_and_load_state`**
    -   **目的**: 驗證狀態儲存與載入。
    -   **操作**: 修改狀態後儲存，再重新載入。
    -   **驗證點**: 載入的狀態屬性應與儲存時一致。

3.  **`test_update_batch_completion`**
    -   **目的**: 驗證 Batch 完成狀態的更新。
    -   **操作**: 標記 Batch 1 與 Batch 2 完成。
    -   **驗證點**: `last_batch_id` 更新，`completed_batches` 包含對應 ID。

4.  **`test_update_global_summary`**
    -   **目的**: 驗證全域摘要的更新與持久化。
    -   **驗證點**: 更新後狀態即時反映，且重啟 Manager 後仍保留。

5.  **`test_is_batch_completed`**
    -   **目的**: 驗證 Batch 完成狀態的查詢功能。
    -   **驗證點**: 已完成的 Batch 回傳 True，未完成的回傳 False。

6.  **`test_get_pending_batches`**
    -   **目的**: 驗證依據計畫 (Plan) 與目前狀態過濾出待執行 Batch 的功能。
    -   **情境**: 計畫包含 Batch 1, 2, 3，狀態標記 Batch 1 已完成。
    -   **驗證點**: 回傳列表應只包含 Batch 2 與 3。
