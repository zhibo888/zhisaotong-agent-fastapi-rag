import streamlit as st

from utils.api_client import AgentApiClient, ApiClientError


st.set_page_config(page_title="智扫通 · 智能客服", page_icon="🤖", layout="centered")
st.title("智扫通机器人智能客服")
st.caption("Streamlit · FastAPI · LangChain Agent · RAG 知识库")

client = AgentApiClient()
backend_ready = client.health()

with st.sidebar:
    st.header("运行状态")
    if backend_ready:
        st.success("FastAPI 后端已连接")
    else:
        st.error("FastAPI 后端未连接")
    st.caption(f"API：{client.base_url}")
    st.caption("演示用户：1001。使用记录来自本地样例 CSV，非实时设备遥测。")
    if st.button("清空对话"):
        st.session_state["message"] = []
        st.rerun()
    st.caption("对话仅保存在当前页面会话；刷新或关闭可能丢失。")

st.session_state.setdefault("message", [])
if not st.session_state["message"]:
    st.info("可以咨询机器人维护、查询城市天气，或生成历史月份的样例使用报告。")
    st.markdown("- 知识问答：扫地机器人吸力变弱了怎么办？\n- 天气查询：查询北京市今天的天气。\n- 样例报告：生成用户 1001 在 2025 年 1 月的使用报告。")

if not backend_ready:
    st.warning("请先启动后端：python -m uvicorn api.main:app --host 127.0.0.1 --port 8000")

for message in st.session_state["message"]:
    with st.chat_message(message["role"]):
        if message.get("tools"):
            st.caption("调用工具：" + " → ".join(message["tools"]))
        st.markdown(message["content"])

prompt = st.chat_input(
    "请输入问题，例如：扫地机器人吸力变弱了怎么办？",
    disabled=not backend_ready,
)
if prompt:
    history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state["message"]
    ]
    st.session_state["message"].append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner("智能客服正在查询，请稍候…"):
                result = client.chat(prompt, history)
            if result["tools_used"]:
                st.caption("调用工具：" + " → ".join(result["tools_used"]))
            st.markdown(result["answer"])
            st.session_state["message"].append({
                "role": "assistant",
                "content": result["answer"],
                "tools": result["tools_used"],
            })
        except ApiClientError as exc:
            st.error(str(exc))
