"""Opt-in real service checks; mocks are never counted as live passes."""
import os
import pytest
from agent.react_agent import ReactAgent
from agent.tools.agent_tools import get_user_location, get_weather, _resolve_city_to_adcode
from model.factory import get_chat_model, get_embed_model
from rag.vector_store import VectorStoreService

pytestmark = [pytest.mark.live,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_TESTS") != "1", reason="Set RUN_LIVE_TESTS=1 for real network calls")]


def test_dashscope_chat():
    assert get_chat_model().invoke("请只回答：连接成功").content


def test_dashscope_embedding():
    assert len(get_embed_model().embed_query("扫地机器人滤网")) == 1024


def test_real_retrieval_and_reinit():
    store = VectorStoreService()
    count = store.count()
    assert count > 0
    result = store.load_document()
    assert result["chunks_added"] == 0
    assert store.count() == count
    docs = store.get_retriever().invoke("扫地机器人吸力变弱了怎么办？")
    assert len(docs) == 3
    assert any("吸力" in doc.page_content for doc in docs)


def test_real_fastapi_chat_and_rag():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    search = client.post("/api/v1/rag/search", json={
        "query": "扫地机器人吸力变弱了怎么办？", "top_k": 3,
    })
    assert search.status_code == 200
    assert len(search.json()["results"]) == 3
    assert any("吸力" in item["content"] for item in search.json()["results"])
    chat = client.post("/api/v1/chat", json={
        "query": "扫地机器人吸力变弱了怎么办？请依据知识库简短回答。",
        "history": [],
    })
    assert chat.status_code == 200
    body = chat.json()
    assert "rag_summarize" in body["tools_used"] and body["answer"]
    assert any(word in body["answer"] for word in ("滤网", "尘盒", "主刷"))


def test_real_agent_report():
    calls = []
    answer = "".join(ReactAgent().execute_stream(
        "请生成用户1001在2025年1月的使用报告，基于样例CSV，简洁呈现。", on_tool=calls.append))
    assert "fill_context_for_report" in calls and "fetch_external_data" in calls
    assert "85%" in answer and "样例" in answer


@pytest.mark.skipif(not os.environ.get("AMAP_API_KEY"), reason="AMAP_API_KEY is absent; real Amap test SKIPPED")
def test_real_amap():
    name, adcode = _resolve_city_to_adcode("北京市")
    assert name and adcode
    assert "失败" not in get_user_location.invoke({})
    assert "数据发布时间" in get_weather.invoke({"city": "北京市"})


def test_real_default_report_uses_identity_and_current_month():
    from agent.tools.agent_tools import get_current_month
    calls = []
    answer = "".join(ReactAgent().execute_stream(
        "请生成我的本月使用报告。请用工具确定演示用户和当前月份，若没有记录直接说明，不要改用历史月份。",
        on_tool=calls.append))
    assert {"fill_context_for_report", "get_user_id", "get_current_month", "fetch_external_data"}.issubset(calls)
    assert "1001" in answer
    month = get_current_month.invoke({})
    assert month in answer or (month[:4] in answer and str(int(month[5:])) + "月" in answer)
    assert any(word in answer for word in ("未找到", "没有", "无记录", "暂无", "无对应"))
    assert "85%" not in answer


def test_real_multiturn_and_report_mode_reset():
    agent = ReactAgent()
    calls = []
    answer = "".join(agent.execute_stream("用户999999在2025年1月有使用记录吗？若没有请直接说明。", on_tool=calls.append))
    assert "fetch_external_data" in calls
    assert any(word in answer for word in ("未找到", "没有", "不存在", "暂无", "无记录"))
    history = [{"role": "user", "content": "请记住测试代号：青竹482。"},
               {"role": "assistant", "content": "已记住测试代号：青竹482。"}]
    calls.clear()
    followup = "".join(agent.execute_stream("刚才的测试代号是什么？只回答代号。", history, calls.append))
    assert "青竹482" in followup
    assert "fill_context_for_report" not in calls and "fetch_external_data" not in calls


@pytest.mark.skipif(not os.environ.get("AMAP_API_KEY"), reason="AMAP_API_KEY is absent")
def test_real_agent_location_then_weather():
    calls = []
    answer = "".join(ReactAgent().execute_stream(
        "请用服务端出口IP近似定位，再查询该城市天气。明确这不是我的GPS位置，简洁回答。",
        on_tool=calls.append))
    assert "get_user_location" in calls and "get_weather" in calls
    assert calls.index("get_user_location") < calls.index("get_weather")
    assert "失败" not in answer
    assert any(word in answer for word in ("气温", "摄氏", "℃", "°C"))
    assert "IP" in answer or "出口" in answer


@pytest.mark.skipif(not os.environ.get("AMAP_API_KEY"), reason="AMAP_API_KEY is absent")
def test_real_nonexistent_city_is_not_invented():
    answer = get_weather.invoke({"city": "不存在的测试城市ZXQ482"})
    assert "天气查询失败" in answer
    assert "未找到城市" in answer or "高德服务响应失败（错误码 300" in answer
    assert "气温" not in answer and "检查 Key" not in answer
