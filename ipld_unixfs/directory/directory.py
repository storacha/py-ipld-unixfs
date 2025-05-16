# ipld_unixfs/directory/__init__.py
import logging
from typing import Optional, Dict, List, Iterable, Tuple, cast, Sequence
from dataclasses import replace # For fork
from ipld_dag_pb import PBLink
from multiformats import CID

from .api import (
    DirectoryWriter,
    DirectoryView,
    DirectoryWriterState,
    EntryLink, # Link to a File or Directory (CID + size)
    DirectoryEntryLink, # Named link (Name + CID + size)
    DirectoryWriteOptions,
    DirectoryCreateOptions,
)
from ..unixfs import (
    Metadata,
    FlatDirectory,
    DirectoryLink,
    NodeType,
)
# Assuming EncoderSettings, BlockWriter, CloseOptions, Block are defined here
from ..file.api import EncoderSettings, BlockWriter, CloseOptions, Block

logger = logging.getLogger(__name__)

# --- Helper: UnixFS Protobuf Data Serialization (Placeholder) ---
def _serialize_unixfs_directory_data(metadata: Optional[Metadata]) -> bytes:
    """Serializes the UnixFS Data field for a Flat Directory."""
    # This function will use your Python Protobuf library for UnixFS.Data
    # data_pb = UnixFSDataPb()
    # data_pb.Type = UnixFSDataPb.Directory # Enum value for Directory
    # if metadata and metadata.mode:
    #     data_pb.mode = metadata.mode.value
    # if metadata and metadata.mtime:
    #     data_pb.mtime.seconds = metadata.mtime.secs
    #     if metadata.mtime.nsecs is not None:
    #         data_pb.mtime.nanos = metadata.mtime.nsecs
    # return data_pb.SerializeToString()
    logger.warning("_serialize_unixfs_directory_data: Placeholder used. Implement with actual Protobuf.")
    # Minimal placeholder if no metadata
    if metadata is None or (metadata.mode is None and metadata.mtime is None):
         # This is the protobuf for Type=Directory, no other fields.
         # The actual bytes depend on your .proto definition.
         # Example for `message Data { enum DataType { Raw = 0; Directory = 1; ... } DataType Type = 1; }`
         # Field Type=1 (tag 0x08), Value Directory=1 (0x01) -> bytes([0x08, 0x01])
        return bytes([0x08, 0x01]) # Minimal Type=Directory
    raise NotImplementedError("UnixFS Protobuf Data serialization for Directory with metadata needed.")


# --- Helper: Cumulative DAG Byte Length (Placeholder) ---
def _calculate_cumulative_dag_byte_length(
    block_bytes: bytes, links: Sequence[PBLink]
) -> int:
    """Calculates cumulative size of a node (block + links)."""
    # This is often just the size of the current block's bytes if Tsize in PBLink
    # already represents the full cumulative size of the linked child.
    # If Tsize is just the child's root block size, then this needs to be recursive.
    # The JS `UnixFS.cumulativeDagByteLength(bytes, entries)` implies it might sum
    # current block bytes with Tsize of entries. Let's assume Tsize in PBLink is cumulative.
    # size = len(block_bytes)
    # for link in links:
    #    size += link.Tsize # This would be double counting if Tsize is already cumulative
    # The spec usually implies Tsize in a PBLink *is* the cumulative size of the target.
    # So the cumulative size of *this* node is its block size + sum of Tsize of its links *if*
    # this node is not a leaf. But for a DirectoryLink, dagByteLength should be *its own* total.
    # The JS implementation: `UnixFS.cumulativeDagByteLength(root.bytes, root.value.entries)`
    # for a HAMT shard. For a flat directory, it's likely the encoded block size.
    # Let's assume for now it's the size of the encoded directory block itself.
    # The `dagByteLength` on a `DirectoryLink` should be the total size of the directory *DAG*.
    # If it's a single flat directory block, then it's just len(block_bytes).
    logger.warning("_calculate_cumulative_dag_byte_length: Placeholder. Verify logic.")
    return len(block_bytes)


