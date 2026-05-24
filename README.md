# nous-core

**A Japanese-language cognitive engine that answers from a curated knowledge base — with zero runtime LLM dependency.**

Most "AI chat" products today are a prompt-engineering layer over a remote LLM. That introduces three structural problems: per-token cost, hallucination on anything outside the training data, and external data egress. `nous-core` takes the opposite approach — a small, deterministic engine that parses intent, looks up answers in versioned "Books" (JSON), and returns a traceable response. No tokens, no external API calls, no hallucinated facts.

This is a sanitized public version of the engine powering several in-production AI products.

---

## Why this exists

There is a class of business AI use cases where an LLM is the wrong tool:

- **Customer support bots** for products with stable, finite knowledge (manuals, FAQs, policy docs)
- **Internal knowledge assistants** where outbound data egress is not acceptable
- **High-call-volume systems** where per-request token cost destroys margins
- **Regulated domains** where every answer must be auditable back to a source document

For these, you want a system that says **"I don't know"** instead of inventing an answer, that costs zero at runtime, and that can be traced from input to output. `nous-core` is built for exactly that.

| Axis | nous-core | LLM-based assistant |
|---|---|---|
| Truthfulness | Returns `used_fallback` when no source matches — never invents | Hallucinates plausibly |
| Runtime cost | Zero (no API calls) | Per-token billing |
| Data residency | Fully on-prem capable | Sent to vendor |
| Auditability | Full trace via `Response.trace()` | Black box |
| Domain customization | Add a Book (JSON), reload | Requires RAG + embeddings + retrieval tuning |

---

## How it works

```
        User query (JP/EN)
              │
              ▼
   ┌──────────────────────┐
   │  LanguageEngine      │   tokenize · normalize · classify intent
   └──────────┬───────────┘
              │   (intent, slots)
              ▼
   ┌──────────────────────┐
   │  Curator             │   route query → relevant Book(s)
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │  KnowledgeStore      │   4 atomic ops: access · equal · greater · similar
   │  (Bookshelf-backed)  │
   └──────────┬───────────┘
              │   (match or null)
              ▼
   ┌──────────────────────┐
   │  ResponseComposer    │   format answer · attach source · compute confidence
   └──────────┬───────────┘
              │
              ▼
        Response (text + trace)
```

The whole pipeline is deterministic. Given the same query and the same Books, you get the same answer — every time.

---

## Quick start

```python
from nous import Brain

brain = Brain()
brain.load_book("manual", "data/books/company_manual.json")

r = brain.ask("How many days of paid leave do we get?")
print(r.text)          # "Paid leave: 10 days/year..."
print(r.source_book)   # "manual"
print(r.confidence)    # 0.71
print(r.trace())       # {"intent": ..., "source_book": ..., "matched_key": ...}
```

If the answer is not in any loaded Book:

```python
r = brain.ask("Tomorrow's weather?")
r.used_fallback        # True — engine knows it doesn't know
r.text                 # "I don't have information about this."
```

---

## Install

```bash
pip install -e .             # library only
pip install -e ".[server]"   # + FastAPI server
pip install -e ".[dev]"      # + pytest / ruff / mypy
```

---

## Run the demo server

```bash
# Development (local, unauthenticated)
uvicorn server.main:app --host 127.0.0.1 --port 8000

# Production-ish (API key required, bind locally, reverse-proxy for TLS)
NOUS_API_KEY=<strong-random-key> \
  uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> for the built-in demo UI (chat + Book management + dashboard).

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `NOUS_API_KEY` | *unset = open mode* | When set, all mutating + `/ask` + `/chat` endpoints require `X-API-Key` header |
| `NOUS_MAX_TEXT` | `4000` | Max length of one user query (chars) |
| `NOUS_MAX_BOOK_BYTES` | `1048576` | Max serialized size of a submitted Book (bytes) |

---

## Security posture

The server ships with hardening baked in:

- **Path-traversal guards** — Book names must match `[A-Za-z0-9_-]{1,64}`; all writes resolve back into `data/books/`
- **Size limits** — Enforced on `text` (MAX_TEXT) and `content` (MAX_BOOK_BYTES / depth / key count)
- **XSS-hardened UI** — All user/model-provided strings rendered via `textContent` + DOM APIs; never `innerHTML` with untrusted data
- **Intent whitelist** — `Response.intent` field clamped server-side to the known set
- **Optional API-key auth** — `NOUS_API_KEY` env var protects mutating + ask endpoints (constant-time compare)
- **Default local bind** — `127.0.0.1` recommended for on-prem installs; place behind reverse proxy for TLS

Run `pytest` (90 cases) for regression guarantees on these behaviors.

---

## Project layout

```
nous-core/
├── nous/                # Core library
│   ├── knowledge/       # KnowledgeStore — 4 atomic ops (access / equal / greater / similar)
│   ├── language/        # LanguageEngine — JP/EN tokenizer + intent parser
│   ├── bookshelf/       # Book / WritableBook / BookShelf
│   ├── curator/         # Curator — bridges BookShelf ⇄ KnowledgeStore
│   ├── dialogue/        # DialogueManager + ResponseComposer
│   └── brain.py         # Top-level public API
├── server/              # FastAPI wrapper (optional)
├── data/books/          # Sample Books (online_school, saas_manual)
├── examples/            # Usage examples
└── tests/               # 90 pytest cases
```

---

## License

MIT — see [LICENSE](./LICENSE).
