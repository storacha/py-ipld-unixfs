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
from dataclasses import dataclass
from ipld_dag_pb import PBNode, encode, decode, code, PBLink


from ..unixfs import (
    Metadata,
    FileLink,
    DirectoryLink,
    DirectoryEntryLink as BaseDirectoryEntryLink,
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


EntryLink = Union[FileLink, DirectoryLink]
"""
Represents a link to either a file or another directory
"""


DirectoryEntryLink = BaseDirectoryEntryLink
"""
What a directory *yields* or *contains* as an entry (includes the name)
"""


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
    """
    Internal state for a directory writer.
    attributes:
        entries: Dict[str, EntryLink] - stores name to FileLink or DirectoryLink
        metadata: Metadata
        writer: BlockWriter
        settings: BaseEncoderSettings[Layout]
    """
    entries: Dict[str, EntryLink]
    metadata: Metadata
    writer: BlockWriter
    settings: BaseEncoderSettings[Layout]
    closed: bool = False


class DirectoryWriter(Protocol):
    """
    Protocol for a writable directory.
    Corresponds to `Writer<Layout>` in JS.
    """

    def set(
        self, 
        name: str, 
        entry: EntryLink, 
        options: Optional[DirectoryWriteOptions] = None
    ) -> "DirectoryWriter":
        """
        Adds or updates an entry in the directory.
        Throws an error if the name conflicts and overwrite is not allowed.
        """
        pass

    def remove(self, name: str) -> "DirectoryWriter":
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
    ) -> "DirectoryView":
        """Creates a new writable directory view forked from the current state."""
        pass


class DirectoryView(DirectoryWriter, Protocol):
    """
    Protocol for a directory view, providing write methods and read access.
    Corresponds to `View<Layout>` in JS.
    """
    state: DirectoryWriterState

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

    def iter_entry_links(self) -> Iterable[BaseDirectoryEntryLink]:
        """
        Iterates over directory entries, yielding BaseDirectoryEntryLink objects
        (which are NamedDAGLink, including name, CID, and dag_byte_length).
        """

    @property
    def size(self) -> int:
        """Returns the number of entries in the directory."""
        pass


@dataclass
class DirectoryCreateOptions:
    writer: BlockWriter
    settings: Optional[BaseEncoderSettings] = None
    metadata: Optional[Metadata] = None