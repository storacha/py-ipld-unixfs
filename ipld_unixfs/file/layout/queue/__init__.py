# import * as Layout from "./api.js"
# import * as Queue from "./queue/api.js"
# export * from "./queue/api.js"

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, TypeVar, TypedDict
from ipld_unixfs.file.layout.api import Branch, NodeID
from ipld_unixfs.file.layout.queue.api import (
    Delta,
    FileLink,
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


def add_nodes(new_nodes: Branch, input: Queue) -> Result:
    queue = patch(input, {})


# /**
#  *
#  * @param {Layout.Branch[]} newNodes
#  * @param {Queue.Queue} input
#  * @returns {Queue.Result}
#  */
# export const addNodes = (newNodes, input) => {
#   let queue = patch(input, {})
#   for (const node of newNodes) {
#     const { ready, has, wants } = collect(node.children, queue.links)
#     // If node isn't waiting on any of the children it's ready to be linked
#     // so we add linked node diretly.
#     if (wants.length === 0) {
#       queue = patch(queue, {
#         links: assign(undefined, has),
#         linked: [{ id: node.id, links: ready }],
#       })
#     } else {
#       queue = patch(queue, {
#         needs: assign(node.id, wants),
#         nodes: {
#           [node.id]: {
#             children: node.children,
#             count: wants.length,
#           },
#         },
#       })
#     }
#   }

#   return queue
# }

# /**
#  * Adds link to the queue. If queue contains a node that needs this link it gets
#  * updated. Either it's gets linked (when it was blocked only on this link) or
#  * it's want could is reduced. If no node needed this link it just gets stored
#  * for the future node that will need it.
#  *
#  *
#  * @param {Queue.NodeID} id
#  * @param {Queue.Link} link
#  * @param {Queue.Queue} queue
#  * @returns {Queue.Result}
#  */

# export const addLink = (id, link, queue) => {
#   const nodeID = queue.needs[id]
#   const node = queue.nodes[nodeID]
#   // We have node than needs this link.
#   if (node != null) {
#     // This is the only link it needed so we materialize the node and remove
#     // links and needs associated with it.
#     if (node.count === 1) {
#       const { ready, has } = collect(node.children, {
#         ...queue.links,
#         [id]: link,
#       })

#       return patch(queue, {
#         needs: { [id]: undefined },
#         links: assign(undefined, has),
#         nodes: { [nodeID]: undefined },
#         linked: [{ id: nodeID, links: ready }],
#       })
#     }
#     // If node needs more links we just reduce a want count and remove this
#     // need.
#     else {
#       return patch(queue, {
#         needs: { [id]: undefined },
#         links: { [id]: link },
#         nodes: {
#           [nodeID]: {
#             ...node,
#             count: node.count - 1,
#           },
#         },
#       })
#     }
#   }
#   // If we have no one waiting for this link just add it to the queue
#   else {
#     return patch(queue, {
#       links: { [id]: link },
#     })
#   }
# }


def patch(queue: Queue, delta: Delta) -> Result:
    result = (
        queue
        if queue.mutable
        else Queue(
            mutable=False,
            needs=queue.needs,
            nodes=queue.nodes,
            links=queue.links,
            linked=queue.linked,
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
    target: dict[K, V],
    delta: dict[K, Optional[V]],
    original: Optional[dict[K, V]] = None,
) -> dict[K, V]:
    if original is None:
        original = target

    result = target if target is not original else dict(target)
    for id, value in delta.items():
        if value is None:
            result.pop(id)
        else:
            result[id] = value

    return result


def add_links(entries: Sequence[tuple[NodeID, FileLink]], queue) -> Queue:
    for id, link in entries:
        queue = add_link(id, link, queue)
    return queue


def is_empty(queue: Queue) -> bool:
    return len(queue.nodes) == 0 and len(queue.links) == 0


T = TypeVar("T")


def append(
    target: list[T], items: list[T], original: Optional[list[T]] = None
) -> list[T]:
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
    {has: Sequence[NodeID], wants: Sequence[NodeID], ready: Sequence[FileLink]},
)


def collect(
    children: Sequence[NodeID], source: Mapping[NodeID, FileLink]
) -> CollectResult:
    has = []
    wants = []
    ready = []
    for child in children:
        if child in source:
            has.append(child)
            ready.append(source[child])
        else:
            wants.append(child)
    return {has: has, wants: wants, ready: ready}


EMPTY = ()

BLANK = {}
