import asyncio
from dataclasses import dataclass
from typing import Generic, Literal, Sequence, TypeAlias, TypeVar, TypedDict, cast

import actress as Task

from ipld_unixfs import codec, unixfs
from ipld_unixfs.file import interfaces as API
from ipld_unixfs.file.chunker.interfaces import Chunk
from ipld_unixfs.file.layout import interfaces as Layout, queue
from ipld_unixfs.file.layout.queue.interfaces import LinkedNode
from ipld_unixfs.multiformats.hashes.interface import MultihashDigest
from ipld_unixfs.writer.utils import EMPTY_BUFFER
from . import chunker


LayoutT = TypeVar("LayoutT")
T = TypeVar("T")


@dataclass(frozen=True)
class Open(Generic[LayoutT, T]):
    metadata: unixfs.Metadata
    config: API.EncoderSettings[LayoutT, T]
    writer: API.BlockWriter
    chunker: chunker.Chunker[T]
    layout: LayoutT
    node_queue: queue.Queue
    status: Literal["open"] = "open"


@dataclass(frozen=True)
class Closed(Generic[LayoutT, T]):
    metadata: unixfs.Metadata
    config: API.EncoderSettings[LayoutT, T]
    writer: API.BlockWriter
    root_id: Layout.NodeID
    end: Task.Fork[None, None, None] | None  # type: ignore[arg-type]
    node_queue: queue.Queue
    status: Literal["closed"]


@dataclass(frozen=True)
class Linked(Generic[LayoutT, T]):
    metadata: unixfs.Metadata
    config: API.EncoderSettings[LayoutT, T]
    writer: API.BlockWriter
    link: unixfs.FileLink
    node_queue: queue.Queue
    status: Literal["linked"]


State: TypeAlias = Open[LayoutT, T] | Closed[LayoutT, T] | Linked[LayoutT, T]


class WriteMessage(TypedDict):
    type: Literal["write"]
    bytes_data: bytes

class LinkMessage(TypedDict):
    type: Literal["link"]
    link: API.EncodedFile


class BlockMessage(TypedDict):
    type: Literal["block"]


class CloseMessage(TypedDict):
    type: Literal["close"]


class EndMessage(TypedDict):
    type: Literal["end"]


Message: TypeAlias = WriteMessage | LinkMessage | BlockMessage | CloseMessage | EndMessage | None


@dataclass
class Update(Generic[LayoutT, T]):
    state: State[LayoutT, T]
    effect: Task.Effect[Message]


def update(message: Message, state: State[LayoutT, T]) -> Update[LayoutT, T]:
    if message is not None:
        match (message["type"]):
            case "write":
                return write(state, message["bytes_data"])
            case "link":
                return link(state, message["link"])
            case "block":
                return Update(state, effect=Task.none_())
            case "close":
                return close(state)
            case "end":
                return Update(state, effect=Task.none_())

    class UnkownFileWriterMessageError(RuntimeError):
        pass
    raise UnkownFileWriterMessageError(f"File writer got unknown message {message}")


def init(writer: API.BlockWriter, metadata: unixfs.Metadata, config: API.EncoderSettings):
    return Open(
        metadata=metadata,
        config=config,
        writer=writer,
        chunker=chunker.open(chunker.Config(chunker=config.chunker)),
        layout=config.file_layout.open(),
        # Note: Writing in large slices e.g 1GiB at a time creates large
        # queues with around `16353` items. Immutable version ends up copying
        # it everytime state of the queue changes, which introduces significant
        # overhead.
        # To avoid this overhead, we use mutable implementation which is API
        # compatible but makes in place updates.
        # TODO: We should consider using Persistent bit-partitioned vector
        # tries instead of arrays which would provide immutable with neglibigle
        # overhead.
        # see: https://github.com/Gozala/vectrie
        node_queue=queue.mutable(),
    )


