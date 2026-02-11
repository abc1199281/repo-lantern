# Test Backend Base (`tests/unit/test_backend_base.py`)

## 目的
測試 Backend Adapter 的基礎介面 (`BackendAdapter`) 與資料結構 (`AnalysisResult`)，確保所有 Backend 實作均遵循一致的契約。

## 測試類別: `TestBackendAdapterInterface`

### 輔助類別
- **`MockAdapter`**: 一個實作了所有抽象方法的 `BackendAdapter` 子類別，用於測試。

### 測試案例 (Test Cases)

1.  **`test_analysis_result_structure`**
    -   **目的**: 驗證 `AnalysisResult` dataclass 的欄位結構。
    -   **驗證點**: `summary`, `key_insights`, `questions`, `raw_output` 欄位是否正確存取。

2.  **`test_adapter_instantiation`**
    -   **目的**: 驗證實作了抽象方法的 Adapter 可以被正確實例化。
    -   **驗證點**: `MockAdapter` 實例是否為 `BackendAdapter` 型別。

3.  **`test_abstract_methods`**
    -   **目的**: 驗證未實作抽象方法的子類別無法被實例化。
    -   **驗證點**: 嘗試實例化未實作方法的 `IncompleteAdapter` 是否拋出 `TypeError`。

4.  **`test_contract_execution`**
    -   **目的**: 驗證介面方法的執行契約。
    -   **驗證點**:
        -   `analyze_batch` 回傳 `AnalysisResult`。
        -   `synthesize` 回傳字串。
        -   `health_check` 回傳布林值。
