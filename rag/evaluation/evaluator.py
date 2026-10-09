from __future__ import annotations

import csv
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import statistics
import time

from rag.evaluation.metrics import compute_query_metrics


KS = (1, 3, 5)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def evaluate(samples: list[dict], search, include_draft: bool = False) -> dict:
    selected = [s for s in samples if include_draft or s["review_status"] == "reviewed"]
    rows = []
    for sample in selected:
        started = time.perf_counter()
        error = ""
        retrieved_sources = []
        distances = []
        try:
            matches = search(sample["question"], max(KS))
            for document, distance in matches:
                retrieved_sources.append(str(document.metadata.get("source", "")))
                distances.append(None if distance is None else float(distance))
            metrics = compute_query_metrics(retrieved_sources, sample["relevant_sources"], KS)
        except Exception as exc:
            error = type(exc).__name__
            metrics = {f"{name}@{k}": 0.0 for k in KS for name in ("hit", "recall", "mrr")}
        latency_ms = (time.perf_counter() - started) * 1000
        rows.append({
            "id": sample["id"], "question": sample["question"],
            "review_status": sample["review_status"],
            "relevant_sources": sample["relevant_sources"],
            "retrieved_sources": retrieved_sources, "distances": distances,
            "latency_ms": round(latency_ms, 2), "error": error, **metrics,
        })
    aggregate = {}
    for k in KS:
        for name in ("hit", "recall", "mrr"):
            key = f"{name}@{k}"
            aggregate[key] = None if not rows else round(statistics.mean(row[key] for row in rows), 4)
    successful_latencies = [row["latency_ms"] for row in rows if not row["error"]]
    aggregate.update({
        "p50_latency_ms": None if not successful_latencies else round(_percentile(successful_latencies, .5), 2),
        "p95_latency_ms": None if not successful_latencies else round(_percentile(successful_latencies, .95), 2),
        "errors": sum(bool(row["error"]) for row in rows),
    })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "DRAFT" if include_draft else ("REVIEWED" if rows else "PENDING"),
        "dataset_total": len(samples), "evaluated_queries": len(rows),
        "excluded_drafts": len(samples) - len(rows), "ks": list(KS),
        "aggregate": aggregate, "queries": rows, "samples": selected,
    }


def _fmt(value) -> str:
    return "—" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)


