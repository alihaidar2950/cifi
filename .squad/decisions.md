# Squad Decisions

## Active Decisions

### 2026-04-11: Vectorization vs. Token-Budget in preprocessor.py
**By:** Ripley (Lead)
**Verdict:** Not warranted for Phase 1

**Reasoning:**
- Phase 1 runs as a stateless GitHub Action inside Docker — no persistent storage, no retrieval index, no inter-run state. A vector DB has nothing to persist to.
- LLM context windows (32K–128K tokens) comfortably exceed real-world CI log sizes. The current 8,000-token budget with structured priority allocation (error region 40%, stack trace 20%, source 25%, diff 10%, deps 5%) is deliberately conservative and can be raised without architectural change.
- The preprocessor already performs semantic extraction: `_extract_error_region`, `_extract_stack_trace`, and `_extract_test_failures` locate the high-signal content deterministically. This achieves the same selection goal as vector retrieval without embedding overhead or dependency cost.
- Vectorization introduces a runtime dependency (embedding model + vector DB client), latency (embed → index → query), and operational complexity — all net negatives for a zero-infrastructure Action.
- YAGNI: no phase in the current plan introduces a vector DB. Phase 3 adds PostgreSQL for history/pattern detection, not RAG.

**Conditions for revisit:**
- Logs routinely exceed the model's full context window (e.g., monorepo builds producing 500K+ character logs where even error-region extraction doesn't fit). Evaluate sliding-window chunking (not a vector DB — just multi-pass summarization).
- Phase 3 introduces pattern-detection needing semantic similarity across historical failures. At that point, pgvector on the existing PostgreSQL instance may be appropriate — scoped to cross-run pattern matching, not per-run log retrieval.
- A future LLM integration requires retrieval-augmented grounding. Evaluate only if explicitly planned.

---

### 2026-04-11: preprocessor.py cleanup
**By:** Dallas (Core Dev)
**What:** Deduplicated `_ERROR_MARKERS` list (24 → 18 entries); removed vestigial `combined` alias
**Why:** Dead code cleanup — case variants were redundant given case-insensitive matching; `combined` alias had no consumers

---

### 2026-04-11: preprocessor.py test coverage expansion
**By:** Lambert (Tester)
**What:** Added 8 new test cases to `tests/test_preprocessor.py`
**Coverage gaps closed:** `_truncate_to_budget`, token budget enforcement, PR metadata passthrough, empty `source_files`, stack trace extraction, error region context window, no-error fallback, case-insensitive marker matching
**Result:** 16/16 tests passing

---

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
