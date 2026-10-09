import argparse
from pathlib import Path

from rag.evaluation.dataset import load_dataset
from rag.evaluation.evaluator import evaluate, write_outputs
from rag.vector_store import VectorStoreService
from utils.path_tool import get_abs_path


def main():
    parser = argparse.ArgumentParser(description="Evaluate the current Chroma retrieval path.")
    parser.add_argument("--dataset", default=get_abs_path("data/evaluation/rag_eval.jsonl"))
    parser.add_argument("--output-dir", default=get_abs_path("reports/rag_evaluation"))
    parser.add_argument("--include-draft", action="store_true", help="Run unreviewed labels as an exploratory DRAFT evaluation.")
    args = parser.parse_args()
    store = VectorStoreService()
    metadata_rows = store.vector_store.get(include=["metadatas"])["metadatas"]
    sources = sorted({Path(row.get("source", "")).name for row in metadata_rows if row.get("source")})
    samples = load_dataset(args.dataset, set(sources))
    result = evaluate(samples, store.search, include_draft=args.include_draft)
    metadata = {
        "index_signature": store.signature, "vector_count": store.count(),
        "embedding_model": store.vector_store._collection.metadata.get("embedding_model"),
        "top_k_values": [1, 3, 5], "sources": sources,
        "chunk_size": store.conf["chunk_size"], "chunk_overlap": store.conf["chunk_overlap"],
    }
    write_outputs(result, args.output_dir, metadata)
    print(f"status={result['status']} queries={result['evaluated_queries']} errors={result['aggregate']['errors']}")
    print(Path(args.output_dir).resolve())


if __name__ == "__main__":
    main()
