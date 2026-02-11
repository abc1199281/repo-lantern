# Test Gemini Adapter (`tests/unit/test_backend_gemini.py`)

## 目的
測試 `GeminiAdapter` (API Backend) 的功能，驗證其與 Google Gemini API 的互動、環境變數處理以及回應解析邏輯。

## 測試類別: `TestGeminiAdapter`

### Fixtures
- **`adapter`**: 建立 `GeminiAdapter` 實例。

### 測試案例 (Test Cases)

1.  **`test_health_check_success`**
    -   **目的**: 驗證 API Key 存在時的健康檢查。
    -   **Mock**: 設定 `GEMINI_API_KEY` 環境變數。
    -   **驗證點**: 回傳 True。

2.  **`test_health_check_failure`**
    -   **目的**: 驗證 API Key 缺失時的健康檢查。
    -   **Mock**: 清空環境變數。
    -   **驗證點**: 回傳 False。

3.  **`test_analyze_batch`**
    -   **目的**: 驗證 API 呼叫流程。
    -   **Mock**: `_call_api` 方法回傳模擬的字串。
    -   **驗證點**: 回傳 `AnalysisResult`，且內容正確解析。

4.  **`test_parse_output`**
    -   **目的**: 驗證 LLM 輸出的解析邏輯。
    -   **輸入**: 包含 Markdown 標題 (Summary, Key Insights, Questions) 的字串。
    -   **驗證點**:
        -   Summary 區塊正確提取。
        -   Key Insights 列表正確解析 (去除項目符號)。
        -   Questions 列表正確解析。
