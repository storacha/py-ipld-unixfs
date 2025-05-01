from typing import (
    Any,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Sequence,
    TypeVar,
    TypedDict,
)
from ipld_unixfs.file.layout.api import Branch, NodeID
from ipld_unixfs.file.layout.queue.api import (
    Delta,
    FileLink,
    LinkedNode,
    PendingChildren,
    PropertyKey,
    Queue,
    Result,
)


def empty() -> Result:
    return Result(mutable=False, needs={}, nodes={}, links={}, linked=[])


def mutable() -> Result:
    return Result(mutable=True, needs={}, nodes={}, links={}, linked=EMPTY)


def add_node(node: Branch, input: Queue) -> Result:
    """
    Adds given layout node to the layout queue. If links for all of the node
    children are available correspnoding linked node is added (removing links
    form the queue) otherwise `nood` is added to the wait queue until all the
    needed links are added.
    """
    return add_nodes([node], input)


def add_nodes(new_nodes: Sequence[Branch], input: Queue) -> Result:
    queue = patch(input, Delta())
    for node in new_nodes:
        result = collect(node.children, queue.links)
        # If node isn't waiting on any of the children it's ready to be linked
        # so we add linked node diretly.
        if len(result["wants"]) == 0:
            queue = patch(
                queue,
                Delta(
                    links=assign(None, result["has"]),
                    linked=[LinkedNode(id=node.id, links=result["ready"])],
                ),
            )
        else:
            queue = patch(
                queue,
                Delta(
                    needs=assign(node.id, result["wants"]),
                    nodes={
                        node.id: PendingChildren(
                            children=node.children,
                            count=len(result["wants"]),
                        )
                    },
                ),
            )
    return queue


def add_link(id: NodeID, link: FileLink, queue: Queue) -> Result:
    """
    Adds a link to the queue. If the queue contains a node that needs this link
    it gets updated. Either it's gets linked (when it was blocked only on this
    link) or it's want count is reduced. If no node needed this link it just
    gets stored for the future node that will need it.
    """
    nodeID = queue.needs.get(id)
    node = queue.nodes.get(nodeID) if nodeID is not None else None

    # If we have no one waiting for this link just add it to the queue
    if nodeID is None or node is None:
        return patch(queue, Delta(links={id: link}))

    # We have node that needs this link.

    # This is the only link it needed so we materialize the node and remove
    # links and needs associated with it.
    if node.count == 1:
        result = collect(node.children, {**queue.links, id: link})
        return patch(
            queue,
            Delta(
                needs={id: None},
                links=assign(None, result["has"]),
                nodes={nodeID: None},
                linked=[LinkedNode(id=nodeID, links=result["ready"])],
            ),
        )

    # If node needs more links we just reduce the want count and remove this
    # need.
    return patch(
        queue,
        Delta(
            needs={id: None},
            links={id: link},
            nodes={
                nodeID: PendingChildren(
                    children=node.children,
                    count=node.count - 1,
                )
            },
        ),
    )


def patch(queue: Queue, delta: Delta) -> Result:
    result = (
        queue
        if queue.mutable and isinstance(queue, Result)
        else Result(
            mutable=False,
            needs=queue.needs,
            nodes=queue.nodes,
            links=queue.links,
            linked=queue.linked if queue.linked is not None else [],
        )
    )
    original = BLANK if queue.mutable else None

    if delta.needs is not None:
        result.needs = patch_dict(queue.needs, delta.needs, original)

    if delta.nodes is not None:
        result.nodes = patch_dict(queue.nodes, delta.nodes, original)

    if delta.links is not None:
        result.links = patch_dict(queue.links, delta.links, original)

    if delta.linked is None:
        result.linked = queue.linked if queue.linked is not None else []
    else:
        result.linked = append(
            queue.linked if queue.linked is not None else EMPTY, delta.linked, EMPTY
        )

    return result


K = TypeVar("K", bound=PropertyKey)
V = TypeVar("V")


def assign(value: V, keys: Sequence[K]) -> dict[K, V]:
    delta: dict[K, V] = {}
    for k in keys:
        delta[k] = value
    return delta


def patch_dict(
    target: MutableMapping[K, V],
    delta: Mapping[K, Optional[V]],
    original: Optional[Mapping[K, V]] = None,
) -> MutableMapping[K, V]:
    if original is None:
        original = target

    result = target if target is not original else dict(target)
    for id, value in delta.items():
        if value is None:
            result.pop(id, None)
        else:
            result[id] = value

    return result


def add_links(entries: Sequence[tuple[NodeID, FileLink]], queue: Queue) -> Queue:
    for id, link in entries:
        queue = add_link(id, link, queue)
    return queue


def is_empty(queue: Queue) -> bool:
    return len(queue.nodes) == 0 and len(queue.links) == 0


T = TypeVar("T")


def append(
    target: MutableSequence[T],
    items: Sequence[T],
    original: Optional[Sequence[T]] = None,
) -> MutableSequence[T]:
    if original is None:
        original = target

    if target is original:
        target = list(target)
        target.extend(items)
        return target

    for item in items:
        target.append(item)

    return target


CollectResult = TypedDict(
    "CollectResult",
    {"has": Sequence[NodeID], "wants": Sequence[NodeID], "ready": Sequence[FileLink]},
)


def collect(
    children: Sequence[NodeID], source: Mapping[NodeID, FileLink]
) -> CollectResult:
    has: list[NodeID] = []
    wants: list[NodeID] = []
    ready: list[FileLink] = []
    for child in children:
        if child in source:
            has.append(child)
            ready.append(source[child])
        else:
            wants.append(child)
    return {"has": has, "wants": wants, "ready": ready}


EMPTY: list[Any] = []

BLANK: dict[Any, Any] = {}
