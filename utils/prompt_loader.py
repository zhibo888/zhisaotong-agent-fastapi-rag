from pathlib import Path
from utils.config_handler import prompts_conf
from utils.path_tool import get_abs_path


def _read(key):
    text = Path(get_abs_path(prompts_conf[key])).read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("提示词文件不能为空")
    return text


def load_system_prompts():
    return _read("main_prompt_path")


def load_rag_prompts():
    return _read("rag_summarize_prompt_path")


def load_report_prompts():
    return _read("report_prompt_path")
