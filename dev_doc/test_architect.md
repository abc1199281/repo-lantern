# Test Architect (`tests/unit/test_architect.py`)

## 目的
測試 `Architect` 模組的核心功能，驗證其是否能正確生成分析計畫 (`Plan`)，包含分層結構、學習目標生成以及依賴關係圖。

## 測試類別: `TestArchitect`

### Fixtures
- **`mock_dependency_graph`**: 模擬 `DependencyGraph`，定義了模組的分層關係 (Layer 0: utils, Layer 1: core, Layer 2: api) 與依賴結構。
- **`architect`**: 建立 `Architect` 實例，使用模擬的依賴圖。

### 測試案例 (Test Cases)

1.  **`test_generate_plan_structure`**
    -   **目的**: 驗證 `generate_plan` 是否產生正確的 `Plan` 物件結構。
    -   **驗證點**:
        -   回傳物件是否為 `Plan` 實例。
        -   Phase 數量是否正確 (對應層數)。
        -   檢查各 Phase 的 ID 與包含的檔案是否符合分層定義。

2.  **`test_learning_objectives`**
    -   **目的**: 驗證學習目標 (Learning Objectives) 的生成。
    -   **驗證點**:
        -   每個 Phase 是否包含學習目標。
        -   每個 Phase 是否包含關鍵問題 (Key Questions)。

3.  **`test_confidence_score`**
    -   **目的**: 驗證信心分數 (Confidence Score) 的計算邏輯。
    -   **驗證點**:
        -   若依賴圖包含循環 (Cycles)，分數應小於 1.0。
        -   若依賴圖完美無循環，分數應為 1.0。

4.  **`test_plan_markdown_generation`**
    -   **目的**: 驗證計畫轉為 Markdown 格式的輸出。
    -   **驗證點**:
        -   輸出是否包含標題 ("Lantern Analysis Plan")。
        -   輸出是否包含 Phase 區塊。
        -   輸出是否包含 Batch 列表。
        -   輸出是否包含 Mermaid 依賴圖語法。

5.  **`test_batch_size_limit`**
    -   **目的**: 驗證 Batch 大小限制功能。
    -   **驗證點**:
        -   當單一層級檔案過多時，是否會正確拆分為多個 Batch (例如 10 個檔案拆分為 3+3+3+1)。
