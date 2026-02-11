# Generic Analyzer (`src/lantern_cli/static_analysis/generic.py`)

## 概述
通用型的靜態分析器，用於處理非 Python 語言 (如 JS/TS) 或作為 Python AST 解析失敗時的備案。使用正規表達式 (Regex) 或 Ripgrep (`rg`) 來提取引用。

## 主要類別

### `GenericAnalyzer`
-   **`extract_imports(file_path, language)`**:
    -   根據語言選擇 Regex Pattern。
    -   **Python**: 匹配 `import x`, `from x import y`。
    -   **JS/TS**: 匹配 `import ... from 'x'`, `require('x')`。
-   **`grep_imports(directory, pattern)`**:
    -   如果系統安裝了 `rg` (Ripgrep)，使用它進行高效搜尋。
    -   否則，使用 Python 的 `pathlib` 進行遞迴掃描 (Fallback)。
