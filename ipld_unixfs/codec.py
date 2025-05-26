from collections.abc import Sequence
from logging import getLogger

import ipld_dag_pb
import unixfs
from gen.unixfs_pb2 import Data

logger = getLogger(__name__)

EMPTY = ()  # read-only tuple
EMPTY_BUFFER = bytes()

BLANK = {}
DEFAULT_FILE_MODE = 0o644
DEFAULT_DIRECTORY_MODE = 0o755

code = ipld_dag_pb.code
name = "UnixFS"

def encode_pb(data: Data, links: list[ipld_dag_pb.PBLink]) -> memoryview[int]:
    logger.debug({"data": data, "links": links})
    return ipld_dag_pb.encode(
        # We run through prepare as links need to be sorted by name which it will do
        ipld_dag_pb.prepare(
            {
                "data": data.SerializeToString(),
                "links": links
            }
        )
    )


def create_raw(content: bytes) -> unixfs.Raw:
    return unixfs.Raw(content)


def create_empty_file(metadata: unixfs.Metadata):
    create_simple_file(content=EMPTY_BUFFER, metadata=metadata)


def create_simple_file(content: bytes, metadata: unixfs.Metadata) -> unixfs.SimpleFile:
    return unixfs.SimpleFile(type=unixfs.NodeType.File, layout="simple", content=content, metadata=decode_metadata(metadata))


def create_file_chunk(content: bytes) -> unixfs.FileChunk:
    return unixfs.FileChunk(
        type=unixfs.NodeType.File,
        layout="simple",
        content=content
    )


def decode_mode(mode: unixfs.Mode) -> unixfs.Mode:
    return (mode & 0xfff) | (mode & 0xfffff000)


def decode_metadata(data: unixfs.Metadata | None) -> unixfs.Metadata | None:
    if data is None:
        return unixfs.Metadata()
    return unixfs.Metadata(
        mode=decode_mode(data.mode) if data.mode is not None else None,
        mtime=data.mtime
    )


def create_advanced_file(parts: tuple[unixfs.FileLink, ...], metadata: unixfs.Metadata) -> unixfs.AdvancedFile:
    return unixfs.AdvancedFile(
        type=unixfs.NodeType.File,
        layout="advanced",
        parts=parts,
        metadata=decode_metadata(metadata)
    )


def create_file_shard(parts: tuple[unixfs.FileLink, ...]) -> unixfs.FileShard:
    return unixfs.FileShard(type=unixfs.NodeType.File, layout="advanced", parts=parts)


def create_complex_file(
    content: bytes,
    parts: tuple[unixfs.FileLink, ...],
    metadata: unixfs.Metadata | None
) -> unixfs.ComplexFile:
    return unixfs.ComplexFile(
        type=unixfs.NodeType.File,
        layout="complex",
        content=content,
        parts=parts,
        metadata=decode_metadata(metadata)
    )


def create_flat_directory(
    entries: tuple[unixfs.DirectoryEntryLink, ...],
    metadata: unixfs.Metadata | None
) -> unixfs.FlatDirectory:
    return unixfs.FlatDirectory(
        type=unixfs.NodeType.Directory,
        metadata=decode_metadata(metadata),
        entries=entries
    )


def create_sharded_directory(
    entries: tuple[unixfs.ShardedDirectoryLink, ...],
    bitfield: bytes,
    fanout: int,
    hash_type: int,
    metadata: unixfs.Metadata | None,
) -> unixfs.ShardedDirectory:
    return unixfs.ShardedDirectory(
        type=unixfs.NodeType.HAMTShard,
        bitfield=bitfield,
        fanout=fanout,
        hash_type=hash_type,
        entries=entries,
        metadata=decode_metadata(metadata)
    )


def create_directory_shard(
    entries: tuple[unixfs.ShardedDirectoryLink, ...],
    bitfield: bytes,
    fanout: int,
    hash_type: int
) -> unixfs.DirectoryShard:
    return unixfs.DirectoryShard(
        type=unixfs.NodeType.HAMTShard,
        bitfield=bitfield,
        fanout=fanout,
        hash_type=hash_type,
        entries=entries
    )