def write(state: State[LayoutT, T], bytes_data: bytes) -> Update[LayoutT, T]:
    if (state.status == "open"):
        # chunk up the provided bytes
        chunker_with_chunks = chunker.write(state=state.chunker, bytes_data=bytes_data)
        chunks = chunker_with_chunks.chunks

        # pass chunks to layout engine to produce nodes.
        write_result = state.config.file_layout.write(layout=state.layout, chunks=chunks)
        layout = write_result.layout
        nodes = write_result.nodes
        leaves = write_result.leaves

        result = queue.add_nodes(nodes, state.node_queue)
        linked = list(result.linked)
        if result.mutable:
            result.linked.clear()

        # create leaf encode tasks for all new leaves
        tasks = encode_leaves(leaves, state.config) + encode_branches(linked, state.config)

        chunker_wout_chunks = chunker.Chunker(buffer=chunker_with_chunks.buffer, config=chunker_with_chunks.config)
        return Update(
            effect=Task.listen(sources={"link": Task.effects(tasks)}),  # pyright: ignore[reportArgumentType]
            state=Open(
                metadata=state.metadata,
                config=state.config,
                writer=state.writer,
                chunker=chunker_wout_chunks,
                layout=layout,
                node_queue=result
            ),
        )
    else:
        raise Exception("Unable to perform write on a closed file")


def link(state: State[LayoutT, T], entry: API.EncodedFile) -> Update[LayoutT, T]:
    result = queue.add_link(id=entry.id, link=entry.link, queue=state.node_queue)
    linked = list(result.linked)
    if result.mutable:
        result.linked.clear()

    tasks = encode_branches(linked, config=state.config)

    new_state: State[LayoutT, T] = None  # type: ignore[assignment]
    if (state.status == "closed") and (entry.id == state.root_id):
        new_state = Linked(
            metadata=state.metadata,
            config=state.config,
            writer=state.writer,
            link=entry.link,
            node_queue=result,
            status="linked"
        )
    else:
        if state.status == "closed":
            new_state = Closed(
                root_id=state.root_id,
                metadata=state.metadata,
                config=state.config,
                writer=state.writer,
                end=state.end,
                node_queue=result,
                status="closed"
            )
        elif state.status == "linked":
            new_state = Linked(
                metadata=state.metadata,
                config=state.config,
                writer=state.writer,
                link=state.link,
                node_queue=result,
                status="linked"
            )
        else:
            new_state = Open(
                metadata=state.metadata,
                config=state.config,
                writer=state.writer,
                node_queue=result,
                status="open",
                chunker=state.chunker,
                layout=state.layout,
            )
    end = None
    if state.status == "closed" and entry.id == state.root_id and state.end:
        end = state.end.resume()
    else:
        end = Task.none_()

    return Update(
        state=new_state,
        effect=Task.listen(  # pyright: ignore[reportArgumentType]
            sources={
                "link": Task.effects(tasks),
                "block": write_block(state.writer, entry.block),
                "end": end
            },
        )
    )



