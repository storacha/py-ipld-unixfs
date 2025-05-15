# ipld_unixfs/directory/api.py
from typing import (
    Generic,
    TypeVar,
    Protocol,
    Optional,
    Dict,
    Iterable,
    Tuple,
    Union,
    Mapping,
)
from dataclasses import dataclass, field
from ipld_dag_pb import PBNode, encode, decode, code, PBLink

# TODO: currently no support for DirectoryLink yet in 
from ..unixfs import (
    Metadata,
    FileLink,
    # DirectoryLink,
)

# TODO: pending when the File API is ready
# from ..file.api import ( # Or from ipld_unixfs.file.api
#     BlockWriter,
#     EncoderSettings as BaseEncoderSettings, # To avoid name clash if we extend it
#     CloseOptions,
# )


# NOTE: Generic type for Layout, if your directory writers are layout-aware
# (HAMT itself is a layout, so this might be less relevant here than for files)
Layout = TypeVar("Layout")

# NOTE: Represents a link to either a file or another directory
EntryLink = Union[FileLink, DirectoryLink]


@dataclass
class DirectoryWriteOptions:
    """Options for writing an entry to a directory."""
    overwrite: bool = False


@dataclass
class DirectoryEntryData:
    """Data for a single entry within a directory being built."""
    name: str
    link: EntryLink



@dataclass
class DirectoryWriterState(Generic[Layout]):
    """Internal state for a directory writer."""
    entries: Dict[str, EntryLink]
    metadata: Metadata
    writer: BlockWriter
    settings: BaseEncoderSettings[Layout]
    closed: bool = False


class DirectoryWriter(Protocol, Generic[Layout]):
    """
    Protocol for a writable directory.
    Corresponds to `Writer<Layout>` in JS.
    """

    def set(
        self, name: str, entry: EntryLink, options: Optional[DirectoryWriteOptions] = None
    ) -> "DirectoryWriter[Layout]":
        """
        Adds or updates an entry in the directory.
        Throws an error if the name conflicts and overwrite is not allowed.
        """
        pass

    def remove(self, name: str) -> "DirectoryWriter[Layout]":
        """Removes an entry from the directory."""
        pass

    async def close(self, options: Optional[CloseOptions] = None) -> DirectoryLink:
        """
        Finalizes the directory, writes all necessary blocks (e.g., HAMT shards),
        and returns the root DirectoryLink.
        """
        pass

    def fork(
        self, options: Optional[Dict] = None
    ) -> "DirectoryView[Layout]":
        """Creates a new writable directory view forked from the current state."""
        pass


class DirectoryView(DirectoryWriter[Layout], Protocol, Generic[Layout]):
    """
    Protocol for a directory view, providing write methods and read access.
    Corresponds to `View<Layout>` in JS.
    """
    state: DirectoryWriterState[Layout]

    @property
    def writer(self) -> BlockWriter: ...

    @property
    def settings(self) -> BaseEncoderSettings[Layout]: ...

    def entries(self) -> Iterable[Tuple[str, EntryLink]]:
        """Iterates over directory entries as (name, link) tuples."""
        pass

    def has(self, name: str) -> bool:
        """Checks if an entry with the given name exists."""
        pass

    @property
    def size(self) -> int:
        """Returns the number of entries in the directory."""
        pass


@dataclass
class DirectoryCreateOptions(Generic[Layout]):
    writer: BlockWriter
    settings: Optional[BaseEncoderSettings[Layout]] = None
    metadata: Optional[Metadata] = None