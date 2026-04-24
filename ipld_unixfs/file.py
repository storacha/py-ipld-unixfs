from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from actress import task

# from actress import task
#
# from ipld_unixfs import unixfs, codec
from ipld_unixfs.file import interfaces as API, writer as Writer
from ipld_unixfs.file.chunker.fixed import FixedSizeChunker

LayoutT = TypeVar("LayoutT")
T = TypeVar("T")

@dataclass
class UnixFSLeaf():
    code: Literal[0x70] = 0x70
    name: Literal["UnixFS"] = "UnixFS"

class FileEncoderSettings(Generic[LayoutT, T]):
    chunker: FixedSizeChunker
    file_chunk_encoder: UnixFSLeaf


def defaults() -> API.EncoderSettings:
    ...


class Metadata():
    ...


async def write(view: API.View[T, T, LayoutT], bytes_data: bytes):
    await perform(view, task.send(Writer.WriteMessage(type="write", bytes_data=bytes_data)))
    return view


async def perform(view: API.View[T, T, LayoutT], effect: task.Effect[Writer.Message]):
    def next_effect(message: Writer.Message):
        state, effect = Writer.update(message, view.state)
        view.state = state
        return effect
    task.fork(
        task.loop(init=effect, next_=next_effect)
    )


class FileWriterView(API.View[T, T, LayoutT]):
    def __init__(self, state: Writer.State) -> None:
        self.state = state

    @property
    def writer(self) -> API.BlockWriter:
        return self.state.writer

    @property
    def settings(self) -> API.EncoderSettings[LayoutT, T]:
        return self.state.config

    async def write(self, bytes_data: bytes) -> API.View[T, T, LayoutT]:
        return await write(self, bytes_data)

    async def close(self, options: API.CloseOptions) -> unixfs.FileLink:
        ...


def create(writer, metadata=Metadata(), settings=defaults()) -> FileWriterView:
    ...
