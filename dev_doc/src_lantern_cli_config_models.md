# Config Models (`src/lantern_cli/config/models.py`)

## 概述
定義 Lantern 設定的資料模型，使用 Pydantic 進行型別驗證與預設值管理。

## 主要類別

### `LanternConfig`
根設定物件。
-   `language`: 輸出語言 (預設 "en")。
-   `output_dir`: 輸出目錄。
-   `filter`: `FilterConfig` 實例。
-   `backend`: `BackendConfig` 實例。

### `FilterConfig`
檔案過濾設定。
-   `exclude`: 排除規則列表 (Glob patterns)。
-   `include`: 包含規則列表 (優先於 exclude)。

### `BackendConfig`
Backend 相關設定。
-   `type`: "cli" 或 "api"。
-   **CLI 選項**: `cli_command`, `cli_timeout`。
-   **API 選項**: `api_provider`, `api_model`, `api_key_env`。
