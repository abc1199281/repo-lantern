# Lantern Specification

> **Lantern — Your repository mentor.**

## 1. 核心願景 (Core Vision)

Lantern 是一個基於 CLI Agent 的儲存庫（Repository）分析工具。其核心目的不是單純的「生成文檔」，而是透過心理學引導與結構化拆解，幫助開發者在最低認知負擔的情況下，快速且深度地理解一個陌生的程式碼庫。

### 1.1 為什麼選擇 CLI？ (Why CLI?)

本工具選擇驅動現有的 CLI Agents (如 `antigravity`, `gemini-cli`, `claude-code`) 而非直接調用 API，基於以下考量：

- **代理效能優勢 (Agentic Synergy)**: 官方提供的 CLI 工具通常內建了成熟的檔案讀取、環境感知與錯誤回報機制（如 Antigravity 的 Task 系統），直接封裝這些 CLI 能繼承其對大型任務的處理邏輯。
- **開發者體驗 (Developer Experience)**: CLI 存在於開發者的原生環境（終端機）中，無需切換到瀏覽器或複雜的 GUI，符合「零摩擦」的工具設計原則。
- **強大的過程控制 (Process Control)**: 透過 CLI，我們可以輕易地利用 Python 的 `subprocess` 進行日誌重導向（Log Redirection）、超時控制與進度暫停，這在長達數小時的分析任務中至關重要。
- **繞過 API 限制**: 某些實驗性的 Agent 功能僅優先在 CLI 工具中釋出，且 CLI 工具通常具備更好的上下文壓縮與檔案 Token 管理策略。

### 1.2 心理學設計準則 (Psychological Design Principles)

