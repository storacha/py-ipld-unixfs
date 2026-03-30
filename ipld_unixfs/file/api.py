from typing import Generic, Literal, Protocol, TypeAlias, TypeVar
from ipld_unixfs.file.chunker.api import Chunker
from ipld_unixfs.file.layout.api import LayoutEngine
from ipld_unixfs.multiformats.codecs.api import BlockEncoder
from ipld_unixfs import unixfs
from multiformats.multihash import Multihash


Layout = TypeVar("Layout")
T = TypeVar("T")
PB: TypeAlias = Literal[0x70]
RAW: TypeAlias = Literal[0x55]
BytesLike: TypeAlias = bytes | memoryview | bytearray

FileChunkEncoder: TypeAlias = BlockEncoder[PB, BytesLike] | BlockEncoder[RAW, BytesLike]

class FileEncoder(Protocol):
    code: PB
    def encode(self, node: unixfs.File) -> bytes: ...


class EncoderSettings(Generic[Layout, T]):
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

    file_layout: LayoutEngine[Layout]
    """
    Builder that will be used to build file DAG from the leaf nodes.
    """

    hasher: Multihash
