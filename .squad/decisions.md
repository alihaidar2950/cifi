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

### 2026-04-11: Documentation accuracy review — architecture docs
**By:** Ripley (Lead)
**What:** Reviewed and corrected HLD.md, DD.md, PLAN.md, NORTH_STAR.md
**Key corrections:**
- HLD.md: Fixed log source (not `$GITHUB_STEP_SUMMARY`), removed unimplemented api_post node, marked Claude/OpenAI/Ollama as Phase 2
- DD.md: Fixed action.yml inputs, Docker image reference, entrypoint pseudocode, provider BASE_URL, unimplemented provider status, SYSTEM_PROMPT template, output router reference, PR comment format, Tier 1 config table
- PLAN.md: Corrected provider implementation status, collapsed unimplemented providers in project structure diagram, removed "few-shot examples" from prompts.py description
- NORTH_STAR.md: Split multi-provider LLM success criteria into Phase 1 (GitHub Models) vs Phase 2 (Claude, OpenAI, Ollama)
- ARCHITECTURE.md: Reviewed — already accurate, no changes needed

---

### 2026-04-11: Documentation accuracy review — pipeline docs
**By:** Dallas (Core Dev)
**What:** Reviewed and corrected DATA_FLOW.md, LLM_INTEGRATION.md
**Key corrections:**
- DATA_FLOW.md: Fixed build_prompt() placement in sequence diagram (called inside analyze(), not directly from entrypoint); fixed preprocess() call signature (no explicit max_tokens arg)
- LLM_INTEGRATION.md: Renamed "Provider Selection Flow" → "analyze() — Call Flow"; added missing build_prompt(context) step before provider.analyze(prompt)

---

### 2026-04-11: Documentation accuracy review — DevOps and meta docs
**By:** Parker (DevOps)
**What:** Reviewed and corrected GITHUB_ACTION.md, RESUME.md, SQUAD_ADOPTION_PLAN.md
**Key corrections:**
- GITHUB_ACTION.md: Fixed ingest node params in execution flow diagram; added missing env: block to action.yml listing
- RESUME.md: Added CIFI project entry (was missing entirely)
- SQUAD_ADOPTION_PLAN.md: Fixed repo path (cifi), phase count (4 not 6), phase table labels, added Deferred rows for Infrastructure and Dashboard agents

---

### 2026-04-12: Test restructure — unit/ and integration/ separation
**By:** Lambert (Tester)
**What:** Moved all tests into tests/unit/ and tests/integration/. Removed hollow mock-theatre tests from test_action_entrypoint.py: collapsed 9 TestFormatComment tests to 1, removed TestFetchRunLogs class (2 tests), removed 2 hollow TestPostComment tests.
**Net change:** 12 tests removed, 61 remain
**Why:** Mock theatre tests verify that mocks work, not that the code works. 9 separate single-assertion tests for one pure function are noise.

---

### 2026-04-12: pyproject.toml and Makefile updated for test restructure
**By:** Parker (DevOps)
**What:** testpaths updated to tests/unit + tests/integration. Makefile test target now only runs unit by default. test-integration is explicit.
**Why:** Unit and integration tests have different requirements (GITHUB_TOKEN). Separating them prevents CI failures when token isn't set.

---

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
