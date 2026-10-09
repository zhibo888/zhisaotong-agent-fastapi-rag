from functools import lru_cache

from agent.react_agent import ReactAgent
from rag.vector_store import VectorStoreService


class BackendServiceError(RuntimeError):
    """Sanitized boundary error returned by the API layer."""


@lru_cache(maxsize=1)
def get_agent() -> ReactAgent:
    return ReactAgent()


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStoreService:
    return VectorStoreService()


def run_agent_chat(query: str, history: list[dict]) -> tuple[str, list[str]]:
    tools_used: list[str] = []
    try:
        answer = "".join(get_agent().execute_stream(query, history, tools_used.append)).strip()
    except Exception as exc:
        raise BackendServiceError("Agent 服务暂时不可用，请稍后重试") from exc
    if not answer:
        raise BackendServiceError("Agent 未返回有效回答，请稍后重试")
    return answer, tools_used


def search_rag(query: str, top_k: int) -> list[dict]:
    try:
        matches = get_vector_store().search(query, top_k)
    except Exception as exc:
        raise BackendServiceError("RAG 检索暂时不可用，请检查知识库初始化") from exc
    return [
        {
            "rank": rank,
            "source": str(document.metadata.get("source", "未知")),
            "content": document.page_content,
            "distance": float(distance) if distance is not None else None,
            "metadata": dict(document.metadata),
        }
        for rank, (document, distance) in enumerate(matches, 1)
    ]
