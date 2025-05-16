# ipld_unixfs/directory/__init__.py
import logging
from typing import Optional, Dict, List, Iterable, Tuple, cast, Union
from dataclasses import replace, field
from ipld_dag_pb import PBLink
from multiformats import CID # type: ignore

# API definitions for this module
from .api import (
    DirectoryWriter,
    DirectoryView,
    DirectoryWriterState,
    EntryLink,
    DirectoryWriteOptions,
    DirectoryCreateOptions,
)
# Core UnixFS types
from ipld_unixfs.unixfs import (
    Metadata,
    FlatDirectory,
    DirectoryLink,
    NamedDAGLink, # This is our DirectoryEntryLink for logical representation
    NodeType,
    Mode,
)
# Common file/block operation types
from ipld_unixfs.file.api import (
    EncoderSettings,
    BlockWriter,
    CloseOptions,
    Block, # Represents a finalized IPLD block (CID, bytes, value)
)

# TODO: awaiting when the codecs are ready
# from ipld_unixfs.codecs import (
#     serialize_unixfs_data_field,
#     mock_dag_pb_encoder, # Using the mock for now
# )

logger = logging.getLogger(__name__)

class PythonFlatDirectoryWriter(DirectoryView):
    """
    Implementation of a DirectoryView for creating UnixFS flat (single-block)
    directories.
    """
    state: DirectoryWriterState

    def __init__(self, initial_state: DirectoryWriterState):
        """
        Initializes the directory writer with a given state.
        Typically called by the `create` factory function.
        """
        self.state = initial_state

    @property
    def writer(self) -> BlockWriter:
        return self.state.writer

    @property
    def settings(self) -> EncoderSettings:
        return self.state.settings

    def _ensure_writable(self) -> None:
        """Checks if the directory is closed and raises an error if so."""
        if self.state.closed:
            raise RuntimeError(
                "Directory is closed and cannot be modified. "
                "Use fork() to create a new writable version."
            )

    def set(
        self, name: str, entry: EntryLink, options: Optional[DirectoryWriteOptions] = None
    ) -> "PythonFlatDirectoryWriter":
        self._ensure_writable()
        opts = options or DirectoryWriteOptions()

        if "/" in name:
            raise ValueError(
                f"Directory entry name \"{name}\" contains forbidden \"/\" character."
            )
        if not opts.overwrite and name in self.state.entries:
            raise ValueError(
                f"Directory already contains entry with name \"{name}\"."
            )
        
        self.state.entries[name] = entry
        logger.debug(f"Set entry '{name}' -> CID: {entry.cid.to_string()}")
        return self

    def remove(self, name: str) -> "PythonFlatDirectoryWriter":
        self._ensure_writable()
        if name in self.state.entries:
            removed_entry = self.state.entries.pop(name)
            logger.debug(f"Removed entry '{name}' (CID: {removed_entry.cid.to_string()})")
        else:
            logger.debug(f"Attempted to remove non-existent entry '{name}'")
        return self

    async def close(self, options: Optional[CloseOptions] = None) -> DirectoryLink:
        """
        Finalizes the flat directory:
        1. Converts internal entries to sorted NamedDAGLinks.
        2. Creates a logical FlatDirectory object.
        3. Serializes the UnixFS Protobuf Data field for a directory.
        4. Prepares PBLinks for the DAG-PB encoder.
        5. Encodes the DAG-PB node using the configured encoder.
        6. Hashes the encoded block and creates a CID.
        7. Writes the block using the BlockWriter.
        8. Handles BlockWriter closing based on options.
        9. Returns a DirectoryLink to the created directory block.
        """
        if self.state.closed:
            # Consider if it should re-calculate and return the link or raise error.
            # For simplicity, raise error if trying to re-close.
            raise RuntimeError("Directory is already closed.")

        self.state.closed = True # Mark as closed early
        close_opts = options or CloseOptions()
        logger.info(f"Closing directory with {len(self.state.entries)} entries.")

        # 1. Prepare NamedDAGLink list for FlatDirectory object, sorted by name
        # This is crucial for canonical representation.
        sorted_entry_names = sorted(self.state.entries.keys())
        dir_entry_links: List[NamedDAGLink] = []
        for name in sorted_entry_names:
            link_obj = self.state.entries[name]
            dir_entry_links.append(
                NamedDAGLink(name=name, cid=link_obj.cid, dag_byte_length=link_obj.dag_byte_length)
            )

        # 2. Create logical FlatDirectory object
        flat_dir_node_logical = FlatDirectory(
            entries=dir_entry_links,
            metadata=self.state.metadata
        )

        # 3. Serialize UnixFS Data field (Type=DIRECTORY, with metadata)
        # TODO: awaiting when the codecs are ready
        # unixfs_data_bytes = serialize_unixfs_data_field(
        #     node_type=NodeType.DIRECTORY,
        #     metadata=flat_dir_node_logical.metadata
        # )

        # 4. Convert DirectoryEntryLinks (NamedDAGLinks) to PBLinks for DAG-PB encoder
        pb_links_for_encoder: List[PBLink] = [
            PBLink(Name=entry.name, Hash=entry.cid, Tsize=entry.dag_byte_length)
            for entry in flat_dir_node_logical.entries
        ]

        # 5. Encode the DAG-PB node
        # TODO: awaiting when the codecs are ready
        # encoded_block_bytes = self.settings.dag_pb_encoder(
        #     links=pb_links_for_encoder, data=unixfs_data_bytes
        # )
        # logger.debug(f"Encoded DAG-PB block bytes (len: {len(encoded_block_bytes)})")


        # 6. Hash and create CID
        # TODO: awaiting when the codecs are ready
        # digest = await self.settings.hasher.digest(encoded_block_bytes)
        # UnixFS (non-raw leaf) typically uses DAG-PB codec code 0x70
        # cid = self.settings.linker.create_link(codec_code=0x70, digest=digest) # 0x70 is dag-pb
        # logger.info(f"Finalized directory CID: {cid.to_string()}")

        # 7. Write block using BlockWriter
        # TODO: awaiting when the codecs are ready
        # final_block = Block(cid=cid, bytes=encoded_block_bytes, value=flat_dir_node_logical)
        # await self.state.writer.write(final_block)
        # logger.debug(f"Wrote directory block to BlockWriter.")

        # 8. Handle BlockWriter closing options
        if close_opts.close_writer:
            await self.state.writer.close()
            logger.debug("Closed underlying BlockWriter.")

        # 9. Determine dagByteLength for the DirectoryLink
        # For a flat directory, this is the size of its own encoded block.
        # dir_dag_byte_length = len(encoded_block_bytes)

        return DirectoryLink(cid=cid, dag_byte_length=dir_dag_byte_length)

    def fork(self, options: Optional[DirectoryCreateOptions] = None) -> "PythonFlatDirectoryWriter":
        """
        Creates a new PythonFlatDirectoryWriter instance with a copied state,
        allowing for modifications without affecting the original (especially if closed).
        New components (writer, settings, metadata) can be provided via options.
        """
        opts = options or DirectoryCreateOptions( # Provide defaults if options is None
            writer=self.state.writer,
            settings=self.state.settings,
            metadata=self.state.metadata
        )

        # Deep copy mutable parts of the state if necessary,
        # but for dict of immutable CIDs/basic types, .copy() is fine.
        new_entries_map = self.state.entries.copy()

        # Metadata: use new if provided, else copy existing (dataclasses are fine with replace)
        new_metadata = opts.metadata if opts.metadata is not None else \
                       (replace(self.state.metadata) if self.state.metadata else Metadata())


        new_state = DirectoryWriterState(
            entries=new_entries_map,
            metadata=new_metadata, # type: ignore
            writer=opts.writer,
            settings=opts.settings,
            closed=False, # A new fork is always open
        )
        logger.debug(f"Forked directory. Original closed: {self.state.closed}. New entries: {len(new_entries_map)}")
        return PythonFlatDirectoryWriter(new_state)

    def entries(self) -> Iterable[Tuple[str, EntryLink]]:
        """Iterates over (name, EntryLink) pairs."""
        return self.state.entries.items()

    def iter_entry_links(self) -> Iterable[NamedDAGLink]:
        """Iterates over entries yielding NamedDAGLink objects."""
        for name, link_obj in self.state.entries.items():
            yield NamedDAGLink(name=name, cid=link_obj.cid, dag_byte_length=link_obj.dag_byte_length)

    def has(self, name: str) -> bool:
        """Checks if an entry with the given name exists."""
        return name in self.state.entries

    @property
    def size(self) -> int:
        """Returns the number of entries in the directory."""
        return len(self.state.entries)



