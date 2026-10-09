import json

import pytest
from langchain_core.documents import Document

from rag.evaluation.dataset import load_dataset
from rag.evaluation.evaluator import evaluate
from rag.evaluation.metrics import compute_query_metrics, first_relevant_rank


def test_first_result_relevant():
    metrics = compute_query_metrics(["a.txt", "b.txt"], ["a.txt"])
    assert metrics["hit@1"] == metrics["recall@1"] == metrics["mrr@1"] == 1.0


def test_second_result_relevant():
    metrics = compute_query_metrics(["x.txt", "a.txt"], ["a.txt"])
    assert metrics["hit@1"] == 0 and metrics["mrr@1"] == 0
    assert metrics["hit@3"] == 1 and metrics["mrr@3"] == 0.5


def test_no_relevant_result():
    assert all(value == 0 for value in compute_query_metrics(["x.txt"], ["a.txt"]).values())


def test_multiple_relevant_sources_and_recall():
    metrics = compute_query_metrics(["a.txt", "x.txt", "b.txt"], ["a.txt", "b.txt"])
    assert metrics["recall@1"] == 0.5
    assert metrics["recall@3"] == 1.0
    assert metrics["mrr@3"] == 1.0


def test_duplicate_retrieved_sources_are_deduplicated():
    metrics = compute_query_metrics(["x.txt", "x.txt", "a.txt"], ["a.txt"])
    assert metrics["hit@1"] == 0
    assert metrics["hit@3"] == 1
    assert metrics["mrr@3"] == pytest.approx(1 / 3)


def test_empty_and_k_larger_than_results():
    metrics = compute_query_metrics([], ["a.txt"])
    assert metrics["hit@5"] == metrics["recall@5"] == metrics["mrr@5"] == 0
    assert first_relevant_rank(["A.TXT"], ["folder/a.txt"], 5) == 1


@pytest.mark.parametrize("labels", [[], [""], ["   "]])
def test_invalid_relevance_labels(labels):
    with pytest.raises(ValueError):
        compute_query_metrics(["a.txt"], labels)


def test_dataset_rejects_unknown_source(tmp_path):
    path = tmp_path / "eval.jsonl"
    path.write_text(json.dumps({"id": "1", "question": "q", "relevant_sources": ["unknown.txt"],
                                "reference_answer": "a", "evidence": "e",
                                "review_status": "reviewed"}), encoding="utf-8")
    with pytest.raises(ValueError, match="不存在"):
        load_dataset(path, {"known.txt"})


def test_draft_filter_and_query_error():
    samples = [
        {"id": "1", "question": "ok", "relevant_sources": ["a.txt"], "reference_answer": "a", "evidence": "e", "review_status": "reviewed"},
        {"id": "2", "question": "draft", "relevant_sources": ["a.txt"], "reference_answer": "a", "evidence": "e", "review_status": "draft"},
        {"id": "3", "question": "bad", "relevant_sources": ["a.txt"], "reference_answer": "a", "evidence": "e", "review_status": "reviewed"},
    ]
    def search(query, top_k):
        assert top_k == 5
        if query == "bad":
            raise RuntimeError("do not expose")
        return [(Document(page_content="x", metadata={"source": "a.txt"}), 0.1)]
    result = evaluate(samples, search)
    assert result["status"] == "REVIEWED" and result["evaluated_queries"] == 2
    assert result["excluded_drafts"] == 1 and result["aggregate"]["errors"] == 1
    assert result["queries"][-1]["error"] == "RuntimeError"
    assert "do not expose" not in str(result)
    draft = evaluate(samples, search, include_draft=True)
    assert draft["status"] == "DRAFT" and draft["evaluated_queries"] == 3
