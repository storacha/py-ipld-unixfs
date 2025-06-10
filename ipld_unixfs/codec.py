from collections.abc import Sequence
from logging import getLogger
from functools import reduce
import math
from typing import TypeVar

import ipld_dag_pb
from ipld_unixfs import unixfs
from gen.unixfs_pb2 import Data,  UnixTime

logger = getLogger(__name__)

EMPTY = ()  # read-only tuple
EMPTY_BUFFER = bytes()

BLANK = unixfs.Metadata()
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


def create_empty_file(metadata: unixfs.Metadata | None) -> unixfs.SimpleFile:
    return create_simple_file(content=EMPTY_BUFFER, metadata=metadata)


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


def create_advanced_file(
    parts: Sequence[unixfs.FileLink], metadata: unixfs.Metadata
) -> unixfs.AdvancedFile:
    return unixfs.AdvancedFile(
        type=unixfs.NodeType.File,
        layout="advanced",
        parts=tuple(parts),
        metadata=decode_metadata(metadata)
    )


def create_file_shard(parts: Sequence[unixfs.FileLink]) -> unixfs.FileShard:
    return unixfs.FileShard(
        type=unixfs.NodeType.File, layout="advanced", parts=tuple(parts)
    )


def create_complex_file(
    content: bytes,
    parts: Sequence[unixfs.FileLink],
    metadata: unixfs.Metadata | None
) -> unixfs.ComplexFile:
    return unixfs.ComplexFile(
        type=unixfs.NodeType.File,
        layout="complex",
        content=content,
        parts=tuple(parts),
        metadata=decode_metadata(metadata)
    )


def create_flat_directory(
    entries: Sequence[unixfs.DirectoryEntryLink],
    metadata: unixfs.Metadata | None
) -> unixfs.FlatDirectory:
    return unixfs.FlatDirectory(
        type=unixfs.NodeType.Directory,
        metadata=decode_metadata(metadata),
        entries=tuple(entries)
    )


def create_sharded_directory(
    entries: Sequence[unixfs.ShardedDirectoryLink],
    bitfield: bytes,
    fanout: int,
    hash_type: int,
    metadata: unixfs.Metadata | None = BLANK,
) -> unixfs.ShardedDirectory:
    return unixfs.ShardedDirectory(
        type=unixfs.NodeType.HAMTShard,
        bitfield=bitfield,
        fanout=fanout,
        hash_type=hash_type,
        entries=tuple(entries),
        metadata=decode_metadata(metadata)
    )


