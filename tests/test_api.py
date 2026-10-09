import httpx
import pytest
from fastapi.testclient import TestClient

from api import services
from api.main import app
from langchain_core.documents import Document
from utils.api_client import AgentApiClient, ApiClientError


client = TestClient(app)


def test_health_does_not_initialize_services(monkeypatch):
    monkeypatch.setattr(services, "get_agent", lambda: (_ for _ in ()).throw(AssertionError("must not initialize")))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "zhisaotong-agent"}


def test_chat_success_history_tools_and_request_isolation(monkeypatch):
    observed = []

    def fake(query, history):
        observed.append((query, history))
        return f"回答：{query}", ["rag_summarize"]

    monkeypatch.setattr(services, "run_agent_chat", fake)
    first = client.post("/api/v1/chat", json={
        "query": " 第二轮 ",
        "history": [{"role": "user", "content": " 第一轮 "}],
    })
    second = client.post("/api/v1/chat", json={"query": "独立请求"})
    assert first.status_code == second.status_code == 200
    assert first.json() == {"answer": "回答：第二轮", "tools_used": ["rag_summarize"]}
    assert observed == [("第二轮", [{"role": "user", "content": "第一轮"}]), ("独立请求", [])]


@pytest.mark.parametrize("payload", [
    {},
    {"query": ""},
    {"query": "   "},
    {"query": "x", "history": [{"role": "system", "content": "bad"}]},
    {"query": "x", "history": [{"role": "user", "content": ""}]},
    {"query": "x", "history": [{"role": "user", "content": "x"}] * 21},
    {"query": "x", "unexpected": True},
])
def test_chat_validation(payload):
    assert client.post("/api/v1/chat", json=payload).status_code == 422


def test_chat_total_history_limit():
    payload = {"query": "x", "history": [{"role": "user", "content": "x" * 1000}] * 17}
    assert client.post("/api/v1/chat", json=payload).status_code == 422


def test_chat_service_error_is_sanitized(monkeypatch):
    def fail(*_):
        raise services.BackendServiceError("Agent 服务暂时不可用，请稍后重试") from RuntimeError("SECRET")
    monkeypatch.setattr(services, "run_agent_chat", fail)
    response = client.post("/api/v1/chat", json={"query": "测试"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Agent 服务暂时不可用，请稍后重试"
    assert "SECRET" not in response.text


def test_rag_search_contract(monkeypatch):
    document = Document(page_content="清理滤网", metadata={"source": "demo.txt", "page": 0})
    class Store:
        def search(self, query, top_k):
            assert (query, top_k) == ("滤网", 5)
            return [(document, 0.125)]
    monkeypatch.setattr(services, "get_vector_store", lambda: Store())
    response = client.post("/api/v1/rag/search", json={"query": "滤网", "top_k": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["score_type"] == "distance"
    assert body["results"][0] == {
        "rank": 1, "source": "demo.txt", "content": "清理滤网",
        "distance": 0.125, "metadata": {"source": "demo.txt", "page": 0},
    }


@pytest.mark.parametrize("payload", [
    {"query": "", "top_k": 3},
    {"query": "x", "top_k": 0},
    {"query": "x", "top_k": 21},
])
def test_rag_validation(payload):
    assert client.post("/api/v1/rag/search", json=payload).status_code == 422


def test_rag_failure_is_sanitized(monkeypatch):
    monkeypatch.setattr(services, "search_rag", lambda *_: (_ for _ in ()).throw(
        services.BackendServiceError("RAG 检索暂时不可用，请检查知识库初始化")
    ))
    response = client.post("/api/v1/rag/search", json={"query": "滤网"})
    assert response.status_code == 503 and "SECRET" not in response.text


def test_api_client_success(monkeypatch):
    def post(*_, **__):
        return httpx.Response(200, json={"answer": "成功", "tools_used": ["rag_summarize"]},
                              request=httpx.Request("POST", "http://test/api/v1/chat"))
    monkeypatch.setattr(httpx, "post", post)
    assert AgentApiClient("http://test").chat("问题", []) == {
        "answer": "成功", "tools_used": ["rag_summarize"]
    }


def test_api_client_redacts_backend_body(monkeypatch):
    def post(*_, **__):
        return httpx.Response(503, text="SECRET", request=httpx.Request("POST", "http://test/api/v1/chat"))
    monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(ApiClientError) as error:
        AgentApiClient("http://test").chat("问题", [])
    assert "SECRET" not in str(error.value) and "503" in str(error.value)
