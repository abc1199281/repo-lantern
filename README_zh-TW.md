# Lantern

> **照亮陌生的程式碼庫。**

[English](README.md) | [繁體中文]

![Lantern Hero Image](assets/lantern.jpg)

**Lantern 是你的 CLI 導師，將複雜的 Repository 轉化為循序漸進的敘事流程。**

透過 AI 引導的架構掃描、規劃好的學習路徑以及人類可讀的指南，更快速地理解程式碼庫。

**說你的語言**：邏輯已經夠複雜了。Lantern 使用你的母語（中文、日文、西班牙文等）解釋程式碼，同時保持技術術語的精確性。

---

# 為什麼需要 Lantern

理解一個陌生的程式碼庫非常困難。

你通常會遇到：
* 不知道該從哪個檔案開始看起。
* 文件過時或根本不存在。
* 隱藏的系統架構依賴關係。
* 需要閱讀數十個檔案才能理解一個核心概念。

大多數 AI 工具幫助你：
* 寫程式碼 (Write code)。
* 重構程式碼 (Refactor code)。

**Lantern 的目標截然不同：**
> Lantern 幫助你「理解」(Understand) 程式碼。

---

# Lantern 的功能

Lantern 遵循一套結構化的「認知優先」工作流：

1. **掃描 (Scan)**：繪製專案結構與依賴關係圖。
2. **區塊化 (Chunk)**：將分析拆解為易於管理的「小批次」(1-3 個檔案)。
3. **循序漸進 (Step-by-step)**：帶領你一個接一個地理解核心模組。
4. **合成 (Synthesize)**：產生具備 Bottom-up（檔案級別）與 Top-down（架構級別）視角的人類可讀文檔。

---

# Lantern 運作流程

![How Lantern works](assets/latern-2.jpg)

Lantern 採用分階段的教學法：

```bash
Init (輸入 Repo 連結)
   ↓
Static Scan (分析檔案依賴)
   ↓
Orchestration (生成分析計畫 lantern_plan.md)
   ↓
Execution (循環執行批次分析)
   ↓
Synthesis (產出高品質高層次指南)
```

---

# 核心概念

Lantern 的設計基於心理學原則：

### 區塊化 (Chunking - 米勒定律)
我們嚴格限制每個分析批次僅包含約 3 個相關檔案，以防止大腦產生資訊過載。

### 鷹架效應 (Scaffolding)
透過先行生成計畫並允許人工審查，我們為理解複雜系統搭建了穩固的階梯。

### 人類優先輸出 (Human-First Output)
最終產出是專為人類閱讀設計，而非機器消耗，重點在於解釋「為什麼」與「如何運作」，而不僅僅是「做了什麼」。

---

# 快速上手

## 安裝

```bash
pip install lantern-cli
```

## 基本用法

1. **初始化**：將 Lantern 指向一個 Repository。
   ```bash
   lantern init <repo_url_or_path>
   ```

2. **規劃**：生成分析編排計畫。
   ```bash
   lantern plan
   ```

3. **執行**：開始循序漸進的分析。
   ```bash
   lantern run
   ```

---

# 範例輸出

```markdown
# Phase 2: API Layer

API 層是使用 FastAPI 構建的。

認證流程：
用戶端 → 中間件 → JWT 驗證 → 路由處理程式

關鍵洞察：
業務邏輯已與 HTTP 傳輸層分離。
```

---

# 設定

## 語言設定

你可以設定偏好的輸出語言（如繁體中文、日文），進一步降低認知門檻。

**方法 A：命令列參數**
```bash
lantern run --lang zh-TW
```

**方法 B：設定檔 (`lantern.toml`)**
```toml
[lantern]
language = "zh-TW"
```

---

# 支援的代理 (Agents)

Lantern 驅動你喜愛的 CLI Agents：
* Claude Code
* Gemini CLI (Antigravity)
* 開源本地執行器 (Local Runners)

---

# 發展藍圖 (Roadmap)

- [ ] **互動式測驗模式**：在每個階段結束後測驗你的理解程度。
- [ ] **視覺化鷹架**：使用 Mermaid.js 自動生成架構圖。
- [ ] **跨批次推論**：加強跨批次邊界的邏輯關聯分析。
- [ ] **多語言靜態分析支援**：擴展至 Go, Rust, 與 Java。
- [ ] **VSCode 延伸插件**：整合進度追蹤與可視化。

---

# 參與貢獻

歡迎提交 PR！幫助我們打造理解程式碼的終極工具。

---

# 授權協定

MIT
