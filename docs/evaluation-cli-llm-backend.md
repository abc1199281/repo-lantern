# 評估：支援 CLI LLM Backend（如 `codex exec "query"`）

## 現況分析

### 目前的 LangChain 耦合點

| 檔案 | 使用的 LangChain API | 耦合程度 |
|------|---------------------|----------|
| `llm/structured.py` | `ChatPromptTemplate`, `RunnableLambda`, `.with_structured_output()`, `.batch()` | **極高** |
| `llm/factory.py` | 直接回傳 ChatModel | **高** |
| `llm/openai.py` | `ChatOpenAI` | **高** |
| `llm/ollama.py` | `ChatOllama` | **高** |
| `llm/openrouter.py` | `ChatOpenAI` + base_url | **高** |
| `core/runner.py` | 透過 `StructuredAnalyzer` 間接使用 | **中** |
| `core/memory_manager.py` | `.invoke()`, `.content` | **中** |
| `utils/cost_tracker.py` | `.usage_metadata` | **低** |

### 消費者實際使用的 LLM 介面

整理所有呼叫端，LLM 真正被使用的操作只有三種：

```python
# 操作 1: 簡單文字生成（memory_manager.py）
response = llm.invoke(prompt_string)
text = response.content  # str

# 操作 2: 結構化輸出（structured.py）
structured_llm = llm.with_structured_output(json_schema)
result = structured_llm.invoke(prompt_value)  # dict or BaseModel

# 操作 3: 批次結構化輸出（structured.py）
results = chain.batch(items)  # list[dict or BaseModel]
```

附帶讀取（非必要但有用）：
```python
response.usage_metadata  # {"input_tokens": N, "output_tokens": M}
```

---

## 方案比較

### 方案 A：把 CLI 包裝成 LangChain ChatModel

概念：建立一個繼承 `BaseChatModel` 的類別，底層用 `subprocess` 呼叫 CLI。

```python
class CLIChatModel(BaseChatModel):
    command: list[str] = ["codex", "exec"]

    def _generate(self, messages, stop=None, **kwargs):
        prompt = self._format_messages(messages)
        result = subprocess.run([*self.command, prompt], capture_output=True)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=result.stdout))])

    def with_structured_output(self, schema):
        # 問題：CLI 工具通常不支援 structured output
        # 必須自己在 prompt 裡塞 schema 說明，然後 parse JSON
        ...
```

**優點：**
- 改動最小，只需新增一個 provider 檔案 + factory 分支
- 現有 `structured.py`、`runner.py` 完全不用動

**缺點：**
- `with_structured_output()` 很難正確實作。LangChain 的這個方法依賴 provider 原生的 function calling / JSON mode，CLI 工具不支援
- 必須繼承 `BaseChatModel`，綁定大量 LangChain 內部抽象（`BaseMessage`, `ChatResult`, `ChatGeneration` 等）
- `.batch()` 的語義變成 N 次 subprocess 呼叫，效率差且難以控制
- 測試困難：需要 mock LangChain 的完整物件圖
- 未來每換一個 CLI 工具（codex → 其他），都要再重寫一個 ChatModel 子類

**結論：不推薦。** 表面改動小，但 `with_structured_output` 的實作問題是根本性的，會導致大量 workaround 代碼。

---

### 方案 B：Backend 抽象層（推薦）

概念：在 `llm/` 層引入一個 `Backend` Protocol，所有消費者透過 Backend 操作，不再直接碰 LangChain。

#### 核心介面設計

```python
# llm/backend.py

from typing import Protocol, Any, runtime_checkable

@runtime_checkable
class LLMResponse(Protocol):
    """LLM 回應的最小契約"""
    content: str
    usage_metadata: dict[str, int] | None  # {"input_tokens": N, "output_tokens": M}

@runtime_checkable
class Backend(Protocol):
    """LLM Backend 的最小介面"""

    def invoke(self, prompt: str) -> LLMResponse:
        """簡單文字生成"""
        ...

    def invoke_structured(self, prompt: str, json_schema: dict[str, Any]) -> dict[str, Any]:
        """結構化輸出，回傳符合 schema 的 dict"""
        ...

    def batch_invoke_structured(
        self, items: list[dict[str, str]], json_schema: dict[str, Any], prompts: dict[str, str]
    ) -> list[dict[str, Any]]:
        """批次結構化輸出"""
        ...

    @property
    def model_name(self) -> str:
        """模型名稱，用於 cost tracking"""
        ...
```

#### 為什麼是這三個方法？

對照現有消費者的使用：

| 消費者 | 現在用的 API | 對應 Backend 方法 |
|--------|-------------|-------------------|
| `memory_manager.py` | `llm.invoke(str)` → `.content` | `backend.invoke(str)` |
| `structured.py` | `llm.with_structured_output(schema).invoke()` | `backend.invoke_structured()` |
| `structured.py` | `chain.batch(items)` | `backend.batch_invoke_structured()` |
| `cost_tracker.py` | `response.usage_metadata` | 由 `LLMResponse` 攜帶 |

