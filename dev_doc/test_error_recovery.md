# Integration Test: Error Recovery (`tests/integration/test_error_recovery.py`)

## 目的
驗證 Lantern 的斷點續傳 (Resumability) 與錯誤恢復機制。確保當分析過程中發生錯誤時，下次執行能略過已完成的部分並重試失敗的 Batch。

## 測試類別: `TestErrorRecovery`

### Fixtures
- **`repo_path`**: 建立包含多個 Python 檔案的虛擬 Repository。

### 測試案例 (Test Cases)

1.  **`test_resume_after_failure`**
    -   **目的**: 驗證失敗後的續傳行為。
    -   **步驟 1 (First Run)**:
        -   模擬 Backend 對特定 Batch (如包含 `a.py` 或 `main.py`) 拋出異常。
        -   執行 `lantern run`。
        -   驗證 State Manager 記錄了失敗或未完成的狀態。
    -   **步驟 2 (Second Run)**:
        -   重置 Mock，使其對所有 Batch 回傳成功。
        -   再次執行 `lantern run`。
        -   驗證只有待處理/失敗的 Batch 被重新執行。
        -   驗證最終所有 Batch 標記為完成，且無失敗記錄。
