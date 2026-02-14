# Lantern Roadmap

> **Last Updated**: 2025-02

本文件詳細說明 Lantern 的發展路線圖，包含短期、中期與長期計畫。

---

## 📊 當前狀態（v0.1.x）

### ✅ 已完成的核心功能

| 功能 | 狀態 | 版本 |
| :--- | :--- | :--- |
| 依賴圖分析（Python + C++） | ✅ 完成 | v0.1.0 |
| Batch 規劃與執行 | ✅ 完成 | v0.1.0 |
| Bottom-up 文件生成 | ✅ 完成 | v0.1.0 |
| Top-down 文件合成 | ✅ 完成 | v0.1.0 |
| Ollama 本地模型支援 | ✅ 完成 | v0.1.0 |
| **OpenAI API 直接支援** | ✅ 完成 | v0.1.2 |
| OpenRouter 雲端 API 支援 | ✅ 完成 | v0.1.0 |
| **Mermaid 圖表自動生成** | ✅ 完成 | v0.1.1 |
| 成本追蹤與估算 | ✅ 完成 | v0.1.1 |
| 檢查點恢復機制 | ✅ 完成 | v0.1.1 |
| 結構化輸出驗證 | ✅ 完成 | v0.1.1 |

### 🎯 價值定位

Lantern 目前是一個**生產就緒的程式碼理解工具**，具備：
- 🌐 母語文檔生成（zh-TW 預設）
- 📊 自動視覺化（Mermaid 圖表）
- 🔒 隱私保障（Ollama 本地支援）
- 💰 成本透明（執行前估算）
- 🔄 生產級可靠（檢查點恢復）

---

## 🚀 近期計畫（v0.2.x - 3 個月內）

### 優先順序 P0

#### 1. Agentic Synthesis（智慧合成）🔥
**目標**：大幅提升 Top-down 文檔品質

**動機**：
當前 Top-down 合成僅透過 Batch API 聚合 bottom-up 結果，缺乏：
- 橫向比較（如 `sc_port` vs `sc_export`）
- 設計模式識別（Factory、Observer 等）
- 高層次架構洞察

**實作計畫**：
```
階段 1: POC（2 週）
├─ 使用 LangGraph 實作 Synthesis Agent
├─ 工具：read_sense_files, compare_components, identify_architecture
└─ 測試：比較 Agentic vs 純 Batch 的 ARCHITECTURE.md 品質

階段 2: 整合（2 週）
├─ 整合至 lantern run 流程
├─ 新增 --synthesis-mode=batch|agentic 選項
└─ 文檔與範例

階段 3: 優化（2 週）
├─ 錯誤處理與重試
├─ 成本控制（預算限制）
└─ 使用者回饋收集
```

**預期效果**：
- ARCHITECTURE.md 包含設計模式分析
- CONCEPTS.md 自動識別核心抽象
- GETTING_STARTED.md 提供智慧學習路徑

**成本影響**：+$0.30-$1.00 per repository

---

#### 2. 增量更新模式（Incremental Update）
**目標**：支援程式碼變更後的部分更新

**使用場景**：
```
# 初次分析
lantern run --repo ~/my-project

# 修改 3 個檔案後
git diff --name-only HEAD~1
# src/auth.py
# src/models.py
# tests/test_auth.py

# 僅重新分析變更檔案
lantern update --changed-only
```

**實作策略**：
1. **變更偵測**：
   - 整合 Git（`git diff --name-only`）
   - 檔案 hash 比較（`.lantern/file_hashes.json`）
2. **影響分析**：
   - 重新分析變更檔案的 Batch
   - 識別受影響的依賴檔案（透過依賴圖）
3. **部分合成**：
   - 更新受影響的 bottom-up 文檔
   - 重新生成 top-down 文檔（因為需要全域視野）

**挑戰**：
- 如何判斷變更是否需要重新規劃？
- Top-down 文檔是否需要完全重建？

**預估工時**：4 週

---

