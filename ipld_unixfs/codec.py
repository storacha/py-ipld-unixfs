from collections.abc import Sequence
from logging import getLogger
from functools import reduce
import math

import ipld_dag_pb
import unixfs
from gen.unixfs_pb2 import Data, UnixTime

logger = getLogger(__name__)

EMPTY = ()  # read-only tuple
EMPTY_BUFFER = bytes()

BLANK = None  # TODO: change this to unixfs.Metadata()
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


def create_empty_file(metadata: unixfs.Metadata | None):
    create_simple_file(content=EMPTY_BUFFER, metadata=metadata)


def create_simple_file(
    content: bytes, metadata: unixfs.Metadata | None
) -> unixfs.SimpleFile:
    return unixfs.SimpleFile(
        type=unixfs.NodeType.File,
        layout="simple",
        content=content,
        metadata=decode_metadata(metadata)
    )


def create_file_chunk(content: bytes) -> unixfs.FileChunk:
    return unixfs.FileChunk(
        type=unixfs.NodeType.File,
        layout="simple",
        content=content
    )


def decode_mode(mode: unixfs.Mode) -> unixfs.Mode:
    return (mode & 0xfff) | (mode & 0xfffff000)


def decode_metadata(data: unixfs.Metadata | None) -> unixfs.Metadata:
    if data is None:
        return unixfs.Metadata()
    return unixfs.Metadata(
        mode=decode_mode(data.mode) if data.mode is not None else None,
        mtime=data.mtime
    )


def create_advanced_file(
    parts: tuple[unixfs.FileLink, ...], metadata: unixfs.Metadata
) -> unixfs.AdvancedFile:
    return unixfs.AdvancedFile(
        type=unixfs.NodeType.File,
        layout="advanced",
        parts=parts,
        metadata=decode_metadata(metadata)
    )


def create_file_shard(parts: tuple[unixfs.FileLink, ...]) -> unixfs.FileShard:
    return unixfs.FileShard(
        type=unixfs.NodeType.File, layout="advanced", parts=parts
    )


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


def encode_raw(content: bytes) -> memoryview[int]:
    return encode_pb(
        data=Data(
            Type=Data.DataType.Raw,
            Data=(content if len(content) > 0 else None),
            filesize=len(content),
            blocksizes=EMPTY
        ),
        links=[]
    )


def encode_mtime(mtime: unixfs.MTime | None) -> unixfs.MTime | None:
    if mtime is None:
        return

    if not mtime.nsecs:  # mtime.nsecs could either be `None` or `0`
        return unixfs.MTime(secs=mtime.secs, nsecs=None)

    return mtime


def encode_mode(
    specified_mode: int | None, default_mode: int | None
) -> unixfs.Mode | None:
    mode = None
    if specified_mode is not None:
        mode = decode_mode(specified_mode)

    return (None if mode == default_mode or mode is None else mode)


def encode_metadata(
    metadata: unixfs.Metadata, default_mode: unixfs.Mode = DEFAULT_FILE_MODE
) -> unixfs.Metadata:
    return unixfs.Metadata(
        mode=(
            encode_mode(metadata.mode, default_mode)
            if metadata.mode is not None else None
        ),
        mtime=(encode_mtime(metadata.mtime) if metadata.mtime is not None else None)
    )


def encode_simple_file(
    content: bytes, metadata: unixfs.Metadata | None = None
) -> memoryview[int]:
    if metadata:
        metadata = encode_metadata(metadata=metadata)

    data = Data(
        Type=Data.DataType.File,
        # adding an empty file to both the go-ipfs and js-ipfs produces block in
        # which `Data` is omitted but filesize and blocksizes are present.
        # For the sake of hash consistency we do the same.
        Data=(content if len(content) > 0 else None),
        filesize=len(content),
        blocksizes=[],
        mode=(metadata.mode if metadata else None),
        mtime=(
            UnixTime(
                Seconds=metadata.mtime.secs, FractionalNanoseconds=metadata.mtime.nsecs  # pyright: ignore[reportOptionalMemberAccess]
            ) if metadata else None
        )
    )

    return encode_pb(data=data, links=[])


def cumulative_content_byte_length(links: Sequence[unixfs.FileLink]) -> int:
    return reduce(lambda size, link: size + link.content_byte_length, links, 0)


def encode_link(dag: unixfs.DAGLink) -> ipld_dag_pb.PBLink:
    return ipld_dag_pb.PBLink(size=dag.dag_byte_length, hash=dag.cid, name="")


def encode_advanced_file(
    parts: Sequence[unixfs.FileLink], metadata: unixfs.Metadata | None
) -> memoryview[int]:
    if metadata:
        metadata = encode_metadata(metadata=metadata)

    data = Data(
        Type=Data.Type.File,
        blocksizes=[part.content_byte_length for part in parts],
        filesize=cumulative_content_byte_length(parts),
        mode=(metadata.mode if metadata else None),
        mtime=(
            UnixTime(
                Seconds=metadata.mtime.secs, FractionalNanoseconds=metadata.mtime.nsecs  # pyright: ignore[reportOptionalMemberAccess]
            ) if metadata else None
        )
    )

    return encode_pb(data=data, links=[encode_link(part) for part in parts])


