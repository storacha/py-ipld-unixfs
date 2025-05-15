# ipld_unixfs/directory/__init__.py
from typing import TypeVar, Optional, Dict, List, AsyncIterable, Tuple, Any
from dataclasses import dataclass, field
import logging # For logging HAMT operations if needed

from multiformats import CID, multihash # For CID creation and hashing
from multiformats.multihash.murmur3 import murmur3_x64_64 # For HAMT bucket hashing (murmur3-64)
from ipld_dag_pb import PBNode, encode, decode, code, PBLink

# Imports from .api
from .api import (
    DirectoryWriter,
    DirectoryView,
    DirectoryWriterState,
    DirectoryEntryData,
    EntryLink,
    DirectoryWriteOptions,
    DirectoryCreateOptions, # Using the new CreateOptions
)

# Assuming these are (or will be) defined in your Python project structure
from ..unixfs import (
    Metadata,
    FileLink,
    DirectoryLink,
    DirectoryEntryLink, # This should be defined in unixfs.py for named links
    DirectoryShard,     # Logical representation of a HAMT shard
    NodeType,
)
from ..file.api import (
    BlockWriter,
    EncoderSettings, # Assuming this is the concrete type for settings
    CloseOptions,
    Block, # Assuming Block is dataclass(cid: CID, bytes: bytes, value: Any)
)
# TODO: implement a Python HAMT implementation.

# TODO: implement UnixFS Data protobuf serialization
# from ..proptobuf_unixfs_definitions import Data as UnixFSProtobufData # Placeholder for protoc generated class

from ipld_dag_pb import (
    encode_node as encode_dag_pb_node,
    PBLink,
)

# Logger for this module
logger = logging.getLogger(__name__)

Layout = TypeVar("Layout")



def default_directory_settings(base_settings: Optional[EncoderSettings[Layout]] = None) -> EncoderSettings[Layout]:
    """Provides default encoder settings, potentially extending base file settings."""
    if base_settings:
        # NOTE: In JS, directory settings often reuse file settings (hasher, linker)
        # I might not need specific directory overrides if file.api.EncoderSettings is sufficient
        return base_settings
    else:
        # NOTE: Fallback if no base_settings provided; create a minimal one.
        # This part depends heavily on how EncoderSettings is defined in the Python project.
        # For now, i'm assuming it's passed in.
        raise ValueError("Base EncoderSettings must be provided for directory operations.")


def configure_directory_settings(
    options_settings: Optional[EncoderSettings[Layout]] = None,
    global_defaults: Optional[EncoderSettings[Layout]] = None,
) -> EncoderSettings[Layout]:
    """Configures settings by merging options with defaults."""
    final_settings = global_defaults if global_defaults else default_directory_settings()
    if options_settings:
        # NOTE: Perform a merge. For dataclasses, you might use asdict and update.
        # This is simplified; robust merging depends on EncoderSettings structure.
        # For TypedDict, it's a dictionary update.
        if isinstance(final_settings, dict) and isinstance(options_settings, dict): # TypedDict
            final_settings.update(options_settings)
        elif hasattr(final_settings, '__dict__') and hasattr(options_settings, '__dict__'): # Dataclass
            final_settings_dict = final_settings.__dict__
            final_settings_dict.update({k:v for k,v in options_settings.__dict__.items() if v is not None})
            final_settings = type(final_settings)(**final_settings_dict)
        else:
            final_settings = options_settings

    if not (hasattr(final_settings, 'hasher') and hasattr(final_settings, 'linker') and hasattr(final_settings, 'dag_pb_encoder')):
        raise ValueError("EncoderSettings misconfigured: missing hasher, linker or dag_pb_encoder")
    return final_settings