#### LangChain 實作

```python
# llm/backends/langchain_backend.py

class LangChainBackend:
    """把現有的 LangChain 邏輯全部包在這裡"""

    def __init__(self, chat_model: Any):
        self._llm = chat_model

    def invoke(self, prompt: str) -> LLMResponse:
        response = self._llm.invoke(prompt)
        return SimpleResponse(
            content=self._extract_content(response),
            usage_metadata=getattr(response, "usage_metadata", None),
        )

    def invoke_structured(self, prompt: str, json_schema: dict) -> dict:
        structured_llm = self._llm.with_structured_output(json_schema)
        return structured_llm.invoke(prompt)

    def batch_invoke_structured(self, items, json_schema, prompts) -> list[dict]:
        # 把現在 structured.py 的 create_chain 邏輯搬進來
        prompt_tpl = ChatPromptTemplate.from_messages(
            [("system", prompts["system"]), ("user", prompts["user"])]
        )
        structured_llm = self._llm.with_structured_output(json_schema)

        def _runner(inp):
            if isinstance(inp, dict):
                prompt_value = prompt_tpl.format_prompt(**inp)
                return structured_llm.invoke(prompt_value)
            return structured_llm.invoke(inp)

        chain = RunnableLambda(lambda x: _runner(x))
        return chain.batch(items)

    @property
    def model_name(self) -> str:
        return getattr(self._llm, "model_name", "unknown")
```

重點：**所有 LangChain import 集中在這一個檔案**。`ChatPromptTemplate`、`RunnableLambda`、`with_structured_output` 全部不外洩。

#### CLI 實作

```python
# llm/backends/cli_backend.py

import subprocess
import json

class CLIBackend:
    """透過 CLI 工具呼叫 LLM"""

    def __init__(self, command: list[str], model: str = "cli"):
        self._command = command  # e.g. ["codex", "exec"]
        self._model = model

    def invoke(self, prompt: str) -> LLMResponse:
        result = subprocess.run(
            [*self._command, prompt],
            capture_output=True, text=True, check=True
        )
        return SimpleResponse(content=result.stdout.strip(), usage_metadata=None)

    def invoke_structured(self, prompt: str, json_schema: dict) -> dict:
        # 在 prompt 中嵌入 schema 要求，要求回傳 JSON
        structured_prompt = (
            f"{prompt}\n\n"
            f"You MUST respond with a JSON object matching this schema:\n"
            f"```json\n{json.dumps(json_schema, indent=2)}\n```\n"
            f"Output ONLY the JSON, no other text."
        )
        response = self.invoke(structured_prompt)
        return json.loads(_extract_json(response.content))

    def batch_invoke_structured(self, items, json_schema, prompts) -> list[dict]:
        # CLI 不支援原生 batch，逐一呼叫
        results = []
        for item in items:
            prompt_text = prompts["system"] + "\n" + prompts["user"].format(**item)
            results.append(self.invoke_structured(prompt_text, json_schema))
        return results

    @property
    def model_name(self) -> str:
        return self._model
```

#### 改動範圍一覽

```
修改的檔案：
  llm/factory.py          → 回傳 Backend 而非 ChatModel
  llm/structured.py       → 用 backend.batch_invoke_structured() 取代 chain
  core/runner.py           → 型別改為 Backend（介面不變所以改動很小）
  core/memory_manager.py   → 用 backend.invoke() 取代 llm.invoke()
  config/models.py         → BackendConfig.type 新增 "cli" 選項

新增的檔案：
  llm/backend.py           → Protocol 定義
  llm/backends/             → 目錄
  llm/backends/__init__.py
  llm/backends/langchain_backend.py  → 包裝現有 LangChain 邏輯
  llm/backends/cli_backend.py        → CLI 實作

不需要改的檔案：
  llm/openai.py            → 被 langchain_backend.py 內部使用，不變
  llm/ollama.py            → 同上
  llm/openrouter.py        → 同上
  core/architect.py        → 不碰 LLM
  core/synthesizer.py      → 不碰 LLM
  static_analysis/*        → 不碰 LLM
  utils/cost_tracker.py    → 改讀 LLMResponse.usage_metadata（改動極小）
```

#### Factory 改動

```python
# llm/factory.py（改動後）

def create_backend(config: LanternConfig) -> Backend:
    backend_config = config.backend

    if backend_config.type == "cli":
        return CLIBackend(
            command=shlex.split(backend_config.cli_command or "codex exec"),
            model=backend_config.cli_model_name or "cli",
        )

    # LangChain 路徑：先建立 ChatModel，再包裝成 Backend
    if backend_config.type == "ollama":
        chat_model = create_ollama_llm(...)
    elif backend_config.type == "openai":
        chat_model = create_openai_chat(...)
    elif backend_config.type == "openrouter":
        chat_model = create_openrouter_chat(...)
    else:
        raise ValueError(...)

    return LangChainBackend(chat_model)
```

