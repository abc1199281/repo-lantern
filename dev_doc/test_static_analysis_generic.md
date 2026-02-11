# Test Generic Analyzer (`tests/unit/test_static_analysis_generic.py`)

## 目的
測試 `GenericAnalyzer`，驗證其對多語言的通用靜態分析能力，包含 Regex Fallback 機制與 Ripgrep 整合。

## 測試類別: `TestGenericAnalyzer`

### Fixtures
- **`analyzer`**: 建立 `GenericAnalyzer` 實例。

### 測試案例 (Test Cases)

1.  **`test_extract_imports_python_regex`**
    -   **目的**: 驗證 Python Regex Fallback 解析。
    -   **輸入**: `import`, `from ... import`。
    -   **驗證點**: 正確提取模組名稱。

2.  **`test_extract_imports_js_regex`**
    -   **目的**: 驗證 JavaScript Regex Fallback 解析。
    -   **輸入**: ES6 `import`, CommonJS `require`。
    -   **驗證點**: 正確提取模組名稱。

3.  **`test_ripgrep_installed_check`**
    -   **目的**: 驗證 Ripgrep 可用性檢查函式。

4.  **`test_unsupported_language_returns_empty`**
    -   **目的**: 驗證不支援語言的處理。
    -   **驗證點**: 回傳空列表。

5.  **`test_ripgrep_extraction`**
    -   **目的**: 驗證整合 Ripgrep 進行 import 搜尋。
    -   **Mock**: `subprocess.run` 模擬 `rg` 輸出。
    -   **驗證點**: 解析 `rg` 輸出格式 (file:line:content) 並回傳結果。

6.  **`test_scan_directory_integration`**
    -   **目的**: 驗證目錄掃描功能的整合 (Fallback 模式)。
    -   **操作**: 掃描包含多語言檔案的目錄。
    -   **驗證點**: 跨檔案、跨語言的 import 均被找出。