#### 3. 靜態分析擴展（Go + Rust）
**目標**：支援 Go 和 Rust 的依賴分析

**當前支援**：
- ✅ Python（AST-based）
- ✅ C++（regex-based）

**新增支援**：
- 🔵 **Go**：使用 `go/parser` 解析 `import` 語句
- 🔵 **Rust**：解析 `use` 與 `mod` 語句

**實作範例**（Go）：
```python
import subprocess
import json

def analyze_go_imports(file_path: str) -> List[str]:
    """使用 go list 分析 imports"""
    result = subprocess.run(
        ["go", "list", "-json", file_path],
        capture_output=True,
        text=True
    )
    data = json.loads(result.stdout)
    return data.get("Imports", [])
```

**預估工時**：2 週（每語言 1 週）

---

### 優先順序 P1

#### 4. VSCode Extension
**目標**：IDE 整合，提升使用體驗

**功能設計**：
```
功能 1: 進度追蹤
├─ 顯示 Batch 執行進度（側邊欄）
├─ 即時成本更新
└─ 失敗 Batch 一鍵重試

功能 2: 文檔預覽
├─ Markdown 預覽（支援 Mermaid 渲染）
├─ Hover 顯示檔案摘要
└─ 點擊跳轉至 bottom-up 文檔

功能 3: 一鍵分析
├─ 右鍵選單：Analyze with Lantern
├─ 僅分析選中檔案
└─ 快速查看分析結果
```

**技術棧**：
- TypeScript + VSCode Extension API
- Webview for Mermaid rendering
- Language Server Protocol（未來整合 LSP）

**參考競品**：
- GitHub Copilot Chat（側邊欄設計）
- Markdown Preview Enhanced（Mermaid 渲染）

**預估工時**：8 週

---

#### 5. 直接 API 支援（Gemini/Claude SDK）
**目標**：不透過 OpenRouter，直接調用官方 SDK

**動機**：
- 更低延遲（無中間代理）
- 可能更低成本（無 OpenRouter 手續費）
- 支援更多模型專屬功能

**實作**：
```python
# src/lantern_cli/llm/gemini.py
from google.generativeai import GenerativeModel

class GeminiBackend:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.model = GenerativeModel(model)

    def analyze_batch(self, files, context, prompt):
        # 直接調用 Gemini API
        response = self.model.generate_content(prompt)
        return parse_structured_output(response.text)
```

**配置範例**：
```toml
[backend]
type = "gemini"
gemini_model = "gemini-2.0-flash"
gemini_api_key_env = "GEMINI_API_KEY"
```

**預估工時**：2 週

---

## 🎯 中期計畫（v0.3.x - 6 個月內）

### 6. Agentic Planning（智慧規劃）🔥
**目標**：使用 Agent 生成更智慧的分析計畫

**當前問題**：
- 靜態分析僅基於 import 關係
- 無法識別設計模式
- 批次分組缺乏語意理解

**Agentic Planning 流程**：
```
Agent 探索階段：
1. read_file("src/main.py")  # 讀取入口檔案
2. identify_pattern()         # 識別：這是 Flask 應用
3. list_directory("src/")    # 列出所有檔案
4. compare_files(["auth.py", "session.py"])  # 比較相似檔案
5. update_memory("發現 Factory Pattern 在 factory.py")

Agent 規劃階段：
6. generate_batches()        # 基於發現生成批次
   - Batch 1: auth.py + session.py（認證模組）
   - Batch 2: factory.py + builders/*.py（Factory Pattern）
7. add_context_hints()       # 為每個 Batch 加入提示
```

**增強版 `lantern_plan.md`**：
```markdown
## Batch 003: Factory Pattern Implementation

**Files**:
- `factory.py`
- `builders/user_builder.py`
- `builders/post_builder.py`

**Agent Discovery**:
這三個檔案實作了 **Builder Pattern** 的變體。`factory.py` 是工廠入口，兩個 builder 負責具體構建邏輯。

**Analysis Hints**:
- 重點關注 `create()` 方法的多態性
- 比較兩個 builder 的差異（複雜度、依賴）
- 檢查是否有 Abstract Factory 抽象
```