- **塊狀化處理 (Chunking - Miller's Law)**: 嚴格限制每個批次（Batch）僅處理 3 個相關檔案，防止大腦產生資訊過載。
- **鷹架效應 (Scaffolding)**: 透過先生成計畫、再由人工微調、最後逐步執行的流程，為理解複雜系統搭建穩固的階梯。
- **母語預熱 (Native Language Priming)**: 最後階段將技術邏輯轉譯為使用者的母語，消除閱讀外語技術文件帶來的額外認知負擔。

---

## 2. 系統架構 (System Architecture)

### A. 建築師代理 (The Architect Agent)

**職責**: 走訪 Repo 目錄，理解依賴關係，並規劃執行路徑。

#### 靜態分析輔助 (Static Analysis Assistance)

> [!IMPORTANT]
> LLM 不擅長直接掃描大型目錄結構來判斷依賴關係。Architect 採用「混合模式」：
> - **傳統工具收集數據**：使用 `tree-sitter`、`grep`、AST 解析器等靜態分析工具
> - **LLM 做決策**：基於收集的數據，LLM 規劃分析路徑

**支援的靜態分析工具**:
- **Python**: `ast` 模組解析 import 語句
- **JavaScript/TypeScript**: `tree-sitter` 解析依賴
- **通用**: `ripgrep` 搜尋關鍵字（如 `import`, `require`, `use`）

這避免了 LLM 的「幻覺」問題，確保依賴圖的準確性。

#### 檔案過濾與排除機制 (File Filtering)

> [!TIP]
> 排除不必要的檔案可大幅節省 API 成本。

**預設排除規則**：
- 自動尊重 `.gitignore` 中的檔案
- 預設排除目錄：`node_modules/`, `vendor/`, `build/`, `dist/`, `.git/`
- 預設排除檔案：`*.min.js`, `*.map`, `*.lock`

**配置範例** (`lantern.toml`)：
```toml
[filter]
# 額外排除規則
exclude = [
    "tests/",
    "docs/",
    "*.generated.*",
    "migrations/"
]

# 強制包含（覆蓋排除）
include = [
    "tests/integration/"  # 即使 tests/ 被排除，仍分析 integration tests
]
```

**目的**：避免分析不必要的程式碼（如第三方庫、生成檔案），節省 Token 與成本。

**Architect Prompt 範本**:

```markdown
你現在是 Lantern 的「建築師代理」。你的任務是基於靜態分析結果，規劃一份分析計畫。

輸入數據：
- 目錄結構: [tree output]
- 依賴關係圖: [parsed imports]
- 核心模組列表: [detected modules]

生成計畫：
請撰寫一份 lantern_plan.md。

硬性約束：
- 將任務劃分為多個 Phase（功能模組）。
- 每個 Phase 下劃分多個 Batch，每個 Batch 嚴格限制處理 1-3 個檔案。
- 針對每個 Batch，說明為什麼將這幾個檔案放在一起分析（基於認知負荷最小化原則）。
- 標註哪些地方需要人工介入確認。
```

**產出**: `lantern_plan.md` (結構化的待辦清單)。

**規則**:
- 每個 Phase 必須對應一個功能模組。
- 每個 Batch 不得超過 3 個檔案。
- 必須包含「為什麼這三個檔案放在一起」的解釋。

### B. 執行協調員 (The Python Runner/Walker)

**職責**: 自動化驅動 CLI 工具（如 Gemini CLI, Antigravity, Claude CLI）。

**功能**:
- **Watchdog**: 監控 Log 更新，偵測超時或中斷。
- **State Persistence**: 維護 `.lantern/state.json`，解決 CLI 工具「無狀態」的問題。
- **Temporal RAG**: 將 `global_summary` 注入每個 Batch 的 System Prompt，實現跨批次知識傳遞。
- **Intervention Gate**: 在 Phase 結束時自動暫停，確認使用者理解程度。

#### 時序性 RAG (Temporal RAG)

Batch N 需要 Batch 1 到 N-1 的知識。Runner 透過以下機制實現：

1. 每個 Batch 完成後，更新 `.lantern/state.json` 的 `global_summary`
2. 執行 Batch N 時，將 `global_summary` 注入 System Prompt：

```markdown
You are analyzing Batch {N}.

Context from previous batches:
{global_summary}

Now analyze:
- {file1}
- {file2}
```

這確保了邏輯的連貫性，避免重複推理。

#### 狀態恢復與斷點續傳 (Checkpoint Resume)

> [!IMPORTANT]
> 長時間運行的分析可能因 CLI 失敗、網路中斷等原因中斷。Lantern 支援完整的斷點續傳。

**恢復機制**：
1. 重新執行 `lantern run` 時，自動檢測 `.lantern/state.json`
2. 跳過已完成的 Batch（檢查 `.lantern/sense/batch_{N}.sense` 是否存在）
3. 從上次失敗的 Batch 繼續執行

**狀態檔範例** (`.lantern/state.json`)：
```json
{
  "status": "in_progress",
  "last_completed_batch": 49,
  "total_batches": 120,
  "failed_batch": 50,
  "failure_reason": "CLI timeout after 300s",
  "resume_from": 50
}
```

**使用效果**：
- `lantern run` 在 Batch 50 失敗後重新執行，自動從 Batch 50 繼續
- 已生成的 `.sense` 碧片與 bottom-up 文檔保留不重建

### C. 合成器 (The Synthesizer)

**職責**: 生成結構化的 Markdown 文檔庫，提供 Bottom-up 與 Top-down 兩種視角。

#### 雙階段生成策略

Synthesizer 採用**漸進式生成**，而非一次性產出：

**階段 1: Bottom-up 生成**（在 Batch 分析過程中）
- 每個 Batch 完成後，立即生成對應檔案的 `.md` 文檔
- 輸出位置：`.lantern/output/{lang}/bottom_up/`，結構完全鏡像原 Repository
- 每個 `.md` 文件包含：
  - 檔案用途與職責
  - 關鍵函數/類別說明
  - 依賴關係
  - 使用範例

**階段 2: Top-down 合成**（所有 Batch 完成後）
- 讀取所有 `.sense` 檔案與 bottom-up 文檔
- 使用高品質模型（Claude Sonnet, GPT-4o）生成高層次指南
- 輸出位置：`.lantern/output/{lang}/top_down/`

#### 輸出目錄結構

```
.lantern/output/
├── en/                          # 預設語言（英文）
│   ├── top_down/
│   │   ├── OVERVIEW.md         # 專案願景與範圍
│   │   ├── ARCHITECTURE.md     # 系統架構與模組關係
│   │   ├── CONCEPTS.md         # 核心概念（認證流程、快取策略、重試機制）
│   │   ├── FLOWS.md            # 關鍵資料流 (Sequence Diagrams)
│   │   └── GETTING_STARTED.md  # 新手上手指南
│   └── bottom_up/
│       ├── src/
│       │   ├── auth.py.md      # 鏡像 src/auth.py
│       │   ├── models.py.md    # 鏡像 src/models.py
│       │   └── api/
│       │       └── routes.py.md
│       └── tests/
│           └── test_auth.py.md
└── zh-TW/                       # 可選語言（繁體中文）
    ├── top_down/
    │   └── (同 en 結構)
    └── bottom_up/
        └── (同 en 結構)
```

#### Bottom-up 文檔範例

**檔案**: `.lantern/output/en/bottom_up/src/auth.py.md`

```markdown
# auth.py

\u003e **Location**: `src/auth.py`

## Purpose
Handles user authentication and JWT token generation.

## Key Components

### `authenticate(username, password)`
Validates user credentials against the database.

**Dependencies**:
- `models.User`
- `utils.hash_password`

**Returns**: `User` object or `None`

### `generate_jwt(user_id)`
Creates a JWT token for authenticated users.

**Example**:
\`\`\`python
token = generate_jwt(user.id)
\`\`\`
```

#### Top-down 文檔範例

**檔案**: `.lantern/output/en/top_down/ARCHITECTURE.md`

```markdown
# Architecture Overview

## System Design

Lantern follows a layered architecture:

1. **API Layer** (`src/api/`)
   - RESTful endpoints
   - Request validation

2. **Business Logic** (`src/auth.py`, `src/models.py`)
   - Authentication
   - Data models

3. **Data Layer** (`src/db/`)
   - Database connections
   - Migrations

## Module Relationships

\`\`\`mermaid
graph LR
    API --> Auth
    API --> Models
    Auth --> Models
    Models --> DB
\`\`\`
```

---

### D. 後端抽象層 (Backend Abstraction Layer)

> [!IMPORTANT]
> CLI 工具（如 `antigravity`, `gemini-cli`）的輸出格式非穩定 API，可能隨版本改變。
> 為確保長期穩定性，Lantern 必須透過 **Adapter Pattern** 隔離這些不穩定依賴。

#### Adapter 介面設計

所有 LLM 後端必須實作以下介面：

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class AnalysisResult:
    summary: str
    key_insights: list[str]
    questions: list[str]
    raw_output: str  # 原始 CLI/API 輸出，用於除錯

class BackendAdapter(ABC):
    """LLM 後端的抽象介面"""

    @abstractmethod
    def analyze_batch(
        self,
        files: list[str],
        context: str,
        prompt: str
    ) -> AnalysisResult:
        """分析一個 Batch 的檔案"""
        pass

    @abstractmethod
    def synthesize(
        self,
        sense_files: list[str],
        target_language: str
    ) -> str:
        """合成最終文檔"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """檢查後端是否可用"""
        pass
```

#### 後端選項

| 後端類型 | 穩定性 | 成本 | 適用場景 |
| :--- | :--- | :--- | :--- |
| **API (推薦)** | ⭐⭐⭐ 高 | 較高 | 生產環境、需要穩定輸出 |
| **CLI Wrapper** | ⭐⭐ 中 | 較低 | 開發測試、利用最新 Agent 功能 |

#### 配置範例 (`lantern.toml`)

```toml
[backend]
# 可選: "api" | "cli"
type = "api"

# API 後端設定
[backend.api]
provider = "anthropic"  # "anthropic" | "openai" | "google"
model = "claude-sonnet-4-20250514"
api_key_env = "ANTHROPIC_API_KEY"

# CLI 後端設定（備用）
[backend.cli]
command = "antigravity"
timeout_seconds = 300
fallback_to_api = true  # CLI 失敗時自動切換到 API
```

#### 錯誤處理策略

CLI Wrapper 必須處理以下情況：
1. **超時 (Timeout)**：超過設定時間無輸出，視為失敗
2. **格式變更**：輸出無法解析時，記錄原始輸出並標記錯誤
3. **降級策略**：若 `fallback_to_api = true`，自動切換到 API 後端

---

## 3. 文件規格 (Document Specifications)

### `lantern_plan.md`

> [!TIP]
> 增強版 `lantern_plan.md` 設計目標：讓使用者即使不完全理解程式碼，也能有效審查計畫。

```markdown
# Lantern Plan: [Project Name]

## 📋 Output Structure Preview

> 審查提示：以下是 Lantern 預計生成的文檔結構，請確認是否符合您的需求。

\`\`\`
.lantern/output/
├── en/
│   ├── top_down/
│   │   ├── OVERVIEW.md          # ✅ 專案願景
│   │   ├── ARCHITECTURE.md      # ✅ 系統架構
│   │   ├── GETTING_STARTED.md   # ✅ 新手指南
│   │   └── CONCEPTS.md          # ✅ 設計模式
│   └── bottom_up/
│       ├── src/
│       │   ├── auth.py.md       # 對應 src/auth.py
│       │   ├── models.py.md     # 對應 src/models.py
│       │   └── api/
│       │       └── routes.py.md
│       └── tests/
│           └── test_auth.py.md
└── zh-TW/                        # 若選擇繁體中文
    └── (同 en 結構)
\`\`\`

---

## 🎯 Learning Objectives

> 以下是 Architect 規劃的學習目標。請確認這些目標符合您的需求。

### Phase 1: Understand Authentication Flow

#### 🎯 Learning Objective
理解用戶身份如何被驗證，以及認證失敗時的處理流程。

#### 📁 Files
- [x] **Batch 001**: `auth.py`, `models.py`, `decorators.py`
  - 📊 **信心指數**: ⭐⭐⭐ (高)
  - 🔗 **依賴關係**: `decorators.py` → `auth.py` → `models.py`

- [x] **Batch 002**: `session_manager.py`
  - 📊 **信心指數**: ⭐⭐⭐ (高)

#### ❓ Key Questions (學完後應能回答)
- 用戶 token 如何生成與驗證？
- 認證失敗時返回什麼錯誤碼？
- 哪些 endpoint 需要認證？

---

### Phase 2: Understand API Request Lifecycle

#### 🎯 Learning Objective
理解一個 HTTP 請求如何被路由、驗證、處理並返回響應。

#### 📁 Files
- [x] **Batch 003**: `routes.py`, `validators.py`
  - 📊 **信心指數**: ⭐⭐ (中)
  - ⚠️ **低信心提示**: 不確定 `middleware.py` 是否應納入此 Batch

#### ❓ Key Questions (學完後應能回答)
- 請求的路由如何被匹配？
- 參數驗證失敗時如何處理？
- 中間件如何修改請求/響應？

## 🗺️ Dependency Graph

> 以下是 Architect 推斷的模組依賴關係。請檢查是否有遺漏或錯誤。

\`\`\`mermaid
graph TD
    subgraph Phase1["Phase 1: Authentication"]
        auth[auth.py]
        models[models.py]
        decorators[decorators.py]
        session[session_manager.py]

        decorators --> auth
        auth --> models
        session --> models
    end

    subgraph Phase2["Phase 2: API"]
        routes[routes.py]
        validators[validators.py]

        routes --> validators
        routes --> auth
    end

    style middleware fill:#ffcccc,stroke:#ff0000
    middleware[middleware.py<br/>⚠️ 未分類]
\`\`\`

---

## ⚠️ Low Confidence Decisions

> Architect 對以下決策信心較低，請特別審查：

1. **`middleware.py` 未分類**
   - 原因：無法從 import 語句判斷其歸屬
   - 建議：請告知此檔案應歸入哪個 Phase

2. **`utils.py` 暫時歸入 Phase 3**
   - 原因：此檔案被多個模組引用，作為 utility 單獨處理
```

### `.lantern/state.json` (跨批次記憶)

```json
{
  "last_completed_batch": "001",
  "global_logic_summary": "已定義 User 實體，使用 JWT 進行權限校驗...",
  "unresolved_questions": ["為什麼在 decorators.py 中有硬編碼的 ID？"],
  "language_preference": "zh-TW"
}
```

### `.lantern/sense/*.sense` (批次分析碎片)

每個 Batch 的分析結果會儲存為獨立的 `.sense` 檔案。

**格式**: JSON

**命名規則**: `batch_{N:03d}.sense`（例如 `batch_001.sense`）

**範例**:
```json
{
  "batch_id": "001",
  "files": ["auth.py", "models.py", "decorators.py"],
  "summary": "定義了 User 模型與 JWT 認證邏輯",
  "key_insights": [
    "使用 decorator @require_auth 進行權限檢查",
    "JWT token 儲存在 HTTP header"
  ],
  "questions": ["為什麼 user_id 硬編碼為 42？"]
}
```

---

## 4. CLI 命令規格 (CLI Commands)

### 使用模式

Lantern 支援兩種使用模式：

| 模式 | 命令 | 適用場景 |
| :--- | :--- | :--- |
| **簡易模式** | `lantern run` | 快速分析，使用預設設定 |
| **進階模式** | `lantern init` → `lantern plan` → `lantern run` | 需要審查/編輯計畫 |

### 簡易模式

```bash
# 最簡使用：當前目錄作為 repo，輸出至 .lantern/
lantern run

# 指定輸入 repo
lantern run --repo /path/to/repo

# 指定輸出位置
lantern run --output /path/to/output

# 完整範例
lantern run --repo ~/projects/my-app --output ~/docs/my-app-docs
```

### 進階模式

```bash
# Step 1: 初始化（生成 .lantern/ 目錄）
lantern init --repo /path/to/repo

# Step 2: 生成計畫（產出 lantern_plan.md 供審查）
lantern plan

# Step 3: 審查並編輯 lantern_plan.md 後執行
lantern run
```

### CLI 後端自動偵測

> [!NOTE]
> 執行時 Lantern 會自動偵測可用的 CLI 工具。

**偵測順序**（優先使用第一個找到的）：
1. `codex` (OpenAI Codex CLI)
2. `gemini` (Google Gemini CLI)
3. `claude` (Anthropic Claude CLI)
4. `antigravity` (Gemini Antigravity)

**手動指定**：
```bash
lantern run --backend claude
lantern run --backend gemini
```

**錯誤處理**：
- 若無任何 CLI 可用，顯示安裝指引並退出
- 若指定的 CLI 不存在，報錯並建議可用選項

### 配置檔優先順序

設定值的優先順序（高 → 低）：
1. **命令列參數**：`--backend`, `--output`, `--lang`
2. **專案設定檔**：`.lantern/lantern.toml`
3. **使用者設定檔**：`~/.config/lantern/lantern.toml`
4. **預設值**

---

## 5. 工作流程 (Workflow)

> [!IMPORTANT]
> **Human-in-the-loop 已納入 MVP**。在執行分析前,必須由使用者審查計畫。
>
> 原因：AI 規劃的路徑約有 20% 錯誤率。若初期路徑錯誤，後續執行將浪費成本。

1.  **初始化 (Init)**: 使用者輸入 Repo 連結與客製化 Prompt（排除不需學習的檔案）。
2.  **靜態掃描 (Static Scan)**: 使用 tree-sitter、grep 等工具收集依賴關係。
3.  **規劃 (Orchestration)**: Architect 基於靜態分析結果產出 `lantern_plan.md`。
4.  **人工審查 (Human Review)** ⭐:
    - 使用者檢視 `lantern_plan.md`
    - **審查重點**：
      - ✅ **輸出結構預覽**：確認產出的文檔結構符合預期
      - ✅ **分組合理性**：檢查各 Batch 的檔案分組是否合理
      - ✅ **低信心決策**：特別關注 `⚠️ Low Confidence Decisions` 區塊
      - ✅ **依賴圖正確性**：確認 Mermaid 圖中的模組關係無遺漏
    - **操作選項**：
      - ✅ **批准**: 開始執行分析
      - ❌ **拒絕**: Architect 重新生成計畫
      - ✏️ **編輯**: 直接修改 `lantern_plan.md`（勾選/取消 Batch）
5.  **執行 (Iterative Execution)**:
    - Runner 呼叫 CLI 工具（使用便宜模型，如 Gemini Flash）處理 Batch。
    - 將分析結果存入 `.lantern/sense/batch_{N}.sense`。
    - **同時生成 Bottom-up 文檔**：為每個檔案產生對應的 `.md`，存入 `.lantern/output/{lang}/bottom_up/`。
    - 更新 `.lantern/state.json` 的 `global_summary`。
    - 循環執行直至所有 Batch 完成。
6.  **合成 (Top-down Synthesis)**:
    - Synthesizer 讀取所有 `.sense` 片段與 bottom-up 文檔。
    - 呼叫高品質 LLM（Claude Sonnet, GPT-4o）生成高層次指南。
    - 產出 `.lantern/output/{lang}/top_down/` 下的多個文件：
      - `OVERVIEW.md`
      - `ARCHITECTURE.md`
      - `GETTING_STARTED.md`
      - `CONCEPTS.md`

---

## 6. 成本控制策略 (Cost Control)

> [!NOTE]
> Lantern 可能會對大型 Repo 產生高額 API 成本。透過分層模型選擇來優化成本。

### 模型選擇策略

| 階段 | 推薦模型 | 原因 | 估計成本/Repo |
| :--- | :--- | :--- | :--- |
| **靜態掃描** | 無需 LLM | 使用 tree-sitter, grep | $0 |
| **規劃 (Architect)** | Gemini Flash, Claude Haiku | 只需要結構化推理 | $0.10 - $0.50 |
| **批次分析 (Runner)** | Gemini Flash, Claude Haiku | 大量重複性分析 | $1 - $5 |
| **合成 (Synthesizer)** | Claude Sonnet, GPT-4o | 需要高品質母語轉譯 | $0.50 - $2 |

**總估計成本**: $1.60 - $7.50 per repository (中型專案)

**成本優化建議**:
- 允許使用者在 `lantern.toml` 中指定模型偏好
- 提供「快速模式」（全程使用 Gemini Flash）與「高品質模式」

---

## 7. 競品與差異分析 (Competitive Analysis)

| 工具 | 目標 | 與 Lantern 的差異 |
| :--- | :--- | :--- |
| **NotebookLM** | AI 文件問答 | 聊天式問答，無結構化輸出；需上傳雲端，企業環境可能禁止。 |
| **Aider / Cursor** | 協助編碼 | 側重於「改代碼」，而非「教你理解」。 |
| **Autodoc / Sphinx** | 文檔生成 | 依賴代碼註解，缺乏邏輯推理與架構導覽。 |
| **RepoMap** | 關係視覺化 | 只有地圖，沒有導遊。Lantern 提供「導遊式」的步進理解。 |

---

## 8. 未來擴充 (Roadmap)

- **Execution Trace Mode**: 透過 unit test 收集 call graph，實現動態分析。
- **Incremental Update**: 支援增量更新，當 Repository 變更時僅重新分析修改的檔案。
- **API Mode**: 除了 CLI 後端，提供直接調用 LLM API 的模式。
- **Memory Cross-talk**: 實作更強大的跨 Batch 邏輯關聯檢查。
- **Multi-language Support**: 擴展靜態分析支援更多語言（Go, Rust, Java）。
- **VSCode Extension**: 整合進度追蹤與可視化。
