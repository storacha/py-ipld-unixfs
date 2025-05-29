from enum import IntEnum
from dataclasses import dataclass
from typing import Generic, Literal, TypeAlias, TypeVar
from multiformats import CID


# Type variable for generic types
T = TypeVar('T')


class NodeType(IntEnum):
    """Types of UnixFS nodes."""
    Raw = 0
    Directory = 1
    File = 2
    Metadata = 3
    Symlink = 4
    HAMTShard = 5


Node: TypeAlias = "Raw | SimpleFile | AdvancedFile | ComplexFile | Directory | DirectoryShard | ShardedDirectory | Symlink"


File: TypeAlias = "SimpleFile | AdvancedFile | ComplexFile"


@dataclass(frozen=True)
class SimpleFile:
    """
    Logical representation of a file that fits a single block.

    Note this is only semantically different from a `FileChunk` and your 
    interpretation SHOULD vary depending on where you encounter the node 
    (In root of the DAG or not).
    """
    content: bytes
    type: Literal[NodeType.File] = NodeType.File
    layout: Literal["simple"] = "simple"
    metadata: "Metadata | None" = None


@dataclass(frozen=True)
class Metadata:
    mode: "Mode | None" = None
    mtime: "MTime | None" = None


@dataclass(frozen=True)
class AdvancedFile:
    """
    Logical represenatation of a file that consists of multiple blocks. Note it
    is only semantically different from a `FileShard` and your interpretation
    SHOULD vary depending on where you encounter the node (In root of the DAG
    or not).
    """
    type: Literal[NodeType.File]
    layout: Literal["advanced"]
    parts: tuple["FileLink", ...]
    metadata: Metadata | None = None


@dataclass(frozen=True)
class Raw:
    """
    Represents a UnixFS Raw node (a leaf node of the file DAG layout).

    This representation has been subsumed by `FileChunk` representation and
    is therefore marked as deprecated.

    UnixFS consumers are very likely to encounter nodes of this type, as of this
    writing JS & Go implementations can be configured to produce these nodes,
    in trickle DAG use this configuration.

    UnixFS producers are RECOMMENDED to either use `FileChunk` representation or
    better yet raw binary nodes (That is 0x55 multicodec) which will likely
    replace them in the future.

    See: https://github.com/multiformats/multicodec/blob/master/table.csv#L39

    Please note that in the wild Raw nodes are likely to come with other fields
    encoded but both encoder and decoder presented here will ignore them.

    Deprecated: Use FileChunk or raw binary nodes instead.
    """
    content: bytes
    type: Literal[NodeType.Raw] = NodeType.Raw  # This enforces the type at runtime


@dataclass(frozen=True)
class FileChunk:
    """
    Logical representation of a file chunk (a leaf node of the file DAG layout).

    When a large file is added to IPFS it gets chunked into smaller pieces
    (according to the `--chunker` specified) and each chunk is encoded into this
    representation (and linked from file DAG). Please note that in practice
    there are many other representations for file chunks (leaf nodes) like `Raw`
    nodes (deprecated in favor of this representation) and raw binary nodes
    (That is 0x55 multicodec) which are on a way to surpass this representation.

    Please note that in protobuf representation there is only one `file` node
    type with many optional fields, however different combination of fields
    corresponds to a different semntaics and we represent each via different
    type.

    Also note that some file nodes may also have `mode` and `mtime` fields,
    which we represent via `SimpleFile` type, however in practice the two are
    indistinguishable & how to interpret will only depend on whether the node is
    encountered in DAG root position or not. That is because one could take two
    `SimpleFile` nodes and represent their concatination via `AdvancedFile`
    simply by linking to them. In such scenario consumer SHOULD treat leaves as
    `FileChunk`s and ignoring their `mode` and `mtime` fileds. However if those
    leaves are encountered on their own consumer SHOULD treat them as
    `SimpleFile`s and take `mode` and `mtime` fields into account.
    """

    type: Literal[NodeType.File]
    layout: Literal["simple"]
    content: bytes
    metadata: Metadata | None = None


Chunk: TypeAlias = Raw | FileChunk


@dataclass(frozen=True)
class FileShard:
    """
    Logical representation of a file shard. When large files are chunked
    slices that span multiple blocks may be represented via file shards in
    certain DAG layouts (e.g. balanced & trickle DAGs).

    Please note in protobuf representation there is only one `file` node type
    with many optional fields. Different combination of those fields corresponds
    to a different semntaics. Combination of fields in this type represent a
    branch nodes in the file DAGs in which nodes beside leaves and root exist.

    Also note that you may encounter `FileShard`s with `mode` and `mtime` fields
    which according to our definition would be `AdvancedFile`. However just as
    with `FileChunk` / `SimpleFile`, here as well, you should treat node as
    `AdvancedFile` if you encounter it in the root position (that is to say
    regard `mode`, `mtime` field) and treat it as `FileShard` node if encountered
    in any other position (that is ignore `mode`, `mtime` fileds).
    """
    type: Literal[NodeType.File]
    layout: Literal["advanced"]
    parts: tuple["FileLink", ...]


@dataclass(frozen=True)
class DAGLink(Generic[T]):
    cid: CID
    """*C*ontent *Id*entifier of the target DAG."""

    dag_byte_length: int
    """
    Cumulative number of bytes in the target DAG, that is number of bytes in the
    block and all the blocks it links to.
    """


