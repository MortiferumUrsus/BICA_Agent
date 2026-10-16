import json
import base64
import hashlib
from functools import lru_cache
from pathlib import Path

import tiktoken


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


@lru_cache(maxsize=1)
def encoding():
    # Bundle the public ranks: offline tests must not make tiktoken's first-use
    # network request, even on a machine with an empty tokenizer cache.
    data = (Path(__file__).parent / "assets" / "cl100k_base.tiktoken").read_bytes()
    if hashlib.sha256(data).hexdigest() != "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7":
        raise ValueError("Bundled cl100k_base ranks failed SHA-256 verification")
    ranks = {base64.b64decode(token): int(rank) for token, rank in (line.split() for line in data.splitlines())}
    return tiktoken.Encoding(
        name="cl100k_base",
        pat_str=r"'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s",
        mergeable_ranks=ranks,
        special_tokens={"<|endoftext|>": 100257, "<|fim_prefix|>": 100258,
                        "<|fim_middle|>": 100259, "<|fim_suffix|>": 100260, "<|endofprompt|>": 100276},
    )


def count(value):
    text = value if isinstance(value, str) else dumps(value)
    return len(encoding().encode(text, disallowed_special=()))


def prefix(text, limit):
    """A Unicode-safe exact prefix. No stripped whitespace or lost token bytes."""
    if not text or limit < 1:
        return ""
    if count(text) <= limit:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if count(text[:mid]) <= limit:
            low = mid
        else:
            high = mid - 1
    return text[:low]


def split_text(text, limit):
    while text:
        part = prefix(text, limit)
        if not part:
            raise ValueError("Token limit cannot fit one character")
        yield part
        text = text[len(part):]
