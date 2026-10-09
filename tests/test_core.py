import csv
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.error import URLError, HTTPError
import pytest
import yaml
from pydantic import ValidationError
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import PrivateAttr
from agent.tools import agent_tools as tools
from agent.react_agent import ReactAgent, TOOLS
from rag.vector_store import VectorStoreService
from utils.config_handler import load_chroma_config, load_rag_config, chroma_conf
from utils.file_handler import listdir_with_allowed_type, get_file_md5_hex, txt_loader, pdf_loader
from utils.path_tool import get_abs_path


def test_paths_independent_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Path(get_abs_path("config/rag.yml")).is_file()
    assert load_rag_config()["chat_model_name"] == "qwen3-max"


@pytest.mark.parametrize("text", ["[]", "", "bad: [", "chat_model_name: x"])
def test_invalid_yaml(tmp_path, text):
    p = tmp_path / "bad.yml"
    p.write_text(text)
    with pytest.raises(ValueError):
        load_rag_config(str(p))


def test_chunk_validation(tmp_path):
    conf = {**chroma_conf, "chunk_overlap": chroma_conf["chunk_size"]}
    p = tmp_path / "bad.yml"
    p.write_text(yaml.safe_dump(conf))
    with pytest.raises(ValueError):
        load_chroma_config(str(p))


def test_missing_directory(tmp_path):
    with pytest.raises(NotADirectoryError):
        listdir_with_allowed_type(str(tmp_path / "missing"), ("txt",))


def test_documents_and_md5(tmp_path):
    p = tmp_path / "doc.TXT"
    p.write_text("机器人滤网维护", encoding="utf-8")
    assert listdir_with_allowed_type(str(tmp_path), ("txt",)) == (str(p),)
    assert txt_loader(str(p))[0].page_content == "机器人滤网维护"
    original = get_file_md5_hex(p)
    p.write_text("已修改", encoding="utf-8")
    assert get_file_md5_hex(p) != original
    # Build a tiny PDF fixture so the public test suite does not depend on
    # upstream knowledge documents whose redistribution license is unclear.
    from pypdf import PdfWriter
    from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject
    pdf = tmp_path / "fixture.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(300, 200)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
    })
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 20 100 Td (Robot filter maintenance) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    with pdf.open("wb") as stream:
        writer.write(stream)
    docs = pdf_loader(str(pdf))
    assert docs and "Robot filter maintenance" in docs[0].page_content


def test_identity_and_month():
    assert tools.get_user_id.invoke({}) == tools.get_user_id.invoke({}) == "1001"
    assert tools.get_current_month.invoke({}) == datetime.now().strftime("%Y-%m")


@pytest.mark.parametrize("args", [{"user_id": "x", "month": "2025-01"},
                                 {"user_id": "1001", "month": "2025-13"},
                                 {"user_id": "1001", "month": "2025-1"}])
def test_report_invalid_args(args):
    with pytest.raises(ValueError):
        tools.fetch_external_data.invoke(args)


def test_schema_validation():
    with pytest.raises(ValidationError):
        tools.get_weather.invoke({})
    with pytest.raises(ValidationError):
        tools.fetch_external_data.invoke({"user_id": 1001, "month": "2025-01"})


def test_sample_records():
    data = json.loads(tools.fetch_external_data.invoke({"user_id": "1001", "month": "2025-01"}))
    assert "85%" in data["效率"]
    assert "非实时" in data["数据来源"]
    assert "未找到" in tools.fetch_external_data.invoke({"user_id": "1001", "month": "2099-01"})


def test_csv_quoted_fields(tmp_path, monkeypatch):
    p = tmp_path / "records.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["用户ID", "特征", "清洁效率", "耗材", "对比", "时间"])
        w.writerow(["1001", "含,逗号", "多行\n内容", "完好", "暂无", "2025-01"])
    monkeypatch.setitem(tools.agent_conf, "external_data_path", str(p))
    result = json.loads(tools.fetch_external_data.invoke({"user_id": "1001", "month": "2025-01"}))
    assert result["特征"] == "含,逗号" and result["效率"] == "多行\n内容"


def test_missing_csv(tmp_path, monkeypatch):
    monkeypatch.setitem(tools.agent_conf, "external_data_path", str(tmp_path / "missing.csv"))
    with pytest.raises(FileNotFoundError):
        tools.fetch_external_data.invoke({"user_id": "1001", "month": "2025-01"})


def test_amap_missing_key(monkeypatch):
    monkeypatch.delenv("AMAP_API_KEY", raising=False)
    assert "AMAP_API_KEY" in tools.get_weather.invoke({"city": "北京"})
    assert "AMAP_API_KEY" in tools.get_user_location.invoke({})


