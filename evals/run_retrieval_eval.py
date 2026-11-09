"""Credentialed Atlas/OpenRouter top-3 retrieval evaluation."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from app.config import settings
from app.kb.embedding import embed_text
from app.kb.retrieval import hybrid_search
from app.models.collections import KbEntries

CORPUS = Path(__file__).parent / "dataset" / "retrieval.jsonl"
TENANT_ID = "retrieval-eval-synthetic"
THRESHOLD = 0.90


def load_corpus() -> list[dict[str, Any]]:
    return [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines()]


def failure_report(error: Exception) -> dict[str, Any]:
    return {
        "adapter_mode": "credentialed",
        "commit": os.environ.get("GITHUB_SHA", "local"),
        "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
        "error": type(error).__name__,
        "passed": False,
    }


async def run() -> dict[str, Any]:
    uri = os.environ.get("VAANI_RETRIEVAL_EVAL_MONGODB_URI", "")
    if not uri or "eval" not in uri.rsplit("/", 1)[-1].split("?", 1)[0].lower():
        raise RuntimeError("VAANI_RETRIEVAL_EVAL_MONGODB_URI must name an eval database")
    if settings.use_mock_adapters:
        raise RuntimeError("credentialed retrieval evaluation cannot use mock adapters")
    if not settings.openrouter_api_key or not settings.llm_model_embedding:
        raise RuntimeError("OpenRouter key and embedding model are required")

    settings.mongodb_uri = uri
    entries = KbEntries(TENANT_ID)
    corpus = load_corpus()
    await entries.delete_many({})
    try:
        for item in corpus:
            text = f"{item['question']}\n{item['answer']}"
            vector = await embed_text(text, input_type="search_document")
            await entries.insert_one(
                {
                    "_id": item["key"],
                    "kind": "faq",
                    "key": item["key"],
                    "question": item["question"],
                    "answer": item["answer"],
                    "embedding": vector,
                    "embedding_model": settings.llm_model_embedding,
                    "embedding_dimensions": len(vector),
                }
            )

        hits = 0
        query_count = 0
        for item in corpus:
            for query in item["queries"]:
                query_count += 1
                results = await hybrid_search(TENANT_ID, query, k=3)
                hits += int(item["key"] in {result["source_ref"] for result in results})

        hit_rate = hits / query_count
        return {
            "adapter_mode": "credentialed",
            "commit": os.environ.get("GITHUB_SHA", "local"),
            "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
            "embedding_model": settings.llm_model_embedding,
            "embedding_dimensions": settings.kb_embedding_dimensions,
            "query_count": query_count,
            "top_k": 3,
            "hits": hits,
            "hit_rate": hit_rate,
            "threshold": THRESHOLD,
            "passed": hit_rate >= THRESHOLD,
        }
    finally:
        await entries.delete_many({})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    failed = False
    try:
        report = asyncio.run(run())
    except Exception as error:
        failed = True
        report = failure_report(error)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    if failed or (args.ci and not report["passed"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
