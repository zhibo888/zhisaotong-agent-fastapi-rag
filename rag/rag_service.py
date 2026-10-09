"""Retrieve top-K passages, then summarize with the configured DashScope model."""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from model.factory import get_chat_model
from utils.errors import UserFacingError


class RagSummarizeService:
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.chain = PromptTemplate.from_template(load_rag_prompts()) | get_chat_model() | StrOutputParser()

    def retriever_docs(self, query):
        if not self.vector_store.count():
            raise UserFacingError("知识库为空，请先运行 python -m rag.vector_store。未返回参考资料，不能生成声称基于知识库的答案")
        return [document for document, _ in self.vector_store.search(query)]

    def rag_summarize(self, query: str) -> str:
        documents = self.retriever_docs(query)
        if not documents:
            return "未检索到知识库资料，无法根据知识库回答。"
        context = "\n\n".join(
            f"【{i} 来源：{doc.metadata.get('source', '未知')}】{doc.page_content}"
            for i, doc in enumerate(documents, 1)
        )
        answer = self.chain.invoke({"input": query, "context": context})
        sources = sorted({doc.metadata.get("source", "未知") for doc in documents})
        return answer + "\n\n参考来源：" + "、".join(sources)
