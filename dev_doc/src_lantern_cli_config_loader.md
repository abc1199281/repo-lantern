# Config Loader (`src/lantern_cli/config/loader.py`)

## 概述
負責載入與合併多個來源的設定。支援 TOML 格式，並實作設定優先權邏輯。

## 主要類別

### `ConfigLoader`
-   **初始化**: 接受 User Config 與 Project Config 的路徑。
-   **`load(cli_overrides)`**: 載入並回傳最終的 `LanternConfig` 物件。
    -   **優先權 (高 -> 低)**:
        1.  CLI 參數 (`cli_overrides`)
        2.  專案設定 (`.lantern/lantern.toml`)
        3.  使用者設定 (`~/.config/lantern/lantern.toml`)
        4.  預設值
-   **`_merge_dicts`**: 遞迴合併字典，確保深層設定能正確覆蓋。

### `load_config(repo_path)`
Helper function，快速載入指定 Repo 的設定。
