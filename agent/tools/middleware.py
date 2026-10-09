from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt
from langchain_core.messages import ToolMessage
from utils.prompt_loader import load_system_prompts, load_report_prompts
from utils.logger_handler import logger
from utils.errors import UserFacingError


@wrap_tool_call
def monitor_tool(request, handler):
    name = request.tool_call["name"]
    logger.info("调用工具：%s", name)
    context = request.runtime.context
    if name == "fetch_external_data" and not context.get("report", False):
        return ToolMessage(content="请先调用 fill_context_for_report 进入报告模式，再查询记录。",
                           tool_call_id=request.tool_call["id"], name=name, status="error")
    try:
        result = handler(request)
        if name == "fill_context_for_report" and getattr(result, "status", None) != "error":
            context["report"] = True
        logger.info("工具完成：%s", name)
        return result
    except UserFacingError as exc:
        logger.warning("工具不可用：%s", name)
        return ToolMessage(content=str(exc), tool_call_id=request.tool_call["id"], name=name, status="error")
    except Exception as exc:
        # Log only the exception type: SDK errors can include URLs or credentials.
        logger.warning("工具失败：%s (%s)", name, type(exc).__name__)
        return ToolMessage(content=f"工具 {name} 执行失败（{type(exc).__name__}）。请检查参数、配置、知识库初始化或网络后重试。",
                           tool_call_id=request.tool_call["id"], name=name, status="error")


@before_model
def log_before_model(state, runtime):
    logger.info("即将调用模型：消息数=%s，报告模式=%s",
                len(state["messages"]), bool(runtime.context.get("report", False)))


@dynamic_prompt
def report_prompt_switch(request):
    if request.runtime.context.get("report", False):
        return load_report_prompts()
    return load_system_prompts()
