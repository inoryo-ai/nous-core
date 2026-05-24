# nous-core

LLM-free cognitive engine for business AI applications.

## Why nous-core

| 軸 | nous-core | LLM組込ソフト |
|----|-----------|---------------|
| 嘘を言わない | ✅ 知識にないと答えない（`used_fallback` で明示） | ❌ ハルシネーション |
| ランニングコスト | ✅ API費ゼロ | ❌ トークン課金 |
| データ機密性 | ✅ 完全オンプレ可能 | ❌ 外部送信 |
| 監査可能性 | ✅ 判断根拠を `Response.trace()` で全トレース | ❌ ブラックボックス |
| カスタム知識 | ✅ Book（JSON）追加で即ドメイン特化 | ⚠️ RAG必須 |

## Quick Start

```python
from nous import Brain

brain = Brain()
brain.load_book("manual", "data/books/company_manual.json")

r = brain.ask("有給休暇は何日？")
print(r.text)          # 【有給休暇】...
print(r.source_book)   # "manual"
print(r.confidence)    # 0.71
print(r.trace())       # {"intent":..., "source_book":..., ...}
```

## Install

```bash
pip install -e .            # library only
pip install -e ".[server]"  # + FastAPI server
pip install -e ".[dev]"     # + pytest / ruff / mypy
```

## Run the demo server

```bash
# Development (local, unauthenticated)
uvicorn server.main:app --host 127.0.0.1 --port 8000

# Production-ish (require API key, bound locally, reverse-proxy for TLS)
NOUS_API_KEY=<strong-random-key> \
  uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 for the built-in demo UI (chat + Book management + dashboard).

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NOUS_API_KEY` | *(unset = open mode)* | When set, all mutating + `/ask` + `/chat` endpoints require `X-API-Key` header. |
| `NOUS_MAX_TEXT` | `4000` | Max length of one user query (chars). |
| `NOUS_MAX_BOOK_BYTES` | `1048576` | Max serialized size of a submitted Book (bytes). |

## Project Layout

```
nous-core/
├── nous/               # Core library
│   ├── knowledge/     # KnowledgeStore (4 atomic ops: access/equal/greater/similar)
│   ├── language/      # LanguageEngine (JP/EN tokenizer + intent parser)
│   ├── bookshelf/     # Book / WritableBook / BookShelf
│   ├── curator/       # Curator (bridges BookShelf ⇄ KS)
│   ├── dialogue/      # DialogueManager + ResponseComposer
│   └── brain.py       # Top-level public API
├── server/             # FastAPI wrapper (optional)
├── data/books/         # Sample Books (online_school, saas_manual)
├── examples/           # Usage examples
└── tests/              # 90 pytest cases
```

## Security posture

The server ships with hardening baked in:

- **Path-traversal guards**: Book names must match `[A-Za-z0-9_-]{1,64}`; all writes resolved back into `data/books/`.
- **Size limits**: Enforced on `text` (MAX_TEXT) and `content` (MAX_BOOK_BYTES / depth / key count).
- **XSS hardened UI**: All user/model-provided strings rendered via `textContent` + DOM APIs. No `innerHTML` with untrusted data.
- **Intent whitelist**: Response `intent` field clamped server-side to the known set.
- **Optional API-key auth**: `NOUS_API_KEY` env var protects mutating + ask endpoints (constant-time compare).
- **Default local bind**: `127.0.0.1` recommended for on-prem installs; put behind reverse proxy for TLS.

Run the test suite (`pytest`) for regression guarantees on these behaviors.

## License

MIT License — see [LICENSE](./LICENSE).
