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
    format_retries: int = 0

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for k, v in asdict(self).items() if k != "format_retries"):
            raise ValueError("All limits must be positive integers")
        if type(self.format_retries) is not int or not 0 <= self.format_retries <= 2:
            raise ValueError("format_retries must be between 0 and 2")
        if self.max_retrieval_rounds != 1 or self.retrieval_top_k > 2:
            raise ValueError("MVP supports one retrieval round and at most two chunks")
        if self.max_output_tokens >= self.window_ref_tokens:
            raise ValueError("Output reserve must be smaller than the application window")

    def to_dict(self):
        return asdict(self)
