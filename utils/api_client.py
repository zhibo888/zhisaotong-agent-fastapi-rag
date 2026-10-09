import os

import httpx


class ApiClientError(RuntimeError):
    """A user-safe frontend error without response bodies or credentials."""


class AgentApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 90.0):
        self.base_url = (base_url or os.environ.get("AGENT_API_BASE_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=2.0)
            response.raise_for_status()
            data = response.json()
            return data.get("status") == "ok" and data.get("service") == "zhisaotong-agent"
        except (httpx.HTTPError, ValueError):
            return False

    def chat(self, query: str, history: list[dict]) -> dict:
        try:
            response = httpx.post(
                f"{self.base_url}/api/v1/chat",
                json={"query": query, "history": history},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.ConnectError as exc:
            raise ApiClientError("无法连接 FastAPI。请先启动：python -m uvicorn api.main:app --host 127.0.0.1 --port 8000") from exc
        except httpx.TimeoutException as exc:
            raise ApiClientError("FastAPI 请求超时，请稍后重试") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise ApiClientError(f"FastAPI 返回错误（HTTP {status}），请检查请求或后端日志") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiClientError("FastAPI 响应异常，请检查后端服务") from exc
        if not isinstance(data, dict) or not isinstance(data.get("answer"), str) or not data["answer"].strip():
            raise ApiClientError("FastAPI 未返回有效回答")
        tools = data.get("tools_used", [])
        if not isinstance(tools, list) or not all(isinstance(name, str) for name in tools):
            raise ApiClientError("FastAPI 返回的工具记录格式异常")
        return {"answer": data["answer"].strip(), "tools_used": tools}
