from dataclasses import dataclass
from typing import Generic, Literal, Optional, Protocol, Sequence, TypeAlias, TypeVar
from ipld_unixfs.multiformats.codecs.interface import BlockEncoder
from ipld_unixfs.file.chunker.interfaces import Chunk
from ipld_unixfs.unixfs import Metadata, File

T = TypeVar("T")
LayoutT = TypeVar("LayoutT")


class ID(int, Generic[T]):
    pass

NodeID: TypeAlias = ID["Node"]


@dataclass
class Branch:
    id: NodeID
    children: Sequence[NodeID]
    metadata: Optional[Metadata] = None


@dataclass
class Leaf:
    id: NodeID
    content: Optional[Chunk]
    metadata: Optional[Metadata]


Node: TypeAlias = Leaf | Branch


@dataclass
class WriteResult(Generic[LayoutT]):
    layout: LayoutT
    nodes: Sequence[Branch]
    leaves: Sequence[Leaf]


@dataclass
class CloseResult:
    root: Node
    nodes: Sequence[Branch]
    leaves: Sequence[Leaf]


PB: TypeAlias = Literal[0x70]
RAW: TypeAlias = Literal[0x55]

FileChunkEncoder: TypeAlias = BlockEncoder[PB, bytes] | BlockEncoder[RAW, bytes]


class FileEncoder(Protocol):
    code: PB

    def encode(self, file: File) -> bytes: ...


class LayoutEngine(Protocol, Generic[LayoutT]):
    def open(self) -> LayoutT:
        """
        When new file is imported importer will call file builders `open`
        function. Here layout implementation can initialize implementation
        specific state.

        Please note it is important that builder does not mutate any state
        outside of returned state object as order of calls is non deterministic.
        """
        ...

    def write(self, layout: LayoutT, chunks: Sequence[Chunk]) -> WriteResult[LayoutT]:
        """
        Importer takes care reading file content chunking it. Afet it produces
        some chunks it will pass those via `write` call along with current
        layout a state (which was returned by `open` or previous `write` calls).

        Layout engine implementation is responsible for returning new layout
        along with all the leaf and branch nodes it created as a result.

        Note: Layout engine should not hold reference to chunks or nodes to
        avoid unecessary memory use.
        """
        ...

    def close(self, layout: LayoutT, metadata: Optional[Metadata] = None) -> CloseResult:
        """
        After importer wrote all the chunks through `write` calls it will call
        `close` so that layout engine can produce all the remaining nodes along
        with a root.
        """
        ...
