# Dallas — History

## Project Context

CIFI (CI Failure Intelligence) — AI-powered CI failure analysis agent.
- **User:** Ali
- **Stack:** Python, Pydantic, pytest, FastAPI
- **Current Phase:** Phase 1 — Core Engine
- **Core package:** `cifi/` — log preprocessor, LLM analyzer, schemas
- **Key principle:** LLM-powered analysis with multi-provider support, structured prompting
- **Output:** Always JSON, validated against Pydantic schemas

## Learnings

- [2026-04-11] Cleaned up preprocessor.py: deduplicated _ERROR_MARKERS, removed vestigial combined variable
