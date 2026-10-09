"""Lazy provider construction: imports require no credentials or network."""
from abc import ABC, abstractmethod
from functools import lru_cache
import os
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from utils.config_handler import rag_conf


def _check_key():
    if not os.environ.get("DASHSCOPE_API_KEY", "").strip():
        raise ValueError("当前进程未继承 DASHSCOPE_API_KEY；请重启终端检查环境变量继承")


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self):
        raise NotImplementedError


class ChatModelFactory(BaseModelFactory):
    def generator(self):
        _check_key()
        return ChatTongyi(model=rag_conf["chat_model_name"], temperature=0, max_retries=2)


class EmbeddingsFactory(BaseModelFactory):
    def generator(self):
        _check_key()
        return DashScopeEmbeddings(model=rag_conf["embedding_model_name"], max_retries=2)


@lru_cache(maxsize=1)
def get_chat_model():
    return ChatModelFactory().generator()


@lru_cache(maxsize=1)
def get_embed_model():
    return EmbeddingsFactory().generator()
