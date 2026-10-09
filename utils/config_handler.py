"""Project-relative YAML configuration with safe validation errors."""
from pathlib import Path
import yaml
from utils.path_tool import get_abs_path


def _load(path, required, encoding="utf-8"):
    path = Path(get_abs_path(str(path)))
    try:
        conf = yaml.safe_load(path.read_text(encoding=encoding))
    except (OSError, yaml.YAMLError):
        raise ValueError(f"无法读取配置 {path.name}，请检查文件及 YAML 格式") from None
    if not isinstance(conf, dict):
        raise ValueError(f"{path.name} 必须是键值映射")
    for key in required:
        if key not in conf or conf[key] is None or conf[key] == "":
            raise ValueError(f"{path.name} 缺少有效字段：{key}")
    return conf


def load_rag_config(config_path="config/rag.yml", encoding="utf-8"):
    return _load(config_path, ("chat_model_name", "embedding_model_name"), encoding)


def load_chroma_config(config_path="config/chroma.yml", encoding="utf-8"):
    conf = _load(config_path, ("collection_name", "persist_directory", "k", "data_path",
        "md5_hex_store", "allow_knowledge_file_type", "chunk_size", "chunk_overlap", "separators"), encoding)
    for key in ("k", "chunk_size"):
        if type(conf[key]) is not int or conf[key] <= 0:
            raise ValueError(f"{key} 必须为正整数")
    if type(conf["chunk_overlap"]) is not int or not 0 <= conf["chunk_overlap"] < conf["chunk_size"]:
        raise ValueError("chunk_overlap 必须大于等于零且小于 chunk_size")
    for key in ("separators", "allow_knowledge_file_type"):
        if not isinstance(conf[key], list) or not conf[key] or not all(isinstance(x, str) for x in conf[key]):
            raise ValueError(f"{key} 必须为非空字符串列表")
    return conf


def load_prompts_config(config_path="config/prompts.yml", encoding="utf-8"):
    return _load(config_path, ("main_prompt_path", "rag_summarize_prompt_path", "report_prompt_path"), encoding)


def load_agent_config(config_path="config/agent.yml", encoding="utf-8"):
    conf = _load(config_path, ("external_data_path", "gaode_base_url", "gaode_timeout", "demo_user_id"), encoding)
    if conf["gaode_base_url"] != "https://restapi.amap.com":
        raise ValueError("gaode_base_url 必须使用高德官方 HTTPS REST 地址")
    if not isinstance(conf["gaode_timeout"], (int, float)) or conf["gaode_timeout"] <= 0:
        raise ValueError("gaode_timeout 必须大于零")
    if not isinstance(conf["demo_user_id"], str) or not conf["demo_user_id"].isdigit():
        raise ValueError("demo_user_id 必须为数字字符串")
    return conf


rag_conf = load_rag_config()
chroma_conf = load_chroma_config()
prompts_conf = load_prompts_config()
agent_conf = load_agent_config()
