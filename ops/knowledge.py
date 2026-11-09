"""Check Vaani's narrow OKF authoring profile and detect source drift; stdlib only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


def fingerprint(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    return hashlib.sha256(text.encode()).hexdigest()


def read_concept(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("missing frontmatter delimiters")
    header, body = text[4:].split("\n---\n", 1)
    metadata = {}
    for line in header.splitlines():
        key, value = line.split(":", 1)
        if key in metadata:
            raise ValueError(f"duplicate metadata key: {key}")
        metadata[key] = json.loads(value)
    if not isinstance(metadata.get("type"), str) or not metadata["type"].strip():
        raise ValueError("type must be a non-empty string")
    return metadata, body


def contained(root: Path, value: str) -> Path:
    target = (root / value).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes root: {value}")
    return target


def check(root: Path) -> list[str]:
    bundle = root / "docs/knowledge"
    errors = []
    if not (bundle / "index.md").is_file():
        return ["missing knowledge index"]
    for path in sorted(bundle.rglob("*.md")):
        try:
            body = path.read_text(encoding="utf-8")
            if path.name not in {"index.md", "log.md"}:
                meta, body = read_concept(path)
                paths, hashes = meta["source_paths"], meta["source_hashes"]
                if (
                    not isinstance(paths, list)
                    or not paths
                    or set(paths) != set(hashes)
                ):
                    raise ValueError("source paths and fingerprints must match")
                for source in paths:
                    if fingerprint(contained(root, source)) != hashes[source]:
                        errors.append(f"{path.stem}: source changed: {source}")
            for link in re.findall(r"\[[^\]\n]*\]\(([^)\s]+)\)", body):
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                target = unquote(parsed.path)
                resolved = (
                    contained(bundle, target.lstrip("/"))
                    if target.startswith("/")
                    else contained(
                        bundle, str(path.parent.relative_to(bundle) / target)
                    )
                )
                if not resolved.is_file():
                    errors.append(f"{path.stem}: missing link: {link}")
        except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
            errors.append(f"{path.name}: {exc}")
    return errors


def refresh(root: Path, concept: str) -> None:
    """Record reviewed source versions, without claiming human verification."""
    bundle = root / "docs/knowledge"
    path = contained(bundle, concept + ".md")
    meta, body = read_concept(path)
    meta["source_hashes"] = {
        source: fingerprint(contained(root, source)) for source in meta["source_paths"]
    }
    meta["source_commit"] = "working-tree; see source_hashes"
    meta["generated"] = {
        "by": "process:knowledge-refresh",
        "at": datetime.now(UTC).isoformat(),
    }
    meta["status"] = "draft"
    meta.pop("verified", None)
    header = "\n".join(
        f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in meta.items()
    )
    path.write_text(f"---\n{header}\n---\n{body}", encoding="utf-8")
    print(f"Refreshed {concept}; review prose and immutable source links in the diff.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "refresh"])
    parser.add_argument("concept", nargs="?")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    if args.command == "refresh":
        if not args.concept:
            parser.error("refresh requires a reviewed concept ID")
        refresh(args.root, args.concept)
    errors = check(args.root)
    for error in errors:
        print(error)
    print(
        f"Knowledge check: {len(errors)} issue(s). Does not establish runtime readiness."
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
