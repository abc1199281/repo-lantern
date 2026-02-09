# Lantern CLI 開發任務清單 (TDD/Spec-Driven)

> **開發策略**: Test-Driven Development + Spec-Driven
>
> 每個模組按照以下順序開發：
> 1. 閱讀 Spec 中的對應章節
> 2. 撰寫測試 (pytest)
> 3. 實作程式碼直到測試通過
> 4. 重構優化
> 5. **記錄狀態**：每個 batch 完成後記錄 ✅ 成功 或 ❌ 失敗 + 原因

---

## 📊 進度總覽

| Phase | 狀態 | 完成時間 | Commit |
| :--- | :--- | :--- | :--- |
| Phase 0.1 | ✅ 完成 | 2026-02-09 | `2b7a764` |
| Phase 0.2 | ✅ 完成 | 2026-02-09 | (pending) |
| Phase 1 | 🔄 進行中 | - | - |

---

## Phase 0: 專案骨架 (Project Skeleton)

- [x] **0.1 初始化專案結構** ✅ 2026-02-09
  - [x] 使用 Poetry 初始化專案
  - [x] 設定 `pyproject.toml`
  - [x] 建立基本目錄結構：
    ```
    lantern/
    ├── cli/              # CLI 入口
    ├── core/             # 核心邏輯
    │   ├── architect.py
    │   ├── runner.py
    │   └── synthesizer.py
    ├── backends/         # 後端 Adapters
    │   ├── base.py       # BackendAdapter ABC
    │   ├── codex.py
    │   ├── gemini.py
    │   └── claude.py
    ├── static_analysis/  # 靜態分析
    │   ├── python.py
    │   ├── javascript.py
    │   └── generic.py
    ├── config/           # 配置管理
    │   └── settings.py
    └── utils/
    tests/
    ├── unit/
    ├── integration/
    └── fixtures/
    ```
  - [x] 設定 pytest, black, ruff, mypy
  - **狀態**: ✅ 成功 - 所有目錄和配置檔案已建立，CLI 可正常運行
  - **Commit**: `2b7a764`

- [x] **0.2 CI/CD 基礎** ✅ 2026-02-09
  - [x] GitHub Actions: lint + test
  - [x] Pre-commit hooks
  - **狀態**: ✅ 成功 - GitHub Actions workflow 已建立，pre-commit hooks 已安裝並測試
  - **Commit**: (pending push)

---

## Phase 1: 配置系統 (Configuration)

> **Spec 參考**: Section 4.4 配置檔優先順序

- [ ] **1.1 配置模型 (Pydantic)**
  - [ ] 定義 `LanternConfig` dataclass/Pydantic model
  - [ ] 測試：驗證配置的預設值
  - [ ] 測試：驗證配置的型別檢查

- [ ] **1.2 配置載入**
  - [ ] 實作 `lantern.toml` 解析 (使用 `tomllib`)
  - [ ] 測試：載入專案設定檔
  - [ ] 測試：載入使用者設定檔
  - [ ] 測試：配置合併優先順序

- [ ] **1.3 檔案過濾配置**
  - [ ] 實作 `[filter]` 區塊解析
  - [ ] 測試：exclude 規則解析
  - [ ] 測試：include 覆蓋 exclude

---

## Phase 2: 靜態分析模組 (Static Analysis)

> **Spec 參考**: Section 2.A 靜態分析輔助

- [ ] **2.1 通用靜態分析 (ripgrep wrapper)**
  - [ ] 實作 `grep_imports()` 函數
  - [ ] 測試：提取 Python import 語句
  - [ ] 測試：提取 JS/TS import/require 語句

- [ ] **2.2 Python 分析器**
  - [ ] 使用 `ast` 模組解析 import
  - [ ] 測試：解析標準 import
  - [ ] 測試：解析 from...import
  - [ ] 測試：解析相對 import

- [ ] **2.3 JavaScript/TypeScript 分析器**
  - [ ] 整合 `tree-sitter` (可選)
  - [ ] 測試：解析 ES6 import
  - [ ] 測試：解析 CommonJS require

