import json
from pathlib import Path

from rag.evaluation.metrics import normalize_source


VALID_REVIEW_STATUSES = {"draft", "reviewed"}


def load_dataset(path: str | Path, allowed_sources: set[str] | None = None) -> list[dict]:
    path = Path(path)
    samples = []
    seen_ids = set()
    allowed = None if allowed_sources is None else {normalize_source(x) for x in allowed_sources}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            sample = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"第 {line_number} 行不是有效 JSON") from exc
        required = {"id", "question", "relevant_sources", "reference_answer", "evidence", "review_status"}
        if not required.issubset(sample):
            raise ValueError(f"第 {line_number} 行缺少字段：{sorted(required - set(sample))}")
        if not isinstance(sample["id"], str) or not sample["id"].strip() or sample["id"] in seen_ids:
            raise ValueError(f"第 {line_number} 行 id 无效或重复")
        if not isinstance(sample["question"], str) or not sample["question"].strip():
            raise ValueError(f"第 {line_number} 行 question 无效")
        for field in ("reference_answer", "evidence"):
            if not isinstance(sample[field], str) or not sample[field].strip():
                raise ValueError(f"第 {line_number} 行 {field} 无效")
        sources = sample["relevant_sources"]
        if not isinstance(sources, list) or not sources or any(not isinstance(x, str) or not x.strip() for x in sources):
            raise ValueError(f"第 {line_number} 行 relevant_sources 无效")
        if sample["review_status"] not in VALID_REVIEW_STATUSES:
            raise ValueError(f"第 {line_number} 行 review_status 无效")
        normalized = {normalize_source(x) for x in sources}
        if allowed is not None and not normalized.issubset(allowed):
            raise ValueError(f"第 {line_number} 行含索引中不存在的相关来源：{sorted(normalized - allowed)}")
        seen_ids.add(sample["id"])
        samples.append(sample)
    if not samples:
        raise ValueError("评测集为空")
    return samples
