from dataclasses import dataclass
from typing import Generic, Literal, TypeAlias, TypeVar, TypedDict

import actress as Task

from ipld_unixfs import unixfs
from ipld_unixfs.file import interfaces as API
from ipld_unixfs.file.layout import interfaces as Layout
from ipld_unixfs.file import chunker
from ipld_unixfs.file.layout import queue


LayoutT = TypeVar("LayoutT")
T = TypeVar("T")


@dataclass(frozen=True)
class Open(Generic[LayoutT, T]):
    metadata: unixfs.Metadata
    config: API.EncoderSettings[LayoutT, T]
    writer: API.BlockWriter
    chunker: chunker.Chunker
    layout: LayoutT
    node_queue: queue.Queue
    status: Literal["open"] = "open"


@dataclass(frozen=True)
class Closed(Generic[LayoutT, T]):
    metadata: unixfs.Metadata
    config: API.EncoderSettings[LayoutT, T]
    writer: API.BlockWriter
    root_id: Layout.NodeID
    end: Task.Fork[None, None, None] | None  # type: ignore[arg-type]
    node_queue: queue.Queue
    status: Literal["closed"]


@dataclass(frozen=True)
class Linked(Generic[LayoutT, T]):
    metadata: unixfs.Metadata
    config: API.EncoderSettings[LayoutT, T]
    writer: API.BlockWriter
    link: unixfs.FileLink
    node_queue: queue.Queue
    status: Literal["linked"]


State: TypeAlias = Open[LayoutT, T] | Closed[LayoutT, T] | Linked[LayoutT, T]


class WriteMessage(TypedDict):
    type: Literal["write"]
    bytes_data: bytes

class LinkMessage(TypedDict):
    type: Literal["link"]
    link: API.EncodedFile


class BlockMessage(TypedDict):
    type: Literal["block"]


class CloseMessage(TypedDict):
    type: Literal["close"]


class EndMessage(TypedDict):
    type: Literal["end"]


Message: TypeAlias = WriteMessage | LinkMessage | BlockMessage | CloseMessage | EndMessage | None


@dataclass
class Update(Generic[LayoutT, T]):
    state: State[LayoutT, T]
    effect: Task.Effect[Message]


def update(message: Message, state: State[LayoutT, T]):
    if message is not None:
        match (message["type"]):
            case "write":
                return write(state, message["bytes_data"])
            case "link":
                return link(state, message["link"])
            case "block":
                return Update(state, effect=Task.none_())
            case "close":
                return close(state)
            case "end":
                return Update(state, effect=Task.none_())
            case _:
                raise Exception(f"File writer got unknown message {message}")


def write(state: State[LayoutT], bytes_data: memoryview) -> Update[LayoutT, T]:
    if (state.status == "open"):
        # chunk up the provided bytes
        chunker.write(state.chunker, buf=bytes_data)

def link(state: State[LayoutT], entry: API.EncodedFile) -> Update[LayoutT, T]:
    pass

def close(state: State[LayoutT]) -> Update[LayoutT]:
    pass