- [ ] **2.4 依賴圖建構**
  - [ ] 實作 `DependencyGraph` 類別
  - [ ] 測試：建立依賴樹
  - [ ] 測試：偵測循環依賴
  - [ ] 測試：計算模組層級

- [ ] **2.5 檔案過濾器**
  - [ ] 實作 `.gitignore` 解析
  - [ ] 實作預設排除規則
  - [ ] 測試：過濾 node_modules
  - [ ] 測試：include 覆蓋 exclude

---

## Phase 3: 後端抽象層 (Backend Adapters)

> **Spec 參考**: Section 2.D 後端抽象層

- [ ] **3.1 Adapter 介面**
  - [ ] 定義 `BackendAdapter` ABC
  - [ ] 定義 `AnalysisResult` dataclass
  - [ ] 測試：介面合約驗證

- [ ] **3.2 CLI 後端自動偵測**
  - [ ] 實作 `detect_cli()` 函數
  - [ ] 測試：偵測順序 (codex → gemini → claude)
  - [ ] 測試：全部不存在時拋出錯誤

- [ ] **3.3 Codex Adapter**
  - [ ] 實作 `CodexAdapter`
  - [ ] 測試：`health_check()`
  - [ ] 測試：`analyze_batch()` 基本呼叫
  - [ ] 測試：超時處理

- [ ] **3.4 Gemini Adapter**
  - [ ] 實作 `GeminiAdapter`
  - [ ] 測試：`health_check()`
  - [ ] 測試：`analyze_batch()` 基本呼叫

- [ ] **3.5 Claude Adapter**
  - [ ] 實作 `ClaudeAdapter`
  - [ ] 測試：`health_check()`
  - [ ] 測試：`analyze_batch()` 基本呼叫

- [ ] **3.6 API 後端 (未來)**
  - [ ] 預留 `APIAdapter` 介面

---

## Phase 4: Architect 模組 (規劃)

> **Spec 參考**: Section 2.A 建築師代理

- [ ] **4.1 Plan 生成**
  - [ ] 實作 `Architect.generate_plan()`
  - [ ] 測試：產出符合 `lantern_plan.md` 格式
  - [ ] 測試：Phase/Batch 結構正確
  - [ ] 測試：每個 Batch ≤ 3 個檔案

- [ ] **4.2 Learning Objectives 生成**
  - [ ] 實作學習目標提取
  - [ ] 測試：每個 Phase 有 Learning Objective
  - [ ] 測試：Key Questions 生成

- [ ] **4.3 信心指數評估**
  - [ ] 實作信心計算邏輯
  - [ ] 測試：靜態分析完整時信心高
  - [ ] 測試：無法判斷依賴時信心低

- [ ] **4.4 Dependency Graph 生成**
  - [ ] 實作 Mermaid 圖生成
  - [ ] 測試：圖格式正確
  - [ ] 測試：標記未分類模組

---

## Phase 5: Runner 模組 (執行)

> **Spec 參考**: Section 2.B 執行協調員

- [ ] **5.1 State 管理**
  - [ ] 實作 `StateManager` 類別
  - [ ] 實作 `.lantern/state.json` 讀寫
  - [ ] 測試：狀態持久化
  - [ ] 測試：狀態更新

- [ ] **5.2 斷點續傳**
  - [ ] 實作 resume 邏輯
  - [ ] 測試：跳過已完成 Batch
  - [ ] 測試：從失敗 Batch 繼續

- [ ] **5.3 Temporal RAG**
  - [ ] 實作 `global_summary` 注入
  - [ ] 測試：Batch N 包含 N-1 的摘要
  - [ ] 測試：摘要長度控制

- [ ] **5.4 Batch 執行器**
  - [ ] 實作 `run_batch()`
  - [ ] 測試：呼叫 Backend Adapter
  - [ ] 測試：儲存 `.sense` 檔案
  - [ ] 測試：超時處理

- [ ] **5.5 Bottom-up 文檔生成**
  - [ ] 實作即時 `.md` 生成
  - [ ] 測試：目錄結構鏡像
  - [ ] 測試：文檔格式正確

- [ ] **5.6 Watchdog**
  - [ ] 實作超時監控
  - [ ] 實作中斷處理
  - [ ] 測試：超時後狀態保存

---