def create(options: DirectoryCreateOptions) -> PythonFlatDirectoryWriter:
    """
    Factory function to create a new PythonFlatDirectoryWriter instance.
    Ensures that necessary settings and a block writer are provided.
    """
    if not isinstance(options, DirectoryCreateOptions):
        raise TypeError("Invalid options type for directory creation.")
    if not hasattr(options.settings, 'hasher') or \
       not hasattr(options.settings, 'linker') or \
       not hasattr(options.settings, 'dag_pb_encoder'):
        raise ValueError("EncoderSettings must provide hasher, linker, and dag_pb_encoder.")

    # Initialize with default metadata if none provided
    current_metadata = options.metadata if options.metadata is not None else Metadata()
    # You might want to set default mode/mtime for directories here if not present
    if current_metadata.mode is None:
        current_metadata.mode = Mode(0o755) # Default directory mode
    # if current_metadata.mtime is None:
    #    current_metadata.mtime = UnixFSTime(Seconds=int(time.time()), FractionalNanoseconds=0)


    initial_state = DirectoryWriterState(
        entries={}, # Starts empty
        metadata=current_metadata,
        writer=options.writer,
        settings=options.settings,
        closed=False,
    )
    logger.info("Created new PythonFlatDirectoryWriter.")
    return PythonFlatDirectoryWriter(initial_state)

__all__ = [
    "DirectoryWriter",
    "DirectoryView",
    "DirectoryWriterState",
    "EntryLink",
    "DirectoryWriteOptions",
    "DirectoryCreateOptions",
    "create",
    "PythonFlatDirectoryWriter",
]
