# Integration Test: Simple E2E (`tests/integration/test_e2e_simple.py`)

## 目的
執行端對端 (End-to-End) 的簡單整合測試，驗證從初始化、計畫生成到分析執行的完整工作流程。使用真實的 CLI 命令與臨時檔案系統，但 Mock 後端 API 呼叫。

## 測試類別: `TestE2ESimple`

### Fixtures
- **`repo_path`**: 建立一個包含 `src/main.py` 與 `src/utils.py` 的虛擬 Repository 結構。

### 測試案例 (Test Cases)

1.  **`test_full_workflow`**
    -   **目的**: 驗證 `init` -> `plan` -> `run` 的完整流程。
    -   **步驟**:
        1.  **Initialize**: 執行 `lantern init`，驗證 `.lantern/lantern.toml` 建立。
        2.  **Plan**: 執行 `lantern plan`，驗證 `.lantern/lantern_plan.md` 建立。
        3.  **Run**: 執行 `lantern run` (Mock Backend)。
    -   **驗證點**:
        -   所有指令 Exit Code 為 0。
        -   Stdout 包含預期訊息 (如 "Analysis Complete")。
        -   輸出目錄 (`.lantern/output/en`) 包含：
            -   Top-down 文件 (`OVERVIEW.md`, `ARCHITECTURE.md`)。
            -   Bottom-up 文件 (`main.py.md`, `utils.py.md`)。
