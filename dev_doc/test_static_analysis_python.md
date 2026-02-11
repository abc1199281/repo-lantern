# Test Python Analyzer (`tests/unit/test_static_analysis_python.py`)

## 目的
測試 `PythonAnalyzer` 的靜態分析功能，主要驗證其是否能正確解析 Python 程式碼中的 import 語句與依賴關係。

## 測試類別: `TestPythonAnalyzer`

### Fixtures
- **`analyzer`**: 建立 `PythonAnalyzer` 實例。

### 測試案例 (Test Cases)

1.  **`test_std_imports`**
    -   **目的**: 驗證標準程式庫 import 的解析。
    -   **輸入**: `import os`, `import sys`
    -   **驗證點**: 是否包含 "os", "sys"。

2.  **`test_from_imports`**
    -   **目的**: 驗證 `from ... import ...` 語法的解析。
    -   **輸入**: `from pathlib import Path`, `from typing import List`
    -   **驗證點**: 是否包含 "pathlib", "typing"。

3.  **`test_relative_imports`**
    -   **目的**: 驗證相對路徑 import 的解析。
    -   **輸入**: `from . import utils`, `from ..core import config`
    -   **驗證點**: 是否包含 ".utils", "..core"。

4.  **`test_import_as_alias`**
    -   **目的**: 驗證別名 (Alias) import 的解析。
    -   **輸入**: `import pandas as pd`
    -   **驗證點**: 是否解析出原始模組名稱 "pandas"。

5.  **`test_syntax_error_handling`**
    -   **目的**: 驗證語法錯誤的處理。
    -   **輸入**: 包含無效 Python 語法的檔案。
    -   **驗證點**: 是否優雅處理並回傳空列表 (或其他預定義的錯誤行為)。

6.  **`test_non_existent_file`**
    -   **目的**: 驗證檔案不存在的處理。
    -   **驗證點**: 是否回傳空列表。

7.  **`test_generic_exception`**
    -   **目的**: 驗證解析過程中發生未預期異常的處理。
    -   **Mock**: `ast.parse` 拋出通用 Exception。
    -   **驗證點**: 是否回傳空列表，不導致程式崩潰。
