from __future__ import annotations

import json

from evals.run_evals import DATASET_LABEL, write_report


def test_eval_report_is_summary_only_and_uses_stable_corpus_path(tmp_path) -> None:
    output = tmp_path / "report.json"
    write_report(
        output,
        {
            "pass": True,
            "case_count": 1,
            "language_metrics": {"en": {"accuracy": 1.0, "macro_f1": 1.0}},
            "hallucination_incidents": 0,
            "ungrounded_responses": 0,
            "results": [{"case": {"text": "private fixture"}, "response": "private"}],
        },
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["corpus"]["path"] == DATASET_LABEL
    assert "results" not in report
    assert "private" not in output.read_text(encoding="utf-8")