## Phase 6: Synthesizer 模組 (合成)

> **Spec 參考**: Section 2.C 合成器

- [ ] **6.1 `.sense` 檔案讀取**
  - [ ] 實作 `load_sense_files()`
  - [ ] 測試：解析所有 `.sense`
  - [ ] 測試：處理損壞的 `.sense`

- [ ] **6.2 Top-down 文檔生成**
  - [ ] 實作 `generate_overview()`
  - [ ] 實作 `generate_architecture()`
  - [ ] 實作 `generate_concepts()`
  - [ ] 實作 `generate_flows()`
  - [ ] 實作 `generate_getting_started()`
  - [ ] 測試：各文檔格式正確

- [ ] **6.3 Mermaid 圖表嵌入**
  - [ ] 實作流程圖生成
  - [ ] 測試：Sequence Diagram 語法正確
  - [ ] 測試：Architecture Diagram 語法正確

- [ ] **6.4 多語言支援**
  - [ ] 實作語言切換
  - [ ] 測試：輸出至正確的語言目錄

---

## Phase 7: CLI 入口 (Command Line Interface)

> **Spec 參考**: Section 4 CLI 命令規格

- [ ] **7.1 CLI 框架設定**
  - [ ] 使用 Click/Typer 建立 CLI
  - [ ] 測試：help 訊息正確

- [ ] **7.2 `lantern init`**
  - [ ] 實作 init 命令
  - [ ] 測試：建立 `.lantern/` 目錄
  - [ ] 測試：`--repo` 參數

- [ ] **7.3 `lantern plan`**
  - [ ] 實作 plan 命令
  - [ ] 測試：呼叫 Architect
  - [ ] 測試：產出 `lantern_plan.md`

- [ ] **7.4 `lantern run`**
  - [ ] 實作 run 命令 (簡易模式)
  - [ ] 測試：自動偵測 CLI 後端
  - [ ] 測試：完整執行流程

- [ ] **7.5 命令列參數**
  - [ ] `--repo`, `--output`, `--backend`, `--lang`
  - [ ] 測試：參數覆蓋配置檔

---

## Phase 8: 整合測試 (Integration Tests)

- [ ] **8.1 E2E 簡易模式**
  - [ ] 測試：小型 Python 專案從頭到尾
  - [ ] 驗證產出結構正確

- [ ] **8.2 E2E 進階模式**
  - [ ] 測試：init → plan → (人工審查) → run
  - [ ] 驗證中斷續傳

- [ ] **8.3 效能基準**
  - [ ] 測試：中型專案 (50 檔案) 執行時間
  - [ ] 測試：API 成本估算

---

## Phase 9: 文檔與發布

- [ ] **9.1 使用者文檔**
  - [ ] 完善 README.md 的安裝說明
  - [ ] 建立 `docs/` 使用者指南

- [ ] **9.2 發布**
  - [ ] 設定 PyPI 發布流程
  - [ ] 建立 `lantern-cli` 套件

---

## 開發優先順序建議

| 優先級 | 模組 | 原因 |
| :--- | :--- | :--- |
| P0 | Phase 0, 1 | 專案骨架與配置是基礎 |
| P0 | Phase 3 | 後端抽象層決定整體架構 |
| P1 | Phase 2 | 靜態分析是 Architect 的輸入 |
| P1 | Phase 4 | Architect 是核心規劃模組 |
| P2 | Phase 5 | Runner 依賴 Architect 與 Backend |
| P2 | Phase 7 | CLI 依賴所有核心模組 |
| P3 | Phase 6 | Synthesizer 是最後執行的 |
| P3 | Phase 8, 9 | 整合測試與發布 |

---

## 技術棧

| 類別 | 選擇 | 備註 |
| :--- | :--- | :--- |
| **套件管理** | Poetry | 或 uv |
| **CLI 框架** | Typer | 基於 Click，型別提示友好 |
| **配置解析** | tomllib + Pydantic | Python 3.11+ 內建 TOML |
| **測試框架** | pytest + pytest-cov | |
| **靜態分析** | ast (Python), ripgrep | tree-sitter 可選 |
| **型別檢查** | mypy | |
| **格式化** | black + ruff | |
