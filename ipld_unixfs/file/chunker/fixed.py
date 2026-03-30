from math import floor
from ipld_unixfs.file.chunker.api import Chunk, StatelessChunker

DEFAULT_MAX_CHUNK_SIZE = 262144


class FixedSizeContext:
    max_chunk_size: int

    def __init__(self, max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE) -> None:
        self.max_chunk_size = max_chunk_size


class FixedSizeChunker(StatelessChunker[FixedSizeContext]):
    name = "fixed"
    type = "Stateless"

    def __init__(self, max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE) -> None:
        self.context = FixedSizeContext(max_chunk_size)

    def cut(
        self, context: FixedSizeContext, buffer: Chunk, end: bool = False
    ) -> list[int]:
        # number of fixed size chunks that would fit, and whatever else is left
        n, remainder = divmod(buffer.byte_length, context.max_chunk_size)
        chunks = [context.max_chunk_size] * n
        if end and remainder > 0:
            chunks.append(remainder)
        return chunks
