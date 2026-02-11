# Dependency Graph (`src/lantern_cli/static_analysis/dependency_graph.py`)

## 概述
負責建構專案的模組依賴圖，並計算模組的分層 (Layers)，這是 `Architect` 規劃分析順序的基礎。

## 主要類別

### `DependencyGraph`
-   **初始化**: 接收 Root Path 與排除規則。
-   **`build()`**:
    1.  掃描所有 Python 檔案 (排除忽略項目)。
    2.  解析每個檔案的 imports (使用 `PythonAnalyzer`)。
    3.  將 import 路徑解析為專案內的模組，建立依賴關係。
-   **`calculate_layers()`**:
    -   計算拓撲排序/分層。
    -   **Level 0**: 無依賴的模組 (最底層)。
    -   **Level N**: 依賴於 Level < N 的模組。
    -   支援處理簡單的 DAG 結構。
-   **`detect_cycles()`**: 使用 DFS 偵測循環依賴，回傳循環路徑列表。
