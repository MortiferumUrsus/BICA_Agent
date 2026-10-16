class MemoryExperimentError(Exception):
    """An expected experiment failure, safe to show without credentials."""


class LimitError(MemoryExperimentError):
    pass


class ResponseError(MemoryExperimentError):
    pass


class APIError(MemoryExperimentError):
    pass