def close(state: State[LayoutT, T]) -> Update[LayoutT, T]:
    if state.status == "open":
        chunker_with_chunks = chunker.close(state.chunker)
        write_result = state.config.file_layout.write(state.layout, chunker_with_chunks.chunks)

        close_result = state.config.file_layout.close(write_result.layout, state.metadata)
        nodes: Sequence[Layout.Branch] = None  # type: ignore[assignment]
        leaves: Sequence[Layout.Leaf] = None # type: ignore[assignment]
        if is_leaf_node(close_result.root):
            nodes = (list(write_result.nodes) + list(close_result.nodes))
            leaves = (
                [cast(Layout.Leaf, leaf) for leaf in write_result.leaves] +
                [cast(Layout.Leaf, leaf) for leaf in close_result.leaves] +
                [cast(Layout.Leaf, close_result.root)]
            )
        else:
            nodes = (
                [cast(Layout.Branch, node) for node in write_result.nodes] +
                [cast(Layout.Branch, node) for node in close_result.nodes] +
                [cast(Layout.Branch, close_result.root)]
            )
            leaves = (list(write_result.leaves) + list(close_result.leaves))

        add_nodes_result = queue.add_nodes(nodes, state.node_queue)
        linked = list(add_nodes_result.linked)
        if add_nodes_result.mutable:
            add_nodes_result.linked.clear()

        tasks = list(encode_leaves(leaves, state.config)) + list(encode_branches(linked, state.config))

        # We want to keep run loop around until root node is linked. To
        # accomplish this we fork a task that suspends itself, which we will
        # resume when root is linked (see link function).
        # Below we join this forked task in our effect, this way effect is not
        # complete until forked task is, which will do once we link the root.
        fork = Task.fork(Task.suspend())

        state_for_update = Closed(
            metadata=state.metadata,
            config=state.config,
            writer=state.writer,
            root_id=close_result.root.id,
            end=fork,
            node_queue=add_nodes_result,
            status="closed",
        )
        return Update(
            state=state_for_update,
            effect=Task.listen({"link": Task.effects(tasks), "end": Task.join(fork)})
        )
    return Update(state=state, effect=Task.none_())



def encode_leaves(leaves: Sequence[Layout.Leaf], config: API.EncoderSettings[LayoutT, T]):
    """
    Creates concurrent leaf encode tasks. Each one will have an ID
    corresponding to an index in the queue.
    """
    return list(map((lambda leaf: encode_leaf(config=config, leaf=leaf, encoder=config.file_chunk_encoder)), leaves))

def encode_leaf(
    config: API.EncoderSettings[LayoutT, T],
    leaf: Layout.Leaf,
    encoder: API.FileChunkEncoder
) -> Task.Task[None, API.EncodedFile]:
    encoded_bytes = encoder.encode(as_memoryview(leaf.content) if leaf.content else EMPTY_BUFFER)
    hash = yield from Task.wait(config.hasher.digest(memoryview(encoded_bytes)))
    cid = config.linker.create_link(encoder.code, cast(MultihashDigest, hash))

    block = unixfs.Block(cid, encoded_bytes)
    link = unixfs.FileLink(cid, dag_byte_length=len(encoded_bytes), content_byte_length=leaf.content.byte_length if leaf.content else 0)

    return API.EncodedFile(id=leaf.id, block=block, link=link)


def write_block(writer: API.BlockWriter, block: unixfs.Block) -> Task.Task[None, None]:
    if ((writer.desired_size or 0) <= 0):
        yield from Task.wait(writer.ready)

    yield from Task.wait(writer.write(block))
    return


def as_memoryview(buffer: memoryview | Chunk) -> memoryview:
    if isinstance(buffer, memoryview):
        return buffer
    else:
        target = bytearray(buffer.byte_length)
        return buffer.copy_to(memoryview(target), 0)


def encode_branches(nodes: Sequence[LinkedNode], config: API.EncoderSettings[LayoutT, T]):
    return list(map(lambda node: encode_branch(config, node), nodes))


def encode_branch(
    config: API.EncoderSettings[LayoutT, T],
    node: queue.LinkedNode,
    metadata: unixfs.Metadata | None = None,
    ) -> Task.Task[None, API.EncodedFile]:
    encoded_bytes = config.file_encoder.encode(node=unixfs.AdvancedFile(parts=node.links, metadata=metadata))
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    future.set_result(config.hasher.digest(encoded_bytes))
    hash = yield from Task.wait(future)
    cid = config.linker.create_link(config.file_encoder.code, hash)
    block = unixfs.Block(cid, encoded_bytes)
    link = unixfs.FileLink(cid=cid, content_byte_length=codec.cumulative_content_byte_length(node.links), dag_byte_length=codec.cumulative_dag_byte_length(encoded_bytes, node.links))
    return API.EncodedFile(node.id, block, link)


def is_leaf_node(node: Layout.Node) -> bool:
    return (node.children is None)