**技術實作**：
```python
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolExecutor

# Agent tools
tools = [
    read_file_tool,
    list_directory_tool,
    analyze_imports_tool,
    identify_pattern_tool,
    compare_files_tool
]

# LangGraph workflow
planning_graph = StateGraph()
planning_graph.add_node("explore", explore_codebase_node)
planning_graph.add_node("identify", identify_patterns_node)
planning_graph.add_node("plan", generate_enhanced_plan_node)
planning_graph.add_edge("explore", "identify")
planning_graph.add_edge("identify", "plan")

# Execute
result = planning_graph.invoke({
    "repo_path": "/path/to/repo",
    "language": "python"
})
```

**成本估算**：
- Agent 探索：50K-100K tokens
- 模型：Claude Sonnet 4
- 成本：$0.50-$2.00 per repository

**預估工時**：6 週

---

### 7. Execution Trace Mode（動態分析）
**目標**：透過執行 unit tests 收集 call graph

**動機**：
靜態分析無法知道：
- 實際執行路徑
- 哪些函數被頻繁呼叫
- 熱點程式碼（hot path）

**實作方式**：
```python
# 1. 插樁 (Instrumentation)
import sys
import trace

tracer = trace.Trace(count=True, trace=True)
tracer.run('pytest tests/')

# 2. 收集 call graph
call_graph = tracer.results()

# 3. 注入至分析 prompt
prompt = f"""
這個檔案的靜態分析如下...

動態執行資訊：
- authenticate() 被呼叫 1250 次
- generate_jwt() 被呼叫 1250 次
- check_password() 被呼叫 1300 次（50 次失敗）

請重點分析高頻呼叫的函數。
"""
```

**輸出範例**（ARCHITECTURE.md）：
```markdown
## Hot Paths (Based on Test Execution)

\`\`\`mermaid
graph TD
    API[API Layer<br/>1250 calls] --> Auth[authenticate()<br/>1250 calls]
    Auth --> CheckPwd[check_password()<br/>1300 calls]
    Auth --> JWT[generate_jwt()<br/>1250 calls]

    style API fill:#ff6b6b
    style Auth fill:#ff6b6b
    style CheckPwd fill:#ffd93d
```

**挑戰**：
- 需要可執行的 unit tests
- Instrumentation 可能影響執行時間
- 如何處理非同步程式碼？

**預估工時**：4 週

---

### 8. 社群模板市場（Community Templates）
**目標**：分享與下載社群貢獻的 prompt templates

**使用場景**：
```bash
# 瀏覽社群模板
lantern templates list

# 使用特定模板
lantern run --template=rails-api-focus

# 分享自己的模板
lantern templates publish my-react-template
```

**模板範例**（Rails API 專用）：
```json
{
  "name": "rails-api-focus",
  "description": "專注於 Rails API 端點與 ActiveRecord 模型",
  "prompts": {
    "system": "你是 Ruby on Rails 專家。重點分析 RESTful API 設計與資料庫關係。",
    "user": "分析這個 Rails controller/model..."
  },
  "schema": {
    "api_endpoints": {
      "type": "array",
      "description": "此檔案定義的 API 端點"
    },
    "activerecord_associations": {
      "type": "array",
      "description": "ActiveRecord 關聯（has_many, belongs_to 等）"
    }
  }
}
```

**技術實作**：
- GitHub Gist 作為模板儲存
- 本地快取（`~/.lantern/templates/`）
- 版本控制與評分系統

**預估工時**：4 週

---

## 🔮 長期願景（v1.0+ - 12 個月內）

### 9. Live Codebase Monitoring
**目標**：監控程式碼變更，自動更新文檔

**架構**：
```
File Watcher (inotify/fswatch)
    ↓
Detect changes (git diff)
    ↓
Trigger incremental analysis
    ↓
Update affected docs
    ↓
Notify user (VSCode notification)
```

