# Test Synthesizer (`tests/unit/test_synthesizer.py`)

## 目的
測試 `Synthesizer` 模組，驗證其匯總個別 Batch 的分析結果 (`.sense` files) 並生成最終文件 (Top-Down Documentation) 的流程。

## 測試類別: `TestSynthesizer`

### Fixtures
- **`synthesizer`**: 建立 `Synthesizer` 實例，預先建立模擬的 `.sense` 檔案。

### 測試案例 (Test Cases)

1.  **`test_load_sense_files`**
    -   **目的**: 驗證讀取 `.sense` 檔案的功能。
    -   **操作**: 讀取包含兩個 Batch 分析結果的目錄。
    -   **驗證點**: 回傳的內容列表包含預期的字串。

2.  **`test_generate_top_down_docs`**
    -   **目的**: 驗證文件生成流程。
    -   **Mock**: 模擬檔案寫入 (`builtins.open`)。
    -   **驗證點**: `open` 方法被呼叫 (表示有嘗試寫入文件，如 OVERVIEW.md)。

3.  **`test_empty_sense_files`**
    -   **目的**: 驗證無 `.sense` 檔案時的行為。
    -   **驗證點**: 回傳空列表，程式不崩潰。