class PythonHAMTDirectoryWriter(DirectoryView[Layout]):
    """
    Python implementation mirroring JS HAMTDirectoryWriter.
    Requires a Python HAMT library.
    """
    state: DirectoryWriterState[Layout]

    def __init__(self, initial_state: DirectoryWriterState[Layout]):
        self.state = initial_state
        # Ensure the 'entries' in state is a HAMT map/builder instance
        # if not isinstance(self.state.entries, YourPythonHAMTLibrary.Map):
        #     # Or initialize it here if it wasn't pre-initialized
        #     self.state.entries = YourPythonHAMTLibrary.builder() # Example

    @property
    def writer(self) -> BlockWriter:
        return self.state.writer

    @property
    def settings(self) -> EncoderSettings[Layout]:
        return self.state.settings

    def _as_writable_state(self) -> DirectoryWriterState[Layout]:
        if self.state.closed:
            raise RuntimeError(
                "Directory is closed and cannot be modified. "
                "Use fork() to create a new writable version."
            )
        return self.state

    def set(
        self, name: str, entry: EntryLink, options: Optional[DirectoryWriteOptions] = None
    ) -> "PythonHAMTDirectoryWriter[Layout]":
        state = self._as_writable_state()
        write_opts = options or DirectoryWriteOptions()

        # TODO: implement HAMT-specific logic:
        # current_hamt_map = state.entries # Assuming entries is the HAMT map/builder
        # if not write_opts.overwrite and current_hamt_map.has(name):
        #     raise ValueError(f"Entry '{name}' already exists and overwrite is false.")
        # current_hamt_map.set(name, entry)
        logger.warning("HAMT set() logic not fully implemented. Needs Python HAMT library.")
        state.entries[name] = entry # Simplified: direct dict operation
        return self

    def remove(self, name: str) -> "PythonHAMTDirectoryWriter[Layout]":
        state = self._as_writable_state()
        # TODO: implement HAMT-specific logic:
        # current_hamt_map = state.entries
        # current_hamt_map.delete(name)
        logger.warning("HAMT remove() logic not fully implemented. Needs Python HAMT library.")
        if name in state.entries: # Simplified: direct dict operation
            del state.entries[name]
        return self

    async def _encode_hamt_shard_block(
        self, shard_data: DirectoryShard
    ) -> Block[DirectoryShard]:
        """
        Encodes a logical DirectoryShard into an IPLD Block.
        Mirrors JS `encodeHAMTShardBlock`.
        """
        # TODO: implement UnixFS Protobuf Data field for the HAMTShard
        # unixfs_pb = UnixFSProtobufData(
        #     Type=NodeType.HAMTShard.value, # Ensure NodeType has .value for enum int
        #     # fanout=shard_data.fanout, # from DirectoryShard object
        #     # hashType=shard_data.hash_type, # from DirectoryShard object
        #     # data=shard_data.bitfield, # Bitfield might go into data or a specific field
        # )
        # Actual fanout, hashType, bitfield population depends on your DirectoryShard definition
        # and how it maps to the UnixFSData protobuf message.
        # unixfs_pb_bytes = unixfs_pb.SerializeToString() # Using actual protobuf library


        # The DAG-PB encoder needs links (from shard_data.entries) and the UnixFS data bytes
        # Convert shard_data.entries (DirectoryEntryLink) to PBLink for DAG-PB encoder
        pb_links: List[PBLink] = []
        for entry_link in shard_data.entries: # Assuming shard_data has 'entries'
            pb_links.append(PBLink(Name=entry_link.name, Hash=entry_link.cid, Tsize=entry_link.dag_byte_length))

        # TODO: implement UnixFS for HAMTShard
        # unixfs_data_for_dagpb_node = self._serialize_unixfs_protobuf_for_hamtshard(shard_data)
        # block_bytes = self.settings.dag_pb_encoder(links=pb_links, data=unixfs_data_for_dagpb_node)
        raise NotImplementedError("_encode_hamt_shard_block: UnixFS & DAG-PB encoding for HAMTShard needed.")


        # TODO: Hash the block bytes
        # block_hash_digest = await self.settings.hasher.digest(block_bytes) # Assuming async hasher

        # 3. Create CID
        # block_cid = self.settings.linker.create_link(
        #     # Assuming dag-pb codec code (0x70)
        #     # Your linker might take the codec name or code directly
        #     codec_code=0x70, # dag-pb
        #     digest=block_hash_digest
        # )
        # return Block(cid=block_cid, bytes=block_bytes, value=shard_data)


    async def _iterate_hamt_blocks(
        self, hamt_node: Any # Python HAMT node type
    ) -> AsyncIterable[Block[DirectoryShard]]:
        """
        Recursively iterates HAMT nodes, encodes them, and yields blocks.
        Mirrors JS `iterateBlocks`. Highly dependent on Python HAMT library.
        """
        # This is a very complex part that needs a Python HAMT library
        # with similar iteration capabilities as @perma/map.
        # Conceptual structure:
        #
        # collected_entries_for_current_shard: List[DirectoryEntryLink] = []
        #
        # for item in your_hamt_lib.iterate_node_contents(hamt_node):
        #     if item.is_direct_value_entry: # e.g. ('foo.txt', FileLink(...))
        #         collected_entries_for_current_shard.append(
        #             DirectoryEntryLink(name=item.key, cid=item.value.cid, dag_byte_length=item.value.dag_byte_length)
        #         )
        #     elif item.is_sub_hamt_node_pointer: # A link to another shard
        #         sub_shard_root_block: Optional[Block[DirectoryShard]] = None
        #         async for block in self._iterate_hamt_blocks(item.sub_node_pointer):
        #             yield block
        #             sub_shard_root_block = block # Keep track of the last yielded (root of sub-shard)
        #
        #         if sub_shard_root_block is None:
        #             raise RuntimeError("Sub-shard iteration yielded no root block.")
        #
        #         # Create a link to this sub-shard's root
        #         collected_entries_for_current_shard.append(
        #             DirectoryEntryLink(
        #                 name=item.prefix_for_sub_node, # HAMT prefix
        #                 cid=sub_shard_root_block.cid,
        #                 dag_byte_length=sub_shard_root_block.value.calculate_cumulative_size() # Or from block
        #             )
        #         )
        #
        # # After collecting all entries for the current hamt_node (shard):
        # current_shard_logical_data = DirectoryShard(
        #     entries=collected_entries_for_current_shard,
        #     bitfield=your_hamt_lib.get_bitfield(hamt_node),
        #     fanout=your_hamt_lib.get_fanout(hamt_node), # Or from settings
        #     hash_type=murmur3_x64_64.code # Multicodec for murmur3-64
        # )
        #
        # encoded_block = await self._encode_hamt_shard_block(current_shard_logical_data)
        # yield encoded_block
        logger.critical("PythonHAMTDirectoryWriter._iterate_hamt_blocks requires a compatible Python HAMT library.")
        raise NotImplementedError("HAMT block iteration not implemented.")
        yield # Make it an async generator

    async def close(self, options: Optional[CloseOptions] = None) -> DirectoryLink:
        state = self._as_writable_state()
        close_opts = options or CloseOptions() # Assuming CloseOptions is defined

        # Finalize the HAMT structure
        # final_hamt_structure = state.entries.build() # Or however your HAMT lib finalizes
        # hamt_root_node = final_hamt_structure.root_node()
        logger.critical("PythonHAMTDirectoryWriter.close requires Python HAMT finalization.")
        if not state.entries: # Simplified for non-HAMT case
             # Handle empty directory case: create an empty DAG-PB node with UnixFS Directory type
            empty_unixfs_pb = UnixFSProtobufData(Type=NodeType.Directory.value)
            # empty_unixfs_pb_bytes = empty_unixfs_pb.SerializeToString()
            # empty_dir_block_bytes = self.settings.dag_pb_encoder(links=[], data=empty_unixfs_pb_bytes)
            # empty_dir_hash = await self.settings.hasher.digest(empty_dir_block_bytes)
            # empty_dir_cid = self.settings.linker.create_link(0x70, empty_dir_hash)
            # return DirectoryLink(cid=empty_dir_cid, dag_byte_length=len(empty_dir_block_bytes))
            raise NotImplementedError("Empty directory closing not fully implemented.")


        # Iterate through HAMT shards, encode them, and write to BlockWriter
        root_hamt_block: Optional[Block[DirectoryShard]] = None
        # async for block in self._iterate_hamt_blocks(hamt_root_node):
        #     root_hamt_block = block
        #     # Handle BlockWriter backpressure if necessary
        #     # if (self.state.writer.desired_size is not None and self.state.writer.desired_size <= 0):
        #     #    await self.state.writer.ready() # If your BlockWriter supports this
        #     await self.state.writer.write(block) # Assuming BlockWriter is async

        # if root_hamt_block is None:
        #     raise RuntimeError("HAMT processing yielded no root block for the directory.")
        raise NotImplementedError("PythonHAMTDirectoryWriter.close HAMT processing not implemented.")

        state.closed = True

        # Handle BlockWriter closing/releasing lock
        # if close_opts.close_writer:
        #     await self.state.writer.close()
        # elif close_opts.release_lock: # If writer has a locking mechanism
        #     self.state.writer.releaseLock()

        # Calculate cumulative size for the root DirectoryLink
        # cumulative_size = root_hamt_block.value.calculate_cumulative_size() # Or from block.bytes and links

        # return DirectoryLink(cid=root_hamt_block.cid, dag_byte_length=cumulative_size)


    def fork(self, options: Optional[Dict] = None) -> "PythonHAMTDirectoryWriter[Layout]":
        opts = options or {}
        current_state = self.state

        # Create a new state, deep copying mutable parts, especially the HAMT structure
        # new_hamt_map_builder = current_state.entries.fork_builder() # If HAMT lib supports efficient forking
        new_entries_map = current_state.entries.copy() # Simplified for dict
        logger.warning("HAMT fork() logic not fully implemented. Needs Python HAMT library support for efficient forking.")


        new_state = DirectoryWriterState(
            entries=new_entries_map,
            metadata=current_state.metadata, # Assumed immutable or deep copied if mutable
            writer=opts.get("writer", current_state.writer),
            settings=configure_directory_settings(
                opts.get("settings"), current_state.settings
            ),
            closed=False,
        )
        return PythonHAMTDirectoryWriter(new_state)

    def entries(self) -> Iterable[Tuple[str, EntryLink]]:
        # For HAMT, this would iterate through the HAMT map
        # return self.state.entries.items_iterable() # Example
        return self.state.entries.items() # For dict

    def has(self, name: str) -> bool:
        # return self.state.entries.has(name) # For HAMT
        return name in self.state.entries # For dict

    @property
    def size(self) -> int:
        # return self.state.entries.size() # For HAMT
        return len(self.state.entries) # For dict