@dataclass(frozen=True)
class ContentDAGLink(DAGLink[T]):
    content_byte_length: int
    """Total number of bytes in the file."""


FileLink: TypeAlias = ContentDAGLink[bytes] | ContentDAGLink[Chunk] | ContentDAGLink[FileShard]


@dataclass(frozen=True)
class ComplexFile:
    """
    These type of nodes are not produces by referenece IPFS implementations, yet
    such file nodes could be represented and therefor defined with this type.

    In this file representation first chunk of the file is represented by a
    `data` field while rest of the file is represented by links.

    It is NOT RECOMMENDED to use this representation (which is why it's marked
    deprecated), however it is still valid representation and UnixFS consumers
    SHOULD recognize it and interpret as described.
    """
    type: Literal[NodeType.File]
    layout: Literal["complex"]
    content: bytes
    parts: tuple[FileLink, ...]
    metadata: Metadata | None = None


@dataclass(frozen=True)
class UnknownFile:
    """
    This is a utility type that represents any kind of file which is then refined to
    one of the other definitions
    """
    type: Literal[NodeType.File]
    content: bytes | None = None
    parts: tuple[FileLink, ...] | None = None
    metadata: Metadata | None = None


Directory: TypeAlias = "FlatDirectory | ShardedDirectory"
"""
Type for either UnixFS directory representation
"""


@dataclass(frozen=True)
class FlatDirectory:
    """
    Logical Representation of a directory that fits a single block
    """
    type: Literal[NodeType.Directory]
    entries: tuple["DirectoryEntryLink", ...]
    metadata: Metadata | None = None


@dataclass(frozen=True)
class NamedDAGLink(DAGLink[T]):
    name: str


DirectoryEntryLink: TypeAlias = NamedDAGLink[File] | NamedDAGLink[Directory] | NamedDAGLink[bytes]

DirectoryLink: TypeAlias = DAGLink[Directory]


@dataclass(frozen=True)
class DirectoryShard:
    """
    Logical represenatation of the shard of the sharded directory. Please note
    that it only semantically different from `AdvancedDirectoryLayout`, in
    practice they are the same and interpretation should vary based on view. If
    viewed from the root position it is `AdvancedDirectoryLayout` and it's `mtime`
    `mode` field to be respected, otherwise it is `DirectoryShard` and it's
    `mtime` and `mode` field to be ignored.

    :param bitfield: HAMT table width (In IPFS it's usually 256)

    :param fanout: Multihash code for the hashing function used (In IPFS it's `murmur3-64`_ )
        .. _murmur3-64: https://github.com/multiformats/multicodec/blob/master/table.csv#L24
    """
    type: Literal[NodeType.HAMTShard]
    bitfield: bytes
    fanout: int
    hash_type: int
    entries: tuple["ShardedDirectoryLink", ...]
    metadata: Metadata | None = None


@dataclass(frozen=True)
class ShardedDirectory(DirectoryShard):
    """
    Logical representation of directory encoded in multiple blocks (usually when
    it contains large number of entries). Such directories are represented via
    Hash Array Map Tries (HAMT).

    See: https://en.wikipedia.org/wiki/Hash_array_mapped_trie
    """
    pass


ShardedDirectoryLink: TypeAlias = NamedDAGLink[File] | NamedDAGLink[bytes] | NamedDAGLink[Directory] | NamedDAGLink[DirectoryShard]



@dataclass(frozen=True)
class Symlink:
    """
    Logical representation of a `symbolic link`_.

    .. _symbolic link: https://en.wikipedia.org/wiki/Symbolic_link

    :param content: UTF-8 encoded path to the symlink target
    """
    type: Literal[NodeType.Symlink]
    content: bytes
    metadata: Metadata | None = None


@dataclass(frozen=True)
class UnixTime:
    """Representing the modification time in seconds relative to the unix epoch
    1970-01-01T00:00:00Z.

    :param seconds: (signed 64bit integer): represents the amount of seconds 
        after or before the epoch.
    :param fractional_nano_seconds: (optional, 32bit unsigned integer): when 
        specified represents the fractional part of the mtime as the amount 
        of nanoseconds. The valid range for this value are the integers 
        [1, 999999999].
    """
    seconds: int
    fractional_nano_seconds: int | None = None


Mode: TypeAlias = int
"""
The mode is for persisting the file permissions in `numeric notation`_ .
If unspecified this defaults to
- `0755` for directories/HAMT shards
- `0644` for all other types where applicable

The nine least significant bits represent `ugo-rwx`
The next three least significant bits represent setuid, setgid and the sticky bit.
The remaining 20 bits are reserved for future use, and are subject to change.
Spec implementations MUST handle bits they do not expect as follows: 
- For future-proofing the (de)serialization layer must preserve the entire
  `uint32` value during clone/copy operations, modifying only bit values that
   have a well defined meaning:
   `clonedValue = ( modifiedBits & 07777 ) | ( originalValue & 0xFFFFF000 )`
- Implementations of this spec MUST proactively mask off bits without a
  defined meaning in the implemented version of the spec:
  `interpretedValue = originalValue & 07777`


.. _numeric notation: https://en.wikipedia.org/wiki/File-system_permissions#Numeric_notation

See: https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/sys_stat.h.html
"""

@dataclass(frozen=True)
class MTime:
    """
    Represents modification time in seconds relative to the unix epoch
    1970-01-01T00:00:00Z.
    """
    secs: int
    nsecs: int | None = None