#### Config 新增

```python
# config/models.py 新增欄位

class BackendConfig(BaseModel):
    type: Literal["api", "ollama", "openai", "openrouter", "cli"] = "ollama"

    # CLI backend options
    cli_command: str | None = Field(
        default=None,
        description="CLI command to execute (e.g., 'codex exec')",
    )
    cli_model_name: str | None = Field(
        default=None,
        description="Model name for display/cost tracking",
    )
```

#### TOML 設定範例

```toml
[backend]
type = "cli"
cli_command = "codex exec"
cli_model_name = "codex-default"
```

---

## 關鍵設計決策

### 1. Structured Output 在 CLI 端怎麼處理？

CLI 工具不支援 LangChain 的 `with_structured_output()`（那依賴 provider 原生 function calling）。

解法是 **prompt-based structured output**：在 prompt 尾端插入 JSON schema 要求，讓模型以純文字回傳 JSON，然後在 `CLIBackend` 內 parse。

這已經是 `structured.py` 中 `_extract_json()` 在做的事——它本來就處理了模型回傳非嚴格 JSON 的情況。可以直接復用。

### 2. batch 在 CLI 端怎麼處理？

CLI 沒有原生 batch 支援。`CLIBackend.batch_invoke_structured()` 逐一呼叫即可。

未來可以加 `concurrent.futures.ThreadPoolExecutor` 做並行，但不是第一步。

### 3. 不同 API provider 的改動量

引入 Backend 後，**新增 API provider 的步驟不變**：

1. 寫一個 `create_xxx_chat()` 函式回傳 LangChain ChatModel（跟現在一樣）
2. 在 `factory.py` 加一個 `elif` 分支
3. 用 `LangChainBackend(chat_model)` 包裝

差異只在 factory 現在回傳的是 `Backend` 而非裸 ChatModel。**現有的 `openai.py`、`ollama.py`、`openrouter.py` 完全不需要改。**

### 4. usage_metadata / cost tracking

`LLMResponse` Protocol 包含 `usage_metadata`。

- `LangChainBackend`: 從 LangChain response 直接轉傳
- `CLIBackend`: 回傳 `None`（CLI 工具通常不提供 token 計數）
- `cost_tracker.py` 已經用 `getattr(response, "usage_metadata", None)` 防禦性讀取，幾乎不用改

---

## 實作順序建議

```
Phase 1: 引入 Backend Protocol（不破壞現有功能）
  1. 新增 llm/backend.py（Protocol 定義 + SimpleResponse dataclass）
  2. 新增 llm/backends/langchain_backend.py
  3. 修改 llm/factory.py → create_backend() 回傳 LangChainBackend
  4. 修改 llm/structured.py → StructuredAnalyzer 接受 Backend
  5. 修改 core/runner.py → 使用 Backend
  6. 修改 core/memory_manager.py → 使用 Backend
  7. 跑測試確認不 break

Phase 2: 加入 CLI Backend
  1. 新增 llm/backends/cli_backend.py
  2. config/models.py 加 cli 選項
  3. factory.py 加 cli 分支
  4. 寫 CLI backend 的整合測試

Phase 3: 進階（可選）
  1. batch 並行化（ThreadPoolExecutor）
  2. retry / timeout 機制
  3. streaming 支援（如果未來需要）
```

---

## 預期的檔案結構

```
src/lantern_cli/
├── llm/
│   ├── backend.py              ← NEW: Protocol + SimpleResponse
│   ├── backends/
│   │   ├── __init__.py         ← NEW
│   │   ├── langchain_backend.py ← NEW: 包裝現有 LangChain
│   │   └── cli_backend.py      ← NEW: CLI 實作
│   ├── factory.py              ← MODIFIED: 回傳 Backend
│   ├── structured.py           ← MODIFIED: 用 Backend
│   ├── openai.py               ← UNCHANGED
│   ├── ollama.py               ← UNCHANGED
│   └── openrouter.py           ← UNCHANGED
├── core/
│   ├── runner.py               ← MODIFIED（小改）
│   ├── memory_manager.py       ← MODIFIED（小改）
│   └── ...
└── config/
    └── models.py               ← MODIFIED（加 cli 欄位）
```

---

## 結論

**推薦方案 B（Backend 抽象層）。**

理由：
1. **CLI 的 structured output 問題只能在 Backend 層解決**——方案 A 強行塞進 LangChain 的 `with_structured_output()` 介面會很彆扭
2. **現有 provider 檔案（openai.py 等）完全不需要改**，只是被 `LangChainBackend` 包一層
3. **未來新增 provider 的流程幾乎不變**（寫 factory → LangChainBackend 包裝）
4. **Backend Protocol 只有 3 個方法**，介面極簡，不會過度抽象
5. **測試變簡單**——可以直接 mock Backend，不用 mock LangChain 整套物件
