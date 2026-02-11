# Test Config Loader (`tests/unit/test_config_loader.py`)

## 目的
測試 `ConfigLoader` 模組，驗證設定檔 (Default, User, Project) 的載入、合併邏輯，以及 CLI 參數的覆蓋機制。

## 測試類別: `TestConfigLoader`

### 測試案例 (Test Cases)

1.  **`test_load_default_config`**
    -   **目的**: 驗證預設設定的載入。
    -   **操作**: 指向不存在的設定檔路徑。
    -   **驗證點**: 回傳 `LanternConfig` 實例，屬性為預設值 (如 language="en")。

2.  **`test_load_from_toml_file`**
    -   **目的**: 驗證從 TOML 檔案載入設定。
    -   **輸入**: 包含 `[lantern]`, `[filter]`, `[backend]` 區段的 TOML 內容。
    -   **驗證點**: 載入的 Config 物件屬性應與 TOML 內容一致。

3.  **`test_config_priority_cli_overrides_file`**
    -   **目的**: 驗證 CLI 參數優先權高於設定檔。
    -   **操作**: 提供設定檔與 `cli_overrides` 字典。
    -   **驗證點**: 最終 Config 屬性應採用 CLI 參數的值。

4.  **`test_load_nonexistent_file_returns_default`**
    -   **目的**: 驗證指定檔案不存在時的回退 (Fallback) 行為。
    -   **驗證點**: 回退至預設設定，不拋出錯誤。

5.  **`test_merge_user_and_project_config`**
    -   **目的**: 驗證設定層級合併 (User < Project)。
    -   **情境**: User Config 設定語言與 Backend，Project Config 設定輸出目錄與 Filter。
    -   **驗證點**: Project 設定覆蓋同名 User 設定 (如有)，未覆蓋處保留 User 設定。

6.  **`test_invalid_toml_raises_error`**
    -   **目的**: 驗證無效 TOML 格式的錯誤處理。
    -   **驗證點**: 拋出解析錯誤 (Exception)。
