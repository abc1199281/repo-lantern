# File Filter (`src/lantern_cli/static_analysis/file_filter.py`)

## 概述
負責檔案過濾邏輯，決定哪些檔案應被納入分析。整合了多層次的過濾規則。

## 主要類別

### `FileFilter`
-   **驗證優先順序**:
    1.  **Config Include**: 強制包含 (白名單)。
    2.  **Config Exclude**: 使用者自定義排除。
    3.  **Default Exclude**: 系統預設排除 (如 `.git/`, `__pycache__/`, `node_modules/` 等)。
    4.  **.gitignore**: 遵循專案的 gitignore 規則。
-   **`should_ignore(file_path)`**: 判斷單一檔案是否應被忽略。
-   **`walk()`**: Generator，遞迴遍歷專案目錄，並自動過濾檔案。
