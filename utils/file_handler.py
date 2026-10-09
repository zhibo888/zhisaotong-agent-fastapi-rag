from pathlib import Path
import hashlib
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader


def get_file_md5_hex(filepath: str) -> str:
    with open(filepath, "rb") as stream:
        return hashlib.file_digest(stream, "md5").hexdigest()


def listdir_with_allowed_type(path: str, allowed_types: tuple[str]) -> tuple[str, ...]:
    directory = Path(path)
    if not directory.is_dir():
        raise NotADirectoryError("知识库文档目录不存在")
    extensions = {"." + ext.lower().lstrip(".") for ext in allowed_types}
    return tuple(str(p) for p in sorted(directory.iterdir()) if p.is_file() and p.suffix.lower() in extensions)


def pdf_loader(filepath: str, passwd=None) -> list[Document]:
    return PyPDFLoader(filepath, password=passwd).load()


def txt_loader(filepath: str) -> list[Document]:
    return TextLoader(filepath, encoding="utf-8-sig").load()
