"""E2E tests for nous-server FastAPI app."""

import pytest
from fastapi.testclient import TestClient

from server.main import app, brain, DATA_ROOT


@pytest.fixture(autouse=True)
def reset_brain():
    """Isolate each test: fresh brain + reload bundled books."""
    brain.ks.facts.clear()
    brain.ks.confidence.clear()
    brain.ks._props_by_concept.clear()
    brain.ks._concepts_by_prop.clear()
    brain.shelf._books.clear()
    brain.dialogue.clear()
    for p in sorted(DATA_ROOT.glob("*.json")):
        brain.load_book(p.stem, str(p))
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_summary_endpoint(client):
    r = client.get("/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["book_count"] >= 2
    assert "online_school" in data["books"]


def test_list_books(client):
    r = client.get("/books")
    assert r.status_code == 200
    names = {b["name"] for b in r.json()}
    assert "online_school" in names
    assert "saas_manual" in names


def test_ask_hits_online_school(client):
    r = client.post("/ask", json={"text": "受講料の支払いは？"})
    assert r.status_code == 200
    data = r.json()
    assert data["source_book"] == "online_school"
    assert "受講料支払い" in data["source_key"] or "支払い" in data["source_key"]


def test_ask_hits_saas(client):
    r = client.post("/ask", json={"text": "ログインできない"})
    assert r.status_code == 200
    data = r.json()
    assert data["source_book"] == "saas_manual"


def test_ask_with_book_filter(client):
    r = client.post("/ask", json={
        "text": "支払い方法は？",
        "books": ["online_school"]
    })
    assert r.status_code == 200
    assert r.json()["source_book"] == "online_school"


def test_ask_unknown_returns_fallback(client):
    r = client.post("/ask", json={"text": "全く関係のない架空の何か"})
    assert r.status_code == 200
    data = r.json()
    if data["used_fallback"]:
        assert "登録された知識にありません" in data["text"]


def test_conversation_context_preserved(client):
    r1 = client.post("/ask", json={"text": "受講料について教えて"})
    assert r1.json()["source_key"] == "受講料支払い"
    r2 = client.post("/ask", json={"text": "それの期日は？"})
    assert r2.json()["source_key"] == "受講料支払い"


def test_clear_conversation(client):
    client.post("/ask", json={"text": "受講料"})
    r = client.delete("/conversation")
    assert r.status_code == 200
    s = client.get("/summary").json()
    assert s["dialogue_turns"] == 0


def test_register_book_from_content(client):
    payload = {
        "name": "test_dynamic",
        "content": {
            "_meta": {"title": "動的テスト"},
            "項目A": {"説明": "テスト用エントリ"}
        }
    }
    r = client.post("/books", json=payload)
    assert r.status_code == 200
    assert r.json()["name"] == "test_dynamic"

    q = client.post("/ask", json={"text": "項目Aについて"})
    data = q.json()
    assert data["source_book"] == "test_dynamic"

    # Cleanup the file created
    (DATA_ROOT / "test_dynamic.json").unlink(missing_ok=True)


def test_register_book_missing_body_fails(client):
    r = client.post("/books", json={"name": "bad"})
    assert r.status_code == 422  # pydantic schema rejects missing content


def test_register_book_rejects_traversal_name(client):
    r = client.post("/books", json={
        "name": "../../etc/passwd",
        "content": {"x": 1},
    })
    assert r.status_code == 422  # name regex rejects


def test_register_book_rejects_backslash_name(client):
    r = client.post("/books", json={
        "name": "..\\..\\secret",
        "content": {"x": 1},
    })
    assert r.status_code == 422


def test_register_book_rejects_oversized(client):
    # > 1MB payload
    big = {"k" + str(i): "x" * 100 for i in range(15000)}
    r = client.post("/books", json={"name": "big", "content": big})
    assert r.status_code in (400, 413)


def test_register_book_rejects_deep_nesting(client):
    nested = {}
    cur = nested
    for _ in range(10):
        cur["n"] = {}
        cur = cur["n"]
    r = client.post("/books", json={"name": "deep", "content": nested})
    assert r.status_code == 400


def test_ask_rejects_oversized_text(client):
    big_text = "a" * 5000
    r = client.post("/ask", json={"text": big_text})
    assert r.status_code == 422


def test_ask_rejects_bad_book_filter_name(client):
    r = client.post("/ask", json={
        "text": "有給",
        "books": ["../../etc/passwd"],
    })
    assert r.status_code == 422


def test_ask_requires_api_key_when_configured(monkeypatch, client):
    import server.main as srv
    monkeypatch.setattr(srv, "API_KEY", "secret-xyz")
    r = client.post("/ask", json={"text": "有給"})
    assert r.status_code == 401


def test_ask_accepts_correct_api_key(monkeypatch, client):
    import server.main as srv
    monkeypatch.setattr(srv, "API_KEY", "secret-xyz")
    r = client.post("/ask",
                    json={"text": "有給"},
                    headers={"X-API-Key": "secret-xyz"})
    assert r.status_code == 200


def test_books_post_requires_api_key(monkeypatch, client):
    import server.main as srv
    monkeypatch.setattr(srv, "API_KEY", "secret-xyz")
    r = client.post("/books",
                    json={"name": "test", "content": {"x": 1}})
    assert r.status_code == 401


def test_stored_book_name_sanitized_on_disk(tmp_path, client):
    """Registering a valid book does not create files outside DATA_ROOT."""
    from server.main import DATA_ROOT
    r = client.post("/books", json={
        "name": "safe_test",
        "content": {"x": {"y": 1}},
    })
    assert r.status_code == 200
    created = DATA_ROOT / "safe_test.json"
    assert created.exists()
    assert created.resolve().is_relative_to(DATA_ROOT.resolve())
    created.unlink(missing_ok=True)


def test_root_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "nous-core" in r.text.lower() or "nous-core" in r.text


def test_websocket_chat(client):
    with client.websocket_connect("/chat") as ws:
        ws.send_json({"text": "料金プランは？"})
        data = ws.receive_json()
        assert data["source_book"] in ("saas_manual", "online_school")
        assert data["used_fallback"] is False


def test_websocket_chat_validates_input(client):
    with client.websocket_connect("/chat") as ws:
        ws.send_json({})
        data = ws.receive_json()
        assert "error" in data
