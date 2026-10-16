from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Config:
    window_ref_tokens: int = 4096
    memory_ref_tokens: int = 512
    state_ref_tokens: int = 256
    chunk_ref_tokens: int = 1024
    max_output_tokens: int = 768
    max_retrieval_rounds: int = 1
    retrieval_top_k: int = 2
    max_api_calls: int = 200

    def __post_init__(self):
        if any(not isinstance(v, int) or v <= 0 for v in asdict(self).values()):
            raise ValueError("All limits must be positive integers")
        if self.max_retrieval_rounds != 1 or self.retrieval_top_k > 2:
            raise ValueError("MVP supports one retrieval round and at most two chunks")
        if self.max_output_tokens >= self.window_ref_tokens:
            raise ValueError("Output reserve must be smaller than the application window")

    def to_dict(self):
        return asdict(self)
