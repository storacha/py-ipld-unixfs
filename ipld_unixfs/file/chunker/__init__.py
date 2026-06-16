from typing import Generic, TypeVar
from dataclasses import dataclass

from . import interfaces as ChunkerAPI, buffer as BufferQueue
from ipld_unixfs.writer.utils import EMPTY


T = TypeVar("T")

@dataclass
class Config(Generic[T]):
    chunker: ChunkerAPI.Chunker[T]


@dataclass
class Chunker(Generic[T]):
    buffer: BufferQueue.BufferView
    config: Config[T]


@dataclass
class ChunkerWithChunks(Chunker[T]):
    chunks: list[ChunkerAPI.Chunk]


def open(config: Config[T]) -> Chunker[T]:
    return Chunker(buffer=BufferQueue.empty(), config=config)


def write(state: Chunker[T], bytes_data: bytes) -> ChunkerWithChunks[T]:
    if len(bytes_data) > 0:
        return split(state.config, state.buffer.push(memoryview(bytes_data)), False)
    else:
        return ChunkerWithChunks(buffer=state.buffer, config=state.config, chunks=EMPTY)

def close(state: Chunker[T]) -> ChunkerWithChunks[T]:
    return split(state.config, buffer=state.buffer, end=True)


def split(config: Config[T], buffer: BufferQueue.BufferView, end: bool) -> ChunkerWithChunks[T]:
    chunker = config.chunker
    chunks: list[ChunkerAPI.Chunk] = []

    offset = 0
    for size in chunker.cut(chunker.context, buffer, end):
        # we may be splitting an empty buffer, in this case there will be no
        # chunks in it so we make sure that we do not emit empty buffer
        if size > 0:
            chunk = buffer[offset:offset + size]
            chunks.append(chunk)
            offset += size

    return ChunkerWithChunks(config=config, buffer=buffer[offset:], chunks=chunks)