def create_directory_shard(
    entries: Sequence[unixfs.ShardedDirectoryLink],
    bitfield: bytes,
    fanout: int,
    hash_type: int
) -> unixfs.DirectoryShard:
    return unixfs.DirectoryShard(
        type=unixfs.NodeType.HAMTShard,
        bitfield=bitfield,
        fanout=fanout,
        hash_type=hash_type,
        entries=tuple(entries)
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


def encode_link(dag: unixfs.DAGLink) -> ipld_dag_pb.PBLink:
    return ipld_dag_pb.PBLink(size=dag.dag_byte_length, hash=dag.cid, name="")


def encode_advanced_file(
    parts: Sequence[unixfs.FileLink], metadata: unixfs.Metadata | None
) -> memoryview[int]:
    if metadata:
        metadata = encode_metadata(metadata=metadata)

    data = Data(
        Type=Data.DataType.File,
        blocksizes=[part.content_byte_length for part in parts],
        filesize=cumulative_content_byte_length(parts),
        mode=(metadata.mode if metadata else None),
        mtime=(
            UnixTime(
                Seconds=metadata.mtime.secs,  # pyright: ignore[reportOptionalMemberAccess]
                FractionalNanoseconds=metadata.mtime.nsecs  # pyright: ignore[reportOptionalMemberAccess]
            ) if metadata else None
        )
    )

    return encode_pb(data=data, links=[encode_link(part) for part in parts])


def encode_complex_file(content: bytes, parts: Sequence[unixfs.FileLink], metadata: unixfs.Metadata | None = BLANK) -> memoryview[int]:
    data = Data(
        Type=Data.DataType.File,
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
        raise TypeError(f"Expected an integer value instead got {n}")


def read_data(data: bytes) -> bytes | None:
    if len(data) > 0:
        return data
    else:
        return None


def encode_hamt_shard(node: unixfs.ShardedDirectory | unixfs.DirectoryShard) -> memoryview[int]:
    metadata = None
    if node.metadata:
        metadata = encode_directory_metadata(node.metadata)

    data = Data(
        Type=Data.DataType.HAMTShard,
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


def encode_symlink(node: unixfs.Symlink, ignore_metadata: bool = False) -> memoryview[int]:
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
            Type=Data.DataType.Symlink,
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


def encode(node: unixfs.Node, root: bool = True) -> memoryview[int]:
    match node.type:
        case unixfs.NodeType.Raw:
            return encode_raw(node.content)
        case unixfs.NodeType.File:
            return encode_file(node)
        case unixfs.NodeType.Directory:
            return encode_directory(node)
        case unixfs.NodeType.HAMTShard:
            return encode_hamt_shard(node)
        case unixfs.NodeType.Symlink:
            return encode_symlink(node)
        case _:
            raise ValueError(f"Unknown node type {node.type}")


def decode(bytes_data: memoryview[int]) -> unixfs.Node:
    pb = ipld_dag_pb.decode(bytes_data)
    message = Data()
    message.ParseFromString(bytes_data.tobytes())

    metadata = unixfs.Metadata(mode=message.mode, mtime=decode_mtime(message.mtime))

    links = pb.links


    match message.Type:
        case Data.DataType.Raw:
            return create_raw(message.Data)
        case Data.DataType.File:
            if (len(links) == 0):
                return unixfs.SimpleFile(content=message.Data, metadata=metadata)
            elif (len(message.Data) == 0):
                return unixfs.AdvancedFile(
                    parts=tuple(decode_file_links(message.blocksizes, links)),
                    metadata=metadata
                )
            else:
                return unixfs.ComplexFile(
                    content=message.Data,
                    parts=tuple(decode_file_links(message.blocksizes, links))
                )
        case Data.DataType.Directory:
            return create_flat_directory(
                entries=decode_directory_links(links=links),
                metadata=metadata
            )
        case Data.DataType.HAMTShard:
            data = message.Data
            return create_sharded_directory(
                entries=decode_directory_links(links),
                bitfield=data if data is not None else EMPTY_BUFFER,
                fanout=message.fanout,
                hash_type=message.hashType,
                metadata=metadata
            )
        case Data.DataType.Symlink:
            return create_sym_link(message.Data, metadata)
        case _:
            raise ValueError(f"Unsupported node type {message.Type}")


def decode_mtime(mtime: UnixTime | None) -> unixfs.MTime | None:
    if mtime is None:
        return None
    else:
        return unixfs.MTime(secs=mtime.Seconds, nsecs=mtime.FractionalNanoseconds)


def decode_blocksizes(type: Data.DataType, blocksizes: list[int] | None) -> list[int] | None:
    match type:
        case Data.DataType.File:
            if blocksizes and len(blocksizes) > 0:
                return blocksizes
            else:
                return None
        case _:
            return None


def decode_file_links(blocksizes: Sequence[int], links: Sequence[ipld_dag_pb.PBLink]) -> list[unixfs.FileLink]:
    parts: list[unixfs.ContentDAGLink] = []
    length = len(blocksizes)
    n = 0
    for n in range(length):
        dag_byte_length = links[n].t_size
        parts.append(
            unixfs.ContentDAGLink(
                cid=links[n].hash,
                dag_byte_length=(dag_byte_length if dag_byte_length is not None else 0),
                content_byte_length=blocksizes[n],
            )
        )
    return parts


def decode_directory_links(links: Sequence[ipld_dag_pb.PBLink]) -> list[unixfs.DirectoryEntryLink]:
    dir_entry_links: list[unixfs.NamedDAGLink] = []
    for link in links:
        dag_byte_length = link.t_size
        name = link.name
        dir_entry_links.append(
            unixfs.NamedDAGLink(
                cid=link.hash,
                dag_byte_length=dag_byte_length if dag_byte_length is not None else 0,
                name=name if name is not None else "",
            )
        )
    return dir_entry_links


def cumulative_content_byte_length(links: Sequence[unixfs.FileLink]) -> int:
    return reduce(lambda size, link: size + link.content_byte_length, links, 0)


def cumulative_dag_byte_length(root: bytes, links: Sequence[unixfs.DAGLink]) -> int:
    return reduce(lambda size, link: size + link.dag_byte_length, links, len(root))


def match_file(
    content: bytes = EMPTY_BUFFER,
    parts: Sequence[unixfs.FileLink] = EMPTY,
    metadata: unixfs.Metadata | None = BLANK
) -> unixfs.SimpleFile | unixfs.AdvancedFile | unixfs.ComplexFile:
    if len(parts) == 0:
        return unixfs.SimpleFile(content=content, metadata=metadata)
    elif (len(content) == 0):
        return unixfs.AdvancedFile(parts=tuple(parts), metadata=metadata)
    else:
        return unixfs.ComplexFile(content=content, parts=tuple(parts), metadata=metadata)


def file_size(node: unixfs.Node) -> int:
    match node.type:
        case unixfs.NodeType.Raw | unixfs.NodeType.Symlink:
            return len(node.content)
        case unixfs.NodeType.File:
            match node.layout:
                case "simple":
                    return len(node.content)
                case "advanced":
                    return cumulative_content_byte_length(node.parts)
                case "complex":
                    return len(node.content) + cumulative_content_byte_length(node.parts)
        case _:
            return 0
