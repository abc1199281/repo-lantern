# Test Config Models (`tests/unit/test_config_models.py`)

## 目的
測試 Pydantic Configuration Models (`FilterConfig`, `BackendConfig`, `LanternConfig`)，驗證預設值設定與型別驗證邏輯。

## 測試類別: `TestFilterConfig`
-   **`test_default_values`**: 驗證 Exclude/Include 預設為空列表。
-   **`test_exclude_patterns`**: 驗證 Exclude 規則設定。
-   **`test_include_patterns`**: 驗證 Include 規則設定。

## 測試類別: `TestBackendConfig`
-   **`test_default_backend_type`**: 驗證預設 Backend Type 為 "cli"。
-   **`test_cli_backend_config`**: 驗證 CLI Backend 相關參數 (Command, Timeout) 設定。
-   **`test_api_backend_config`**: 驗證 API Backend 相關參數 (Provider, Model, Key Env) 設定。
-   **`test_invalid_backend_type`**: 驗證輸入無效 Type (如 "invalid") 時拋出 `ValidationError`。

## 測試類別: `TestLanternConfig`
-   **`test_default_config`**: 驗證全域設定 (Language, Output Dir) 的預設值。
-   **`test_custom_language`**, **`test_custom_output_dir`**: 驗證自定義值設定。
-   **`test_nested_filter_config`**: 驗證巢狀 Filter 設定的正確性。
-   **`test_nested_backend_config`**: 驗證巢狀 Backend 設定的正確性。
