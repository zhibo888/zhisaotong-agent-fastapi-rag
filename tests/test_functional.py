"""Additional behavioral checks for the full-function acceptance run."""
import csv
import json
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from agent.tools import agent_tools as tools
from utils.path_tool import get_abs_path


def test_all_sample_records_are_accessible():
    records = tools.generate_external_data()
    assert len(records) == 10
    assert sum(len(months) for months in records.values()) == 120
    for user_id, months in records.items():
        for month, expected in months.items():
            actual = json.loads(tools.fetch_external_data.invoke({"user_id": user_id, "month": month}))
            assert actual["用户ID"] == user_id and actual["月份"] == month
            assert all(actual[key] == value for key, value in expected.items())
            assert "非实时" in actual["数据来源"]


def test_unknown_user_has_no_fabricated_record():
    assert "未找到" in tools.fetch_external_data.invoke({"user_id": "999999", "month": "2025-01"})


@pytest.mark.parametrize("kind", ["columns", "incomplete", "duplicate", "bad_month"])
def test_invalid_csv_rejected(tmp_path, monkeypatch, kind):
    file = tmp_path / "records.csv"
    header = ["用户ID", "特征", "清洁效率", "耗材", "对比", "时间"]
    row = ["1001", "测试", "85%", "完好", "暂无", "2025-01"]
    with file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header if kind != "columns" else header[:-1])
        writer.writerow(row[:-1] if kind == "incomplete" else row[:-1] + ["2025-13"] if kind == "bad_month" else row)
        if kind == "duplicate":
            writer.writerow(row)
    monkeypatch.setitem(tools.agent_conf, "external_data_path", str(file))
    with pytest.raises(ValueError):
        tools.generate_external_data()


@pytest.mark.parametrize("payloads", [
    [{"status": "1", "geocodes": []}],
    [{"status": "1", "geocodes": [{"city": "测试"}]}],
    [{"status": "1", "geocodes": [{"city": "测试", "adcode": "110000"}]}, {"status": "1", "lives": []}],
    [{"status": "1", "geocodes": [{"city": "测试", "adcode": "110000"}]}, {"status": "1", "lives": [None]}],
])
def test_malformed_weather_is_an_actionable_failure(monkeypatch, payloads):
    monkeypatch.setattr(tools, "_gaode_get", Mock(side_effect=payloads))
    assert "天气查询失败" in tools.get_weather.invoke({"city": "测试"})


def test_location_unavailable(monkeypatch):
    monkeypatch.setattr(tools, "_gaode_get", lambda *args: {"city": [], "province": []})
    assert "请直接提供城市名称" in tools.get_user_location.invoke({})


@pytest.mark.parametrize("code", ["30001", "30002", "30003"])
def test_amap_engine_failure_does_not_blame_valid_key(monkeypatch, code):
    monkeypatch.setenv("AMAP_API_KEY", "SECRET")
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps({"status": "0", "infocode": code, "info": "SECRET"}).encode()
    monkeypatch.setattr(tools, "urlopen", Mock(return_value=response))
    result = tools.get_weather.invoke({"city": "不存在的城市"})
    assert "服务响应失败" in result and code in result
    assert "城市名称" in result and "检查 Key" not in result and "SECRET" not in result


def test_ui_recovery_clear_history_and_session_isolation(monkeypatch):
    from utils import api_client
    from utils.api_client import ApiClientError
    observed = []

    class Stub:
        base_url = "http://testserver"
        def health(self):
            return True
        def chat(self, query, history):
            observed.append((query, list(history)))
            if query == "失败":
                raise ApiClientError("后端暂时不可用")
            if query == "空回答":
                raise ApiClientError("FastAPI 未返回有效回答")
            return {"answer": "测试回答", "tools_used": []}

    monkeypatch.setattr(api_client, "AgentApiClient", Stub)
    app = AppTest.from_file(get_abs_path("app.py")).run()
    app.chat_input[0].set_value("第一轮").run()
    calls_after_first_submit = len(observed)
    app.run()
    assert len(observed) == calls_after_first_submit
    app.chat_input[0].set_value("失败").run()
    assert app.session_state["message"][-1]["role"] == "user"
    assert any("后端暂时不可用" in item.value for item in app.error)
    app.chat_input[0].set_value("恢复").run()
    assert app.session_state["message"][-1]["content"] == "测试回答"
    assert observed[-1][1][0]["content"] == "第一轮"
    app.chat_input[0].set_value("空回答").run()
    assert app.session_state["message"][-1]["role"] == "user"
    assert any("未返回有效回答" in item.value for item in app.error)
    other = AppTest.from_file(get_abs_path("app.py")).run()
    assert other.session_state["message"] == []
    app.button[0].click().run()
    assert app.session_state["message"] == []
    app.chat_input[0].set_value("清空后").run()
    assert observed[-1][1] == []
    assert not app.exception and not other.exception


def test_ui_backend_unavailable_is_actionable(monkeypatch):
    from utils import api_client
    class Stub:
        base_url = "http://127.0.0.1:8000"
        def health(self):
            return False
    monkeypatch.setattr(api_client, "AgentApiClient", Stub)
    app = AppTest.from_file(get_abs_path("app.py")).run()
    assert not app.exception
    assert any("FastAPI 后端未连接" in item.value for item in app.error)
    assert len(app.chat_input) == 1
    assert app.chat_input[0].disabled
