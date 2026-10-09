from pathlib import Path


def normalize_source(source: str) -> str:
    return Path(str(source).replace("\\", "/")).name.casefold()


def _unique_sources(retrieved_sources: list[str]) -> list[str]:
    seen = set()
    result = []
    for source in retrieved_sources:
        normalized = normalize_source(source)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def first_relevant_rank(retrieved_sources: list[str], relevant_sources: list[str], k: int) -> int | None:
    relevant = {normalize_source(source) for source in relevant_sources}
    for rank, source in enumerate((normalize_source(item) for item in retrieved_sources[:k]), 1):
        if source in relevant:
            return rank
    return None


def compute_query_metrics(retrieved_sources: list[str], relevant_sources: list[str], ks=(1, 3, 5)) -> dict:
    if not relevant_sources or any(not str(source).strip() for source in relevant_sources):
        raise ValueError("relevant_sources 必须包含至少一个有效来源")
    relevant = {normalize_source(source) for source in relevant_sources}
    retrieved = [normalize_source(source) for source in retrieved_sources]
    metrics = {}
    for k in ks:
        if not isinstance(k, int) or k < 1:
            raise ValueError("k 必须是正整数")
        top = retrieved[:k]
        found = relevant.intersection(set(top))
        rank = first_relevant_rank(retrieved, list(relevant), k)
        metrics[f"hit@{k}"] = 1.0 if found else 0.0
        metrics[f"recall@{k}"] = len(found) / len(relevant)
        metrics[f"mrr@{k}"] = 0.0 if rank is None else 1.0 / rank
    return metrics
