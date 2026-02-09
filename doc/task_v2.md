# Lantern MVP v2 Development Task List

## Objective

將 Lantern 從 CLI-wrapper 架構升級為 **API-first** 架構，使用真正的 LLM SDK 進行分析，並為未來的 Agentic 模式奠定基礎。

---

## Phase 1: API Backend Implementation (Core Priority)

### 1.1 Gemini API Integration
- [ ] **安裝依賴**: Add `google-generativeai` to `pyproject.toml`
- [ ] **實現真正的 API 調用**: 更新 `GeminiAdapter._call_api()` 使用 SDK
- [ ] **結構化 Prompt**: 設計適合程式碼分析的 prompt template
- [ ] **輸出解析**: 改進 `_parse_output()` 以處理真實 LLM 回應
- [ ] **錯誤處理**: 處理 rate limits, timeouts, API errors

### 1.2 Claude/Anthropic API Integration
- [ ] **安裝依賴**: Add `anthropic` to `pyproject.toml`
- [ ] **實現 API 調用**: 更新 `ClaudeAdapter` 使用 Anthropic SDK
- [ ] **Prompt 適配**: 調整 prompt 以適應 Claude 的特性

### 1.3 Configuration Updates
- [ ] **API Key 管理**: 支援 `.env` 或環境變數
- [ ] **Model 選擇**: 允許用戶在 `lantern.toml` 中指定 model
- [ ] **Rate Limit 配置**: 添加 `requests_per_minute` 配置

---

## Phase 2: Prompt Engineering & Quality

### 2.1 程式碼分析 Prompt
- [ ] **檔案摘要 Prompt**: 設計單檔 bottom-up 分析模板
- [ ] **批次分析 Prompt**: 設計關聯檔案一起分析的模板
- [ ] **多語言輸出 Prompt**: 確保 `--lang zh-TW` 產出品質

### 2.2 文件合成 Prompt
- [ ] **Top-down 合成 Prompt**: 設計 OVERVIEW.md, ARCHITECTURE.md 生成模板
- [ ] **Concept 提取 Prompt**: 設計 CONCEPTS.md 生成模板

---

## Phase 3: (Optional) Agentic Foundation

> 此階段為可選，取決於是否需要更智能的分析模式

### 3.1 Tool Definition
- [ ] **定義工具**: `read_file`, `list_directory`, `search_code`
- [ ] **工具執行器**: 實現安全的工具調用框架

### 3.2 Agent Loop (可選 LangGraph)
- [ ] **ReAct Pattern**: 實現 Thought → Action → Observation 循環
- [ ] **Autonomous Exploration**: LLM 自主決定「下一步看什麼」
- [ ] **Memory**: 維護已分析內容的摘要

---

## Phase 4: Testing & Verification

### 4.1 Unit Tests
- [ ] **Mock API Tests**: 使用 mock 測試 API adapters
- [ ] **Prompt Tests**: 驗證 prompt 模板生成正確

### 4.2 Integration Tests
- [ ] **E2E with Real API**: 使用真實 API 測試完整流程 (需 API Key)
- [ ] **Output Quality Check**: 手動檢查生成文件品質

---

## Dependencies to Add

```toml
[tool.poetry.dependencies]
google-generativeai = "^0.8.0"  # Gemini API
anthropic = "^0.50.0"           # Claude API
python-dotenv = "^1.0.0"        # .env support
# langchain-core = "^0.3.0"     # (Optional) For future Agent mode
# langgraph = "^0.2.0"          # (Optional) For Agent orchestration
```

---

## Design Decision: API vs CLI vs Agent

| Approach | Stability | Complexity | Use Case |
|----------|-----------|------------|----------|
| **API (推薦)** | ⭐⭐⭐ | 中等 | 穩定的批次分析 |
| CLI Wrapper | ⭐ | 低 | 快速 PoC，不推薦 production |
| Agentic (LangGraph) | ⭐⭐ | 高 | 自主探索、問答互動 |

**結論**: MVP 優先實現 API 模式，Agentic 作為 Roadmap 項目。