**使用場景**：
```bash
# 啟動監控模式
lantern watch --repo ~/my-project

# 背景運行，偵測到變更時自動更新
# [Lantern] Detected changes in src/auth.py
# [Lantern] Re-analyzing Batch 003...
# [Lantern] Updated ARCHITECTURE.md
```

**技術挑戰**：
- 頻繁變更導致成本爆炸（需要智慧節流）
- 如何避免干擾開發流程？

---

### 10. AI Tutor Mode（互動式導師）
**目標**：從文檔生成工具進化為**互動式學習助手**

**功能設計**：
```bash
# 啟動 Tutor 模式
lantern tutor --repo ~/systemc

# 互動式對話
> User: 我想理解 sc_port 是如何運作的
> Lantern: 讓我引導你。首先，請看 ARCHITECTURE.md 中的這段...
>          [顯示相關段落 + Mermaid 圖]
>
>          sc_port 是一個模板類別，用於...
>
>          我建議你按照以下順序學習：
>          1. 先看 sc_port.h 的介面定義
>          2. 再看 sc_port.cpp 的實作
>          3. 最後看 examples/port_example.cpp
>
>          準備好了嗎？

> User: 好的，開始吧
> Lantern: [打開 VSCode，跳轉至 sc_port.h:42]
>          這裡定義了 bind() 方法...
```

**技術實作**：
- RAG over generated docs
- VSCode Extension 整合
- Conversational AI (Claude/GPT)

**差異化價值**：
- 不只是「問答」，而是**引導式學習**
- 基於靜態 + 動態分析的深度理解
- 個性化學習路徑

---

### 11. 多模態支援（Diagrams + Screenshots）
**目標**：不只分析程式碼，也分析系統圖與截圖

**使用場景**：
```bash
# 加入架構圖
lantern run --include-diagrams docs/architecture.png

# Lantern 分析圖片內容
# "這個架構圖顯示了微服務架構，包含 API Gateway、Auth Service、User Service..."

# 與程式碼交叉驗證
# "圖中顯示的 Auth Service 對應程式碼中的 src/auth/"
```

**技術**：
- Vision LLM (GPT-4V, Claude 3)
- OCR + Mermaid 生成
- 圖文對應分析

---

## 📈 成功指標（Success Metrics）

### 產品指標
- **使用者數**：1000+ active users (6 months)
- **Repo 分析次數**：10K+ repositories analyzed
- **模板下載**：500+ community template downloads

### 品質指標
- **文檔品質評分**：使用者評分 4.5+/5.0
- **Agentic 提升**：Top-down 文檔品質提升 30%（人工評估）
- **成本效率**：平均成本 < $3 per repository

### 技術指標
- **測試覆蓋率**：90%+
- **平均執行時間**：< 5 min for 100-file repo
- **失敗率**：< 5% (with checkpoint resume)

---

## 🤝 社群貢獻優先事項

我們歡迎社群貢獻以下領域：

### 高優先級
- [ ] 新語言支援（Java, JavaScript, TypeScript）
- [ ] 社群模板貢獻
- [ ] VSCode Extension 開發
- [ ] 文檔範例與教學

### 中優先級
- [ ] 效能優化（平行化、快取）
- [ ] 錯誤處理改進
- [ ] i18n 支援（更多語言輸出）

### 長期實驗
- [ ] Agentic 架構 POC
- [ ] Live monitoring 原型
- [ ] AI Tutor 對話設計

---

## 📚 參考資源

- [spec.md](spec.md) - 技術規格
- [task_v2.md](task_v2.md) - 開發任務追蹤
- [README.md](../README.md) - 使用者指南
- [LangGraph 文檔](https://langchain-ai.github.io/langgraph/) - Agentic 架構參考

---

**最後更新**: 2025-02
**維護者**: [@powei-lin](https://github.com/powei-lin)
**意見回饋**: [GitHub Issues](https://github.com/powei-lin/lantern-cli/issues)