def write_outputs(result: dict, output_dir: str | Path, metadata: dict) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    complete = {**result, "retrieval": metadata}
    (output / "summary.json").write_text(json.dumps(complete, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["id", "question", "review_status", "relevant_sources", "retrieved_sources", "distances",
              "latency_ms", "error"] + [f"{name}@{k}" for k in KS for name in ("hit", "recall", "mrr")]
    with (output / "query_results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in result["queries"]:
            writer.writerow({**row,
                "relevant_sources": " | ".join(row["relevant_sources"]),
                "retrieved_sources": " | ".join(row["retrieved_sources"]),
                "distances": " | ".join("" if x is None else f"{x:.6f}" for x in row["distances"]),
            })
    with (output / "answer_review_template.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "question", "reference_answer", "evidence", "answer",
                                                        "correctness_0_2", "evidence_support_0_2",
                                                        "unsupported_content_0_2", "completeness_0_2",
                                                        "reviewer", "notes"])
        writer.writeheader()
        for row in result["queries"][:15]:
            sample = next(item for item in result.get("samples", []) if item["id"] == row["id"])
            writer.writerow({"id": row["id"], "question": row["question"],
                             "reference_answer": sample["reference_answer"], "evidence": sample["evidence"],
                             "answer": "", "correctness_0_2": "", "evidence_support_0_2": "",
                             "unsupported_content_0_2": "", "completeness_0_2": "",
                             "reviewer": "", "notes": ""})
    (output / "answer_review_guide.md").write_text("""# 答案人工评分说明

对模板中的每条问题填写实际 Agent 回答，再由人工依据参考答案和证据评分。所有维度都是 0、1、2 三档，2 分最好。

| 维度 | 0 | 1 | 2 |
|---|---|---|---|
| 正确性 | 错误或答非所问 | 部分正确，存在明显遗漏或小错误 | 关键结论正确 |
| 证据支持 | 与证据冲突或无支持 | 部分内容有证据支持 | 关键陈述都有证据支持 |
| 无依据内容 | 有明显编造或越界结论 | 有轻微或不确定的无依据扩展 | 没有明显无依据内容 |
| 完整性 | 未回应核心问题 | 回应部分要点 | 完整回应问题所需要点 |

模板不预填答案和分数，也不宣称已自动计算答案忠实性。
""", encoding="utf-8")
    agg = result["aggregate"]
    table = "\n".join(
        f"| {k} | {_fmt(agg[f'hit@{k}'])} | {_fmt(agg[f'recall@{k}'])} | {_fmt(agg[f'mrr@{k}'])} |"
        for k in KS
    )
    failed = [row for row in result["queries"] if row["hit@5"] == 0 and not row["error"]]
    failure_lines = "\n".join(
        f"- `{row['id']}`：{row['question']}；Top-5 来源：{', '.join(row['retrieved_sources']) or '空结果'}"
        for row in failed[:5]
    ) or "- 无 Hit@5 失败样本。"
    report = f"""# RAG 检索评测报告

状态：**{result['status']}**。数据集共 {result['dataset_total']} 条，本次评测 {result['evaluated_queries']} 条，排除草案 {result['excluded_drafts']} 条。

| K | Hit@K | Recall@K | MRR@K |
|---:|---:|---:|---:|
{table}

- 成功查询延迟 P50：{_fmt(agg['p50_latency_ms'])} ms
- 成功查询延迟 P95：{_fmt(agg['p95_latency_ms'])} ms
- 查询错误：{agg['errors']}
- 相关性粒度：文档来源；K 按原始切片排名计算，重复来源不重复增加 Recall。
- 分数语义：Chroma distance，越小越相似；指标只使用排名，不把 distance 当概率。
- 索引签名：`{metadata.get('index_signature', 'unknown')}`
- 向量数：{metadata.get('vector_count', 'unknown')}
- 来源：{', '.join(metadata.get('sources', [])) or 'unknown'}

`DRAFT` 表示相关性标签尚未人工复核，结果仅用于工程诊断；正式结论应使用 `reviewed` 样本。

## 典型检索失败案例

{failure_lines}

## 误差分析

- 当前只把 `demo_knowledge.txt` 标为相关来源；本机另有 6 份内容相近的旧资料，它们可能语义相关但未被草案标签计为相关，因此指标较保守。
- 标签采用文档级粒度，只能确认来源，不能证明具体片段完整覆盖答案证据。
- Baseline 使用纯向量 Top-K，没有阈值、关键词混合检索或 Rerank；相似主题会竞争有限名额。
- 200 字符分块可能把问题所需的完整步骤拆开，或者让短标题与长正文的表示权重不同。

## 后续改进

1. 人工逐条核对问题、参考答案、证据和所有真实相关来源，再将 `review_status` 改为 `reviewed`。
2. 用仅包含可公开资料的独立索引运行正式基线，避免授权不明旧资料干扰。
3. 保留相同数据集、索引版本和 K，增加 Rerank 后重复评测并比较逐题差异；不得只报告更高的汇总值。
4. 若补齐稳定 chunk ID，可增加片段级标签，并分别报告文档级与片段级指标。
"""
    (output / "rag_evaluation_report.md").write_text(report, encoding="utf-8")
    _write_svg({**agg, "status": result["status"]}, output / "metrics.svg")


def _write_svg(aggregate: dict, path: Path) -> None:
    width, height = 720, 380
    colors = {"hit": "#2563eb", "recall": "#16a34a", "mrr": "#9333ea"}
    bars = []
    labels = []
    x = 72
    for k in KS:
        for name in ("hit", "recall", "mrr"):
            value = aggregate.get(f"{name}@{k}") or 0
            bar_height = value * 240
            y = 300 - bar_height
            bars.append(f'<rect x="{x}" y="{y:.1f}" width="28" height="{bar_height:.1f}" fill="{colors[name]}" rx="3"/>')
            labels.append(f'<text x="{x + 14}" y="320" text-anchor="middle" font-size="12">{html.escape(name)}@{k}</text>')
            x += 68
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/><text x="30" y="30" font-family="sans-serif" font-size="20" font-weight="bold">RAG Retrieval Metrics</text>
<line x1="55" y1="60" x2="55" y2="300" stroke="#475569"/><line x1="55" y1="300" x2="690" y2="300" stroke="#475569"/>
<text x="18" y="65" font-family="sans-serif" font-size="12">1.0</text><text x="25" y="304" font-family="sans-serif" font-size="12">0</text>
{''.join(bars)}{''.join(labels)}
<text x="55" y="355" font-family="sans-serif" font-size="12" fill="#64748b">Status: {html.escape(str(aggregate.get('status', 'see report')))}</text></svg>'''
    path.write_text(svg, encoding="utf-8")
