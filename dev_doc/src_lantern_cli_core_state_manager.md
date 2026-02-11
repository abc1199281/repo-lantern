# State Manager (`src/lantern_cli/core/state_manager.py`)

## 概述
負責管理 Lantern 執行期間的狀態持久化 (Persistence)，實現斷點續傳 (Resumability) 功能。狀態儲存於 `.lantern/state.json`。

## 主要類別

### `ExecutionState` (Dataclass)
狀態資料模型。
-   `last_batch_id`: 最後處理的 Batch ID。
-   `completed_batches`: 已完成的 Batch ID 列表。
-   `failed_batches`: 失敗的 Batch ID 列表。
-   `global_summary`: 目前累積的全域摘要 (Context string)。

### `StateManager`
-   **`load_state()`**: 從 JSON 檔案載入狀態，若無則建立預設值。
-   **`save_state()`**: 將當前狀態寫入 JSON 檔案。
-   **`update_batch_status(batch_id, success)`**: 更新特定 Batch 的狀態 (成功加入 completed，失敗加入 failed)。
-   **`update_global_summary(summary)`**: 更新全域摘要。
-   **`get_pending_batches(plan)`**: 根據 Plan 與當前狀態，過濾出尚未完成的 Batches。
