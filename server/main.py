"""nous-server FastAPI entry point.

Run:
    uvicorn server.main:app --host 127.0.0.1 --port 8000

Env vars:
    NOUS_API_KEY   — if set, all mutating + /ask endpoints require X-API-Key header
    NOUS_MAX_TEXT  — max length of user text (default 4000)
    NOUS_MAX_BOOK_BYTES — max serialized size of a submitted book (default 1MB)

Endpoints:
    GET  /                 -> Minimal HTML UI (chat + admin + dashboard)
    POST /ask              -> Ask one question
    POST /books            -> Register a new book (from JSON content)
    GET  /books            -> List registered books
    DELETE /conversation   -> Clear dialogue history
    GET  /summary          -> Brain state
    WS   /chat             -> Multi-turn WebSocket chat
"""

import hmac
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field, field_validator

from nous import Brain


APP_ROOT = Path(__file__).resolve().parent
DATA_ROOT = (APP_ROOT.parent / "data" / "books").resolve()
DATA_ROOT.mkdir(parents=True, exist_ok=True)

API_KEY = os.environ.get("NOUS_API_KEY")  # empty → open mode (dev only)
MAX_TEXT_LEN = int(os.environ.get("NOUS_MAX_TEXT", "4000"))
MAX_BOOK_BYTES = int(os.environ.get("NOUS_MAX_BOOK_BYTES", str(1 * 1024 * 1024)))
MAX_BOOK_DEPTH = 5
MAX_BOOK_KEYS = 5000
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
ALLOWED_INTENTS = {"ask", "solve", "prove", "discover", "learn", "create", "general"}

logger = logging.getLogger("nous-core.server")
brain = Brain()


@asynccontextmanager
async def lifespan(app: FastAPI):
    for p in sorted(DATA_ROOT.glob("*.json")):
        try:
            brain.load_book(p.stem, str(p))
            logger.info("loaded book: %s", p.stem)
        except Exception:
            logger.exception("failed to load book: %s", p.stem)
    yield


app = FastAPI(title="nous-core server", version="0.1.0", lifespan=lifespan)


# -------- Auth --------

def require_api_key(x_api_key: str | None = Header(default=None)):
    """Enforce API key if NOUS_API_KEY is set. No-op otherwise (dev mode)."""
    if not API_KEY:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid or missing API key")


# -------- Helpers --------

def _safe_book_path(name: str) -> Path:
    """Resolve name to a path inside DATA_ROOT. Raises if traversal attempted."""
    if not NAME_RE.match(name):
        raise HTTPException(400, "book name must match [A-Za-z0-9_-]{1,64}")
    target = (DATA_ROOT / f"{name}.json").resolve()
    try:
        target.relative_to(DATA_ROOT)
    except ValueError:
        raise HTTPException(400, "invalid book path")
    return target


def _validate_book_content(content: dict) -> None:
    """Guard against oversized, too-deep, or too-many-keys JSON payloads."""
    try:
        serialized = json.dumps(content, ensure_ascii=False)
    except (TypeError, ValueError):
        raise HTTPException(400, "content must be JSON-serializable")
    if len(serialized.encode("utf-8")) > MAX_BOOK_BYTES:
        raise HTTPException(413, f"book exceeds {MAX_BOOK_BYTES} bytes")

    def depth_and_count(obj, d=0):
        if d > MAX_BOOK_DEPTH:
            raise HTTPException(400, f"book nested deeper than {MAX_BOOK_DEPTH}")
        n = 0
        if isinstance(obj, dict):
            n += len(obj)
            for v in obj.values():
                n += depth_and_count(v, d + 1)
        elif isinstance(obj, list):
            for v in obj:
                n += depth_and_count(v, d + 1)
        return n

    if depth_and_count(content) > MAX_BOOK_KEYS:
        raise HTTPException(400, f"book exceeds {MAX_BOOK_KEYS} total keys/items")


def _sanitize_intent(value: str) -> str:
    return value if value in ALLOWED_INTENTS else "general"


def _response_payload(r) -> dict:
    return {
        "text": r.text,
        "intent": _sanitize_intent(r.intent),
        "source_book": r.source_book,
        "source_key": r.source_key,
        "confidence": r.confidence,
        "keywords": r.keywords,
        "used_fallback": r.used_fallback,
    }


# -------- Schemas --------

class AskRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LEN)
    books: list[str] | None = Field(default=None, max_length=32)

    @field_validator("books")
    @classmethod
    def _validate_book_names(cls, v):
        if v is None:
            return v
        for n in v:
            if not NAME_RE.match(n):
                raise ValueError(f"invalid book name: {n!r}")
        return v


class AskResponse(BaseModel):
    text: str
    intent: str
    source_book: str
    source_key: str
    confidence: float
    keywords: list[str]
    used_fallback: bool


class BookRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    content: dict[str, Any]

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v):
        if not NAME_RE.match(v):
            raise ValueError("name must match [A-Za-z0-9_-]{1,64}")
        return v


class BookInfo(BaseModel):
    name: str


class SummaryResponse(BaseModel):
    books: list[str]
    book_count: int
    fact_count: int
    pattern_count: int
    dialogue_turns: int


# -------- Endpoints --------

@app.get("/summary", response_model=SummaryResponse)
def get_summary():
    return brain.summary()


@app.get("/books", response_model=list[BookInfo])
def list_books():
    return [{"name": n} for n in brain.books()]


@app.post("/books", response_model=BookInfo,
          dependencies=[])
def register_book(req: BookRegisterRequest, _=Header(default=None, include_in_schema=False)):
    require_api_key(_)
    _validate_book_content(req.content)
    target = _safe_book_path(req.name)
    try:
        with open(target, "w", encoding="utf-8") as f:
            json.dump(req.content, f, ensure_ascii=False, indent=2)
        brain.load_book(req.name, str(target))
    except HTTPException:
        raise
    except Exception:
        logger.exception("register_book failed for %s", req.name)
        raise HTTPException(500, "failed to register book")
    return {"name": req.name}


# Re-declare with proper dependency parameter (FastAPI pattern).
@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    r = brain.ask(req.text, books=req.books)
    return _response_payload(r)


@app.delete("/conversation")
def clear_conversation(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    brain.clear_conversation()
    return {"status": "cleared"}


@app.websocket("/chat")
async def chat_ws(ws: WebSocket):
    # Auth: if API key set, require matching Sec-WebSocket-Protocol or query param.
    if API_KEY:
        supplied = ws.headers.get("x-api-key") or ws.query_params.get("api_key")
        if not supplied or not hmac.compare_digest(supplied, API_KEY):
            await ws.close(code=1008)
            return
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            text = (msg.get("text") or "").strip()
            if not text:
                await ws.send_json({"error": "text is required"})
                continue
            if len(text) > MAX_TEXT_LEN:
                await ws.send_json({"error": f"text exceeds {MAX_TEXT_LEN} chars"})
                continue
            books = msg.get("books")
            if books is not None:
                if not isinstance(books, list) or any(
                    not isinstance(b, str) or not NAME_RE.match(b) for b in books
                ):
                    await ws.send_json({"error": "invalid books filter"})
                    continue
            r = brain.ask(text, books=books)
            await ws.send_json(_response_payload(r))
    except WebSocketDisconnect:
        pass


# -------- Minimal HTML UI --------

@app.get("/", response_class=HTMLResponse)
def root():
    html_path = APP_ROOT / "static" / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    return HTMLResponse("<h1>nous-core server</h1><p>UI not found at /static/index.html.</p>")