class PythonFlatDirectoryWriter(DirectoryView):
    state: DirectoryWriterState

    def __init__(self, initial_state: DirectoryWriterState):
        self.state = initial_state

    @property
    def writer(self) -> BlockWriter:
        return self.state.writer

    @property
    def settings(self) -> EncoderSettings:
        return self.state.settings

    def _as_writable_state(self) -> DirectoryWriterState:
        if self.state.closed:
            raise RuntimeError(
                "Directory is closed and cannot be modified. "
                "Use fork() to create a new writable version."
            )
        return self.state.entries, self.state.metadata

    def set(
        self, name: str, entry: EntryLink, options: Optional[DirectoryWriteOptions] = None
    ) -> "PythonFlatDirectoryWriter":
        current_entries, _ = self._as_writable_state()
        opts = options or DirectoryWriteOptions()

        if "/" in name:
            raise ValueError(
                f"Directory entry name \"{name}\" contains forbidden \"/\" character"
            )
        if not opts.overwrite and name in current_entries:
            raise ValueError(
                f"Directory already contains entry with name \"{name}\""
            )
        current_entries[name] = entry
        return self

    def remove(self, name: str) -> "PythonFlatDirectoryWriter":
        current_entries, _ = self._as_writable_state()
        if name in current_entries:
            del current_entries[name]
        return self

    async def close(self, options: Optional[CloseOptions] = None) -> DirectoryLink:
        if self.state.closed:
            # If already closed, perhaps return the existing link if stored, or raise error
            raise RuntimeError("Directory is already closed.")

        # Mark as closed early
        self.state.closed = True
        close_opts = options or CloseOptions()

        # Prepare DirectoryEntryLink list for FlatDirectory object
        dir_entry_links: List[DirectoryEntryLink] = []
        for name, link_obj in self.state.entries.items():
            dir_entry_links.append(
                DirectoryEntryLink(name=name, cid=link_obj.cid, dag_byte_length=link_obj.dag_byte_length)
            )
        
        # Sort entries by name for canonical representation
        dir_entry_links.sort(key=lambda x: x.name)


        # 1. Create logical FlatDirectory object
        flat_dir_node = FlatDirectory(
            entries=dir_entry_links,
            metadata=self.state.metadata
        )

        # 2. Serialize UnixFS Data field (Type=Directory, with metadata)
        unixfs_data_bytes = _serialize_unixfs_directory_data(flat_dir_node.metadata)

        # 3. Convert DirectoryEntryLinks to PBLinks for DAG-PB encoder
        pb_links: List[PBLink] = [
            PBLink(Name=entry.name, Hash=entry.cid, Tsize=entry.dag_byte_length)
            for entry in flat_dir_node.entries
        ]

        # 4. Encode the DAG-PB node
        if not hasattr(self.settings, 'dag_pb_encoder') or not callable(self.settings.dag_pb_encoder):
            raise AttributeError("dag_pb_encoder is not defined or not callable in settings.")
        
        encoded_block_bytes = self.settings.dag_pb_encoder(
            links=pb_links, data=unixfs_data_bytes
        )

        # 5. Hash and create CID
        digest = await self.settings.hasher.digest(encoded_block_bytes)
        # UnixFS (non-raw) typically uses DAG-PB codec code 0x70
        # The JS `UnixFS.code` is likely this.
        cid = self.settings.linker.create_link(codec_code=0x70, digest=digest)

        # 6. Write block using BlockWriter
        #    The JS version checks writer.desiredSize for backpressure.
        #    Assuming Python BlockWriter has an async write method.
        #    If backpressure needed:
        #    if (self.writer.desired_size is not None and self.writer.desired_size <= 0):
        #        await self.writer.ready() # If your BlockWriter supports this
        await self.writer.write(
            Block(cid=cid, bytes=encoded_block_bytes, value=flat_dir_node)
        ) # Passing the logical node as value

        # 7. Handle BlockWriter closing options
        if close_opts.close_writer:
            await self.writer.close()
        # elif close_opts.release_lock and hasattr(self.writer, 'release_lock'):
        #    self.writer.releaseLock()


        # 8. Determine dagByteLength for the DirectoryLink
        # For a flat directory, this is just the size of its own encoded block.
        # The JS `UnixFS.cumulativeDagByteLength(bytes, entries)` suggests that for a flat dir,
        # it might sum its own block size with the Tsize of its direct entries.
        # However, a DirectoryLink's dagByteLength should represent the total size of the *directory object itself*.
        # Let's stick to len(encoded_block_bytes) for a flat directory.
        # The Tsize in the PBLinks *inside* this directory block refer to the cumulative sizes of the *children*.
        dir_dag_byte_length = len(encoded_block_bytes)


        return DirectoryLink(cid=cid, dag_byte_length=dir_dag_byte_length)

    def fork(self, options: Optional[Dict] = None) -> "PythonFlatDirectoryWriter":
        opts = options or {}
        current_state = self.state

        new_entries_map = current_state.entries.copy() # Shallow copy is fine for dict of immutable CIDs/basic types

        # Deepcopy metadata if it's mutable and complex, otherwise direct assignment or replace is fine
        new_metadata = current_state.metadata
        if "metadata" in opts and opts["metadata"] is not None:
            new_metadata = opts["metadata"]
        elif new_metadata is not None: # Ensure we are not modifying the original if it's complex
             new_metadata = replace(new_metadata) # if Metadata is a dataclass

        new_writer = opts.get("writer", current_state.writer)
        
        # Settings merge logic can be complex. Assuming direct override or use current.
        new_settings = opts.get("settings", current_state.settings)
        if "settings" in opts and opts["settings"] is not None:
            # Potentially merge settings if EncoderSettings supports it, or just replace
            new_settings = configure_directory_settings(opts["settings"], current_state.settings)
        else:
            new_settings = current_state.settings


        new_state = DirectoryWriterState(
            entries=new_entries_map,
            metadata=new_metadata,
            writer=new_writer,
            settings=new_settings, # type: ignore
            closed=False,
        )
        return PythonFlatDirectoryWriter(new_state)

    def entries(self) -> Iterable[Tuple[str, EntryLink]]:
        return self.state.entries.items()

    def iter_entry_links(self) -> Iterable[DirectoryEntryLink]:
        """Yields DirectoryEntryLink objects (NamedDAGLink)."""
        for name, link_obj in self.state.entries.items():
            yield DirectoryEntryLink(name=name, cid=link_obj.cid, dag_byte_length=link_obj.dag_byte_length)

    def has(self, name: str) -> bool:
        return name in self.state.entries

    @property
    def size(self) -> int:
        return len(self.state.entries)



