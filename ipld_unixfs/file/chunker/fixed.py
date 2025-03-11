from math import floor
from typing import Final, Optional
from .api import StatelessChunker

default_max_chunk_size = 262144


class FixedSizeContext:
    max_chunk_size: int

    def __init__(self, max_chunk_size: int = default_max_chunk_size) -> None:
        self.max_chunk_size = max_chunk_size


class FixedSizeChunker(StatelessChunker[FixedSizeContext]):
    name: Final = "fixed"
    type: Final = "Stateless"

    def __init__(self, max_chunk_size: int = default_max_chunk_size) -> None:
        self.context = FixedSizeContext(max_chunk_size)

    def cut(self, context, buffer, end=False):
        # number of fixed size chunks that would fit
        n = floor(buffer.byte_length / context.max_chunk_size)
        chunks = list(map(lambda _: context.max_chunk_size, range(n)))
        if end:
            chunks.append(buffer.byte_length - n * context.max_chunk_size)
        return chunks
