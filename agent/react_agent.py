from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from model.factory import get_chat_model
from agent.tools.agent_tools import (
    rag_summarize, get_weather, get_user_location, get_user_id,
    get_current_month, fetch_external_data, fill_context_for_report,
)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch

TOOLS = [rag_summarize, get_weather, get_user_location, get_user_id,
         get_current_month, fetch_external_data, fill_context_for_report]


class ReactAgent:
    def __init__(self, model=None):
        self.agent = create_agent(
            model=model if model is not None else get_chat_model(),
            tools=TOOLS,
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def execute_stream(self, query: str, history=None, on_tool=None):
        """Yield final AI answers only; pass prior user/assistant turns to the model."""
        if not query.strip():
            raise ValueError("问题不能为空")
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in (history or [])
            if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
        ]
        messages.append({"role": "user", "content": query})
        seen = set()
        for update in self.agent.stream(
            {"messages": messages}, stream_mode="updates",
            context={"report": False}, config={"recursion_limit": 30},
        ):
            for state in update.values():
                if not isinstance(state, dict):
                    continue
                for message in state.get("messages", []):
                    if not isinstance(message, AIMessage):
                        continue
                    if message.tool_calls:
                        if on_tool:
                            for call in message.tool_calls:
                                marker = call.get("id") or str(call)
                                if marker not in seen:
                                    seen.add(marker)
                                    on_tool(call["name"])
                        continue
                    content = message.content
                    if isinstance(content, list):
                        content = "".join(
                            x if isinstance(x, str) else x.get("text", "")
                            for x in content if isinstance(x, (str, dict))
                        )
                    if content and content.strip():
                        yield content.strip()
