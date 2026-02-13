# Agent Rules

## Backend / Vendor Boundary

- Only LLM provider/vendor integration code may live in vendor/backend files (for example: `src/lantern_cli/backends/*.py`).
- Keep provider-specific concerns there only:
  - SDK/client construction
  - authentication/env wiring
  - request/response transport adaptation
- Do not place product/business orchestration logic in vendor/backend files.
- Put orchestration and domain logic in core/llm layers (for example: `src/lantern_cli/core/*`, `src/lantern_cli/llm/*`).

