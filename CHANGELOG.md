# Changelog

All notable changes to nous-core are documented in this file.

## [0.1.0] - 2026-04-20

### Added — Core library (`nous/`)
- **KnowledgeStore**: fact database with 4 atomic operations (`access` / `equal` / `greater` / `similar`). Supports numeric + string values. Reverse indices for O(1) property/concept lookup. Contradiction detection on conflicting high-confidence writes.
- **LanguageEngine**: JP/EN tokenizer with longest-match dictionary segmentation. Intent parser for 6 intent classes (`prove` / `solve` / `discover` / `learn` / `create` / `ask`). Pattern learning via KnowledgeStore for user-feedback-based intent customization.
- **BookShelf / Book / WritableBook**: JSON knowledge DBs with lazy loading. Fuzzy text search combining key-substring / query-substring / char 2-gram overlap. Cross-book search.
- **Curator**: bridges BookShelf ⇄ KnowledgeStore. `checkout` / `retrieve` / `best_match` / `return_all`.
- **DialogueManager**: multi-turn context. Reference resolution for demonstratives (それ/あれ/これ/etc.).
- **ResponseComposer**: Japanese response templates keyed by intent.
- **Brain**: top-level integrated entry point. Plugin-aware `ask()` pipeline.

### Added — Plugin system
- `Brain.register(plugin)` / `unregister` / `plugins()`.
- 6 duck-typed hook points: `before_parse` / `after_parse` / `before_search` / `after_search` / `before_compose` / `after_compose`.
- Plugins run in registration order; missing callbacks are skipped.

### Added — FastAPI server (`server/`)
- `GET /summary`, `GET /books`, `POST /books`, `POST /ask`, `DELETE /conversation`, `WS /chat`, `GET /`.
- Built-in HTML demo UI (chat + Book management + dashboard).
- Auto-loads any `data/books/*.json` at startup via lifespan context.
- Demo Books: `online_school` (オンラインスクール受講ガイド), `saas_manual` (SaaS利用マニュアル).

### Added — Security hardening
- Path-traversal guards: book names must match `[A-Za-z0-9_-]{1,64}`; writes resolved back inside `DATA_ROOT`.
- Input size limits: `NOUS_MAX_TEXT` (default 4000 chars), `NOUS_MAX_BOOK_BYTES` (default 1 MB), depth ≤ 5, keys ≤ 5000.
- XSS hardening: all user/model-provided strings rendered via `textContent` + DOM APIs. No `innerHTML` with untrusted data.
- Intent whitelist: response `intent` field clamped server-side.
- Optional API-key auth: `NOUS_API_KEY` env var protects mutating + `/ask` + `/chat` endpoints (constant-time compare).
- Default local bind (`127.0.0.1`) recommended in README.

### Added — Tests
- 107 pytest cases, all passing:
  - KnowledgeStore: 15
  - LanguageEngine: 15
  - BookShelf: 14
  - Curator: 10
  - Brain: 13
  - Plugin system: 17
  - Server E2E + security: 23
- `ruff`: clean.
- `mypy`: clean.

### Known limitations (deferred)
- `Brain` is a process-global instance; concurrent requests share `DialogueManager` state (QA天城 B1 finding). Session isolation needed before multi-tenant production.
- No persistent audit log of Q&A pairs (QA天城 B3 finding).
- Search is char n-gram based; synonym handling (e.g. お金/費用/学費) not yet built (天城 accuracy note). Intended as `nous-synonyms` plugin.
- HTML UI is a development console; Next.js front-end deferred to client-delivery phase.

### Project decisions locked on 2026-04-20
- Target: open-source cognitive engine library for LLM-free Japanese NLP applications.
- Additional products will ride on the plugin system: `nous-synonyms`, `nous-memory`, `nous-audit`, `nous-line`, `nous-slack`, `nous-voice`, `nous-ocr`, `nous-scheduler`.
