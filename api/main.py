from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api import services
from api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    RagSearchRequest,
    RagSearchResponse,
)
from utils.logger_handler import logger


app = FastAPI(
    title="智扫通 Agent API",
    description="智扫通本地 Agent、工具调用与 RAG 调试接口。未实现生产级身份认证。",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8501", "http://localhost:8501"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Liveness only: never initializes or calls a model."""
    return HealthResponse()


@app.post("/api/v1/chat", response_model=ChatResponse, tags=["agent"])
def chat(request: ChatRequest) -> ChatResponse:
    history = [message.model_dump() for message in request.history]
    try:
        answer, tools_used = services.run_agent_chat(request.query, history)
    except services.BackendServiceError as exc:
        logger.warning("API Agent 请求失败：%s", type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__)
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return ChatResponse(answer=answer, tools_used=tools_used)


@app.post("/api/v1/rag/search", response_model=RagSearchResponse, tags=["rag"])
def rag_search(request: RagSearchRequest) -> RagSearchResponse:
    try:
        results = services.search_rag(request.query, request.top_k)
    except services.BackendServiceError as exc:
        logger.warning("API RAG 请求失败：%s", type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__)
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return RagSearchResponse(query=request.query, top_k=request.top_k, results=results)
