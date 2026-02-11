# Python Analyzer (`src/lantern_cli/static_analysis/python.py`)

## 概述
專門用於解析 Python 程式碼的靜態分析器。使用 Python 內建的 `ast` 模組來準確提取 import 語句。

## 主要類別

### `PythonAnalyzer`
-   **`analyze_imports(file_path)`**:
    -   讀取檔案內容並解析為 AST (Abstract Syntax Tree)。
    -   走訪 AST 尋找 `ast.Import` 與 `ast.ImportFrom` 節點。
    -   解析相對引用 (如 `from . import utils`) 與絕對引用。
    -   回傳標準化的模組名稱列表。
    -   忽略語法錯誤 (SyntaxError)，確保分析過程不中斷。
