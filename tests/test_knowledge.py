"""Offline integrity and source-drift regression; no application imports."""

import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "knowledge", Path(__file__).resolve().parents[1] / "ops/knowledge.py"
)
knowledge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(knowledge)


def test_graph_integrity_and_drift(tmp_path):
    bundle = tmp_path / "docs/knowledge"
    bundle.mkdir(parents=True)
    (bundle / "index.md").write_text("[Example](example.md)", encoding="utf-8")
    source = tmp_path / "source.py"
    source.write_text("original\n", encoding="utf-8")
    meta = {
        "type": "Subsystem",
        "source_paths": ["source.py"],
        "source_hashes": {"source.py": hashlib.sha256(b"original\n").hexdigest()},
    }
    concept = bundle / "example.md"
    header = "\n".join(f"{k}: {json.dumps(v)}" for k, v in meta.items())
    concept.write_text(f"---\n{header}\n---\n# Example\n", encoding="utf-8")
    assert knowledge.check(tmp_path) == []
    source.write_text("changed\n", encoding="utf-8")
    assert any("source changed" in issue for issue in knowledge.check(tmp_path))
    knowledge.refresh(tmp_path, "example")
    assert knowledge.check(tmp_path) == []
    concept.write_text(
        concept.read_text(encoding="utf-8") + "[Missing](missing.md)", encoding="utf-8"
    )
    assert any("missing link" in issue for issue in knowledge.check(tmp_path))
    try:
        knowledge.refresh(tmp_path, "../../escape")
    except ValueError:
        pass
    else:
        raise AssertionError("refresh allowed a path outside the bundle")