def create(options: DirectoryCreateOptions[Layout]) -> PythonHAMTDirectoryWriter[Layout]:
    """
    Creates a new directory writer.
    Mirrors `create` in JS.
    """
    # Get global default settings if your project has a way to provide them
    # For now, assume EncoderSettings must be somewhat complete in options or we make one.
    if options.settings is None:
        raise ValueError("EncoderSettings must be provided in DirectoryCreateOptions.")

    # # In a real scenario, you'd have a global default_settings_instance
    # # configured_settings = configure_directory_settings(options.settings, global_default_settings_instance)
    # configured_settings = options.settings # Assuming options.settings is already fully configured

    initial_hamt_entries_map: Dict[str, EntryLink] = {} # TODO: Replace with PythonHAMTMap() or Builder()

    initial_state = DirectoryWriterState(
        entries=initial_hamt_entries_map,
        metadata=options.metadata or Metadata(), # Assuming Metadata() creates a default
        writer=options.writer,
        settings=configured_settings,
        closed=False,
    )
    return PythonHAMTDirectoryWriter(initial_state)

# Exports for users of this module
__all__ = [
    "DirectoryWriter",
    "DirectoryView",
    "DirectoryWriterState",
    "DirectoryEntryData",
    "EntryLink",
    "DirectoryWriteOptions",
    "DirectoryCreateOptions",
    "create",
    "PythonHAMTDirectoryWriter",
    "default_directory_settings",
    "configure_directory_settings",
]