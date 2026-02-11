# Test File Filter (`tests/unit/test_file_filter.py`)

## 目的
測試 `FileFilter` 模組，驗證檔案過濾邏輯，包含預設排除規則、`.gitignore` 整合以及 Config 的 Include/Exclude 覆蓋機制。

## 測試類別: `TestFileFilter`

### Fixtures
- **`filter_config`**: 建立包含自定義 Include/Exclude 規則的設定。
- **`file_filter`**: 建立 `FileFilter` 實例。

### 測試案例 (Test Cases)

1.  **`test_default_excludes`**
    -   **目的**: 驗證預設排除規則 (如 `.git/`, `node_modules/`)。
    -   **驗證點**: 這些檔案/目錄應被忽略。

2.  **`test_custom_excludes`**
    -   **目的**: 驗證來自 Config 的自定義排除規則。
    -   **驗證點**: 符合 Config Exclude 規則的檔案應被忽略。

3.  **`test_include_overrides`**
    -   **目的**: 驗證 Include 規則優先於 Exclude (白名單機制)。
    -   **情境**: 檔案同時符合 Exclude 與 Include 規則 (如排除 `*.tmp` 但包含 `important.tmp`)。
    -   **驗證點**: 檔案不應被忽略。

4.  **`test_gitignore_parsing`**
    -   **目的**: 驗證 `.gitignore` 檔案解析功能。
    -   **操作**: 建立包含忽略規則的 `.gitignore` 檔案。
    -   **驗證點**: 符合 `.gitignore` 規則的檔案應被忽略。

5.  **`test_walk_files`**
    -   **目的**: 驗證目錄遍歷 (Walk) 與過濾功能的整合。
    -   **操作**: 遍歷包含多種檔案與 `.gitignore` 的目錄結構。
    -   **驗證點**: 回傳的檔案列表應排除所有被忽略的檔案，且不包含 `.git` 目錄等。