@pytest.mark.parametrize("failure", [URLError("https://example.invalid?key=SECRET"),
    HTTPError("https://example.invalid?key=SECRET", 403, "SECRET", {}, None), TimeoutError("SECRET")])
def test_amap_network_errors_redacted(monkeypatch, failure):
    monkeypatch.setenv("AMAP_API_KEY", "SECRET")
    monkeypatch.setattr(tools, "urlopen", Mock(side_effect=failure))
    result = tools.get_weather.invoke({"city": "北京"})
    assert "失败" in result and "SECRET" not in result


def test_amap_request_and_weather(monkeypatch):
    from urllib.parse import urlparse, parse_qs
    monkeypatch.setenv("AMAP_API_KEY", "test-only")
    responses = [
        {"status": "1", "geocodes": [{"city": "北京市", "adcode": "110000"}]},
        {"status": "1", "lives": [{"weather": "晴", "temperature": "20", "humidity": "35",
          "winddirection": "北", "windpower": "3", "reporttime": "test-time"}]},
    ]
    urls = []
    def opener(url, timeout):
        urls.append(url)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(responses.pop(0)).encode()
        return response
    monkeypatch.setattr(tools, "urlopen", opener)
    result = tools.get_weather.invoke({"city": "北京"})
    assert "晴" in result and "20" in result
    assert urlparse(urls[0]).path == "/v3/geocode/geo"
    assert parse_qs(urlparse(urls[1]).query)["city"] == ["110000"]
    assert parse_qs(urlparse(urls[1]).query)["extensions"] == ["base"]


@pytest.mark.parametrize("payload", [[], {"status": "0", "info": "SECRET", "infocode": "10001"}])
def test_amap_bad_response(monkeypatch, payload):
    monkeypatch.setenv("AMAP_API_KEY", "SECRET")
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps(payload).encode()
    monkeypatch.setattr(tools, "urlopen", Mock(return_value=response))
    result = tools.get_weather.invoke({"city": "北京"})
    assert "失败" in result and "SECRET" not in result


def test_location_and_empty_city(monkeypatch):
    monkeypatch.setattr(tools, "_gaode_get", lambda *args: {"city": [], "province": "北京市"})
    assert "北京市" in tools.get_user_location.invoke({})
    assert "服务端" in tools.get_user_location.invoke({})
    assert "未提供" in tools.get_weather.invoke({"city": " "})


def test_rag_tool_contract(monkeypatch):
    service = Mock()
    service.rag_summarize.return_value = "检索到的答案"
    monkeypatch.setattr(tools, "get_rag_service", lambda: service)
    assert tools.rag_summarize.invoke({"query": "滤网"}) == "检索到的答案"
    service.rag_summarize.assert_called_once_with("滤网")
    with pytest.raises(ValueError):
        tools.rag_summarize.invoke({"query": " "})


def test_empty_rag_is_an_actionable_failure():
    from rag.rag_service import RagSummarizeService
    from utils.errors import UserFacingError
    service = RagSummarizeService.__new__(RagSummarizeService)
    service.vector_store = Mock()
    service.vector_store.count.return_value = 0
    with pytest.raises(UserFacingError, match="python -m rag.vector_store"):
        service.retriever_docs("滤网")


def test_missing_dashscope_key(monkeypatch):
    from model.factory import ChatModelFactory
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="未继承"):
        ChatModelFactory().generator()


def make_store(tmp_path, embedding=None):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    (data / "a.txt").write_text("清理滤网，检查尘盒。\n" * 100, encoding="utf-8")
    conf = {**chroma_conf, "data_path": str(data), "persist_directory": str(tmp_path / "db"),
            "md5_hex_store": str(tmp_path / "md5.text"), "chunk_size": 40, "chunk_overlap": 5}
    return VectorStoreService(conf, embedding or DeterministicFakeEmbedding(size=16))


def check_index_dedup_persistence_and_stale_md5(tmp_path):
    store = make_store(tmp_path)
    ledger = tmp_path / "md5.text"
    ledger.write_text(get_file_md5_hex(tmp_path / "data/a.txt") + "\n")
    first = store.load_document()
    assert first["chunks_added"] > 0
    count = store.count()
    assert count > 0
    second = VectorStoreService(store.conf, DeterministicFakeEmbedding(size=16))
    assert second.load_document()["chunks_added"] == 0
    assert second.count() == count
    assert len(second.get_retriever().invoke("滤网")) == min(count, chroma_conf["k"])
    assert len(ledger.read_text().splitlines()) == 1
    ledger.unlink()
    assert second.load_document()["chunks_added"] == 0
    assert ledger.exists()


