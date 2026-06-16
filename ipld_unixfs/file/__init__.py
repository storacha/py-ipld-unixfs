from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar, Optional, TYPE_CHECKING

import actress as Task
from multiformats import multihash

from ipld_unixfs import codec, unixfs
from . import interfaces as API, writer as Writer
from .chunker.fixed import FixedSizeChunker, with_max_chunk_size
from .layout import balanced

from .interfaces import (
    FileChunkEncoder,
    FileEncoder,
    Linker,
    EncoderSettings,
    EncodedFile,
    CloseOptions,
    BlockWriter,
    WriteableBlockStream,
    Writer as FileWriter,
    View,
    Options
)

if TYPE_CHECKING:
    from .writer import State

LayoutT = TypeVar("LayoutT")
T = TypeVar("T")

@dataclass
class UnixFSLeaf():
    code: Literal[0x70] = 0x70
    name: str = "UnixFS"

    def encode(self, data: bytes) -> memoryview:
        return codec.encode_file_chunk(content=data)

@dataclass
class UnixFSRawLeaf():
    code: Literal[0x70] = 0x70
    name: str = "UnixFS"

    def encode(self, data: bytes) -> memoryview:
        return codec.encode_raw(content=data)


class FileEncoderSettings(Generic[LayoutT, T]):
    chunker: FixedSizeChunker
    file_chunk_encoder: UnixFSLeaf


def defaults() -> API.EncoderSettings:
    sha2_256 = multihash.get("sha2-256")
    return API.EncoderSettings(
        chunker=FixedSizeChunker(),
        file_chunk_encoder=UnixFSLeaf(),
        small_file_encoder=UnixFSLeaf(),
        file_encoder=API.FileEncoder(),
        file_layout=balanced,
        hasher=sha2_256,
        linker=API.Linker()
    )

def configure(settings: Optional[API.EncoderSettings] = None, **kwargs) -> API.EncoderSettings:
    base = settings or defaults()
    for key, value in kwargs.items():
        if hasattr(base, key):
            setattr(base, key, value)
    return base


class Metadata():
    ...


async def write(view: API.View[T, T, LayoutT], bytes_data: bytes) -> API.View:
    await perform(view, Task.send(Writer.WriteMessage(type="write", bytes_data=bytes_data)))
    return view


async def close(view: API.View[T, T, LayoutT], options: API.CloseOptions) -> unixfs.FileLink:
    await perform(view, Task.send(Writer.CloseMessage(type="close")))
    state = view.state
    if state.status == "linked":
        if options.close_writer:
            await view.state.writer.close()
        elif options.release_lock:
            view.state.writer.release_lock()
        return state.link
    else:
        class InvalidStateError(RuntimeError):
            pass
        raise InvalidStateError(
            f"Expected writer to be in 'linked' state after close, but it is in"
            f" {view.state.status} instead"
        )


def perform(
    view: API.View[T, T, LayoutT],
    effect: Task.Effect[Writer.Message]
) -> Task.Fork[None, Exception, None]:
    def next_effect(message: Writer.Message):
        update = Writer.update(message, view.state)
        view.state = update.state
        return update.effect
    return Task.fork(
        Task.loop(init=effect, next_=next_effect)
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
        return await close(self, options)


def create(options: API.Options[LayoutT, T]) -> API.View[LayoutT, T, T]:
    return FileWriterView(state=Writer.init(options.writer, options.metadata, options.settings))

__all__ = [
    "FileChunkEncoder",
    "FileEncoder",
    "Linker",
    "EncoderSettings",
    "EncodedFile",
    "CloseOptions",
    "BlockWriter",
    "WriteableBlockStream",
    "FileWriter",
    "View",
    "Options",
    "UnixFSLeaf",
    "UnixFSRawLeaf",
    "FileEncoderSettings",
    "defaults",
    "configure",
    "with_max_chunk_size",
    "Metadata",
    "write",
    "close",
    "perform",
    "FileWriterView",
    "create",
    "API",
]
