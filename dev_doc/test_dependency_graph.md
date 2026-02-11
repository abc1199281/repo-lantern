# Test Dependency Graph (`tests/unit/test_dependency_graph.py`)

## 目的
測試 `DependencyGraph` 模組，驗證依賴關係的建立、拓撲排序 (分層計算) 以及循環依賴的偵測功能。

## 測試類別: `TestDependencyGraph`

### Fixtures
- **`graph`**: 建立一個空的 `DependencyGraph` 實例。

### 測試案例 (Test Cases)

1.  **`test_add_dependency`**
    -   **目的**: 驗證加入依賴關係的功能。
    -   **操作**: 加入 A->B, A->C。
    -   **驗證點**: A 的依賴列表中應包含 B 與 C。

2.  **`test_topological_sort`**
    -   **目的**: 驗證分層計算 (Layer Calculation)。
    -   **情境**: A -> B -> C。
    -   **驗證點**:
        -   C (無依賴) 應為 Layer 0。
        -   B (依賴 C) 應為 Layer 1。
        -   A (依賴 B) 應為 Layer 2。

3.  **`test_circular_dependency`**
    -   **目的**: 驗證循環依賴偵測。
    -   **情境**: A -> B -> A。
    -   **驗證點**: `detect_cycles()` 應回傳包含 [A, B] 的循環路徑。

4.  **`test_complex_graph_metrics`**
    -   **目的**: 驗證複雜圖結構的分層計算。
    -   **情境**: 菱形依賴 (A -> B, C; B -> D; C -> D)。
    -   **驗證點**:
        -   D 應為 Layer 0。
        -   B, C 應為 Layer 1。
        -   A 應為 Layer 2。
