# Integration Test: CLI Flow (`tests/integration/test_cli_flow.py`)

## 目的
驗證 CLI 指令 (`run`, `init`, `plan`) 與內部核心模組 (Architect, Runner, StateManager, Synthesizer) 之間的互動流程。此測試大量使用 Mock 來隔離外部依賴，專注於流程控制。

## 測試類別: `TestCLIFlow`

### Fixtures
- **`mock_components`**: Mock 所有主要核心元件 (Graph, Architect, State, Runner, Synth, Factory, Config)。

### 測試案例 (Test Cases)

1.  **`test_lantern_run_flow`**
    -   **目的**: 驗證 `lantern run` 指令的執行順序與元件互動。
    -   **驗證流程**:
        1.  Config Loading
        2.  Backend Factory Initialization
        3.  Static Analysis (Graph Build)
        4.  Architect Plan Generation
        5.  Runner Execution Loop
        6.  Synthesizer Documentation Generation

2.  **`test_lantern_init`**
    -   **目的**: 驗證 `lantern init` 指令。
    -   **驗證點**: `.lantern` 目錄與設定檔被建立。

3.  **`test_lantern_plan`**
    -   **目的**: 驗證 `lantern plan` 指令。
    -   **驗證點**:
        -   Graph 與 Architect 被呼叫。
        -   Runner **未**被呼叫 (Plan 模式不執行分析)。
