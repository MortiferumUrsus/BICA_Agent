import json
import re
from pathlib import Path

from .errors import ResponseError


def append_jsonl(path, value):
    with Path(path).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class Journal:
    """Append-only source store; instantiated separately for each example and mode."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise ValueError("Refusing to overwrite or reuse a source journal")
        self.path.touch()
        self._chunks = []

    @property
    def chunks(self):
        return [dict(chunk) for chunk in self._chunks]

    @property
    def ids(self):
        return {chunk["chunk_id"] for chunk in self._chunks}

    def append(self, text):
        chunk = {"chunk_id": f"c{len(self._chunks) + 1:03d}", "order": len(self._chunks), "text": text}
        append_jsonl(self.path, chunk)
        self._chunks.append(chunk)
        return dict(chunk)

    def validate_ids(self, ids):
        unknown = set(ids) - self.ids
        if unknown:
            raise ResponseError("Unknown or unread source IDs: " + ", ".join(sorted(unknown)))

    def retrieve(self, query="", source_ids=(), top_k=2):
        if source_ids:
            self.validate_ids(source_ids)
            wanted = list(dict.fromkeys(source_ids))[:min(top_k, 2)]
            lookup = {c["chunk_id"]: c for c in self._chunks}
            return [dict(lookup[i]) for i in wanted]
        words = set(re.findall(r"\w+", query.casefold()))
        if not words:
            return []
        ranked = []
        for chunk in self._chunks:
            tokens = set(re.findall(r"\w+", chunk["text"].casefold()))
            score = len(words & tokens)
            if score:
                ranked.append((score, chunk["order"], chunk))
        ranked.sort(key=lambda item: (-item[0], -item[1]))
        return [dict(c) for _, _, c in ranked[:min(top_k, 2)]]
