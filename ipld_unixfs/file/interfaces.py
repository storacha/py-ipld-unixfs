from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, Literal, Protocol, TypeAlias, TypeVar

from multiformats import CID as Link, multicodec, multihash

from ipld_unixfs import codec, unixfs
from ipld_unixfs.file.chunker.interfaces import Chunker
from ipld_unixfs.file.layout.interfaces import LayoutEngine, NodeID
from ipld_unixfs.multiformats.codecs.interface import BlockEncoder
from ipld_unixfs.writer.interfaces import Writer as StreamWriter

if TYPE_CHECKING:
    from ipld_unixfs.file.writer import State


LayoutT = TypeVar("LayoutT")
T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
PB: TypeAlias = Literal[0x70]
RAW: TypeAlias = Literal[0x55]

LinkCodec: TypeAlias = int | str | multicodec.Multicodec
"""Multicodec code that corresponds to the codec the linked data is encoded with"""

FileChunkEncoder: TypeAlias = BlockEncoder[PB, memoryview] | BlockEncoder[RAW, memoryview]


@dataclass
class FileEncoder:
    code = codec.code
    def encode(self, node: unixfs.File) -> memoryview:
        return codec.encode(node)


class Linker:
    def create_link(self, code: LinkCodec, hash: bytes) -> Link:
        return Link(base="base32", version=1, codec=code, digest=hash)


@dataclass
class EncoderSettings(Generic[LayoutT, T]):
    chunker: Chunker[T]
    """
    Chunker which will be used to split file content into chunks.
    """

    file_chunk_encoder: FileChunkEncoder
    """
    If provided, leaves will be encoded as raw blocks, unless file has a
    metadata. This is what the `raw_leaves` option used to be except
    instead of a boolean you pass an encoder that will be used.
    """

    small_file_encoder: FileChunkEncoder
    """
    If provided, and file contains a single chunk it will be encoded
    with this encoder. This is what `reduce_single_leaf_to_self` option
    used to be except instead of boolean you pass an encoder that will
    be used.
    """

    file_encoder: FileEncoder

    file_layout: LayoutEngine[LayoutT]
    """Builder that will be used to build file DAG from the leaf nodes."""

    hasher: multihash.Multihash
    """Hasher used to compute multihash for each block in the file."""

    linker: Linker
    """
    This function is used to create CIDs from multihashes. This is
    similar to `cidVersion` option except you give it the CID creator
    to use.
    """


@dataclass
class EncodedFile:
    id: NodeID
    block: unixfs.Block
    link: unixfs.FileLink


@dataclass
class Options(Generic[LayoutT, T]):
    writer: BlockWriter
    metadata: unixfs.Metadata
    settings: EncoderSettings[LayoutT, T]


@dataclass
class CloseOptions:
    release_lock: bool
    close_writer: bool


class BlockWriter(StreamWriter[unixfs.Block]):
    pass

class WriteableBlockStream(Protocol):
    def get_writer(self) -> BlockWriter:
        ...


class Writer(Protocol[T_co]):
    async def write(self, bytes_data: bytes) -> "Writer[T_co]": ...
    async def close(self, options: CloseOptions) -> unixfs.FileLink: ...


class View(Writer[T_co], Protocol[T_co, T, LayoutT]):
    @property
    def writer(self) -> BlockWriter: ...

    @property
    def settings(self) -> EncoderSettings[LayoutT, T]: ...

    state: State[LayoutT, T]