def encode_complex_file(content: bytes, parts: tuple[unixfs.FileLink, ...], metadata: unixfs.Metadata | None = BLANK) -> memoryview[int]:
    data = Data(
        Type=Data.Type.File,
        Data=content,
        filesize=len(content) + cumulative_content_byte_length(parts),
        blocksizes=[part.content_byte_length for part in parts],
    )
    return encode_pb(data=data, links=[encode_link(part) for part in parts])


def encode_file(
    node: unixfs.File | unixfs.FileChunk | unixfs.FileShard,
    ignore_metadata: bool = False
) -> memoryview[int]:
    metadata = BLANK
    if not ignore_metadata:
        metadata = node.metadata

    if node.layout == "simple":
        return encode_simple_file(node.content, metadata)
    elif node.layout == "advanced":
        return encode_advanced_file(node.parts, metadata)
    elif node.layout == "complex":
        return encode_complex_file(node.content, node.parts, metadata)
    else:
        raise TypeError(f"File with unknown layout {node.layout} was passed")


def encode_file_chunk(content: bytes) -> memoryview[int]:
    return encode_simple_file(content, metadata=BLANK)


def encode_file_shard(parts: list[unixfs.FileLink]) -> memoryview[int]:
    return encode_pb(
        data=Data(
            Type=Data.DataType.File,
            blocksizes=[part.content_byte_length for part in parts],
            filesize=cumulative_content_byte_length(parts)
        ),
        links=[encode_link(part) for part in parts]
    )


def encode_directory_metadata(metadata: unixfs.Metadata) -> unixfs.Metadata:
    return encode_metadata(metadata=metadata, default_mode=DEFAULT_DIRECTORY_MODE)


def encode_named_link(link: unixfs.NamedDAGLink) -> ipld_dag_pb.PBLink:
    return ipld_dag_pb.PBLink(hash=link.cid, name=link.name, size=link.dag_byte_length)


def encode_directory(node: unixfs.FlatDirectory) -> memoryview[int]:
    metadata = None
    if node.metadata:
        metadata = encode_directory_metadata(node.metadata)
    return encode_pb(
        data=Data(
            Type=Data.DataType.Directory,
            mode=(metadata.mode if metadata else None),
            mtime=(
                UnixTime(
                    Seconds=metadata.mtime.secs, FractionalNanoseconds=metadata.mtime.nsecs  # pyright: ignore[reportOptionalMemberAccess]
                ) if metadata else None
            )
        ),
        links=[encode_named_link(entry) for entry in node.entries]
    )


def read_fanout(n: int) -> int:
    if (math.log2(n) % 1) == 0:
        return n
    else:
        raise ValueError(
            f"Expected HAMT size to be a power of two instead got {n}"
        )


def read_int(n: int) -> int:
    if n.is_integer():
        return n
    else:
        raise ValueError(f"Expected an integer value instead got {n}")


def encode_hamt_shard(node: unixfs.ShardedDirectory | unixfs.DirectoryShard) -> memoryview[int]:
    metadata = None
    if node.metadata:
        metadata = encode_directory_metadata(node.metadata)

    data = Data(
        Type=Data.Type.HAMTShard,
        Data=node.bitfield if node.bitfield else None,
        fanout=read_fanout(node.fanout),
        hashType=read_int(node.hash_type),
        mode=(metadata.mode if metadata else None),
        mtime=(
            UnixTime(
                Seconds=metadata.mtime.secs, FractionalNanoseconds=metadata.mtime.nsecs  # pyright: ignore[reportOptionalMemberAccess]
            ) if metadata else None
        )
    )
    return encode_pb(data, links=[encode_named_link(entry) for entry in node.entries])


def create_sym_link(path: bytes, metadata: unixfs.Metadata | None = BLANK) -> unixfs.Symlink:
    return unixfs.Symlink(
        type=unixfs.NodeType.Symlink, content=path, metadata=decode_metadata(metadata)
    )


def encode_symlink(node: unixfs.Symlink, ignore_metadata: bool =False) -> memoryview[int]:
    # We do not include filesize on symlinks because that is what go-ipfs does when
    # doing `ipfs add mysymlink`. js-ipfs on the other hand seems to store it, here
    # we choose to follow go-ipfs.
    # See: https://explore.ipld.io/#/explore/QmPZ1CTc5fYErTH2XXDGrfsPsHicYXtkZeVojGycwAfm3v
    # See: https://github.com/ipfs/js-ipfs-unixfs/issues/195
    metadata = None
    if node.metadata:
        metadata = encode_metadata(node.metadata)

    return encode_pb(
        data=Data(
            Type=Data.Type.Symlink,
            Data=node.content,
            mode=(metadata.mode if metadata else None),
            mtime=(
                UnixTime(
                    Seconds=metadata.mtime.secs, FractionalNanoseconds=metadata.mtime.nsecs  # pyright: ignore[reportOptionalMemberAccess]
                ) if metadata else None
            )
        ),
        links=[]
    )
