"""The seven original tools, with explicit demo identity and safe API failures."""
import csv
from datetime import datetime
from functools import lru_cache
import json
import os
import re
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError
from langchain_core.tools import tool
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


class AmapError(RuntimeError):
    """A sanitized error safe to display to a user."""


def _gaode_get(path: str, params: dict) -> dict:
    key = os.environ.get("AMAP_API_KEY", "").strip()
    if not key:
        raise AmapError("未配置 AMAP_API_KEY，无法查询真实定位或天气")
    url = agent_conf["gaode_base_url"] + path + "?" + urlencode({**params, "key": key})
    try:
        with urlopen(url, timeout=agent_conf["gaode_timeout"]) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise AmapError(f"高德 HTTP 请求失败（状态码 {exc.code}）") from None
    except Exception:
        # URL-bearing exception messages must never be logged or returned.
        raise AmapError("高德网络超时、连接失败或响应不是有效 JSON") from None
    if not isinstance(data, dict):
        raise AmapError("高德响应格式异常")
    if data.get("status") != "1":
        code = str(data.get("infocode", ""))
        code = code if re.fullmatch(r"\d{5,6}", code) else "未知"
        if code.startswith("300"):
            raise AmapError(f"高德服务响应失败（错误码 {code}），请检查城市名称或请求参数，稍后重试")
        raise AmapError(f"高德拒绝请求（错误码 {code}），请检查 Key 与服务权限")
    return data


def _resolve_city_to_adcode(city: str) -> tuple[str, str]:
    data = _gaode_get("/v3/geocode/geo", {"address": city})
    results = data.get("geocodes")
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise AmapError("未找到城市，请提供更完整的城市名称")
    first = results[0]
    if not first.get("adcode"):
        raise AmapError("城市解析没有返回行政区编码")
    name = first.get("city") or first.get("district") or city
    if isinstance(name, list):
        name = "".join(str(x) for x in name)
    return str(name), str(first["adcode"])


@tool
def get_weather(city: str) -> str:
    """通过高德 REST API 查询指定城市的实时天气、温度、湿度及风力。"""
    if not city.strip():
        return "未提供城市名称，无法查询天气"
    try:
        name, adcode = _resolve_city_to_adcode(city.strip())
        data = _gaode_get("/v3/weather/weatherInfo", {"city": adcode, "extensions": "base"})
        if not data.get("lives"):
            raise AmapError("高德未返回该城市的实况天气")
        live = data["lives"][0]
        return (f"城市{name}天气为{live.get('weather', '未知')}，气温{live.get('temperature', '未知')}摄氏度，"
                f"空气湿度{live.get('humidity', '未知')}%，{live.get('winddirection', '未知')}风"
                f"{live.get('windpower', '未知')}级，数据发布时间{live.get('reporttime', '未知')}。")
    except AmapError as exc:
        return f"天气查询失败：{exc}"
    except Exception as exc:
        logger.warning("天气响应处理失败：%s", type(exc).__name__)
        return "天气查询失败：高德响应格式异常"


@tool
def get_user_location() -> str:
    """高德 IP 定位服务端出口城市；不是浏览器 GPS，代理或部署会影响结果。"""
    try:
        data = _gaode_get("/v3/ip", {})
        city = data.get("city") or data.get("province")
        if isinstance(city, list):
            city = "".join(str(x) for x in city)
        if not city:
            raise AmapError("无法确定出口城市，请直接提供城市名称")
        return f"{city}（服务端出口 IP 定位，仅供参考）"
    except AmapError as exc:
        return f"定位失败：{exc}"
    except Exception as exc:
        logger.warning("定位响应处理失败：%s", type(exc).__name__)
        return "定位失败：高德响应格式异常"


@lru_cache(maxsize=1)
def get_rag_service():
    from rag.rag_service import RagSummarizeService
    return RagSummarizeService()


@tool
def rag_summarize(query: str) -> str:
    """从本地机器人知识库检索资料，并通过通义千问总结；输入非空问题。"""
    if not query.strip():
        raise ValueError("知识库问题不能为空")
    return get_rag_service().rag_summarize(query.strip())


@tool
def get_user_id() -> str:
    """返回配置中的固定演示用户 ID；本项目未实现真实登录或身份认证。"""
    return agent_conf["demo_user_id"]


@tool
def get_current_month() -> str:
    """返回服务器本地时钟的当前月份，格式 YYYY-MM；不会随机选择历史月份。"""
    return datetime.now().strftime("%Y-%m")


def generate_external_data():
    """Read the original local sample CSV on every request (no stale global cache)."""
    records = {}
    required = {"用户ID", "特征", "清洁效率", "耗材", "对比", "时间"}
    with open(get_abs_path(agent_conf["external_data_path"]), encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("使用记录 CSV 缺少必要列")
        for row in reader:
            if any(row.get(k) is None for k in required):
                raise ValueError("使用记录 CSV 存在不完整行")
            uid, month = row["用户ID"], row["时间"]
            if not re.fullmatch(r"\d+", uid) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
                raise ValueError("使用记录 CSV 的用户 ID 或月份格式错误")
            if month in records.get(uid, {}):
                raise ValueError("使用记录 CSV 存在重复用户月份")
            records.setdefault(uid, {})[month] = {
                "特征": row["特征"], "效率": row["清洁效率"],
                "耗材": row["耗材"], "对比": row["对比"],
            }
    return records


@tool
def fetch_external_data(user_id: str, month: str) -> str:
    """读取本地样例 CSV 的指定用户和月份记录；user_id 为数字字符串，month 为 YYYY-MM。"""
    if not re.fullmatch(r"\d+", user_id):
        raise ValueError("user_id 必须为数字字符串")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("month 必须为 YYYY-MM 格式")
    data = generate_external_data().get(user_id, {}).get(month)
    if data is None:
        return "未找到该用户在指定月份的样例使用记录；不能据此推断实际使用情况"
    return json.dumps({"数据来源": "本地样例 CSV（非实时设备遥测）",
                       "用户ID": user_id, "月份": month, **data}, ensure_ascii=False)


@tool
def fill_context_for_report() -> str:
    """进入本次请求的报告模式，触发动态系统提示词；无参数。"""
    return "已进入样例设备使用报告模式"