def check_partial_index_retry(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    original = store.vector_store.add_documents
    calls = 0
    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated embedding failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(store.vector_store, "add_documents", fail_second)
    with pytest.raises(RuntimeError):
        store.load_document()
    assert store.count() == 10
    assert not (tmp_path / "md5.text").read_text()
    monkeypatch.setattr(store.vector_store, "add_documents", original)
    store.load_document()
    count = store.count()
    assert store.load_document()["chunks_added"] == 0
    assert store.count() == count > 10


@pytest.mark.parametrize("case", ["dedup", "retry"])
def test_native_index_in_subprocess(tmp_path, case):
    # A broken native DLL must fail a test, not kill the rest of the test suite.
    import subprocess
    import sys
    script = (
        "import runpy,pathlib,pytest; "
        "ns=runpy.run_path('tests/test_core.py'); "
        f"p=pathlib.Path({str(tmp_path)!r}); "
        + ("ns['check_index_dedup_persistence_and_stale_md5'](p)" if case == "dedup"
           else "ns['check_partial_index_retry'](p,pytest.MonkeyPatch())")
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=get_abs_path("."),
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    assert result.returncode == 0, f"Chroma native check failed (exit={result.returncode}); verify VC++ x64 runtime. {result.stderr[-1500:]}"


class ScriptedModel(BaseChatModel):
    replies: list
    _seen: list = PrivateAttr(default_factory=list)
    _cursor: int = PrivateAttr(default=0)

    @property
    def _llm_type(self):
        return "scripted-test"

    def bind_tools(self, tools, **kwargs):
        assert len(tools) == 7
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._seen.append(messages)
        reply = self.replies[self._cursor]
        self._cursor += 1
        return ChatResult(generations=[ChatGeneration(message=reply)])


def tool_reply(name, args, ident):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": ident, "type": "tool_call"}])


def test_real_agent_graph_dynamic_prompt_and_history():
    model = ScriptedModel(replies=[
        tool_reply("fill_context_for_report", {}, "1"),
        tool_reply("fetch_external_data", {"user_id": "1001", "month": "2025-01"}, "2"),
        AIMessage(content="报告完成"),
        AIMessage(content="普通问答完成"),
    ])
    agent = ReactAgent(model)
    calls = []
    result = list(agent.execute_stream("生成报告", [{"role": "user", "content": "请记住演示信息"}], calls.append))
    assert result == ["报告完成"]
    assert calls == ["fill_context_for_report", "fetch_external_data"]
    assert any(m.content == "请记住演示信息" for m in model._seen[0])
    assert "当前请求已进入报告模式" in model._seen[1][0].content
    assert any(isinstance(m, ToolMessage) and "85%" in m.content for m in model._seen[-1])
    assert list(agent.execute_stream("你好")) == ["普通问答完成"]
    assert "当前请求已进入报告模式" not in model._seen[-1][0].content


def test_tool_failure_returns_to_model():
    model = ScriptedModel(replies=[
        tool_reply("fill_context_for_report", {}, "1"),
        tool_reply("fetch_external_data", {"user_id": "bad", "month": "2025-01"}, "2"),
        AIMessage(content="参数错误，请重试"),
    ])
    assert list(ReactAgent(model).execute_stream("报告")) == ["参数错误，请重试"]
    assert any(isinstance(m, ToolMessage) and m.status == "error" for m in model._seen[-1])


def test_report_guard():
    model = ScriptedModel(replies=[
        tool_reply("fetch_external_data", {"user_id": "1001", "month": "2025-01"}, "1"),
        AIMessage(content="需要先进入报告模式"),
    ])
    list(ReactAgent(model).execute_stream("报告"))
    assert any(isinstance(m, ToolMessage) and "请先调用" in m.content for m in model._seen[-1])


def test_ui_success_and_error(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from utils import api_client
    class Stub:
        base_url = "http://testserver"
        def health(self):
            return True
        def chat(self, query, history):
            if query == "失败":
                from utils.api_client import ApiClientError
                raise ApiClientError("安全错误提示")
            assert history == [] or history[0]["content"] == "你好"
            return {"answer": "知识库回答", "tools_used": ["rag_summarize"]}
    monkeypatch.setattr(api_client, "AgentApiClient", Stub)
    app = AppTest.from_file(get_abs_path("app.py")).run()
    assert not app.exception
    app.chat_input[0].set_value("你好").run()
    assert app.session_state["message"][-1]["content"] == "知识库回答"
    count = len(app.session_state["message"])
    app.chat_input[0].set_value("失败").run()
    assert len(app.session_state["message"]) == count + 1
    assert app.session_state["message"][-1]["role"] == "user"
    assert any("安全错误提示" in item.value for item in app.error)
    assert not app.exception
