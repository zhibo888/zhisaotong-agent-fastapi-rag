"""Explicit, idempotent indexing with Chroma as the source of truth."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from model.factory import get_embed_model
from utils.config_handler import chroma_conf, rag_conf
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


class VectorStoreService:
    def __init__(self, config=None, embedding=None):
        self.conf = dict(chroma_conf if config is None else config)
        self.signature = hashlib.sha256(json.dumps({
            "model": rag_conf["embedding_model_name"],
            "chunk_size": self.conf["chunk_size"],
            "chunk_overlap": self.conf["chunk_overlap"],
            "separators": self.conf["separators"],
        }, sort_keys=True).encode()).hexdigest()[:16]
        self.vector_store = Chroma(
            collection_name=self.conf["collection_name"],
            embedding_function=embedding if embedding is not None else get_embed_model(),
            persist_directory=get_abs_path(self.conf["persist_directory"]),
        )
        collection = self.vector_store._collection
        metadata = collection.metadata or {}
        if collection.count() and metadata.get("index_signature") != self.signature:
            raise ValueError("现有向量库的模型/分块签名不匹配或未知；请先备份，再配置新的持久化目录和 MD5 文件重建")
        if not collection.count():
            collection.modify(metadata={**metadata, "index_signature": self.signature,
                                        "embedding_model": rag_conf["embedding_model_name"]})
        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=self.conf["chunk_size"], chunk_overlap=self.conf["chunk_overlap"],
            separators=self.conf["separators"], length_function=len,
        )

    def count(self):
        return self.vector_store._collection.count()

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": self.conf["k"]})

    def search(self, query: str, top_k: int | None = None):
        """Return (Document, distance) pairs; lower distance means a closer match."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("检索问题不能为空")
        k = self.conf["k"] if top_k is None else top_k
        if not isinstance(k, int) or not 1 <= k <= 20:
            raise ValueError("top_k 必须是 1 到 20 的整数")
        return self.vector_store.similarity_search_with_score(query.strip(), k=k)

    def load_document(self):
        ledger = Path(get_abs_path(self.conf["md5_hex_store"]))
        original = ledger.read_text(encoding="utf-8") if ledger.exists() else ""
        files = listdir_with_allowed_type(get_abs_path(self.conf["data_path"]),
                                         tuple(self.conf["allow_knowledge_file_type"]))
        if not files:
            raise ValueError("知识库目录没有支持的文档")
        # Preserve a stale ledger once before repairing it; never delete existing DB files.
        known_md5s = set(original.splitlines())
        indexed_md5s = {m.get("file_md5") for m in self.vector_store.get(include=["metadatas"])["metadatas"]}
        if known_md5s - indexed_md5s:
            backup = Path(get_abs_path(".local/backups")) / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ledger, backup / ledger.name)
            logger.warning("发现 MD5 与向量库不一致；已备份 MD5，将按实际向量修复")
        complete, seen = set(), set()
        summary = {"loaded_files": 0, "skipped_files": 0, "chunks_added": 0}
        try:
            for filename in files:
                digest = get_file_md5_hex(filename)
                if digest in seen:
                    summary["skipped_files"] += 1
                    continue
                seen.add(digest)
                documents = pdf_loader(filename) if Path(filename).suffix.lower() == ".pdf" else txt_loader(filename)
                chunks = [d for d in self.spliter.split_documents(documents) if d.page_content.strip()]
                if not chunks:
                    raise ValueError("知识库文档没有可提取文本")
                ids = [f"{self.signature}:{digest}:{i}" for i in range(len(chunks))]
                existing = set(self.vector_store.get(where={"file_md5": digest}, include=[])["ids"])
                missing = [(i, d) for i, d in enumerate(chunks) if ids[i] not in existing]
                if missing:
                    for i, document in missing:
                        document.metadata = {
                            "source": Path(filename).name, "file_md5": digest,
                            "chunk_index": i, "page": document.metadata.get("page", 0),
                        }
                    # Small batches keep DashScope request sizes predictable. IDs make retry safe.
                    for offset in range(0, len(missing), 10):
                        batch = missing[offset:offset + 10]
                        self.vector_store.add_documents([d for _, d in batch],
                                                        ids=[ids[i] for i, _ in batch])
                    verified = set(self.vector_store.get(where={"file_md5": digest}, include=[])["ids"])
                    if not set(ids).issubset(verified):
                        raise RuntimeError("向量写入不完整")
                    summary["loaded_files"] += 1
                    summary["chunks_added"] += len(missing)
                else:
                    summary["skipped_files"] += 1
                complete.add(digest)
                logger.info("知识库文档完成：%s，分块数=%s", Path(filename).name, len(chunks))
        finally:
            # Only verified complete documents are recorded; interrupted imports remain resumable.
            ledger.parent.mkdir(parents=True, exist_ok=True)
            temp = ledger.with_suffix(ledger.suffix + ".tmp")
            temp.write_text("".join(x + "\n" for x in sorted(complete)), encoding="utf-8")
            temp.replace(ledger)
        summary["vectors"] = self.count()
        return summary


if __name__ == "__main__":
    try:
        print(json.dumps(VectorStoreService().load_document(), ensure_ascii=False))
    except Exception as exc:
        logger.error("知识库初始化失败：%s；检查依赖、模型配置或网络", type(exc).__name__)
        raise SystemExit(1) from None