_DEFAULT_ENCODER_SETTINGS: Optional[EncoderSettings] = None # Module-level placeholder

def get_default_settings() -> EncoderSettings:
    """ Placeholder for global default EncoderSettings specific to the library. """
    global _DEFAULT_ENCODER_SETTINGS
    if _DEFAULT_ENCODER_SETTINGS is None:
        # This should be initialized by your library's main __init__ or config module
        raise RuntimeError("Default EncoderSettings not initialized for ipld-unixfs.")
    return _DEFAULT_ENCODER_SETTINGS

def configure_directory_settings_globally(
    options_settings: Optional[EncoderSettings] = None,
) -> EncoderSettings:
    """ Configures settings by merging options with global defaults. """
    # This function would be more complex, merging dataclasses or TypedDicts field by field
    base = get_default_settings()
    if options_settings:
        # Simplified: assumes options_settings can override base if it's a dict or similar
        # For dataclasses: return replace(base, **{k:v for k,v in asdict(options_settings).items() if v is not None})
        # For TypedDict: return {**base, **options_settings}
        if isinstance(base, dict) and isinstance(options_settings, dict):
             return {**cast(dict, base), **cast(dict,options_settings)} # type: ignore
        # Add proper merging for your EncoderSettings structure
        logger.warning("configure_directory_settings_globally: Using simplistic settings override.")
        return options_settings
    return base


def create(options: DirectoryCreateOptions) -> PythonFlatDirectoryWriter:
    """
    Creates a new flat directory writer.
    """
    # The JS version pulls defaults() then merges settings.
    # Python equivalent would be:
    # final_settings = configure_directory_settings_globally(options.settings)
    # We made EncoderSettings non-optional in DirectoryCreateOptions
    final_settings = options.settings

    initial_state = DirectoryWriterState(
        entries={},
        metadata=options.metadata if options.metadata is not None else Metadata(),
        writer=options.writer,
        settings=final_settings,
        closed=False,
    )
    return PythonFlatDirectoryWriter(initial_state)

__all__ = [
    "DirectoryWriter",
    "DirectoryView",
    "DirectoryWriterState",
    "EntryLink",
    "DirectoryEntryLink",
    "DirectoryWriteOptions",
    "DirectoryCreateOptions",
    "create",
    "PythonFlatDirectoryWriter",
]